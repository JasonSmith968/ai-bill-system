"""Chaos Test: Celery Worker Crash

Tests behavior when Celery workers are unavailable:
- Tasks fail gracefully (not crash the web app)
- Task submission returns error, not hang
- Web API works independently of Celery
- Background tasks don't block foreground requests
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


def test_celery_worker_status():
    """Check if Celery workers are running."""
    try:
        import subprocess
        result = subprocess.run(
            ['celery', '-A', 'celery_app', 'inspect', 'ping', '--timeout=3'],
            capture_output=True, text=True, timeout=10, cwd='backend'
        )
        if 'pong' in result.stdout.lower():
            return False, 'Celery workers are running — stop them for chaos test'
        return True, 'No Celery workers responding (expected for chaos test)'
    except FileNotFoundError:
        return True, 'Celery not installed — workers unavailable (expected)'
    except Exception as e:
        return True, f'Cannot reach Celery: {e}'


def test_web_api_without_celery():
    """Verify web API works independently of Celery."""
    token = get_token()
    if not token:
        return False, 'Cannot authenticate'

    headers = {'Authorization': f'Bearer {token}'}

    endpoints = [
        '/api/transactions?page=1&per_page=5',
        '/api/transactions/categories',
        '/api/dashboard/summary',
        '/api/billing/subscription',
    ]

    results = []
    for ep in endpoints:
        try:
            r = requests.get(f'{BASE_URL}{ep}', headers=headers, timeout=5)
            results.append((ep, r.status_code == 200))
        except Exception:
            results.append((ep, False))

    all_ok = all(ok for _, ok in results)
    details = ', '.join(f'{ep.split("/")[-1]}:{"OK" if ok else "FAIL"}' for ep, ok in results)
    return all_ok, details


def test_task_submission_graceful_failure():
    """Verify task submission doesn't hang or crash when workers are down."""
    token = get_token()
    if not token:
        return False, 'Cannot authenticate'

    headers = {'Authorization': f'Bearer {token}'}

    # Try to trigger an async operation (report generation, etc.)
    # These endpoints should return quickly even if Celery is down
    try:
        start = time.time()
        r = requests.post(f'{BASE_URL}/api/reports/export', headers=headers, json={
            'format': 'csv',
            'period': 'month',
        }, timeout=10)
        elapsed = time.time() - start

        # Should either succeed (200/202) or fail fast (4xx/5xx), not hang
        fast_response = elapsed < 5
        not_hung = r.status_code in (200, 201, 202, 400, 404, 500, 503)

        return fast_response and not_hung, f'Status: {r.status_code}, Time: {elapsed:.2f}s'
    except requests.exceptions.Timeout:
        return False, 'Request timed out (hung — bad)'
    except Exception as e:
        return False, str(e)


def test_concurrent_requests_without_celery():
    """Verify concurrent requests don't block each other without Celery."""
    import concurrent.futures

    token = get_token()
    if not token:
        return False, 'Cannot authenticate'

    headers = {'Authorization': f'Bearer {token}'}

    def make_request(ep):
        try:
            r = requests.get(f'{BASE_URL}{ep}', headers=headers, timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    endpoints = [
        '/api/transactions?page=1&per_page=5',
        '/api/dashboard/summary',
        '/api/transactions/categories',
        '/health',
        '/api/billing/subscription',
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request, ep) for ep in endpoints]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    all_ok = all(results)
    return all_ok, f'{sum(results)}/{len(results)} concurrent requests succeeded'


def run():
    """Run all Celery chaos tests."""
    print('=' * 60)
    print(' CHAOS TEST: Celery Worker Crash')
    print('=' * 60)
    print()

    tests = [
        ('No Celery workers responding', test_celery_worker_status),
        ('Web API works without Celery', test_web_api_without_celery),
        ('Task submission fails fast (not hangs)', test_task_submission_graceful_failure),
        ('Concurrent requests work without Celery', test_concurrent_requests_without_celery),
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
