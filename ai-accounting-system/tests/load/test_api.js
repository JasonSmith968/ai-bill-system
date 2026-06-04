// k6 API Baseline Load Test
// Tests core API endpoints under normal load
//
// Run: k6 run tests/load/test_api.js
// With custom URL: k6 run --env BASE_URL=http://staging.example.com tests/load/test_api.js

import { sleep, group } from 'k6';
import http from 'k6/http';
import {
  BASE_URL, authenticate, authHeaders, checkAndRecord,
  errorRate, thresholds,
} from './lib/config.js';

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // ramp up
    { duration: '1m', target: 100 },   // sustained load
    { duration: '30s', target: 0 },    // ramp down
  ],
  thresholds,
};

export function setup() {
  const token = authenticate();
  if (!token) {
    throw new Error('Authentication failed — cannot run load test');
  }
  return { token };
}

export default function (data) {
  const token = data.token;
  const headers = authHeaders(token);

  group('Dashboard API', () => {
    const res = http.get(`${BASE_URL}/api/dashboard/overview`, headers);
    checkAndRecord(res, {
      'dashboard status 200': (r) => r.status === 200,
      'has data': (r) => r.body.length > 10,
    });
  });

  sleep(1);

  group('Transactions API', () => {
    // List transactions
    const listRes = http.get(`${BASE_URL}/api/transactions?page=1&per_page=20`, headers);
    checkAndRecord(listRes, {
      'transactions status 200': (r) => r.status === 200,
      'has transactions array': (r) => {
        try { return Array.isArray(JSON.parse(r.body).transactions); }
        catch(e) { return false; }
      },
    });

    sleep(0.5);

    // Get categories
    const catRes = http.get(`${BASE_URL}/api/transactions/categories`, headers);
    checkAndRecord(catRes, {
      'categories status 200': (r) => r.status === 200,
    });
  });

  sleep(1);

  group('Health Check', () => {
    const res = http.get(`${BASE_URL}/health`);
    checkAndRecord(res, {
      'health status 200': (r) => r.status === 200,
      'has ok status': (r) => {
        try { return JSON.parse(r.body).status === 'ok'; }
        catch(e) { return false; }
      },
    });
  });

  sleep(1);
}
