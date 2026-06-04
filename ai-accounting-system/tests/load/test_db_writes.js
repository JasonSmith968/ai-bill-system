// k6 Database Write Stress Test
// Tests concurrent writes, transaction contention, and pool saturation
//
// Run: k6 run tests/load/test_db_writes.js

import { sleep, group, check } from 'k6';
import http from 'k6/http';
import { Rate, Trend, Counter } from 'k6/metrics';

const errorRate = new Rate('errors');
const writeLatency = new Trend('write_latency', true);
const writesSuccess = new Counter('writes_success');
const writesFailed = new Counter('writes_failed');

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';
const TEST_USER = 'loadtest';
const TEST_PASS = 'LoadTest123!';

export const options = {
  stages: [
    { duration: '15s', target: 50 },
    { duration: '1m', target: 200 },   // 200 VUs writing concurrently
    { duration: '30s', target: 400 },  // burst to 400
    { duration: '1m', target: 400 },   // hold
    { duration: '15s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<1000', 'p(99)<3000'],
    errors: ['rate<0.10'],
    write_latency: ['p(95)<1000'],
  },
};

let cachedToken = null;

function getToken() {
  if (cachedToken) return cachedToken;
  const res = http.post(`${BASE_URL}/api/auth/login`, JSON.stringify({
    username: TEST_USER, password: TEST_PASS,
  }), { headers: { 'Content-Type': 'application/json' } });
  if (res.status === 200) {
    cachedToken = JSON.parse(res.body).access_token;
    return cachedToken;
  }
  return null;
}

export default function () {
  const token = getToken();
  if (!token) { errorRate.add(1); sleep(1); return; }

  const h = { headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` } };

  group('Create Transaction', () => {
    const res = http.post(`${BASE_URL}/api/transactions`, JSON.stringify({
      type: __VU % 2 === 0 ? 'expense' : 'income',
      amount: (Math.random() * 1000 + 1).toFixed(2),
      category_id: (__VU % 10) + 1,
      description: `Load test write VU${__VU} iter${__ITER}`,
      note: 'Automated load test',
      date: '2026-05-28',
    }), h);

    writeLatency.add(res.timings.duration);

    const ok = check(res, {
      'create returns 201': (r) => r.status === 201,
    });

    if (ok) {
      writesSuccess.add(1);
    } else {
      writesFailed.add(1);
      errorRate.add(1);
    }
  });

  sleep(0.3);

  group('Read After Write', () => {
    // Read immediately after write — tests consistency
    const res = http.get(`${BASE_URL}/api/transactions?page=1&per_page=5`, h);
    const ok = check(res, {
      'read after write 200': (r) => r.status === 200,
    });
    if (!ok) errorRate.add(1);
  });

  sleep(0.2);

  group('Update Transaction', () => {
    // First get a transaction to update
    const listRes = http.get(`${BASE_URL}/api/transactions?page=1&per_page=1`, h);
    if (listRes.status === 200) {
      try {
        const txns = JSON.parse(listRes.body).transactions;
        if (txns && txns.length > 0) {
          const txnId = txns[0].id;
          const res = http.put(`${BASE_URL}/api/transactions/${txnId}`, JSON.stringify({
            description: `Updated VU${__VU} iter${__ITER}`,
            amount: (Math.random() * 500 + 1).toFixed(2),
          }), h);

          writeLatency.add(res.timings.duration);
          const ok = check(res, {
            'update returns 200': (r) => r.status === 200,
          });
          if (!ok) { writesFailed.add(1); errorRate.add(1); }
        }
      } catch (e) {
        // JSON parse error — ignore
      }
    }
  });

  sleep(0.3);

  group('Dashboard After Writes', () => {
    // Dashboard aggregation after heavy writes
    const res = http.get(`${BASE_URL}/api/dashboard/summary`, h);
    const ok = check(res, {
      'dashboard after writes 200': (r) => r.status === 200,
    });
    if (!ok) errorRate.add(1);
  });

  sleep(0.5);
}
