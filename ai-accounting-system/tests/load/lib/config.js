// k6 shared configuration for AI Accounting System load tests
// Usage: k6 run --env BASE_URL=http://localhost:5000 tests/load/test_api.js

import http from 'k6/http';
import { check } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
export const errorRate = new Rate('errors');
export const apiLatency = new Trend('api_latency', true);
export const aiCalls = new Counter('ai_calls_total');
export const aiErrors = new Counter('ai_errors_total');

// Environment config
const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';
const TEST_USER = __ENV.TEST_USER || 'loadtest';
const TEST_PASS = __ENV.TEST_PASS || 'LoadTest123!';

export { BASE_URL, TEST_USER, TEST_PASS };

// Shared thresholds
export const thresholds = {
  http_req_duration: ['p(95)<500', 'p(99)<1000'],
  http_req_failed: ['rate<0.05'],
  errors: ['rate<0.05'],
};

export const strictThresholds = {
  http_req_duration: ['p(95)<200', 'p(99)<500'],
  http_req_failed: ['rate<0.01'],
  errors: ['rate<0.01'],
};

// Authenticate and return token
export function authenticate(email, password) {
  const loginRes = http.post(`${BASE_URL}/api/auth/login`, JSON.stringify({
    username: email || TEST_USER,
    password: password || TEST_PASS,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  const success = check(loginRes, {
    'login status 200': (r) => r.status === 200,
    'has access_token': (r) => {
      try { return JSON.parse(r.body).access_token !== undefined; }
      catch(e) { return false; }
    },
  });

  if (!success) {
    errorRate.add(1);
    return null;
  }

  errorRate.add(0);
  return JSON.parse(loginRes.body).access_token;
}

// Authenticated request helper
export function authHeaders(token) {
  return {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
  };
}

// Check and record latency
export function checkAndRecord(res, checks, tags = {}) {
  const passed = check(res, checks);
  errorRate.add(!passed);
  apiLatency.add(res.timings.duration, tags);
  return passed;
}

// Register a new test user
export function registerUser(email, password, username) {
  const res = http.post(`${BASE_URL}/api/auth/register`, JSON.stringify({
    username: username || `loadtest_${Date.now()}`,
    email: email || `loadtest_${Date.now()}@example.com`,
    password: password || TEST_PASS,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
  return res;
}
