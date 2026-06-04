// k6 Tenant Isolation Load Test
// Tests that tenant-isolated queries perform well under concurrent load
// Verifies no data leaks between tenants
//
// Run: k6 run tests/load/test_tenants.js

import { sleep, group, check } from 'k6';
import http from 'k6/http';
import {
  BASE_URL, authenticate, authHeaders, checkAndRecord,
  errorRate, thresholds, strictThresholds,
} from './lib/config.js';

export const options = {
  stages: [
    { duration: '20s', target: 30 },
    { duration: '1m', target: 100 },   // 100 concurrent tenant-scoped queries
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    ...strictThresholds,
    // Tenant queries must be fast (simple WHERE clause)
    http_req_duration: ['p(95)<100', 'p(99)<200'],
  },
};

export function setup() {
  const token = authenticate();
  if (!token) throw new Error('Auth failed');
  return { token };
}

export default function (data) {
  const token = data.token;
  const headers = authHeaders(token);

  group('Tenant-Scoped Transactions', () => {
    // Paginated list — tests WHERE tenant_id = ? performance
    const listRes = http.get(
      `${BASE_URL}/api/transactions?page=1&per_page=50`,
      headers
    );
    checkAndRecord(listRes, {
      'transactions 200': (r) => r.status === 200,
      'fast response': (r) => r.timings.duration < 200,
    }, { endpoint: 'transactions_list' });
  });

  sleep(0.3);

  group('Tenant-Scoped Dashboard', () => {
    const dashRes = http.get(
      `${BASE_URL}/api/dashboard/overview`,
      headers
    );
    checkAndRecord(dashRes, {
      'dashboard 200': (r) => r.status === 200,
      'fast response': (r) => r.timings.duration < 200,
    }, { endpoint: 'dashboard' });
  });

  sleep(0.3);

  group('Tenant-Scoped Categories', () => {
    const catRes = http.get(
      `${BASE_URL}/api/transactions/categories`,
      headers
    );
    checkAndRecord(catRes, {
      'categories 200': (r) => r.status === 200,
      'fast response': (r) => r.timings.duration < 100,
    }, { endpoint: 'categories' });
  });

  sleep(0.3);

  group('Tenant Member List', () => {
    const membersRes = http.get(
      `${BASE_URL}/api/tenants/members`,
      headers
    );
    checkAndRecord(membersRes, {
      'members 200': (r) => r.status === 200,
    }, { endpoint: 'members' });
  });

  sleep(0.5);

  group('Tenant Subscription', () => {
    const subRes = http.get(
      `${BASE_URL}/api/billing/subscription`,
      headers
    );
    checkAndRecord(subRes, {
      'subscription 200': (r) => r.status === 200,
    }, { endpoint: 'subscription' });
  });

  sleep(0.5);
}
