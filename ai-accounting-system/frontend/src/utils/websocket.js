/**
 * WebSocket client — singleton Socket.IO wrapper with auto-reconnect and heartbeat.
 *
 * Usage:
 *   import { getWSClient } from '@/utils/websocket'
 *   const ws = getWSClient()
 *   ws.connect(token)
 *   ws.on('llm_chunk', handler)
 *   ws.emit('chat_message', { message })
 */

import { io } from 'socket.io-client'

class WSClient {
  constructor() {
    this._socket = null
    this._handlers = new Map() // event → Set<callback>
    this._retries = 0
    this._maxRetries = 5
    this._heartbeatTimer = null
    this._connected = false
  }

  get connected() {
    return this._connected
  }

  /**
   * Connect to the Socket.IO server with JWT authentication.
   * @param {string} token — JWT access token
   */
  connect(token) {
    if (this._socket?.connected) return

    const baseURL = import.meta.env.VITE_WS_URL || window.location.origin

    this._socket = io(baseURL, {
      auth: { token },
      query: { token },
      transports: ['websocket', 'polling'],
      reconnection: false, // We handle reconnection manually
    })

    this._socket.on('connect', () => {
      this._connected = true
      this._retries = 0
      this._startHeartbeat()
      this._emit('ws:connected')
    })

    this._socket.on('disconnect', (reason) => {
      this._connected = false
      this._stopHeartbeat()
      this._emit('ws:disconnected', reason)
      this._scheduleReconnect(token)
    })

    this._socket.on('connect_error', (err) => {
      this._connected = false
      this._emit('ws:error', err.message)
      this._scheduleReconnect(token)
    })

    // Forward all custom events to registered handlers
    const forwardedEvents = [
      'connected', 'llm_chunk', 'llm_done', 'llm_error',
      'agent_start', 'agent_done', 'agent_error',
      'workflow_step', 'workflow_done', 'workflow_error',
      'task_update', 'subscribed',
    ]

    for (const event of forwardedEvents) {
      this._socket.on(event, (data) => this._emit(event, data))
    }
  }

  disconnect() {
    this._stopHeartbeat()
    this._retries = this._maxRetries // Prevent reconnect
    if (this._socket) {
      this._socket.disconnect()
      this._socket = null
    }
    this._connected = false
  }

  on(event, callback) {
    if (!this._handlers.has(event)) {
      this._handlers.set(event, new Set())
    }
    this._handlers.get(event).add(callback)
    return () => this.off(event, callback)
  }

  off(event, callback) {
    this._handlers.get(event)?.delete(callback)
  }

  emit(event, data) {
    if (this._socket?.connected) {
      this._socket.emit(event, data)
      return true
    }
    return false
  }

  _emit(event, data) {
    const handlers = this._handlers.get(event)
    if (handlers) {
      for (const cb of handlers) {
        try { cb(data) } catch (e) { console.error(`WS handler error [${event}]:`, e) }
      }
    }
  }

  _scheduleReconnect(token) {
    if (this._retries >= this._maxRetries) return
    const delay = Math.min(1000 * 2 ** this._retries, 16000)
    this._retries++
    setTimeout(() => {
      if (!this._connected && this._socket) {
        this._socket.connect()
      }
    }, delay)
  }

  _startHeartbeat() {
    this._stopHeartbeat()
    this._heartbeatTimer = setInterval(() => {
      if (this._socket?.connected) {
        this._socket.emit('ping')
      }
    }, 30000)
  }

  _stopHeartbeat() {
    if (this._heartbeatTimer) {
      clearInterval(this._heartbeatTimer)
      this._heartbeatTimer = null
    }
  }
}

// Singleton
let instance = null

export function getWSClient() {
  if (!instance) {
    instance = new WSClient()
  }
  return instance
}

export default WSClient
