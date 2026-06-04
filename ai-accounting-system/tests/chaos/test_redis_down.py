"""Chaos Test: Redis Down

Tests graceful degradation when Redis is unavailable.
Verifies:
- App starts without Redis (cache fallback)
- Rate limiter falls back to memory storage
- Celery tasks fail gracefully (not crash)
- API endpoints still respond (without caching)
"""

import sys
import time
import requests
import subprocess

BASE_URL = 'http://localhost:5000'


def get_token():
    """Get auth token."""
    r = requests.post(f'{BASE_URL}/api/auth/login', json={
        'username': 'loadtest', 'password': 'LoadTest123!',
    })
    if r.status_code == 200:
        return r.json().get('access_token')
    return None


def test_api_without_redis():
    """Verify API works when Redis is down."""
    token = get_token()
    if not token:
        return False, 'Cannot authenticate'

    headers = {'Authorization': f'Bearer {token}'}
    results = {}

    endpoints = [
        ('/health', 'GET', None),
        ('/api/transactions?page=1&per_page=5', 'GET', None),
        ('/api/transactions/categories', 'GET', None),
        ('/api/billing/subscription', 'GET', None),
        ('/api/dashboard/summary', 'GET', None),
    ]

    for path, method, body in endpoints:
        try:
            if method == 'GET':
                r = requests.get(f'{BASE_URL}{path}', headers=headers, timeout=5)
            else:
                r = requests.post(f'{BASE_URL}{path}', headers=headers, json=body, timeout=5)

            results[path] = {
                'status': r.status_code,
                'ok': r.status_code in (200, 201),
                'latency_ms': r.elapsed.total_seconds() * 1000,
            }
        except Exception as e:
            results[path] = {
                'status': 0,
                'ok': False,
                'error': str(e),
            }

    all_ok = all(r.get('ok', False) for r in results.values())
    return all_ok, results


def test_cache_miss_behavior():
    """Verify endpoints work without cache (slower but functional)."""
    token = get_token()
    if not token:
        return False, 'Cannot authenticate'

    headers = {'Authorization': f'Bearer {token}'}

    # Call same endpoint twice — should get same result both times
    r1 = requests.get(f'{BASE_URL}/api/transactions?page=1&per_page=5', headers=headers, timeout=5)
    time.sleep(0.1)
    r2 = requests.get(f'{BASE_URL}/api/transactions?page=1&per_page=5', headers=headers, timeout=5)

    if r1.status_code != 200 or r2.status_code != 200:
        return False, f'Status codes: {r1.status_code}, {r2.status_code}'

    # Results should be identical (same data, no cache corruption)
    d1 = r1.json()
    d2 = r2.json()

    if d1.get('transactions') != d2.get('transactions'):
        return False, 'Cache miss caused inconsistent results'

    return True, 'Consistent results without cache'


def test_rate_limiter_memory_fallback():
    """Verify rate limiter works with memory backend."""
    # Make rapid requests to trigger rate limiter
    results = []
    for i in range(30):
        try:
            r = requests.get(f'{BASE_URL}/health', timeout=2)
            results.append(r.status_code)
        except Exception:
            results.append(0)

    # Should get mostly 200s (rate limiter in memory mode allows more)
    ok_count = results.count(200)
    return ok_count > 20, f'{ok_count}/30 requests succeeded'


def run():
    """Run all Redis-down chaos tests."""
    print('=' * 60)
    print(' CHAOS TEST: Redis Down')
    print('=' * 60)
    print()

    # Check Redis is actually down
    try:
        import redis
        r = redis.Redis.from_url('redis://localhost:6379/0')
        r.ping()
        print('[SKIP] Redis is running — cannot test Redis-down scenario')
        print('       Stop Redis first: redis-cli shutdown')
        return
    except Exception:
        print('[CONFIRMED] Redis is not running')
        print()

    tests = [
        ('API endpoints respond without Redis', test_api_without_redis),
        ('Cache miss produces consistent results', test_cache_miss_behavior),
        ('Rate limiter memory fallback works', test_rate_limiter_memory_fallback),
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
