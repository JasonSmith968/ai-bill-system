// k6 MySQL Connection Pool Stress Test
// Tests DB-heavy endpoints to stress the SQLAlchemy connection pool
//
// Run: k6 run tests/load/test_mysql_pool.js

import { sleep, group, check } from 'k6';
import http from 'k6/http';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const dbLatency = new Trend('db_latency', true);

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';

export const options = {
  stages: [
    { duration: '15s', target: 50 },
    { duration: '1m', target: 200 },
    { duration: '15s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<3000'],
    errors: ['rate<0.30'],
  },
};

let cachedToken = null;

function getToken() {
  if (cachedToken) return cachedToken;
  const res = http.post(`${BASE_URL}/api/auth/login`, JSON.stringify({
    username: 'loadtest', password: 'LoadTest123!',
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

  group('Heavy DB Queries', () => {
    // Transaction list with pagination — hits DB
    const r1 = http.get(`${BASE_URL}/api/transactions?page=1&per_page=50`, h);
    const ok1 = check(r1, { '200': (r) => r.status === 200 });
    errorRate.add(!ok1); dbLatency.add(r1.timings.duration);

    sleep(0.2);

    // Categories — simple query
    const r2 = http.get(`${BASE_URL}/api/transactions/categories`, h);
    const ok2 = check(r2, { '200': (r) => r.status === 200 });
    errorRate.add(!ok2); dbLatency.add(r2.timings.duration);

    sleep(0.2);

    // Dashboard summary — aggregation queries
    const r3 = http.get(`${BASE_URL}/api/dashboard/summary`, h);
    const ok3 = check(r3, { '200': (r) => r.status === 200 });
    errorRate.add(!ok3); dbLatency.add(r3.timings.duration);

    sleep(0.2);

    // Weekly data — date range query
    const r4 = http.get(`${BASE_URL}/api/dashboard/weekly`, h);
    const ok4 = check(r4, { '200': (r) => r.status === 200 });
    errorRate.add(!ok4); dbLatency.add(r4.timings.duration);

    sleep(0.2);

    // Recent transactions
    const r5 = http.get(`${BASE_URL}/api/dashboard/recent`, h);
    const ok5 = check(r5, { '200': (r) => r.status === 200 });
    errorRate.add(!ok5); dbLatency.add(r5.timings.duration);
  });

  sleep(0.5);
}
