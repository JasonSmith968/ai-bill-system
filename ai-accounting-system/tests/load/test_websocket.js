// k6 WebSocket Load Test
// Tests WebSocket connections and message throughput
//
// Run: k6 run tests/load/test_websocket.js

import { sleep, check } from 'k6';
import http from 'k6/http';
import ws from 'k6/ws';
import {
  BASE_URL, authenticate, errorRate,
} from './lib/config.js';

export const options = {
  stages: [
    { duration: '20s', target: 30 },
    { duration: '1m', target: 100 },   // 100 concurrent WS connections
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    ws_connecting: ['p(95)<1000'],
    ws_msgs_received: ['count>100'],
    errors: ['rate<0.1'],
  },
};

export function setup() {
  const token = authenticate();
  if (!token) throw new Error('Auth failed');
  return { token };
}

export default function (data) {
  const token = data.token;
  // WebSocket URL from HTTP URL
  const wsUrl = BASE_URL.replace(/^http/, 'ws') + `/socket.io/?EIO=4&transport=websocket&token=${token}`;

  const res = ws.connect(wsUrl, {}, function (socket) {
    socket.on('open', () => {
      check(socket, {
        'ws connected': (s) => s.readyState === 1,
      });

      // Send a ping
      socket.send('2probe');
    });

    socket.on('message', (msg) => {
      // Socket.IO sends '3probe' on connect, '3' on pong
      check(msg, {
        'received message': (m) => m.length > 0,
      });
    });

    socket.on('error', (e) => {
      errorRate.add(1);
      console.error(`WebSocket error: ${e.error()}`);
    });

    // Keep connection alive for a bit
    sleep(5);

    socket.close();
  });

  check(res, {
    'ws connection successful': (r) => r && r.status === 101,
  });

  if (!res || res.status !== 101) {
    errorRate.add(1);
  }

  sleep(1);
}
