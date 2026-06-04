<script setup>
import { ref, onMounted } from 'vue'
import api from '@/utils/api'
import { useToastStore } from '@/stores/toast'
import { formatCurrency } from '@/utils/format'
import ReceiptUpload from '@/components/ReceiptUpload.vue'

const toast = useToastStore()

const inputText = ref('')
const loading = ref(false)
const parsedResult = ref(null)
const showConfirm = ref(false)
const savedTransaction = ref(null)
const activeTab = ref('text') // 'text' or 'receipt'
const ocrAvailable = ref(false)
const ocrEngine = ref('')
const receiptUploadRef = ref(null)
const ocrResult = ref(null)

const tips = [
  { icon: '💬', text: '输入一句话描述收支，如「午饭花了25元」' },
  { icon: '🤖', text: 'AI 自动识别收入/支出、金额和分类' },
  { icon: '📸', text: '上传小票图片，OCR 自动识别' },
  { icon: '⚡', text: '点击「直接记账」一步完成，更快捷' },
]

const examples = [
  { text: '今天午饭花了25块钱', emoji: '🍜' },
  { text: '打车去公司花了15元', emoji: '🚕' },
  { text: '发工资了8000元', emoji: '💰' },
  { text: '买了一件衣服299元', emoji: '👗' },
  { text: '收到红包188元', emoji: '🧧' },
  { text: '充话费50元', emoji: '📱' },
  { text: '看电影花了80元', emoji: '🎬' },
  { text: '做兼职赚了500元', emoji: '💼' },
]

onMounted(async () => {
  try {
    const { data } = await api.get('/ai/ocr-status')
    ocrAvailable.value = data.available
    ocrEngine.value = data.engine
  } catch (e) {
    ocrAvailable.value = false
  }
})

function useExample(text) {
  inputText.value = text
}

async function handleParse() {
  if (!inputText.value.trim()) return
  loading.value = true
  parsedResult.value = null
  ocrResult.value = null
  try {
    const response = await api.post('/ai/parse', { text: inputText.value })
    parsedResult.value = response.data
    showConfirm.value = true
  } catch (error) {
    toast.error(error.response?.data?.error || 'AI解析失败，请重试')
  } finally {
    loading.value = false
  }
}

async function handleReceiptUpload(file) {
  if (!file) return

  console.log('upload start', file.name, file.size)
  loading.value = true
  parsedResult.value = null
  ocrResult.value = null

  const formData = new FormData()
  formData.append('image', file)

  try {
    const response = await api.post('/ai/receipt', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })

    console.log('ocr response', response.data)
    const data = response.data

    ocrResult.value = {
      engine: data.ocr_engine,
      lineCount: data.line_count,
      receiptInfo: data.receipt_info,
    }

    parsedResult.value = {
      parsed: data.parsed,
      category_id: data.category_id,
      original_text: data.original_text,
      receipt_image: data.receipt_image,
    }

    showConfirm.value = true
    toast.success('小票识别成功！请确认信息')
  } catch (error) {
    console.error('ocr error', error)
    const msg = error.response?.data?.error || '小票识别失败，请重试'
    toast.error(msg)
  } finally {
    loading.value = false
  }
}

async function handleConfirm() {
  if (!parsedResult.value) return
  loading.value = true
  try {
    const data = {
      ...parsedResult.value.parsed,
      category_id: parsedResult.value.category_id,
      original_text: parsedResult.value.original_text,
      receipt_image: parsedResult.value.receipt_image || '',
      ocr_text: parsedResult.value.original_text || '',
      merchant: ocrResult.value?.receiptInfo?.merchant || '',
    }
    const response = await api.post('/ai/confirm', data)
    savedTransaction.value = response.data.transaction
    showConfirm.value = false
    parsedResult.value = null
    ocrResult.value = null
    inputText.value = ''
    if (receiptUploadRef.value) {
      receiptUploadRef.value.removeImage()
    }
    toast.success('记账成功！')
  } catch (error) {
    toast.error(error.response?.data?.error || '保存失败')
  } finally {
    loading.value = false
  }
}

async function handleQuickAdd() {
  if (!inputText.value.trim()) return
  loading.value = true
  try {
    const response = await api.post('/ai/quick-add', { text: inputText.value })
    savedTransaction.value = response.data.transaction
    parsedResult.value = null
    inputText.value = ''
    toast.success('记账成功！')
  } catch (error) {
    toast.error(error.response?.data?.error || 'AI记账失败')
  } finally {
    loading.value = false
  }
}

// formatCurrency 已从 @/utils/format 导入
</script>

<template>
  <div class="animate-fade-in max-w-3xl mx-auto pb-24 sm:pb-8">
    <!-- Hero Section (compact on mobile) -->
    <div class="text-center mb-4 sm:mb-8">
      <div class="inline-flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-1 sm:py-1.5 rounded-full bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400 text-xs sm:text-sm font-medium mb-2 sm:mb-4">
        <svg class="w-3.5 h-3.5 sm:w-4 sm:h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
        </svg>
        Powered by DeepSeek AI
      </div>
      <h1 class="text-2xl sm:text-3xl font-bold text-surface-900 dark:text-white mb-1 sm:mb-2">AI 智能记账</h1>
      <p class="text-surface-500 dark:text-surface-400 text-sm sm:text-base">用自然语言或小票图片，AI 自动识别并记录</p>
    </div>

    <!-- Success Toast (compact) -->
    <Transition name="slide-down">
      <div v-if="savedTransaction" class="mb-4 sm:mb-6 p-3 sm:p-4 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-xl sm:rounded-2xl">
        <div class="flex items-center gap-2 sm:gap-3">
          <div class="w-8 h-8 sm:w-10 sm:h-10 rounded-lg sm:rounded-xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center flex-shrink-0">
            <svg class="w-4 h-4 sm:w-5 sm:h-5 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <p class="font-semibold text-emerald-800 dark:text-emerald-200 text-sm sm:text-base">记账成功！</p>
            <p class="text-xs sm:text-sm text-emerald-600 dark:text-emerald-400 mt-0.5">
              {{ savedTransaction.type === 'income' ? '收入' : '支出' }}
              {{ formatCurrency(savedTransaction.amount) }}
              · {{ savedTransaction.category?.name || '未分类' }}
            </p>
          </div>
          <button @click="savedTransaction = null" class="p-1 rounded-lg hover:bg-emerald-100 dark:hover:bg-emerald-900/30 text-emerald-500 flex-shrink-0">
            <svg class="w-4 h-4 sm:w-5 sm:h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      </div>
    </Transition>

    <!-- Tab Switcher (larger touch targets) -->
    <div class="flex gap-1 p-1 bg-surface-100 dark:bg-surface-800 rounded-xl mb-4 sm:mb-6">
      <button
        @click="activeTab = 'text'"
        class="flex-1 flex items-center justify-center gap-1.5 sm:gap-2 py-2.5 sm:py-2.5 px-3 sm:px-4 rounded-lg text-sm font-medium transition-all duration-200"
        :class="activeTab === 'text'
          ? 'bg-white dark:bg-surface-700 text-brand-600 dark:text-brand-400 shadow-sm'
          : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
        </svg>
        文字记账
      </button>
      <button
        @click="activeTab = 'receipt'"
        class="flex-1 flex items-center justify-center gap-1.5 sm:gap-2 py-2.5 sm:py-2.5 px-3 sm:px-4 rounded-lg text-sm font-medium transition-all duration-200"
        :class="activeTab === 'receipt'
          ? 'bg-white dark:bg-surface-700 text-brand-600 dark:text-brand-400 shadow-sm'
          : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'"
        :disabled="!ocrAvailable"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
          <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z" />
        </svg>
        小票识别
        <span v-if="!ocrAvailable" class="text-xs text-surface-400 hidden sm:inline">(不可用)</span>
      </button>
    </div>

    <!-- Text Input Tab -->
    <div v-if="activeTab === 'text'">
      <div class="card mb-4 sm:mb-6 relative overflow-hidden">
        <div class="absolute top-0 right-0 w-48 sm:w-64 h-48 sm:h-64 bg-gradient-to-br from-violet-100/50 to-brand-100/50 dark:from-violet-900/10 dark:to-brand-900/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none" />

        <div class="relative">
          <label class="label text-sm sm:text-base mb-2 sm:mb-3">描述您的收支</label>
          <textarea
            v-model="inputText"
            class="input-field text-base sm:text-lg py-3 sm:py-4 px-4 sm:px-5 resize-none"
            rows="3"
            placeholder="例如：今天午饭花了25块钱..."
            @keyup.ctrl.enter="handleParse"
          />

          <!-- Examples (scrollable on mobile) -->
          <div class="mt-3 sm:mt-4">
            <p class="text-xs font-medium text-surface-400 dark:text-surface-500 mb-2 uppercase tracking-wider">试试这些</p>
            <div class="flex flex-wrap gap-1.5 sm:gap-2">
              <button
                v-for="ex in examples"
                :key="ex.text"
                @click="useExample(ex.text)"
                class="inline-flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs sm:text-sm bg-surface-50 dark:bg-surface-700 text-surface-600 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-600 border border-surface-200 dark:border-surface-600 transition-all duration-200"
              >
                <span>{{ ex.emoji }}</span>
                <span class="whitespace-nowrap">{{ ex.text }}</span>
              </button>
            </div>
          </div>

          <!-- Actions (stacked on very small screens) -->
          <div class="flex gap-2 sm:gap-3 mt-4 sm:mt-5">
            <button
              @click="handleParse"
              class="flex-1 btn-secondary flex items-center justify-center gap-1.5 sm:gap-2 py-2.5 sm:py-3 text-sm sm:text-base"
              :disabled="loading || !inputText.trim()"
            >
              <svg v-if="!loading" class="w-4 h-4 sm:w-5 sm:h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <svg v-else class="animate-spin w-4 h-4 sm:w-5 sm:h-5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
              {{ loading ? '解析中...' : '先解析' }}
            </button>
            <button
              @click="handleQuickAdd"
              class="flex-1 btn-primary flex items-center justify-center gap-1.5 sm:gap-2 py-2.5 sm:py-3 text-sm sm:text-base"
              :disabled="loading || !inputText.trim()"
            >
              <svg v-if="!loading" class="w-4 h-4 sm:w-5 sm:h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
              </svg>
              {{ loading ? '处理中...' : '直接记账' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Receipt Upload Tab -->
    <div v-if="activeTab === 'receipt'">
      <div class="card mb-4 sm:mb-6">
        <div class="flex items-center gap-2 sm:gap-3 mb-4 sm:mb-5">
          <div class="w-8 h-8 sm:w-10 sm:h-10 rounded-lg sm:rounded-xl bg-amber-50 dark:bg-amber-900/20 flex items-center justify-center flex-shrink-0">
            <svg class="w-4 h-4 sm:w-5 sm:h-5 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z" />
            </svg>
          </div>
          <div class="min-w-0">
            <h3 class="font-semibold text-surface-900 dark:text-white text-sm sm:text-base">小票图片识别</h3>
            <p class="text-xs sm:text-sm text-surface-500">上传小票照片，AI 自动识别金额和分类</p>
          </div>
        </div>

        <ReceiptUpload
          ref="receiptUploadRef"
          @upload="handleReceiptUpload"
        />

        <!-- OCR Result Info -->
        <div v-if="ocrResult" class="mt-4 p-4 bg-surface-50 dark:bg-surface-700/30 rounded-xl">
          <div class="flex items-center gap-2 mb-2">
            <svg class="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            <span class="text-sm font-medium text-surface-700 dark:text-surface-300">OCR 识别完成</span>
          </div>
          <div class="grid grid-cols-3 gap-3 text-xs">
            <div>
              <span class="text-surface-400">引擎</span>
              <p class="font-medium text-surface-700 dark:text-surface-300">{{ ocrResult.engine }}</p>
            </div>
            <div>
              <span class="text-surface-400">识别行数</span>
              <p class="font-medium text-surface-700 dark:text-surface-300">{{ ocrResult.lineCount }} 行</p>
            </div>
            <div>
              <span class="text-surface-400">商户</span>
              <p class="font-medium text-surface-700 dark:text-surface-300">{{ ocrResult.receiptInfo?.merchant || '未识别' }}</p>
            </div>
          </div>
        </div>

        <!-- Engine info -->
        <div class="mt-4 flex items-center gap-2 text-xs text-surface-400">
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
          </svg>
          OCR 引擎: {{ ocrEngine || '未检测到' }} · 支持 JPG/PNG/WEBP
        </div>
      </div>
    </div>

    <!-- Confirm Panel -->
    <Transition name="scale">
      <div v-if="showConfirm && parsedResult" class="card mb-4 sm:mb-6">
        <div class="flex items-center gap-2 sm:gap-3 mb-4 sm:mb-5">
          <div class="w-8 h-8 sm:w-10 sm:h-10 rounded-lg sm:rounded-xl bg-brand-50 dark:bg-brand-900/20 flex items-center justify-center flex-shrink-0">
            <svg class="w-4 h-4 sm:w-5 sm:h-5 text-brand-600 dark:text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          </div>
          <div class="min-w-0">
            <h3 class="font-semibold text-surface-900 dark:text-white text-sm sm:text-base">AI 解析结果</h3>
            <p class="text-xs sm:text-sm text-surface-500">请确认以下信息是否正确</p>
          </div>
        </div>

        <div class="space-y-0 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden mb-5">
          <div class="flex justify-between items-center px-4 py-3 bg-surface-50 dark:bg-surface-700/30">
            <span class="text-sm text-surface-500">类型</span>
            <span :class="parsedResult.parsed.type === 'income' ? 'tag-income' : 'tag-expense'">
              {{ parsedResult.parsed.type === 'income' ? '收入' : '支出' }}
            </span>
          </div>
          <div class="flex justify-between items-center px-4 py-3 border-t border-surface-100 dark:border-surface-700/50">
            <span class="text-sm text-surface-500">金额</span>
            <span class="font-semibold text-surface-900 dark:text-white">{{ formatCurrency(parsedResult.parsed.amount) }}</span>
          </div>
          <div class="flex justify-between items-center px-4 py-3 bg-surface-50 dark:bg-surface-700/30 border-t border-surface-100 dark:border-surface-700/50">
            <span class="text-sm text-surface-500">分类</span>
            <span class="font-medium text-surface-800 dark:text-surface-200">{{ parsedResult.parsed.category }}</span>
          </div>
          <div v-if="ocrResult?.receiptInfo?.merchant" class="flex justify-between items-center px-4 py-3 border-t border-surface-100 dark:border-surface-700/50">
            <span class="text-sm text-surface-500">商户</span>
            <span class="font-medium text-surface-800 dark:text-surface-200">{{ ocrResult.receiptInfo.merchant }}</span>
          </div>
          <div class="flex justify-between items-center px-4 py-3 bg-surface-50 dark:bg-surface-700/30 border-t border-surface-100 dark:border-surface-700/50">
            <span class="text-sm text-surface-500">置信度</span>
            <div class="flex items-center gap-2">
              <div class="w-16 h-1.5 bg-surface-200 dark:bg-surface-600 rounded-full overflow-hidden">
                <div class="h-full bg-brand-500 rounded-full" :style="{ width: `${parsedResult.parsed.confidence * 100}%` }" />
              </div>
              <span class="text-sm font-medium text-surface-700 dark:text-surface-300">{{ (parsedResult.parsed.confidence * 100).toFixed(0) }}%</span>
            </div>
          </div>
          <div v-if="parsedResult.parsed.description" class="flex justify-between items-center px-4 py-3 border-t border-surface-100 dark:border-surface-700/50">
            <span class="text-sm text-surface-500">描述</span>
            <span class="text-sm text-surface-700 dark:text-surface-300">{{ parsedResult.parsed.description }}</span>
          </div>
        </div>

        <!-- OCR text preview (collapsible) -->
        <details v-if="parsedResult.original_text" class="mb-5">
          <summary class="text-xs text-surface-400 cursor-pointer hover:text-surface-600 dark:hover:text-surface-300 transition-colors">
            查看 OCR 识别原文
          </summary>
          <div class="mt-2 p-3 bg-surface-50 dark:bg-surface-800 rounded-xl text-xs text-surface-600 dark:text-surface-400 whitespace-pre-wrap max-h-32 overflow-y-auto">
            {{ parsedResult.original_text }}
          </div>
        </details>

        <div class="flex gap-2 sm:gap-3">
          <button @click="handleConfirm" class="flex-1 btn-primary py-2.5 sm:py-3 text-sm sm:text-base" :disabled="loading">
            {{ loading ? '保存中...' : '确认保存' }}
          </button>
          <button @click="showConfirm = false; ocrResult = null" class="flex-1 btn-secondary py-2.5 sm:py-3 text-sm sm:text-base">
            取消
          </button>
        </div>
      </div>
    </Transition>

    <!-- Tips -->
    <div class="card">
      <h3 class="font-semibold text-surface-900 dark:text-white mb-3 sm:mb-4 flex items-center gap-2 text-sm sm:text-base">
        <svg class="w-4 h-4 sm:w-5 sm:h-5 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
        </svg>
        使用技巧
      </h3>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
        <div v-for="(tip, i) in tips" :key="i" class="flex items-start gap-2 sm:gap-3 p-2.5 sm:p-3 rounded-lg sm:rounded-xl bg-surface-50 dark:bg-surface-700/30">
          <span class="text-base sm:text-lg flex-shrink-0">{{ tip.icon }}</span>
          <span class="text-xs sm:text-sm text-surface-600 dark:text-surface-400">{{ tip.text }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.slide-down-enter-active { transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.slide-down-leave-active { transition: all 0.2s ease; }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; transform: translateY(-12px); }

.scale-enter-active { transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.scale-leave-active { transition: all 0.2s ease; }
.scale-enter-from, .scale-leave-to { opacity: 0; transform: scale(0.96); }
</style>
