/**
 * Composable for streaming task results via WebSocket with SSE fallback.
 *
 * Replaces the duplicated fetch+getReader+SSE parsing in 5+ views.
 *
 * Usage:
 *   const { startTask, status, result, streaming, error, progress } = useTaskStream('chat')
 *   startTask({ message: '分析我的消费' })
 */

import { ref } from 'vue'
import { getWSClient } from '@/utils/websocket'

export function useTaskStream(taskType = 'chat') {
  const status = ref('idle') // idle | connecting | streaming | done | error
  const result = ref('')
  const streaming = ref(false)
  const error = ref('')
  const progress = ref(0)
  const callChain = ref([])
  const activeAgent = ref(null)

  let _cleanup = null

  function _reset() {
    status.value = 'idle'
    result.value = ''
    streaming.value = false
    error.value = ''
    progress.value = 0
    callChain.value = []
    activeAgent.value = null
  }

  function _cleanupListeners() {
    if (_cleanup) {
      _cleanup()
      _cleanup = null
    }
  }

  /**
   * Start a chat task via WebSocket.
   * Falls back to SSE if WebSocket is not connected.
   */
  async function startChat(message) {
    _reset()
    _cleanupListeners()
    streaming.value = true
    status.value = 'connecting'

    const ws = getWSClient()

    if (ws.connected) {
      // --- WebSocket path ---
      const unsubs = []

      unsubs.push(ws.on('llm_chunk', (data) => {
        status.value = 'streaming'
        result.value += data.content
      }))

      unsubs.push(ws.on('llm_done', (data) => {
        status.value = 'done'
        streaming.value = false
        _cleanupListeners()
      }))

      unsubs.push(ws.on('llm_error', (data) => {
        error.value = data.error || '处理失败'
        status.value = 'error'
        streaming.value = false
        _cleanupListeners()
      }))

      _cleanup = () => unsubs.forEach(fn => fn())

      const sent = ws.emit('chat_message', { message })
      if (!sent) {
        // WS disconnected mid-flight, fall back
        _cleanupListeners()
        return _fallbackSSEChat(message)
      }
    } else {
      // --- SSE fallback ---
      return _fallbackSSEChat(message)
    }
  }

  /**
   * Start an agent task via WebSocket.
   */
  async function startAgent(agent, task, params = {}) {
    _reset()
    _cleanupListeners()
    streaming.value = true
    status.value = 'connecting'
    activeAgent.value = agent

    const ws = getWSClient()

    if (ws.connected) {
      const unsubs = []

      unsubs.push(ws.on('agent_start', (data) => {
        status.value = 'streaming'
        activeAgent.value = data.agent
      }))

      unsubs.push(ws.on('agent_done', (data) => {
        result.value = data.result?.content || JSON.stringify(data.result)
        callChain.value = data.call_chain || []
        status.value = 'done'
        streaming.value = false
        _cleanupListeners()
      }))

      unsubs.push(ws.on('agent_error', (data) => {
        error.value = data.error || 'Agent 执行失败'
        status.value = 'error'
        streaming.value = false
        _cleanupListeners()
      }))

      _cleanup = () => unsubs.forEach(fn => fn())
      ws.emit('agent_run', { agent, task, params })
    } else {
      return _fallbackSSEAgent(agent, task, params)
    }
  }

  /**
   * Start a workflow task via WebSocket.
   */
  async function startWorkflow(workflowName, params = {}) {
    _reset()
    _cleanupListeners()
    streaming.value = true
    status.value = 'connecting'

    const ws = getWSClient()

    if (ws.connected) {
      const unsubs = []

      unsubs.push(ws.on('workflow_step', (data) => {
        status.value = 'streaming'
        callChain.value.push(data)
        result.value += (data.content || '') + '\n'
      }))

      unsubs.push(ws.on('workflow_done', (data) => {
        callChain.value = data.call_chain || callChain.value
        status.value = 'done'
        streaming.value = false
        _cleanupListeners()
      }))

      unsubs.push(ws.on('workflow_error', (data) => {
        error.value = data.error || '工作流执行失败'
        status.value = 'error'
        streaming.value = false
        _cleanupListeners()
      }))

      _cleanup = () => unsubs.forEach(fn => fn())
      ws.emit('workflow_run', { workflow_name: workflowName, params })
    } else {
      error.value = 'WebSocket 未连接'
      status.value = 'error'
      streaming.value = false
    }
  }

  /**
   * SSE fallback for chat — uses the v2 agent chat endpoint.
   */
  async function _fallbackSSEChat(message) {
    try {
      const token = localStorage.getItem('token')
      const resp = await fetch('/api/agent/v2/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ message }),
      })

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        error.value = err.error || `请求失败 (${resp.status})`
        status.value = 'error'
        streaming.value = false
        return
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6).trim()
          if (data === '[DONE]') {
            status.value = 'done'
            streaming.value = false
            return
          }
          try {
            const parsed = JSON.parse(data)
            if (parsed.type === 'route') {
              activeAgent.value = parsed.agent
              status.value = 'streaming'
              continue
            }
            if (parsed.type === 'error') {
              error.value = parsed.payload || parsed.error || '处理失败'
              status.value = 'error'
              streaming.value = false
              return
            }
            if (parsed.content || parsed.payload) {
              result.value += parsed.content || parsed.payload
              status.value = 'streaming'
            }
          } catch {}
        }
      }

      status.value = 'done'
      streaming.value = false
    } catch (e) {
      error.value = '网络错误，请检查连接后重试。'
      status.value = 'error'
      streaming.value = false
    }
  }

  /**
   * SSE fallback for agent run.
   */
  async function _fallbackSSEAgent(agent, task, params) {
    try {
      const token = localStorage.getItem('token')
      const resp = await fetch('/api/agent/v2/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ agent, task, params }),
      })

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        error.value = err.error || `请求失败 (${resp.status})`
        status.value = 'error'
        streaming.value = false
        return
      }

      const data = await resp.json()
      result.value = data.result?.content || JSON.stringify(data.result)
      callChain.value = data.call_chain || []
      status.value = 'done'
      streaming.value = false
    } catch (e) {
      error.value = '网络错误'
      status.value = 'error'
      streaming.value = false
    }
  }

  function cleanup() {
    _cleanupListeners()
    _reset()
  }

  return {
    startChat,
    startAgent,
    startWorkflow,
    cleanup,
    status,
    result,
    streaming,
    error,
    progress,
    callChain,
    activeAgent,
  }
}
