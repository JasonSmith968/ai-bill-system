// k6 AI Endpoint Stress Test
// Tests AI/LLM endpoints under concurrent load
// Validates circuit breaker and token budget behavior
//
// Run: k6 run tests/load/test_ai.js

import { sleep, group, check } from 'k6';
import http from 'k6/http';
import {
  BASE_URL, authenticate, authHeaders, checkAndRecord,
  errorRate, aiCalls, aiErrors, thresholds,
} from './lib/config.js';

export const options = {
  stages: [
    { duration: '20s', target: 10 },   // gentle ramp (AI endpoints are expensive)
    { duration: '2m', target: 20 },    // sustained 20 concurrent AI calls
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<5000', 'p(99)<10000'],
    http_req_failed: ['rate<0.05'],
    errors: ['rate<0.05'],
    ai_errors_total: ['count<50'],
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

  group('AI Chat Endpoint', () => {
    aiCalls.add(1);
    const res = http.post(`${BASE_URL}/api/ai/chat`, JSON.stringify({
      message: '分析一下我本月的消费情况',
      conversation_id: `loadtest_${__VU}_${__ITER}`,
    }), {
      headers: headers.headers,
      timeout: '30s',
    });

    const ok = checkAndRecord(res, {
      'ai chat returns 200': (r) => r.status === 200,
      'has ai response': (r) => {
        try { return !!JSON.parse(r.body).response; }
        catch(e) { return false; }
      },
    });

    if (!ok) aiErrors.add(1);
  });

  sleep(3); // Longer sleep for AI endpoints

  group('AI Analysis Endpoint', () => {
    aiCalls.add(1);
    const res = http.post(`${BASE_URL}/api/ai/analyze`, JSON.stringify({
      analysis_type: 'spending',
      period: 'month',
    }), {
      headers: headers.headers,
      timeout: '30s',
    });

    const ok = checkAndRecord(res, {
      'ai analysis returns 200 or 429': (r) => r.status === 200 || r.status === 429,
    });

    if (!ok) aiErrors.add(1);
  });

  sleep(3);

  group('Agent V2 Endpoint', () => {
    aiCalls.add(1);
    const res = http.post(`${BASE_URL}/api/agent/v2/run`, JSON.stringify({
      agent: 'finance',
      task: 'summarize',
      input: {},
    }), {
      headers: headers.headers,
      timeout: '30s',
    });

    const ok = checkAndRecord(res, {
      'agent run returns 200 or 503': (r) => r.status === 200 || r.status === 503,
    });

    if (!ok) aiErrors.add(1);
  });

  sleep(3);
}
