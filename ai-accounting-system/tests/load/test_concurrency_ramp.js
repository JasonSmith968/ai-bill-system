// k6 Concurrency Ramp Load Test
// Tests system stability from 100 → 300 → 500 → 1000 concurrent users
//
// Run: k6 run tests/load/test_concurrency_ramp.js

import { sleep, group, check } from 'k6';
import http from 'k6/http';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency', true);
const activeVUs = new Gauge('active_vus');
const reqCount = new Counter('total_requests');

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';
const TEST_USER = 'loadtest';
const TEST_PASS = 'LoadTest123!';

export const options = {
  stages: [
    { duration: '30s', target: 100 },   // ramp to 100
    { duration: '1m', target: 100 },    // hold 100
    { duration: '30s', target: 300 },   // ramp to 300
    { duration: '1m', target: 300 },    // hold 300
    { duration: '30s', target: 500 },   // ramp to 500
    { duration: '1m', target: 500 },    // hold 500
    { duration: '30s', target: 1000 },  // ramp to 1000
    { duration: '1m', target: 1000 },   // hold 1000
    { duration: '30s', target: 0 },     // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000', 'p(99)<5000'],
    http_req_failed: ['rate<0.15'],
    errors: ['rate<0.15'],
  },
};

// Shared token (login once per VU)
let cachedToken = null;

function getToken() {
  if (cachedToken) return cachedToken;

  const res = http.post(`${BASE_URL}/api/auth/login`, JSON.stringify({
    username: TEST_USER,
    password: TEST_PASS,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  if (res.status === 200) {
    const body = JSON.parse(res.body);
    cachedToken = body.access_token;
    return cachedToken;
  }
  return null;
}

export default function () {
  const token = getToken();
  if (!token) {
    errorRate.add(1);
    sleep(1);
    return;
  }

  const headers = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
  };

  activeVUs.add(__VU);

  group('Health Check', () => {
    const res = http.get(`${BASE_URL}/health`);
    reqCount.add(1);
    const ok = check(res, {
      'health 200': (r) => r.status === 200,
    });
    errorRate.add(!ok);
    apiLatency.add(res.timings.duration);
  });

  sleep(0.5);

  group('Dashboard', () => {
    const res = http.get(`${BASE_URL}/api/dashboard/summary`, headers);
    reqCount.add(1);
    const ok = check(res, {
      'dashboard 200': (r) => r.status === 200,
    });
    errorRate.add(!ok);
    apiLatency.add(res.timings.duration);
  });

  sleep(0.5);

  group('Transactions List', () => {
    const res = http.get(`${BASE_URL}/api/transactions?page=1&per_page=20`, headers);
    reqCount.add(1);
    const ok = check(res, {
      'transactions 200': (r) => r.status === 200,
    });
    errorRate.add(!ok);
    apiLatency.add(res.timings.duration);
  });

  sleep(0.5);

  group('Categories', () => {
    const res = http.get(`${BASE_URL}/api/transactions/categories`, headers);
    reqCount.add(1);
    const ok = check(res, {
      'categories 200': (r) => r.status === 200,
    });
    errorRate.add(!ok);
    apiLatency.add(res.timings.duration);
  });

  sleep(0.5);

  group('Billing Subscription', () => {
    const res = http.get(`${BASE_URL}/api/billing/subscription`, headers);
    reqCount.add(1);
    const ok = check(res, {
      'subscription 200': (r) => r.status === 200,
    });
    errorRate.add(!ok);
    apiLatency.add(res.timings.duration);
  });

  sleep(1);
}
