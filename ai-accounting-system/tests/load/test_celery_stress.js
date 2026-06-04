// k6 Celery Queue Stress Test
// Tests async task submission and queue backlog behavior
//
// Run: k6 run tests/load/test_celery_stress.js

import { sleep, group, check } from 'k6';
import http from 'k6/http';
import { Rate, Trend, Counter } from 'k6/metrics';

const errorRate = new Rate('errors');
const taskLatency = new Trend('task_submission_latency', true);
const tasksSubmitted = new Counter('tasks_submitted');
const taskErrors = new Counter('task_errors');

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';
const TEST_USER = 'loadtest';
const TEST_PASS = 'LoadTest123!';

export const options = {
  stages: [
    { duration: '15s', target: 30 },
    { duration: '1m', target: 100 },   // 100 VUs submitting tasks
    { duration: '30s', target: 200 },  // burst
    { duration: '1m', target: 200 },   // hold
    { duration: '15s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<3000'],
    errors: ['rate<0.15'],
    task_submission_latency: ['p(95)<2000'],
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

  group('Report Export Task', () => {
    // Export triggers a Celery task
    const res = http.post(`${BASE_URL}/api/reports/export`, JSON.stringify({
      format: 'csv',
      period: 'month',
    }), h);
    taskLatency.add(res.timings.duration);
    tasksSubmitted.add(1);

    const ok = check(res, {
      'export accepted': (r) => r.status === 200 || r.status === 201 || r.status === 202,
    });
    if (!ok) { errorRate.add(1); taskErrors.add(1); }
  });

  sleep(0.5);

  group('AI Analysis Task', () => {
    // AI analysis may trigger async processing
    const res = http.post(`${BASE_URL}/api/ai/analyze`, JSON.stringify({
      analysis_type: 'spending',
      period: 'month',
    }), { headers: h.headers, timeout: '15s' });
    taskLatency.add(res.timings.duration);
    tasksSubmitted.add(1);

    const ok = check(res, {
      'analysis accepted or completed': (r) =>
        r.status === 200 || r.status === 202 || r.status === 429,
    });
    if (!ok) { errorRate.add(1); taskErrors.add(1); }
  });

  sleep(0.5);

  group('Task Status Polling', () => {
    // Check if task status endpoint works under load
    const res = http.get(`${BASE_URL}/api/tasks`, h);
    const ok = check(res, {
      'task list returns 200': (r) => r.status === 200,
    });
    if (!ok) errorRate.add(1);
  });

  sleep(0.5);
}
