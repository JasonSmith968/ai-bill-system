// k6 Corrected Concurrency Ramp — fixed endpoints
// Tests: /health, /api/dashboard/summary, /api/transactions, /api/transactions/categories, /api/billing/subscription
//
// Run: k6 run tests/load/test_ramp_corrected.js

import { sleep, group, check } from 'k6';
import http from 'k6/http';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';

const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency', true);
const reqCount = new Counter('total_requests');

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';
const TEST_USER = 'loadtest';
const TEST_PASS = 'LoadTest123!';

export const options = {
  stages: [
    { duration: '20s', target: 100 },
    { duration: '1m', target: 100 },
    { duration: '20s', target: 300 },
    { duration: '1m', target: 300 },
    { duration: '20s', target: 500 },
    { duration: '1m', target: 500 },
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<3000', 'p(99)<8000'],
    errors: ['rate<0.30'],
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

  group('Health', () => {
    const r = http.get(`${BASE_URL}/health`);
    reqCount.add(1);
    const ok = check(r, { '200': (r) => r.status === 200 });
    errorRate.add(!ok); apiLatency.add(r.timings.duration);
  });
  sleep(0.3);

  group('Dashboard Summary', () => {
    const r = http.get(`${BASE_URL}/api/dashboard/summary`, h);
    reqCount.add(1);
    const ok = check(r, { '200': (r) => r.status === 200 });
    errorRate.add(!ok); apiLatency.add(r.timings.duration);
  });
  sleep(0.3);

  group('Transactions', () => {
    const r = http.get(`${BASE_URL}/api/transactions?page=1&per_page=20`, h);
    reqCount.add(1);
    const ok = check(r, { '200': (r) => r.status === 200 });
    errorRate.add(!ok); apiLatency.add(r.timings.duration);
  });
  sleep(0.3);

  group('Categories', () => {
    const r = http.get(`${BASE_URL}/api/transactions/categories`, h);
    reqCount.add(1);
    const ok = check(r, { '200': (r) => r.status === 200 });
    errorRate.add(!ok); apiLatency.add(r.timings.duration);
  });
  sleep(0.3);

  group('Billing', () => {
    const r = http.get(`${BASE_URL}/api/billing/subscription`, h);
    reqCount.add(1);
    const ok = check(r, { '200': (r) => r.status === 200 });
    errorRate.add(!ok); apiLatency.add(r.timings.duration);
  });
  sleep(1);
}
