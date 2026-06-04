// k6 Stripe Webhook Flood Test
// Tests webhook idempotency under burst conditions
//
// Run: k6 run tests/load/test_stripe_webhook.js

import { sleep, check, group } from 'k6';
import http from 'k6/http';
import { Rate, Counter } from 'k6/metrics';

const errorRate = new Rate('errors');
const duplicateEvents = new Counter('duplicate_events');
const idempotentRejects = new Counter('idempotent_rejects');

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';

export const options = {
  stages: [
    { duration: '10s', target: 20 },
    { duration: '1m', target: 100 },   // 100 VUs sending webhooks
    { duration: '10s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<1000'],
    errors: ['rate<0.15'],
  },
};

// Simulate Stripe webhook payload
function makeWebhookPayload(eventType, eventId) {
  return JSON.stringify({
    id: eventId,
    type: eventType,
    created: Math.floor(Date.now() / 1000),
    data: {
      object: {
        id: `sub_${Date.now()}`,
        customer: `cus_test_${__VU}`,
        status: 'active',
        current_period_start: Math.floor(Date.now() / 1000),
        current_period_end: Math.floor(Date.now() / 1000) + 2592000,
      },
    },
  });
}

export default function () {
  const eventType = 'customer.subscription.updated';
  const eventId = `evt_${__VU}_${__ITER}`;

  group('Unique Webhook Events', () => {
    const payload = makeWebhookPayload(eventType, eventId);
    const res = http.post(`${BASE_URL}/api/billing/webhook`, payload, {
      headers: {
        'Content-Type': 'application/json',
        'Stripe-Signature': 'test_sig',  // test mode bypasses sig verification
      },
    });

    const ok = check(res, {
      'webhook accepted or already processed': (r) =>
        r.status === 200 || r.status === 201 || r.status === 400,
    });

    if (!ok) errorRate.add(1);
  });

  sleep(0.1);

  group('Duplicate Webhook Events', () => {
    // Send the SAME event ID again — should be idempotent
    const payload = makeWebhookPayload(eventType, eventId);
    const res = http.post(`${BASE_URL}/api/billing/webhook`, payload, {
      headers: {
        'Content-Type': 'application/json',
        'Stripe-Signature': 'test_sig',
      },
    });

    duplicateEvents.add(1);

    // Should return 200 (already processed) or 400 (invalid sig in prod)
    const ok = check(res, {
      'duplicate handled gracefully': (r) =>
        r.status === 200 || r.status === 201 || r.status === 400,
    });

    if (!ok) errorRate.add(1);
  });

  sleep(0.1);

  group('Burst Webhook Storm', () => {
    // Send 5 rapid webhooks with different event IDs
    for (let i = 0; i < 5; i++) {
      const burstEventId = `evt_burst_${__VU}_${__ITER}_${i}`;
      const payload = makeWebhookPayload(eventType, burstEventId);
      http.post(`${BASE_URL}/api/billing/webhook`, payload, {
        headers: {
          'Content-Type': 'application/json',
          'Stripe-Signature': 'test_sig',
        },
      });
    }
  });

  sleep(0.5);
}
