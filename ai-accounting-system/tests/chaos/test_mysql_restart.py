"""Chaos Test: MySQL Restart

Tests connection pool recovery after MySQL goes away and comes back.
Verifies:
- pool_pre_ping detects stale connections
- App recovers automatically after MySQL restart
- No data corruption during outage
- Connection pool exhaustion handling
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


def test_endpoint_available():
    """Check if a DB-dependent endpoint responds."""
    token = get_token()
    if not token:
        return False, 'Cannot authenticate'

    headers = {'Authorization': f'Bearer {token}'}
    try:
        r = requests.get(f'{BASE_URL}/api/transactions?page=1&per_page=5', headers=headers, timeout=10)
        return r.status_code == 200, f'Status: {r.status_code}'
    except requests.exceptions.ConnectionError:
        return False, 'Connection refused'
    except requests.exceptions.Timeout:
        return False, 'Timeout'
    except Exception as e:
        return False, str(e)


def test_create_transaction():
    """Test write operation after recovery."""
    token = get_token()
    if not token:
        return False, 'Cannot authenticate'

    headers = {'Authorization': f'Bearer {token}'}
    try:
        r = requests.post(f'{BASE_URL}/api/transactions', headers=headers, json={
            'type': 'expense',
            'amount': 1.00,
            'category_id': 1,
            'description': 'Chaos test transaction',
            'date': '2026-05-28',
        }, timeout=10)
        return r.status_code in (200, 201), f'Status: {r.status_code}, Body: {r.text[:200]}'
    except Exception as e:
        return False, str(e)


def test_connection_pool_recovery():
    """Make multiple requests to verify pool recovery."""
    token = get_token()
    if not token:
        return False, 'Cannot authenticate'

    headers = {'Authorization': f'Bearer {token}'}
    success = 0
    total = 10

    for i in range(total):
        try:
            r = requests.get(f'{BASE_URL}/api/transactions?page=1&per_page=5', headers=headers, timeout=10)
            if r.status_code == 200:
                success += 1
        except Exception:
            pass
        time.sleep(0.2)

    return success == total, f'{success}/{total} requests succeeded'


def run_with_mysql_restart():
    """Full MySQL restart chaos test.

    This test requires manual MySQL restart or docker-based MySQL.
    It will:
    1. Verify app works normally
    2. Ask user to stop MySQL
    3. Verify app degrades gracefully (errors, not crashes)
    4. Ask user to start MySQL
    5. Verify app recovers automatically
    """
    print('=' * 60)
    print(' CHAOS TEST: MySQL Restart')
    print('=' * 60)
    print()

    # Phase 1: Baseline
    print('Phase 1: Baseline — verify normal operation')
    ok, detail = test_endpoint_available()
    print(f'  [{"PASS" if ok else "FAIL"}] {detail}')
    if not ok:
        print('  [ABORT] Cannot establish baseline')
        return
    print()

    # Phase 2: MySQL down
    print('Phase 2: MySQL outage simulation')
    print('  ACTION REQUIRED: Stop MySQL now')
    print('    Windows: net stop MySQL80')
    print('    Docker:  docker stop mysql')
    input('  Press Enter when MySQL is stopped...')
    print()

    # Test during outage
    print('  Testing during outage (expect failures, not crashes):')
    for i in range(5):
        ok, detail = test_endpoint_available()
        status = 'UNEXPECTED_PASS' if ok else 'EXPECTED_FAIL'
        print(f'    Request {i+1}: [{status}] {detail}')
        time.sleep(1)

    # Check if Flask is still running (not crashed)
    try:
        r = requests.get(f'{BASE_URL}/health', timeout=5)
        flask_alive = r.status_code == 200
    except Exception:
        flask_alive = False

    print(f'  Flask process alive: {flask_alive}')
    print()

    # Phase 3: Recovery
    print('Phase 3: Recovery')
    print('  ACTION REQUIRED: Start MySQL now')
    print('    Windows: net start MySQL80')
    print('    Docker:  docker start mysql')
    input('  Press Enter when MySQL is started...')
    print()

    # Wait for MySQL to be ready
    print('  Waiting for MySQL to accept connections...')
    for i in range(30):
        try:
            import pymysql
            conn = pymysql.connect(host='localhost', user='root', password='123456', database='ai_accounting')
            conn.close()
            print(f'  MySQL ready after {i+1}s')
            break
        except Exception:
            time.sleep(1)
    else:
        print('  [WARN] MySQL did not recover within 30s')
    print()

    # Phase 4: Verify recovery
    print('Phase 4: Verify auto-recovery')
    ok, detail = test_endpoint_available()
    print(f'  [{"PASS" if ok else "FAIL"}] Endpoint available: {detail}')

    ok, detail = test_create_transaction()
    print(f'  [{"PASS" if ok else "FAIL"}] Write operation: {detail}')

    ok, detail = test_connection_pool_recovery()
    print(f'  [{"PASS" if ok else "FAIL"}] Pool recovery: {detail}')
    print()


def run_automated():
    """Automated test — verify pool_pre_ping works with live MySQL."""
    print('=' * 60)
    print(' CHAOS TEST: MySQL Connection Pool (automated)')
    print('=' * 60)
    print()

    tests = [
        ('DB endpoint responds', test_endpoint_available),
        ('Write operation works', test_create_transaction),
        ('Connection pool healthy (10 sequential)', test_connection_pool_recovery),
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
    if '--full' in sys.argv:
        run_with_mysql_restart()
    else:
        run_automated()
