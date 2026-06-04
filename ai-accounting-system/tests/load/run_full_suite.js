// k6 Full Production Load Test Suite
// Comprehensive test covering all 7 scenarios in sequence
//
// Run: k6 run tests/load/run_full_suite.js
// With URL: k6 run --env BASE_URL=http://staging.example.com tests/load/run_full_suite.js

import { sleep, group, check } from 'k6';
import http from 'k6/http';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';
import ws from 'k6/ws';

// ── Custom Metrics ──────────────────────────────────────────────────────

const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency', true);
const aiLatency = new Trend('ai_latency', true);
const writeLatency = new Trend('write_latency', true);
const wsLatency = new Trend('ws_latency', true);
const totalRequests = new Counter('total_requests');
const aiCalls = new Counter('ai_calls');
const aiErrors = new Counter('ai_errors');
const cacheHits = new Counter('cache_hits');
const cacheMisses = new Counter('cache_misses');

// ── Config ──────────────────────────────────────────────────────────────

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';
const TEST_USER = 'loadtest';
const TEST_PASS = 'LoadTest123!';

// ── Thresholds ──────────────────────────────────────────────────────────

export const options = {
  scenarios: {
    // Phase 1: API Baseline (100 VUs)
    api_baseline: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '20s', target: 100 },
        { duration: '1m', target: 100 },
      ],
      gracefulRampDown: '10s',
      exec: 'apiBaseline',
    },
    // Phase 2: Database Writes (50 VUs, runs after API baseline)
    db_writes: {
      executor: 'ramping-vus',
      startVUs: 0,
      startTime: '1m30s',
      stages: [
        { duration: '15s', target: 50 },
        { duration: '1m', target: 100 },
      ],
      gracefulRampDown: '10s',
      exec: 'dbWrites',
    },
    // Phase 3: Cache Stress (80 VUs)
    cache_stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      startTime: '3m',
      stages: [
        { duration: '15s', target: 80 },
        { duration: '1m', target: 150 },
      ],
      gracefulRampDown: '10s',
      exec: 'cacheStress',
    },
    // Phase 4: AI Endpoints (15 VUs — expensive)
    ai_stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      startTime: '4m30s',
      stages: [
        { duration: '15s', target: 5 },
        { duration: '1m', target: 15 },
      ],
      gracefulRampDown: '10s',
      exec: 'aiStress',
    },
    // Phase 5: WebSocket (50 connections)
    ws_stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      startTime: '6m',
      stages: [
        { duration: '15s', target: 20 },
        { duration: '1m', target: 50 },
      ],
      gracefulRampDown: '10s',
      exec: 'wsStress',
    },
    // Phase 6: Webhook Flood (30 VUs)
    webhook_flood: {
      executor: 'ramping-vus',
      startVUs: 0,
      startTime: '7m30s',
      stages: [
        { duration: '10s', target: 20 },
        { duration: '30s', target: 30 },
      ],
      gracefulRampDown: '5s',
      exec: 'webhookFlood',
    },
    // Phase 7: Concurrent Ramp (all endpoints, 500 VUs)
    final_ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      startTime: '8m30s',
      stages: [
        { duration: '20s', target: 100 },
        { duration: '30s', target: 300 },
        { duration: '30s', target: 500 },
        { duration: '30s', target: 500 },
        { duration: '20s', target: 0 },
      ],
      gracefulRampDown: '10s',
      exec: 'finalRamp',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<2000', 'p(99)<5000'],
    http_req_failed: ['rate<0.15'],
    errors: ['rate<0.15'],
    api_latency: ['p(95)<1000'],
    ai_latency: ['p(95)<10000'],
    write_latency: ['p(95)<1000'],
  },
};

// ── Auth ────────────────────────────────────────────────────────────────

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

function authH() {
  const token = getToken();
  if (!token) return null;
  return { headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` } };
}

// ── Scenario: API Baseline ──────────────────────────────────────────────

export function apiBaseline() {
  const h = authH();
  if (!h) { errorRate.add(1); sleep(1); return; }

  group('API Baseline - Health', () => {
    const res = http.get(`${BASE_URL}/health`);
    totalRequests.add(1);
    const ok = check(res, { 'health 200': (r) => r.status === 200 });
    errorRate.add(!ok);
    apiLatency.add(res.timings.duration);
  });

  sleep(0.3);

  group('API Baseline - Dashboard', () => {
    const res = http.get(`${BASE_URL}/api/dashboard/summary`, h);
    totalRequests.add(1);
    const ok = check(res, { 'dashboard 200': (r) => r.status === 200 });
    errorRate.add(!ok);
    apiLatency.add(res.timings.duration);
  });

  sleep(0.3);

  group('API Baseline - Transactions', () => {
    const res = http.get(`${BASE_URL}/api/transactions?page=1&per_page=20`, h);
    totalRequests.add(1);
    const ok = check(res, { 'transactions 200': (r) => r.status === 200 });
    errorRate.add(!ok);
    apiLatency.add(res.timings.duration);
  });

  sleep(0.3);

  group('API Baseline - Categories', () => {
    const res = http.get(`${BASE_URL}/api/transactions/categories`, h);
    totalRequests.add(1);
    const ok = check(res, { 'categories 200': (r) => r.status === 200 });
    errorRate.add(!ok);
    apiLatency.add(res.timings.duration);
  });

  sleep(0.5);
}

// ── Scenario: DB Writes ─────────────────────────────────────────────────

export function dbWrites() {
  const h = authH();
  if (!h) { errorRate.add(1); sleep(1); return; }

  group('DB Write - Create', () => {
    const res = http.post(`${BASE_URL}/api/transactions`, JSON.stringify({
      type: __VU % 2 === 0 ? 'expense' : 'income',
      amount: (Math.random() * 1000 + 1).toFixed(2),
      category_id: (__VU % 10) + 1,
      description: `Load test VU${__VU} iter${__ITER}`,
      date: '2026-05-28',
    }), h);
    writeLatency.add(res.timings.duration);
    totalRequests.add(1);
    const ok = check(res, { 'create 201': (r) => r.status === 201 });
    errorRate.add(!ok);
  });

  sleep(0.3);

  group('DB Write - Read After Write', () => {
    const res = http.get(`${BASE_URL}/api/transactions?page=1&per_page=5`, h);
    totalRequests.add(1);
    const ok = check(res, { 'raw 200': (r) => r.status === 200 });
    errorRate.add(!ok);
  });

  sleep(0.3);
}

// ── Scenario: Cache Stress ──────────────────────────────────────────────

export function cacheStress() {
  const h = authH();
  if (!h) { errorRate.add(1); sleep(1); return; }

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
    totalRequests.add(1);

    if (elapsed < 50) cacheHits.add(1);
    else cacheMisses.add(1);

    const ok = check(res, { [`${ep} 200`]: (r) => r.status === 200 });
    errorRate.add(!ok);
    sleep(0.05);
  }

  sleep(0.2);
}

// ── Scenario: AI Stress ─────────────────────────────────────────────────

export function aiStress() {
  const h = authH();
  if (!h) { errorRate.add(1); sleep(1); return; }

  group('AI Chat', () => {
    aiCalls.add(1);
    const res = http.post(`${BASE_URL}/api/ai/chat`, JSON.stringify({
      message: '分析本月消费',
      conversation_id: `stress_${__VU}_${__ITER}`,
    }), { headers: h.headers, timeout: '30s' });
    aiLatency.add(res.timings.duration);
    totalRequests.add(1);
    const ok = check(res, { 'ai chat 200 or 429': (r) => r.status === 200 || r.status === 429 });
    if (!ok) { errorRate.add(1); aiErrors.add(1); }
  });

  sleep(2);

  group('Agent V2', () => {
    aiCalls.add(1);
    const res = http.post(`${BASE_URL}/api/agent/v2/run`, JSON.stringify({
      agent: 'finance',
      task: 'summarize',
      input: {},
    }), { headers: h.headers, timeout: '30s' });
    aiLatency.add(res.timings.duration);
    totalRequests.add(1);
    const ok = check(res, { 'agent 200 or 503': (r) => r.status === 200 || r.status === 503 });
    if (!ok) { errorRate.add(1); aiErrors.add(1); }
  });

  sleep(3);
}

// ── Scenario: WebSocket ─────────────────────────────────────────────────

export function wsStress() {
  const token = getToken();
  if (!token) { errorRate.add(1); sleep(1); return; }

  const wsUrl = BASE_URL.replace(/^http/, 'ws') +
    `/socket.io/?EIO=4&transport=websocket&token=${token}`;

  const start = Date.now();
  const res = ws.connect(wsUrl, {}, function (socket) {
    socket.on('open', () => {
      socket.send('2probe');
    });
    socket.on('message', () => {});
    socket.on('error', () => { errorRate.add(1); });
    sleep(3);
    socket.close();
  });

  wsLatency.add(Date.now() - start);
  totalRequests.add(1);

  if (!res || res.status !== 101) {
    errorRate.add(1);
  }

  sleep(1);
}

// ── Scenario: Webhook Flood ─────────────────────────────────────────────

export function webhookFlood() {
  const eventType = 'customer.subscription.updated';
  const eventId = `evt_${__VU}_${__ITER}`;

  const payload = JSON.stringify({
    id: eventId,
    type: eventType,
    created: Math.floor(Date.now() / 1000),
    data: { object: { id: `sub_${Date.now()}`, status: 'active' } },
  });

  const res = http.post(`${BASE_URL}/api/billing/webhook`, payload, {
    headers: {
      'Content-Type': 'application/json',
      'Stripe-Signature': 'test_sig',
    },
  });
  totalRequests.add(1);

  const ok = check(res, {
    'webhook handled': (r) => r.status === 200 || r.status === 201 || r.status === 400,
  });
  if (!ok) errorRate.add(1);

  // Duplicate event
  const res2 = http.post(`${BASE_URL}/api/billing/webhook`, payload, {
    headers: {
      'Content-Type': 'application/json',
      'Stripe-Signature': 'test_sig',
    },
  });
  totalRequests.add(1);

  sleep(0.2);
}

// ── Scenario: Final Ramp (mixed workload) ───────────────────────────────

export function finalRamp() {
  const h = authH();
  if (!h) { errorRate.add(1); sleep(1); return; }

  // Mixed workload simulating real user behavior
  group('Final - Dashboard', () => {
    const res = http.get(`${BASE_URL}/api/dashboard/summary`, h);
    totalRequests.add(1);
    errorRate.add(res.status !== 200);
    apiLatency.add(res.timings.duration);
  });

  sleep(0.2);

  group('Final - Transactions', () => {
    const res = http.get(`${BASE_URL}/api/transactions?page=1&per_page=20`, h);
    totalRequests.add(1);
    errorRate.add(res.status !== 200);
    apiLatency.add(res.timings.duration);
  });

  sleep(0.2);

  group('Final - Create', () => {
    const res = http.post(`${BASE_URL}/api/transactions`, JSON.stringify({
      type: 'expense',
      amount: (Math.random() * 100 + 1).toFixed(2),
      category_id: 1,
      description: 'Final ramp test',
      date: '2026-05-28',
    }), h);
    totalRequests.add(1);
    writeLatency.add(res.timings.duration);
    errorRate.add(res.status !== 201);
  });

  sleep(0.2);

  group('Final - Health', () => {
    const res = http.get(`${BASE_URL}/health`);
    totalRequests.add(1);
    errorRate.add(res.status !== 200);
  });

  sleep(0.5);
}
