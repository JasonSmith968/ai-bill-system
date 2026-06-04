<script setup>
import { ref, computed, onMounted, nextTick, watch, onUnmounted } from 'vue'
import { renderSafeMarkdown } from '@/utils/safeMarkdown'
import api from '@/utils/api'
import { useUserStore } from '@/stores/user'
import { getWSClient } from '@/utils/websocket'

const userStore = useUserStore()
const inputText = ref('')
const messages = ref([])
const streaming = ref(false)
const suggestions = ref([])
const chatContainer = ref(null)
const inputRef = ref(null)

const activeAgent = ref(null)
const wsClient = getWSClient()

const STORAGE_KEY = 'ai-chat-history'

// Load history from localStorage
function loadHistory() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      messages.value = JSON.parse(saved)
    }
  } catch {}
}

function saveHistory() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.value))
  } catch {}
}

function clearHistory() {
  messages.value = []
  activeAgent.value = null
  saveHistory()
}

// Load suggestions
async function loadSuggestions() {
  try {
    const res = await api.get('/chat/suggestions')
    suggestions.value = res.data.suggestions || []
  } catch {}
}

// Auto-scroll
function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

watch(messages, scrollToBottom, { deep: true })

// Send message — WebSocket first, SSE fallback
async function sendMessage(text) {
  const content = text || inputText.value.trim()
  if (!content || streaming.value) return

  messages.value.push({ role: 'user', content, time: new Date().toISOString() })
  inputText.value = ''
  saveHistory()

  const aiMsg = { role: 'assistant', content: '', time: new Date().toISOString(), loading: true }
  messages.value.push(aiMsg)
  streaming.value = true

  // --- WebSocket path ---
  if (wsClient.connected) {
    const unsubs = []
    unsubs.push(wsClient.on('llm_chunk', (data) => {
      aiMsg.content += data.content
      scrollToBottom()
    }))
    unsubs.push(wsClient.on('llm_done', () => {
      aiMsg.loading = false
      saveHistory()
      unsubs.forEach(fn => fn())
      streaming.value = false
      nextTick(() => inputRef.value?.focus())
    }))
    unsubs.push(wsClient.on('llm_error', (data) => {
      aiMsg.content = data.error || '处理失败'
      aiMsg.loading = false
      saveHistory()
      unsubs.forEach(fn => fn())
      streaming.value = false
      nextTick(() => inputRef.value?.focus())
    }))
    wsClient.emit('chat_message', { message: content })
    return
  }

  // --- SSE fallback ---
  try {
    const token = localStorage.getItem('token')
    const resp = await fetch('/api/agent/v2/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ message: content })
    })

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      aiMsg.content = err.error || `请求失败 (${resp.status})`
      aiMsg.loading = false
      saveHistory()
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
        if (data === '[DONE]') { aiMsg.loading = false; saveHistory(); return }
        try {
          const parsed = JSON.parse(data)
          if (parsed.type === 'route') { activeAgent.value = parsed.agent; continue }
          if (parsed.type === 'error') { aiMsg.content = parsed.payload || parsed.error || '处理失败'; aiMsg.loading = false; saveHistory(); return }
          if (parsed.content || parsed.payload) { aiMsg.content += parsed.content || parsed.payload; scrollToBottom() }
          if (parsed.error) { aiMsg.content = parsed.error; aiMsg.loading = false; saveHistory(); return }
        } catch {}
      }
    }
    aiMsg.loading = false
    saveHistory()
  } catch (e) {
    aiMsg.content = '网络错误，请检查连接后重试。'
    aiMsg.loading = false
    saveHistory()
  } finally {
    streaming.value = false
    nextTick(() => inputRef.value?.focus())
  }
}

// Copy message
function copyMessage(content) {
  navigator.clipboard.writeText(content).catch(() => {})
}

// Format time
function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

// Render markdown (sanitised)
function renderMd(text) {
  if (!text) return ''
  return renderSafeMarkdown(text)
}

// Has messages
const hasMessages = computed(() => messages.value.length > 0)

// Enter to send
function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

onMounted(() => {
  loadHistory()
  loadSuggestions()
  nextTick(() => inputRef.value?.focus())
})
</script>

<template>
  <div class="h-[calc(100vh-2rem)] md:h-screen flex flex-col bg-slate-900">
    <!-- ======== HEADER ======== -->
    <div class="flex-shrink-0 border-b border-slate-700/60 bg-slate-800/80 backdrop-blur-sm px-4 py-3">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
            <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h1 class="text-sm font-semibold text-white">AI 财务助手</h1>
              <span v-if="activeAgent && streaming" class="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 font-medium animate-pulse">
                {{ activeAgent }}
              </span>
            </div>
            <p class="text-[10px] text-indigo-400">基于您的账单数据智能分析 · Agent Router</p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button v-if="hasMessages" @click="clearHistory"
            class="p-2 rounded-lg hover:bg-slate-700/50 text-slate-400 hover:text-white transition-colors"
            title="新对话">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- ======== MESSAGES AREA ======== -->
    <div ref="chatContainer" class="flex-1 overflow-y-auto">
      <!-- Empty state -->
      <div v-if="!hasMessages" class="h-full flex flex-col items-center justify-center px-4">
        <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 border border-indigo-500/20 flex items-center justify-center mb-6">
          <svg class="w-8 h-8 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
          </svg>
        </div>
        <h2 class="text-lg font-semibold text-white mb-2">你好，{{ userStore.user?.username }}</h2>
        <p class="text-slate-400 text-sm text-center mb-8 max-w-md">我是你的 AI 财务助手，可以帮你分析消费结构、识别异常支出、提供理财建议。试试下面的问题：</p>

        <!-- Suggestion chips -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
          <button v-for="s in suggestions" :key="s" @click="sendMessage(s)"
            class="text-left p-3.5 bg-slate-800/80 border border-slate-700/60 rounded-xl text-sm text-slate-300 hover:border-indigo-500/50 hover:bg-slate-800 transition-all group">
            <div class="flex items-start gap-2">
              <svg class="w-4 h-4 text-indigo-400 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
              <span>{{ s }}</span>
            </div>
          </button>
        </div>
      </div>

      <!-- Chat messages -->
      <div v-else class="max-w-3xl mx-auto px-4 py-6 space-y-6">
        <div v-for="(msg, idx) in messages" :key="idx" class="group">
          <!-- User message -->
          <div v-if="msg.role === 'user'" class="flex justify-end mb-4">
            <div class="max-w-[80%]">
              <div class="bg-indigo-500/20 border border-indigo-500/30 rounded-2xl rounded-br-md px-4 py-3">
                <p class="text-sm text-slate-200 whitespace-pre-wrap break-words">{{ msg.content }}</p>
              </div>
              <p class="text-[10px] text-slate-500 text-right mt-1">{{ fmtTime(msg.time) }}</p>
            </div>
          </div>

          <!-- Assistant message -->
          <div v-else class="flex gap-3">
            <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center flex-shrink-0 mt-1">
              <svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
            </div>
            <div class="flex-1 min-w-0">
              <!-- Loading state -->
              <div v-if="msg.loading && !msg.content" class="flex items-center gap-2 py-3">
                <div class="flex gap-1">
                  <div class="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style="animation-delay:0ms" />
                  <div class="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style="animation-delay:150ms" />
                  <div class="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style="animation-delay:300ms" />
                </div>
                <span class="text-xs text-slate-500">正在分析您的财务数据...</span>
              </div>
              <!-- Content -->
              <div v-else>
                <div class="chat-content text-sm text-slate-300 leading-relaxed" v-html="renderMd(msg.content)" />
                <!-- Streaming cursor -->
                <span v-if="msg.loading" class="inline-block w-0.5 h-4 bg-indigo-400 animate-pulse ml-0.5 align-text-bottom" />
              </div>
              <!-- Actions -->
              <div class="flex items-center gap-2 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <span class="text-[10px] text-slate-600">{{ fmtTime(msg.time) }}</span>
                <button @click="copyMessage(msg.content)"
                  class="p-1 rounded hover:bg-slate-700/50 text-slate-500 hover:text-slate-300 transition-colors"
                  title="复制">
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ======== INPUT AREA ======== -->
    <div class="flex-shrink-0 border-t border-slate-700/60 bg-slate-800/80 backdrop-blur-sm p-4">
      <div class="max-w-3xl mx-auto">
        <!-- Quick suggestions (when has messages) -->
        <div v-if="hasMessages && suggestions.length && !streaming" class="flex gap-2 mb-3 overflow-x-auto pb-1 scrollbar-none">
          <button v-for="s in suggestions.slice(0, 4)" :key="s" @click="sendMessage(s)"
            class="flex-shrink-0 px-3 py-1.5 bg-slate-700/50 border border-slate-600/50 rounded-lg text-xs text-slate-400 hover:text-slate-200 hover:border-indigo-500/50 transition-all">
            {{ s }}
          </button>
        </div>

        <!-- Input box -->
        <div class="relative">
          <textarea ref="inputRef" v-model="inputText" @keydown="handleKeydown"
            :disabled="streaming"
            placeholder="问我任何财务相关的问题... (Enter 发送, Shift+Enter 换行)"
            rows="1"
            class="w-full bg-slate-700/50 border border-slate-600/50 rounded-xl px-4 py-3 pr-12 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-all disabled:opacity-50"
            style="min-height: 44px; max-height: 120px;"
            @input="e => { e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px' }"
          />
          <button @click="sendMessage()" :disabled="!inputText.trim() || streaming"
            class="absolute right-2 bottom-2 p-2 rounded-lg transition-all"
            :class="inputText.trim() && !streaming ? 'bg-indigo-500 text-white hover:bg-indigo-600' : 'text-slate-500'">
            <svg v-if="!streaming" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
            <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </button>
        </div>
        <p class="text-[10px] text-slate-600 mt-2 text-center">AI 财务助手 · 基于您的账单数据提供个性化分析</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Chat markdown content */
.chat-content :deep(h1) { font-size: 1.15rem; font-weight: 700; color: #e2e8f0; margin: 0.75rem 0 0.4rem; }
.chat-content :deep(h2) { font-size: 1rem; font-weight: 600; color: #e2e8f0; margin: 0.75rem 0 0.35rem; padding-bottom: 0.3rem; border-bottom: 1px solid rgba(51,65,85,0.5); }
.chat-content :deep(h3) { font-size: 0.9rem; font-weight: 600; color: #cbd5e1; margin: 0.5rem 0 0.25rem; }
.chat-content :deep(p) { margin: 0.3rem 0; }
.chat-content :deep(ul), .chat-content :deep(ol) { padding-left: 1.25rem; margin: 0.3rem 0; }
.chat-content :deep(li) { margin: 0.2rem 0; }
.chat-content :deep(strong) { color: #f1f5f9; font-weight: 600; }
.chat-content :deep(code) { background: rgba(51,65,85,0.5); padding: 0.1rem 0.35rem; border-radius: 0.25rem; font-size: 0.8rem; }
.chat-content :deep(pre) { background: rgba(15,23,42,0.6); border: 1px solid rgba(51,65,85,0.5); border-radius: 0.5rem; padding: 0.75rem; margin: 0.5rem 0; overflow-x: auto; }
.chat-content :deep(pre code) { background: transparent; padding: 0; }
.chat-content :deep(blockquote) { border-left: 3px solid #6366f1; padding-left: 0.75rem; margin: 0.5rem 0; color: #94a3b8; }
.chat-content :deep(table) { border-collapse: collapse; margin: 0.5rem 0; width: 100%; }
.chat-content :deep(th), .chat-content :deep(td) { border: 1px solid rgba(51,65,85,0.5); padding: 0.35rem 0.6rem; text-align: left; }
.chat-content :deep(th) { background: rgba(30,41,59,0.5); color: #cbd5e1; font-weight: 600; font-size: 0.8rem; }
.chat-content :deep(td) { font-size: 0.8rem; }
.chat-content :deep(hr) { border: none; border-top: 1px solid rgba(51,65,85,0.5); margin: 0.75rem 0; }

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(100,116,139,0.3); border-radius: 4px; }
.scrollbar-none::-webkit-scrollbar { display: none; }
</style>
