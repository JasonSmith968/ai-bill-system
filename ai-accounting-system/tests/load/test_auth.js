// k6 Auth Flow Load Test
// Tests login, token refresh, and authenticated requests under concurrent load
//
// Run: k6 run tests/load/test_auth.js

import { sleep, group, check } from 'k6';
import http from 'k6/http';
import {
  BASE_URL, TEST_USER, TEST_PASS, authenticate,
  authHeaders, checkAndRecord, errorRate, thresholds,
} from './lib/config.js';

export const options = {
  stages: [
    { duration: '20s', target: 30 },   // ramp up
    { duration: '1m', target: 50 },    // sustained concurrent logins
    { duration: '20s', target: 0 },    // ramp down
  ],
  thresholds,
};

export default function () {
  group('Login Flow', () => {
    // Login
    const loginRes = http.post(`${BASE_URL}/api/auth/login`, JSON.stringify({
      email: TEST_USER,
      password: TEST_PASS,
    }), {
      headers: { 'Content-Type': 'application/json' },
    });

    const loginOk = checkAndRecord(loginRes, {
      'login status 200': (r) => r.status === 200,
      'has access_token': (r) => {
        try { return !!JSON.parse(r.body).access_token; }
        catch(e) { return false; }
      },
      'has refresh_token': (r) => {
        try { return !!JSON.parse(r.body).refresh_token; }
        catch(e) { return false; }
      },
    });

    if (!loginOk) {
      errorRate.add(1);
      return;
    }

    const body = JSON.parse(loginRes.body);
    const accessToken = body.access_token;
    const refreshToken = body.refresh_token;

    sleep(0.5);

    group('Token Refresh', () => {
      const refreshRes = http.post(`${BASE_URL}/api/auth/refresh`, JSON.stringify({
        refresh_token: refreshToken,
      }), {
        headers: { 'Content-Type': 'application/json' },
      });

      checkAndRecord(refreshRes, {
        'refresh status 200': (r) => r.status === 200,
        'new access_token': (r) => {
          try { return !!JSON.parse(r.body).access_token; }
          catch(e) { return false; }
        },
      });
    });

    sleep(0.5);

    group('Authenticated Request', () => {
      const meRes = http.get(
        `${BASE_URL}/api/auth/me`,
        authHeaders(accessToken)
      );
      checkAndRecord(meRes, {
        'me status 200': (r) => r.status === 200,
        'has user data': (r) => {
          try { return !!JSON.parse(r.body).user; }
          catch(e) { return false; }
        },
      });
    });

    sleep(0.5);

    group('Invalid Token Rejection', () => {
      const badRes = http.get(
        `${BASE_URL}/api/auth/me`,
        authHeaders('invalid-token-should-fail')
      );
      checkAndRecord(badRes, {
        'invalid token returns 401': (r) => r.status === 401,
      });
    });
  });

  sleep(1);
}
