<script setup>
import { ref, onMounted, computed } from 'vue'
import { renderSafeMarkdown } from '@/utils/safeMarkdown'
import AgentCallChain from '@/components/AgentCallChain.vue'
import api from '@/utils/api'
import { getWSClient } from '@/utils/websocket'

const wsClient = getWSClient()
const period = ref(3)
const loading = ref(false)
const streaming = ref(false)
const agents = ref([])
const workflows = ref([])
const callChain = ref([])
const data = ref(null)
const aiContent = ref('')
const showLogs = ref(false)
const logs = ref([])

// Mode: 'analysis' | 'workflow' | 'router'
const mode = ref('analysis')
const selectedWorkflow = ref('')
const routerInput = ref('')
const routerResult = ref(null)

// Memory
const showMemory = ref(false)
const memories = ref([])

const periodLabel = computed(() => {
  const labels = { 1: '近1个月', 3: '近3个月', 6: '近6个月' }
  return labels[period.value] || `近${period.value}个月`
})

onMounted(async () => {
  try {
    const [agentsRes, workflowsRes] = await Promise.all([
      api.get('/agent/v2/agents'),
      api.get('/agent/v2/workflows'),
    ])
    agents.value = agentsRes.data.agents || []
    workflows.value = workflowsRes.data.workflows || []
    if (workflows.value.length) selectedWorkflow.value = workflows.value[0].name
  } catch {}
})

async function runAnalysis() {
  loading.value = true
  streaming.value = true
  callChain.value = []
  data.value = null
  aiContent.value = ''

  const token = localStorage.getItem('token')

  try {
    const resp = await fetch('/api/multi-agent/analyze/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ period: period.value })
    })
    await processSSEStream(resp)
  } catch (e) {
    console.error('Stream error:', e)
  } finally {
    loading.value = false
    streaming.value = false
  }
}

async function runWorkflow() {
  if (!selectedWorkflow.value) return
  loading.value = true
  streaming.value = true
  callChain.value = []
  data.value = null
  aiContent.value = ''

  if (wsClient.connected) {
    const unsubs = []
    unsubs.push(wsClient.on('workflow_step', (event) => {
      if (event.type === 'step_start' || event.agent) {
        callChain.value.push({
          agent: event.agent,
          step: event.step,
          type: 'workflow_step',
          status: event.status || 'running',
          duration_ms: event.duration_ms || 0,
        })
      }
      if (event.content) aiContent.value += event.content
      loading.value = false
    }))
    unsubs.push(wsClient.on('workflow_done', (event) => {
      if (event.call_chain) callChain.value = event.call_chain
      streaming.value = false
      loading.value = false
      unsubs.forEach(fn => fn())
    }))
    unsubs.push(wsClient.on('workflow_error', (event) => {
      aiContent.value += `\n\n> 错误: ${event.error || '未知错误'}`
      streaming.value = false
      loading.value = false
      unsubs.forEach(fn => fn())
    }))
    wsClient.emit('workflow_run', { workflow_name: selectedWorkflow.value, params: { period: period.value } })
    return
  }

  const token = localStorage.getItem('token')
  try {
    const resp = await fetch('/api/agent/v2/workflow', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ workflow_name: selectedWorkflow.value, params: { period: period.value } })
    })
    await processSSEStream(resp)
  } catch (e) {
    console.error('Workflow error:', e)
  } finally {
    loading.value = false
    streaming.value = false
  }
}

async function runRouter() {
  if (!routerInput.value.trim()) return
  loading.value = true
  streaming.value = true
  callChain.value = []
  data.value = null
  aiContent.value = ''
  routerResult.value = null

  if (wsClient.connected) {
    const unsubs = []
    unsubs.push(wsClient.on('llm_chunk', (d) => { aiContent.value += d.content; loading.value = false }))
    unsubs.push(wsClient.on('llm_done', () => { streaming.value = false; loading.value = false; unsubs.forEach(fn => fn()) }))
    unsubs.push(wsClient.on('llm_error', (d) => { aiContent.value += `\n\n> 错误: ${d.error}`; streaming.value = false; loading.value = false; unsubs.forEach(fn => fn()) }))
    wsClient.emit('chat_message', { message: routerInput.value })
    return
  }

  const token = localStorage.getItem('token')
  try {
    const resp = await fetch('/api/agent/v2/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ message: routerInput.value })
    })
    await processSSEStream(resp)
  } catch (e) {
    console.error('Router error:', e)
  } finally {
    loading.value = false
    streaming.value = false
  }
}

async function processSSEStream(resp) {
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
      const payload = line.slice(6).trim()
      if (!payload) continue

      try {
        const event = JSON.parse(payload)

        if (event.type === 'route') {
          routerResult.value = event
          callChain.value.push({
            agent: event.agent,
            step: `路由 → ${event.agent}(${event.task})`,
            type: 'workflow_step',
            status: 'ok',
            duration_ms: 0,
          })
        } else if (event.type === 'workflow_start') {
          callChain.value.push({
            step: event.workflow,
            type: 'workflow_step',
            status: 'running',
            duration_ms: 0,
          })
        } else if (event.type === 'step_start') {
          callChain.value.push({
            agent: event.agent,
            step: event.step,
            type: 'workflow_step',
            status: 'running',
            duration_ms: 0,
          })
        } else if (event.type === 'step_end') {
          const idx = callChain.value.findLastIndex(c => c.step === event.step)
          if (idx >= 0) {
            callChain.value[idx].status = event.status || 'ok'
            callChain.value[idx].duration_ms = event.duration_ms || 0
            callChain.value[idx].data_keys = event.data_keys || []
          }
          loading.value = false
        } else if (event.type === 'agent_start') {
          if (!callChain.value.find(c => c.agent === event.agent && c.status === 'running')) {
            callChain.value.push({
              agent: event.agent,
              status: 'running',
              duration_ms: 0,
              input_keys: [],
              output_keys: []
            })
          }
        } else if (event.type === 'agent_done') {
          const idx = callChain.value.findLastIndex(c => c.agent === event.agent)
          if (idx >= 0) {
            callChain.value[idx].status = 'ok'
            callChain.value[idx].duration_ms = event.duration_ms || 0
          }
          loading.value = false
        } else if (event.type === 'data') {
          data.value = event.payload
        } else if (event.type === 'content') {
          aiContent.value += event.payload
        } else if (event.type === 'done') {
          if (event.call_chain) callChain.value = event.call_chain
          streaming.value = false
        } else if (event.type === 'error') {
          aiContent.value += `\n\n> 错误: ${event.payload || event.message || '未知错误'}`
          streaming.value = false
        }
      } catch {}
    }
  }
}

async function loadLogs() {
  try {
    const res = await api.get('/multi-agent/logs', { params: { limit: 30 } })
    logs.value = res.data.logs || []
  } catch {}
}

function toggleLogs() {
  showLogs.value = !showLogs.value
  if (showLogs.value && logs.value.length === 0) loadLogs()
}

async function loadMemory() {
  try {
    const res = await api.get('/agent/v2/memory')
    memories.value = res.data.memories || []
  } catch {}
}

function toggleMemory() {
  showMemory.value = !showMemory.value
  if (showMemory.value && memories.value.length === 0) loadMemory()
}

async function deleteMemory(key) {
  try {
    await api.delete(`/agent/v2/memory/${key}`)
    memories.value = memories.value.filter(m => m.key !== key)
  } catch {}
}
</script>

<template>
  <div class="min-h-screen bg-slate-900 text-white">
    <!-- Header -->
    <div class="mb-6">
      <div class="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 class="text-2xl font-bold text-white flex items-center gap-3">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-7 h-7 text-indigo-400">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
            </svg>
            Multi-Agent 协作系统
          </h1>
          <p class="text-sm text-slate-400 mt-1">多个 AI Agent 协同分析您的财务数据</p>
        </div>

        <div class="flex items-center gap-2">
          <button @click="toggleMemory" class="px-3 py-2 rounded-lg text-sm bg-slate-800 border border-slate-700 hover:border-slate-600 transition-all" :class="showMemory ? 'text-indigo-400 border-indigo-500/50' : 'text-slate-400'">
            记忆
          </button>
          <button @click="toggleLogs" class="px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-slate-200 bg-slate-800 border border-slate-700 hover:border-slate-600 transition-all">
            日志
          </button>
        </div>
      </div>
    </div>

    <!-- Mode Tabs -->
    <div class="flex gap-1 mb-6 bg-slate-800/60 rounded-xl p-1 w-fit">
      <button @click="mode = 'analysis'" class="px-4 py-2 rounded-lg text-sm font-medium transition-all"
        :class="mode === 'analysis' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'">
        全量分析
      </button>
      <button @click="mode = 'workflow'" class="px-4 py-2 rounded-lg text-sm font-medium transition-all"
        :class="mode === 'workflow' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'">
        工作流
      </button>
      <button @click="mode = 'router'" class="px-4 py-2 rounded-lg text-sm font-medium transition-all"
        :class="mode === 'router' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'">
        智能路由
      </button>
    </div>

    <!-- Analysis Mode -->
    <div v-if="mode === 'analysis'" class="flex items-center gap-3 mb-6">
      <select v-model="period" class="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-indigo-500">
        <option :value="1">近1个月</option>
        <option :value="3">近3个月</option>
        <option :value="6">近6个月</option>
      </select>
      <button @click="runAnalysis" :disabled="streaming" class="px-5 py-2 rounded-lg font-medium text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
        :class="streaming ? 'bg-slate-700 text-slate-400' : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20'">
        <span v-if="streaming" class="flex items-center gap-2">
          <svg class="animate-spin w-4 h-4" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
          分析中...
        </span>
        <span v-else>运行分析</span>
      </button>
    </div>

    <!-- Workflow Mode -->
    <div v-if="mode === 'workflow'" class="flex items-center gap-3 mb-6">
      <select v-model="selectedWorkflow" class="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-indigo-500">
        <option v-for="w in workflows" :key="w.name" :value="w.name">{{ w.description || w.name }} ({{ w.steps }}步)</option>
      </select>
      <select v-model="period" class="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-indigo-500">
        <option :value="1">近1个月</option>
        <option :value="3">近3个月</option>
        <option :value="6">近6个月</option>
      </select>
      <button @click="runWorkflow" :disabled="streaming || !selectedWorkflow" class="px-5 py-2 rounded-lg font-medium text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
        :class="streaming ? 'bg-slate-700 text-slate-400' : 'bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-500/20'">
        <span v-if="streaming" class="flex items-center gap-2">
          <svg class="animate-spin w-4 h-4" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
          执行中...
        </span>
        <span v-else>执行工作流</span>
      </button>
    </div>

    <!-- Router Mode -->
    <div v-if="mode === 'router'" class="mb-6">
      <div class="flex gap-3">
        <input v-model="routerInput" @keydown.enter="runRouter" placeholder="输入自然语言，如: 帮我分析本月消费、我需要报税建议、看看有没有异常消费..."
          class="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500" />
        <button @click="runRouter" :disabled="streaming || !routerInput.trim()" class="px-5 py-2 rounded-lg font-medium text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          :class="streaming ? 'bg-slate-700 text-slate-400' : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'">
          发送
        </button>
      </div>
      <div v-if="routerResult" class="mt-2 flex items-center gap-2 text-xs text-slate-500">
        <span>路由到:</span>
        <span class="px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 font-medium">{{ routerResult.agent }}</span>
        <span>任务: {{ routerResult.task }}</span>
        <span>置信度: {{ (routerResult.confidence * 100).toFixed(0) }}%</span>
        <span v-if="routerResult.source" class="px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-400">{{ routerResult.source }}</span>
      </div>
    </div>

    <!-- Agent Status Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <div v-for="agent in agents" :key="agent.name"
        class="bg-slate-800/80 rounded-xl p-4 border border-slate-700/60 hover:border-indigo-500/30 transition-all">
        <div class="text-sm font-semibold text-slate-200 capitalize">{{ agent.name }}</div>
        <div class="text-xs text-slate-500 mt-1 line-clamp-2">{{ agent.description }}</div>
        <div class="flex flex-wrap gap-1 mt-2">
          <span v-for="cap in agent.capabilities" :key="cap"
            class="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">{{ cap }}</span>
        </div>
      </div>
    </div>

    <!-- Call Chain Visualization -->
    <AgentCallChain :call-chain="callChain" class="mb-6" />

    <!-- Loading -->
    <div v-if="loading && !data && !aiContent" class="flex items-center justify-center py-20">
      <div class="text-center">
        <div class="flex gap-1.5 justify-center mb-3">
          <div class="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-bounce" style="animation-delay: 0s"></div>
          <div class="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-bounce" style="animation-delay: 0.15s"></div>
          <div class="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-bounce" style="animation-delay: 0.3s"></div>
        </div>
        <p class="text-sm text-slate-400">Agent 正在协同分析...</p>
      </div>
    </div>

    <!-- Results -->
    <div v-if="data" class="space-y-6">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div class="bg-slate-800/80 rounded-xl p-4 border border-slate-700/60">
          <div class="text-xs text-slate-500 mb-1">分析周期</div>
          <div class="text-lg font-bold text-white">{{ periodLabel }}</div>
        </div>
        <div class="bg-slate-800/80 rounded-xl p-4 border border-slate-700/60">
          <div class="text-xs text-slate-500 mb-1">总支出</div>
          <div class="text-lg font-bold text-rose-400">¥{{ (data.total_expense || 0).toLocaleString() }}</div>
        </div>
        <div class="bg-slate-800/80 rounded-xl p-4 border border-slate-700/60">
          <div class="text-xs text-slate-500 mb-1">月均支出</div>
          <div class="text-lg font-bold text-amber-400">¥{{ (data.monthly_avg_expense || 0).toLocaleString() }}</div>
        </div>
        <div class="bg-slate-800/80 rounded-xl p-4 border border-slate-700/60">
          <div class="text-xs text-slate-500 mb-1">订阅年费</div>
          <div class="text-lg font-bold text-cyan-400">¥{{ (data.subscriptions || []).reduce((s, sub) => s + (sub.annual_cost || 0), 0).toLocaleString() }}</div>
        </div>
      </div>

      <div class="grid md:grid-cols-2 gap-4">
        <div class="bg-slate-800/80 rounded-xl p-5 border border-slate-700/60">
          <h3 class="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-cyan-500"></span>
            检测到的订阅 ({{ (data.subscriptions || []).length }})
          </h3>
          <div v-if="data.subscriptions?.length" class="space-y-2 max-h-60 overflow-y-auto">
            <div v-for="sub in data.subscriptions" :key="sub.name" class="flex items-center justify-between p-2 rounded-lg bg-slate-700/30">
              <div>
                <div class="text-sm text-slate-200">{{ sub.name }}</div>
                <div class="text-xs text-slate-500">{{ sub.frequency }} · {{ sub.type }}</div>
              </div>
              <div class="text-right">
                <div class="text-sm font-medium text-cyan-400">¥{{ sub.amount }}</div>
                <div class="text-[10px] text-slate-500">年费 ¥{{ sub.annual_cost?.toLocaleString() }}</div>
              </div>
            </div>
          </div>
          <div v-else class="text-sm text-slate-500 text-center py-4">未检测到订阅</div>
        </div>

        <div class="bg-slate-800/80 rounded-xl p-5 border border-slate-700/60">
          <h3 class="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-rose-500"></span>
            异常消费 ({{ (data.anomalies || []).length }})
          </h3>
          <div v-if="data.anomalies?.length" class="space-y-2 max-h-60 overflow-y-auto">
            <div v-for="a in data.anomalies" :key="a.transaction_id || a.date" class="p-2 rounded-lg bg-slate-700/30">
              <div class="flex items-center justify-between">
                <span class="text-sm text-slate-200">{{ a.category }}</span>
                <span class="text-xs px-1.5 py-0.5 rounded-full" :class="a.severity === 'high' ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400'">
                  {{ a.severity === 'high' ? '高风险' : '中风险' }}
                </span>
              </div>
              <div class="text-xs text-slate-500 mt-1">{{ a.reason }}</div>
            </div>
          </div>
          <div v-else class="text-sm text-slate-500 text-center py-4">未检测到异常</div>
        </div>
      </div>
    </div>

    <!-- AI Content (streamed) -->
    <div v-if="aiContent" class="bg-slate-800/80 rounded-xl p-6 border border-slate-700/60 mt-6">
      <h3 class="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-indigo-500"></span>
        AI 深度分析
        <span v-if="streaming" class="inline-block w-1.5 h-4 bg-indigo-400 animate-pulse rounded-sm ml-1"></span>
      </h3>
      <div class="prose prose-invert prose-sm max-w-none agent-content" v-html="renderSafeMarkdown(aiContent)"></div>
    </div>

    <!-- Memory Panel -->
    <Transition name="fade">
      <div v-if="showMemory" class="mt-6 bg-slate-800/80 rounded-xl border border-slate-700/60 p-5">
        <h3 class="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-violet-500"></span>
          Agent 记忆 ({{ memories.length }})
        </h3>
        <div v-if="memories.length" class="space-y-2 max-h-60 overflow-y-auto">
          <div v-for="mem in memories" :key="mem.key" class="flex items-center justify-between p-2 rounded-lg bg-slate-700/30">
            <div>
              <div class="text-sm text-slate-200">{{ mem.key }}</div>
              <div class="text-xs text-slate-500">
                <span class="px-1.5 py-0.5 rounded bg-slate-600/50 text-slate-400 mr-1">{{ mem.memory_type }}</span>
                置信度: {{ (mem.confidence * 100).toFixed(0) }}%
                <span v-if="mem.source === 'inferred'" class="ml-1 text-amber-400">推断</span>
                <span v-else class="ml-1 text-emerald-400">显式</span>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-slate-400 max-w-[200px] truncate">{{ JSON.stringify(mem.value) }}</span>
              <button @click="deleteMemory(mem.key)" class="p-1 rounded hover:bg-red-500/20 text-slate-500 hover:text-red-400 transition-colors">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>
        <div v-else class="text-sm text-slate-500 text-center py-4">暂无记忆数据</div>
      </div>
    </Transition>

    <!-- Agent Logs -->
    <div class="mt-6">
      <button @click="toggleLogs" class="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200 transition-colors">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
        {{ showLogs ? '收起日志' : '查看 Agent 执行日志' }}
      </button>

      <Transition name="fade">
        <div v-if="showLogs" class="mt-3 bg-slate-800/80 rounded-xl border border-slate-700/60 overflow-hidden">
          <div class="max-h-80 overflow-y-auto">
            <table class="w-full text-sm">
              <thead class="sticky top-0 bg-slate-800">
                <tr class="text-xs text-slate-500 border-b border-slate-700/50">
                  <th class="text-left px-4 py-2">时间</th>
                  <th class="text-left px-4 py-2">Agent</th>
                  <th class="text-left px-4 py-2">状态</th>
                  <th class="text-left px-4 py-2">耗时</th>
                  <th class="text-left px-4 py-2">Request ID</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(log, i) in logs" :key="i" class="border-b border-slate-700/30 hover:bg-slate-700/20">
                  <td class="px-4 py-2 text-slate-400 text-xs">{{ new Date(log.timestamp).toLocaleTimeString() }}</td>
                  <td class="px-4 py-2 text-slate-200 font-medium">{{ log.agent }}</td>
                  <td class="px-4 py-2">
                    <span :class="log.success ? 'text-emerald-400' : 'text-red-400'" class="text-xs">
                      {{ log.success ? 'OK' : 'FAIL' }}
                    </span>
                  </td>
                  <td class="px-4 py-2 text-slate-400 text-xs">{{ log.duration_ms?.toFixed(0) }}ms</td>
                  <td class="px-4 py-2 text-slate-500 text-xs font-mono">{{ log.request_id }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="!logs.length" class="text-center py-8 text-slate-500 text-sm">暂无日志</div>
          </div>
        </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease, max-height 0.3s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.agent-content :deep(h1) { font-size: 1.25rem; font-weight: 700; color: #e2e8f0; margin: 1rem 0 0.5rem; }
.agent-content :deep(h2) { font-size: 1.125rem; font-weight: 600; color: #e2e8f0; margin: 1rem 0 0.5rem; }
.agent-content :deep(h3) { font-size: 1rem; font-weight: 600; color: #cbd5e1; margin: 0.75rem 0 0.375rem; }
.agent-content :deep(p) { color: #94a3b8; line-height: 1.7; margin: 0.5rem 0; }
.agent-content :deep(ul), .agent-content :deep(ol) { color: #94a3b8; padding-left: 1.5rem; margin: 0.5rem 0; }
.agent-content :deep(li) { margin: 0.25rem 0; }
.agent-content :deep(strong) { color: #e2e8f0; }
.agent-content :deep(code) { background: #1e293b; padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-size: 0.875rem; color: #a5b4fc; }
.agent-content :deep(blockquote) { border-left: 3px solid #6366f1; padding-left: 1rem; color: #94a3b8; margin: 0.75rem 0; }
.agent-content :deep(table) { width: 100%; border-collapse: collapse; margin: 0.75rem 0; }
.agent-content :deep(th), .agent-content :deep(td) { border: 1px solid #334155; padding: 0.5rem; text-align: left; font-size: 0.875rem; }
.agent-content :deep(th) { background: #1e293b; color: #cbd5e1; font-weight: 600; }
.agent-content :deep(td) { color: #94a3b8; }
</style>
