<script setup>
import { ref, nextTick, onMounted, computed } from 'vue'
import { renderSafeMarkdown } from '@/utils/safeMarkdown'
import api from '@/utils/api'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()

const messages = ref([])
const loading = ref(false)
const streamText = ref('')
const streamDone = ref(true)
const chatContainer = ref(null)

onMounted(() => {
  messages.value.push({
    role: 'assistant',
    content: '你好！我是你的 **AI 财务顾问**。我可以帮你分析消费习惯、发现超支问题、提供节省建议。\n\n点击下方按钮，我将为你生成本月的财务分析报告。',
    isWelcome: true
  })
})

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTo({
        top: chatContainer.value.scrollHeight,
        behavior: 'smooth'
      })
    }
  })
}

async function generateAnalysis() {
  if (loading.value) return

  loading.value = true
  streamDone.value = false
  streamText.value = ''

  // Add user message
  messages.value.push({
    role: 'user',
    content: '请帮我分析本月的财务状况'
  })
  scrollToBottom()

  try {
    const { data } = await api.post('/ai/analyze')

    // Simulate streaming effect
    const fullText = data.content
    const chunkSize = 3
    let idx = 0

    await new Promise(resolve => {
      const timer = setInterval(() => {
        if (idx < fullText.length) {
          streamText.value += fullText.slice(idx, idx + chunkSize)
          idx += chunkSize
          scrollToBottom()
        } else {
          clearInterval(timer)
          streamText.value = ''
          messages.value.push({
            role: 'assistant',
            content: fullText,
            summary: data.summary,
            timestamp: new Date().toISOString()
          })
          streamDone.value = true
          scrollToBottom()
          resolve()
        }
      }, 15)
    })

    toast.success('分析报告已生成')
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content: '抱歉，分析过程中出现了错误。请稍后重试。',
      isError: true
    })
    toast.error(e.response?.data?.error || '分析失败')
    streamDone.value = true
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function clearChat() {
  messages.value = [{
    role: 'assistant',
    content: '对话已清空。点击下方按钮，我可以为你重新生成财务分析报告。',
    isWelcome: true
  }]
  streamText.value = ''
  streamDone.value = true
}

function renderMarkdown(text) {
  return renderSafeMarkdown(text || '')
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const canGenerate = computed(() => !loading.value && streamDone.value)
</script>

<template>
  <div class="animate-fade-in h-[calc(100vh-7rem)] sm:h-[calc(100vh-5rem)] flex flex-col max-w-3xl mx-auto">

    <!-- Header -->
    <div class="flex items-center justify-between pb-4 flex-shrink-0">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-brand-500 flex items-center justify-center shadow-lg shadow-violet-500/20">
          <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
          </svg>
        </div>
        <div>
          <h1 class="text-lg font-bold text-surface-900 dark:text-white">AI 财务顾问</h1>
          <p class="text-xs text-surface-400 dark:text-surface-500">Powered by DeepSeek</p>
        </div>
      </div>
      <button
        @click="clearChat"
        class="p-2 rounded-xl text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
        title="清空对话"
      >
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.992 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
        </svg>
      </button>
    </div>

    <!-- Chat Area -->
    <div
      ref="chatContainer"
      class="flex-1 overflow-y-auto space-y-5 pb-4 scrollbar-thin"
    >
      <!-- Messages -->
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="flex gap-3"
        :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
      >
        <!-- Assistant avatar -->
        <div v-if="msg.role === 'assistant'" class="flex-shrink-0 mt-1">
          <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-brand-500 flex items-center justify-center">
            <svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          </div>
        </div>

        <!-- Message bubble -->
        <div
          class="max-w-[85%] sm:max-w-[80%]"
          :class="msg.role === 'user' ? 'order-1' : 'order-2'"
        >
          <!-- User message -->
          <div
            v-if="msg.role === 'user'"
            class="px-4 py-2.5 rounded-2xl rounded-tr-md bg-brand-500 text-white text-sm"
          >
            {{ msg.content }}
          </div>

          <!-- Assistant message -->
          <div
            v-else
            class="rounded-2xl rounded-tl-md overflow-hidden"
            :class="msg.isError
              ? 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
              : 'bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 shadow-sm'"
          >
            <div class="px-4 py-3">
              <div
                class="prose prose-sm dark:prose-invert max-w-none
                  prose-headings:text-surface-900 dark:proheadings:text-white
                  prose-h3:text-base prose-h3:font-semibold prose-h3:mb-2 prose-h3:mt-4 prose-h3:first:mt-0
                  prose-p:text-surface-600 dark:prose-p:text-surface-300 prose-p:leading-relaxed
                  prose-strong:text-surface-800 dark:prose-strong:text-surface-100
                  prose-ul:my-2 prose-li:my-0.5 prose-li:text-surface-600 dark:prose-li:text-surface-300
                  prose-blockquote:border-brand-500 prose-blockquote:bg-brand-50/50 dark:prose-blockquote:bg-brand-900/10
                  prose-blockquote:rounded-r-lg prose-blockquote:py-1 prose-blockquote:my-3
                  prose-code:text-brand-600 dark:prose-code:text-brand-400 prose-code:bg-brand-50 dark:prose-code:bg-brand-900/20 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs
                  prose-hr:my-4 prose-hr:border-surface-200 dark:prose-hr:border-surface-700"
                v-html="renderMarkdown(msg.content)"
              />

              <!-- Summary stats (if available) -->
              <div v-if="msg.summary" class="mt-4 pt-3 border-t border-surface-100 dark:border-surface-700">
                <div class="grid grid-cols-3 gap-2">
                  <div class="text-center p-2 rounded-lg bg-emerald-50 dark:bg-emerald-900/10">
                    <p class="text-[10px] text-emerald-600 dark:text-emerald-400 mb-0.5">本月收入</p>
                    <p class="text-xs font-bold text-emerald-700 dark:text-emerald-300">¥{{ Number(msg.summary.month_income).toLocaleString() }}</p>
                  </div>
                  <div class="text-center p-2 rounded-lg bg-rose-50 dark:bg-rose-900/10">
                    <p class="text-[10px] text-rose-600 dark:text-rose-400 mb-0.5">本月支出</p>
                    <p class="text-xs font-bold text-rose-700 dark:text-rose-300">¥{{ Number(msg.summary.month_expense).toLocaleString() }}</p>
                  </div>
                  <div class="text-center p-2 rounded-lg" :class="msg.summary.month_balance >= 0 ? 'bg-blue-50 dark:bg-blue-900/10' : 'bg-amber-50 dark:bg-amber-900/10'">
                    <p class="text-[10px] mb-0.5" :class="msg.summary.month_balance >= 0 ? 'text-blue-600 dark:text-blue-400' : 'text-amber-600 dark:text-amber-400'">结余</p>
                    <p class="text-xs font-bold" :class="msg.summary.month_balance >= 0 ? 'text-blue-700 dark:text-blue-300' : 'text-amber-700 dark:text-amber-300'">
                      {{ msg.summary.month_balance >= 0 ? '+' : '' }}¥{{ Number(msg.summary.month_balance).toLocaleString() }}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <!-- Timestamp -->
            <div v-if="msg.timestamp" class="px-4 py-1.5 bg-surface-50 dark:bg-surface-800/50 border-t border-surface-100 dark:border-surface-700/50">
              <p class="text-[10px] text-surface-400">{{ formatTime(msg.timestamp) }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Streaming indicator -->
      <div v-if="!streamDone && streamText" class="flex gap-3">
        <div class="flex-shrink-0 mt-1">
          <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-brand-500 flex items-center justify-center animate-pulse">
            <svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          </div>
        </div>
        <div class="max-w-[80%]">
          <div class="rounded-2xl rounded-tl-md bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 shadow-sm px-4 py-3">
            <div
              class="prose prose-sm dark:prose-invert max-w-none
                prose-h3:text-base prose-h3:font-semibold prose-h3:mb-2 prose-h3:mt-4 prose-h3:first:mt-0
                prose-p:text-surface-600 dark:prose-p:text-surface-300 prose-p:leading-relaxed
                prose-strong:text-surface-800 dark:prose-strong:text-surface-100
                prose-ul:my-2 prose-li:my-0.5 prose-li:text-surface-600 dark:prose-li:text-surface-300
                prose-blockquote:border-brand-500 prose-blockquote:rounded-r-lg prose-blockquote:py-1 prose-blockquote:my-3"
              v-html="renderMarkdown(streamText)"
            />
            <span class="inline-block w-1.5 h-4 bg-brand-500 animate-blink ml-0.5 align-middle rounded-sm"></span>
          </div>
        </div>
      </div>

      <!-- Loading state -->
      <div v-if="loading && !streamText" class="flex gap-3">
        <div class="flex-shrink-0 mt-1">
          <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-brand-500 flex items-center justify-center">
            <svg class="w-4 h-4 text-white animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
            </svg>
          </div>
        </div>
        <div class="max-w-[80%]">
          <div class="rounded-2xl rounded-tl-md bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 shadow-sm px-4 py-3">
            <div class="flex items-center gap-2">
              <div class="flex gap-1">
                <span class="w-2 h-2 bg-surface-300 dark:bg-surface-600 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
                <span class="w-2 h-2 bg-surface-300 dark:bg-surface-600 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
                <span class="w-2 h-2 bg-surface-300 dark:bg-surface-600 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
              </div>
              <span class="text-xs text-surface-400">正在分析您的财务数据...</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Action Bar -->
    <div class="flex-shrink-0 pt-3 border-t border-surface-100 dark:border-surface-800">
      <div class="flex items-center gap-3">
        <button
          @click="generateAnalysis"
          :disabled="!canGenerate"
          class="flex-1 flex items-center justify-center gap-2 py-3 px-5 rounded-xl font-medium text-sm transition-all duration-200"
          :class="canGenerate
            ? 'bg-gradient-to-r from-violet-500 to-brand-500 hover:from-violet-600 hover:to-brand-600 text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 hover:-translate-y-0.5'
            : 'bg-surface-100 dark:bg-surface-800 text-surface-400 cursor-not-allowed'"
        >
          <svg v-if="!loading" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
          </svg>
          <svg v-else class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
          </svg>
          {{ loading ? '分析中...' : '生成财务分析报告' }}
        </button>
      </div>
      <p class="text-center text-[10px] text-surface-400 dark:text-surface-500 mt-2">
        AI 分析基于您本月的记账数据，仅供参考
      </p>
    </div>
  </div>
</template>

<style scoped>
.scrollbar-thin::-webkit-scrollbar {
  width: 4px;
}
.scrollbar-thin::-webkit-scrollbar-track {
  background: transparent;
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background: rgba(100, 116, 139, 0.2);
  border-radius: 4px;
}
.scrollbar-thin::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 116, 139, 0.4);
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
.animate-blink {
  animation: blink 0.8s step-end infinite;
}
</style>
