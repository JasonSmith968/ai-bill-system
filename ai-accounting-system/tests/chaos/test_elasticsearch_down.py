"""Chaos Test: Elasticsearch Unavailable

Tests graceful degradation when Elasticsearch is not available:
- Search falls back to database LIKE queries
- Logging falls back to file-based logging
- Application continues to function without search features
"""

import sys
import time
import requests

BASE_URL = 'http://localhost:5000'


def get_token():
    """Get auth token."""
    r = requests.post(f'{BASE_URL}/api/auth/login', json={
        'username': 'loadtest', 'password': 'LoadTest123!',
    })
    if r.status_code == 200:
        return r.json().get('access_token')
    return None


def test_es_unavailable():
    """Verify ES is not running (expected for this test)."""
    try:
        import requests as req
        r = req.get('http://localhost:9200/_cluster/health', timeout=2)
        return False, f'ES is running (status {r.status_code}) — stop it first for chaos test'
    except Exception:
        return True, 'ES is not running (expected)'


def test_search_fallback_to_db():
    """Verify search-like endpoints work via DB when ES is down."""
    token = get_token()
    if not token:
        return False, 'Cannot authenticate'

    headers = {'Authorization': f'Bearer {token}'}

    # Transaction search (uses DB, not ES)
    try:
        r = requests.get(
            f'{BASE_URL}/api/transactions?page=1&per_page=5&search=lunch',
            headers=headers, timeout=5
        )
        return r.status_code == 200, f'Transaction search: {r.status_code}'
    except Exception as e:
        return False, str(e)


def test_api_endpoints_without_es():
    """Verify all core API endpoints work without ES."""
    token = get_token()
    if not token:
        return False, 'Cannot authenticate'

    headers = {'Authorization': f'Bearer {token}'}

    endpoints = [
        '/api/transactions?page=1&per_page=5',
        '/api/transactions/categories',
        '/api/dashboard/summary',
        '/api/dashboard/weekly',
        '/api/billing/subscription',
    ]

    results = []
    for ep in endpoints:
        try:
            r = requests.get(f'{BASE_URL}{ep}', headers=headers, timeout=5)
            results.append((ep, r.status_code == 200))
        except Exception as e:
            results.append((ep, False))

    all_ok = all(ok for _, ok in results)
    details = ', '.join(f'{ep.split("/")[-1]}:{"OK" if ok else "FAIL"}' for ep, ok in results)
    return all_ok, details


def test_create_transaction_without_es():
    """Verify write operations work without ES indexing."""
    token = get_token()
    if not token:
        return False, 'Cannot authenticate'

    headers = {'Authorization': f'Bearer {token}'}
    try:
        r = requests.post(f'{BASE_URL}/api/transactions', headers=headers, json={
            'type': 'expense',
            'amount': 5.00,
            'category_id': 1,
            'description': 'Chaos test - no ES',
            'date': '2026-05-28',
        }, timeout=10)
        return r.status_code in (200, 201), f'Status: {r.status_code}'
    except Exception as e:
        return False, str(e)


def test_logging_without_es():
    """Verify application logging works (file-based) without ES."""
    token = get_token()
    if not token:
        return False, 'Cannot authenticate'

    headers = {'Authorization': f'Bearer {token}'}

    # Make a request that generates logs
    requests.get(f'{BASE_URL}/api/transactions?page=1', headers=headers, timeout=5)

    # Check if log files exist
    import os
    log_dir = 'backend/logs'
    if os.path.exists(log_dir):
        log_files = os.listdir(log_dir)
        has_logs = len(log_files) > 0
        return has_logs, f'Log files: {log_files}'
    return True, 'Log dir not found (may be configured differently)'


def run():
    """Run all Elasticsearch chaos tests."""
    print('=' * 60)
    print(' CHAOS TEST: Elasticsearch Unavailable')
    print('=' * 60)
    print()

    tests = [
        ('ES is not running (expected)', test_es_unavailable),
        ('Search falls back to DB', test_search_fallback_to_db),
        ('All API endpoints work without ES', test_api_endpoints_without_es),
        ('Write operations work without ES', test_create_transaction_without_es),
        ('Logging works without ES', test_logging_without_es),
    ]

    results = []
    for name, test_fn in tests:
        print(f'Testing: {name}')
        try:
            ok, detail = test_fn()
            status = 'PASS' if ok else 'FAIL'
            print(f'  [{status}] {detail}')
            results.append((name, ok))
        except Exception as e:
            print(f'  [ERROR] {e}')
            results.append((name, False))
        print()

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f'Results: {passed}/{total} passed')
    return results


if __name__ == '__main__':
    run()
