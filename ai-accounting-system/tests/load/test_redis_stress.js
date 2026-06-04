// k6 Redis Stress Test
// Tests cache hit/miss behavior and Redis memory pressure
//
// Run: k6 run tests/load/test_redis_stress.js

import { sleep, group, check } from 'k6';
import http from 'k6/http';
import { Rate, Trend, Counter } from 'k6/metrics';

const errorRate = new Rate('errors');
const cacheLatency = new Trend('cache_latency', true);
const cacheHits = new Counter('cache_hits');
const cacheMisses = new Counter('cache_misses');

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';
const TEST_USER = 'loadtest';
const TEST_PASS = 'LoadTest123!';

export const options = {
  stages: [
    { duration: '20s', target: 50 },
    { duration: '2m', target: 200 },   // 200 VUs hammering cached endpoints
    { duration: '30s', target: 500 },  // burst to 500
    { duration: '1m', target: 500 },   // hold burst
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<2000'],
    errors: ['rate<0.10'],
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

  group('Cached Dashboard Endpoints', () => {
    // These endpoints should be cached by Flask-Caching
    const endpoints = [
      '/api/dashboard/summary',
      '/api/dashboard/weekly',
      '/api/dashboard/recent',
      '/api/transactions/categories',
    ];

    for (const ep of endpoints) {
      const start = Date.now();
      const res = http.get(`${BASE_URL}${ep}`, h);
      const elapsed = Date.now() - start;
      cacheLatency.add(elapsed);

      const ok = check(res, { [`${ep} returns 200`]: (r) => r.status === 200 });
      errorRate.add(!ok);

      // Fast response suggests cache hit; slow suggests cache miss
      if (elapsed < 50) {
        cacheHits.add(1);
      } else {
        cacheMisses.add(1);
      }

      sleep(0.1);
    }
  });

  group('Cache Invalidation via Write', () => {
    // Create a transaction — should invalidate cache
    const res = http.post(`${BASE_URL}/api/transactions`, JSON.stringify({
      type: 'expense',
      amount: (Math.random() * 100).toFixed(2),
      category_id: 1,
      description: 'Cache stress test',
      date: '2026-05-28',
    }), h);

    check(res, {
      'create returns 201': (r) => r.status === 201,
    });

    sleep(0.2);

    // Immediately read — cache should be invalidated
    const dashRes = http.get(`${BASE_URL}/api/dashboard/summary`, h);
    check(dashRes, {
      'dashboard after invalidation 200': (r) => r.status === 200,
    });
  });

  sleep(0.3);
}
