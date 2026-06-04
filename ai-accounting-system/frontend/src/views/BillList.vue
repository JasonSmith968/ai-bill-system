<script setup>
import { ref, onMounted, computed, watch, onUnmounted } from 'vue'
import api from '@/utils/api'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()

// State
const transactions = ref([])
const categories = ref([])
const loading = ref(true)
const showModal = ref(false)
const editingTransaction = ref(null)
const showDeleteConfirm = ref(null)
const searchInput = ref('')
const refreshing = ref(false)

// Filters
const filters = ref({
  type: '',
  category_id: '',
  start_date: '',
  end_date: '',
  keyword: ''
})

// Pagination
const pagination = ref({
  page: 1,
  per_page: 15,
  total: 0,
  pages: 0
})

// Edit form
const form = ref({
  type: 'expense',
  amount: '',
  category_id: '',
  description: '',
  note: '',
  date: new Date().toISOString().split('T')[0]
})

// Auto-refresh timer
let refreshTimer = null

// Category icon map
const categoryIcons = {
  '餐饮': '🍜', '交通': '🚕', '购物': '🛒', '娱乐': '🎬',
  '住房': '🏠', '医疗': '💊', '教育': '📚', '通讯': '📱',
  '工资': '💰', '奖金': '🎁', '投资': '📈', '兼职': '💼',
  '红包': '🧧', '其他': '📋'
}

function getCategoryIcon(name) {
  if (!name) return '📋'
  for (const [key, icon] of Object.entries(categoryIcons)) {
    if (name.includes(key)) return icon
  }
  return '📋'
}

// Debounced search
let searchTimeout = null
watch(searchInput, (val) => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    filters.value.keyword = val
    pagination.value.page = 1
    loadTransactions()
  }, 400)
})

onMounted(async () => {
  await Promise.all([loadTransactions(), loadCategories()])
  // Auto-refresh every 30s
  refreshTimer = setInterval(() => {
    if (!showModal.value && !showDeleteConfirm.value) {
      silentRefresh()
    }
  }, 30000)
})

onUnmounted(() => {
  clearInterval(refreshTimer)
  clearTimeout(searchTimeout)
})

async function loadTransactions() {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      per_page: pagination.value.per_page,
      ...filters.value
    }
    // Clean empty params
    Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
    const { data } = await api.get('/transactions', { params })
    transactions.value = data.transactions
    pagination.value.total = data.total
    pagination.value.pages = data.pages
  } catch (e) {
    toast.error('加载账单失败')
  } finally {
    loading.value = false
  }
}

async function silentRefresh() {
  try {
    const params = {
      page: pagination.value.page,
      per_page: pagination.value.per_page,
      ...filters.value
    }
    Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
    const { data } = await api.get('/transactions', { params })
    transactions.value = data.transactions
    pagination.value.total = data.total
    pagination.value.pages = data.pages
  } catch (e) { /* silent */ }
}

async function manualRefresh() {
  refreshing.value = true
  await loadTransactions()
  setTimeout(() => { refreshing.value = false }, 600)
}

async function loadCategories() {
  try {
    const { data } = await api.get('/transactions/categories')
    categories.value = data.categories
  } catch (e) { /* ignore */ }
}

// --- CRUD ---
function openModal(transaction = null) {
  editingTransaction.value = transaction
  if (transaction) {
    form.value = {
      type: transaction.type,
      amount: transaction.amount,
      category_id: transaction.category_id || '',
      description: transaction.description || '',
      note: transaction.note || '',
      date: transaction.date
    }
  } else {
    form.value = {
      type: 'expense',
      amount: '',
      category_id: '',
      description: '',
      note: '',
      date: new Date().toISOString().split('T')[0]
    }
  }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingTransaction.value = null
}

async function handleSubmit() {
  if (!form.value.amount || !form.value.type) {
    toast.warning('请填写类型和金额')
    return
  }
  try {
    if (editingTransaction.value) {
      await api.put(`/transactions/${editingTransaction.value.id}`, form.value)
      toast.success('更新成功')
    } else {
      await api.post('/transactions', form.value)
      toast.success('添加成功')
    }
    closeModal()
    await loadTransactions()
  } catch (e) {
    toast.error(e.response?.data?.error || '操作失败')
  }
}

async function confirmDelete() {
  if (!showDeleteConfirm.value) return
  try {
    await api.delete(`/transactions/${showDeleteConfirm.value.id}`)
    toast.success('已删除')
    showDeleteConfirm.value = null
    await loadTransactions()
  } catch (e) {
    toast.error('删除失败')
  }
}

// --- Filters ---
const filteredCategories = computed(() =>
  categories.value.filter(c => c.type === form.value.type)
)

const filterCategories = computed(() => {
  if (!filters.value.type) return categories.value
  return categories.value.filter(c => c.type === filters.value.type)
})

const hasActiveFilters = computed(() =>
  filters.value.type || filters.value.category_id || filters.value.start_date || filters.value.end_date || filters.value.keyword
)

function clearFilters() {
  filters.value = { type: '', category_id: '', start_date: '', end_date: '', keyword: '' }
  searchInput.value = ''
  pagination.value.page = 1
  loadTransactions()
}

function applyFilter(key, val) {
  filters.value[key] = val
  pagination.value.page = 1
  loadTransactions()
}

// --- Formatters ---
function formatAmount(amount) {
  return new Intl.NumberFormat('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount)
}

function formatDate(dateStr) {
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function formatDateFull(dateStr) {
  return new Date(dateStr).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

function formatTime(dateStr) {
  const d = new Date(dateStr)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function isToday(dateStr) {
  const d = new Date(dateStr)
  const now = new Date()
  return d.toDateString() === now.toDateString()
}

function isYesterday(dateStr) {
  const d = new Date(dateStr)
  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)
  return d.toDateString() === yesterday.toDateString()
}

function dateLabel(dateStr) {
  if (isToday(dateStr)) return '今天'
  if (isYesterday(dateStr)) return '昨天'
  return formatDateFull(dateStr)
}

// Group transactions by date
const groupedTransactions = computed(() => {
  const groups = {}
  for (const t of transactions.value) {
    const key = t.date
    if (!groups[key]) groups[key] = { date: key, label: dateLabel(key), items: [] }
    groups[key].items.push(t)
  }
  return Object.values(groups).sort((a, b) => b.date.localeCompare(a.date))
})

// Summary stats
const stats = computed(() => {
  const income = transactions.value.filter(t => t.type === 'income').reduce((s, t) => s + Number(t.amount), 0)
  const expense = transactions.value.filter(t => t.type === 'expense').reduce((s, t) => s + Number(t.amount), 0)
  return { income, expense, net: income - expense }
})
</script>

<template>
  <div class="animate-fade-in space-y-5 max-w-4xl mx-auto">

    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-surface-900 dark:text-white">账单列表</h1>
        <p class="text-sm text-surface-400 dark:text-surface-500 mt-0.5">
          共 {{ pagination.total }} 条记录
          <span v-if="hasActiveFilters" class="text-brand-500">(已筛选)</span>
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="manualRefresh"
          :disabled="refreshing"
          class="p-2.5 rounded-xl bg-surface-100 dark:bg-surface-800 text-surface-500 dark:text-surface-400 hover:bg-surface-200 dark:hover:bg-surface-700 transition-all"
          :class="refreshing ? 'animate-spin' : ''"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.992 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
          </svg>
        </button>
        <button @click="openModal()" class="btn-primary flex items-center gap-2 py-2.5 px-4">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          <span class="hidden sm:inline">记一笔</span>
        </button>
      </div>
    </div>

    <!-- Quick Stats -->
    <div class="grid grid-cols-3 gap-3">
      <div class="card p-3.5 text-center">
        <p class="text-xs text-surface-400 dark:text-surface-500 mb-1">收入</p>
        <p class="text-lg font-bold text-emerald-600 dark:text-emerald-400">
          +{{ formatAmount(stats.income) }}
        </p>
      </div>
      <div class="card p-3.5 text-center">
        <p class="text-xs text-surface-400 dark:text-surface-500 mb-1">支出</p>
        <p class="text-lg font-bold text-rose-600 dark:text-rose-400">
          -{{ formatAmount(stats.expense) }}
        </p>
      </div>
      <div class="card p-3.5 text-center">
        <p class="text-xs text-surface-400 dark:text-surface-500 mb-1">净额</p>
        <p class="text-lg font-bold" :class="stats.net >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'">
          {{ stats.net >= 0 ? '+' : '' }}{{ formatAmount(stats.net) }}
        </p>
      </div>
    </div>

    <!-- Search & Filters -->
    <div class="card p-4 space-y-3">
      <!-- Search bar -->
      <div class="relative">
        <svg class="absolute left-3.5 top-1/2 -translate-y-1/2 w-4.5 h-4.5 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
        <input
          v-model="searchInput"
          type="text"
          class="w-full pl-10 pr-10 py-2.5 bg-surface-50 dark:bg-surface-700/50 border border-surface-200 dark:border-surface-600 rounded-xl text-sm text-surface-800 dark:text-surface-200 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-all"
          placeholder="搜索描述、备注、商户..."
        />
        <button
          v-if="searchInput"
          @click="searchInput = ''; filters.keyword = ''; pagination.page = 1; loadTransactions()"
          class="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 rounded-md hover:bg-surface-200 dark:hover:bg-surface-600 text-surface-400"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Filter chips -->
      <div class="flex flex-wrap items-center gap-2">
        <!-- Type filter -->
        <div class="flex rounded-lg overflow-hidden border border-surface-200 dark:border-surface-600">
          <button
            @click="applyFilter('type', '')"
            class="px-3 py-1.5 text-xs font-medium transition-colors"
            :class="filters.type === '' ? 'bg-brand-500 text-white' : 'bg-surface-50 dark:bg-surface-700 text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'"
          >全部</button>
          <button
            @click="applyFilter('type', 'expense')"
            class="px-3 py-1.5 text-xs font-medium transition-colors border-l border-surface-200 dark:border-surface-600"
            :class="filters.type === 'expense' ? 'bg-rose-500 text-white' : 'bg-surface-50 dark:bg-surface-700 text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'"
          >支出</button>
          <button
            @click="applyFilter('type', 'income')"
            class="px-3 py-1.5 text-xs font-medium transition-colors border-l border-surface-200 dark:border-surface-600"
            :class="filters.type === 'income' ? 'bg-emerald-500 text-white' : 'bg-surface-50 dark:bg-surface-700 text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'"
          >收入</button>
        </div>

        <!-- Category filter -->
        <select
          :value="filters.category_id"
          @change="applyFilter('category_id', $event.target.value)"
          class="px-3 py-1.5 text-xs bg-surface-50 dark:bg-surface-700 border border-surface-200 dark:border-surface-600 rounded-lg text-surface-600 dark:text-surface-300 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
        >
          <option value="">全部分类</option>
          <option v-for="cat in filterCategories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
        </select>

        <!-- Date filters -->
        <input
          :value="filters.start_date"
          @change="applyFilter('start_date', $event.target.value)"
          type="date"
          class="px-3 py-1.5 text-xs bg-surface-50 dark:bg-surface-700 border border-surface-200 dark:border-surface-600 rounded-lg text-surface-600 dark:text-surface-300 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
        />
        <span class="text-xs text-surface-400">至</span>
        <input
          :value="filters.end_date"
          @change="applyFilter('end_date', $event.target.value)"
          type="date"
          class="px-3 py-1.5 text-xs bg-surface-50 dark:bg-surface-700 border border-surface-200 dark:border-surface-600 rounded-lg text-surface-600 dark:text-surface-300 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
        />

        <!-- Clear -->
        <button
          v-if="hasActiveFilters"
          @click="clearFilters"
          class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-rose-500 hover:text-rose-600 bg-rose-50 dark:bg-rose-900/20 rounded-lg transition-colors"
        >
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
          清除
        </button>
      </div>
    </div>

    <!-- Loading Skeleton -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 4" :key="i" class="card p-4 animate-pulse">
        <div class="flex items-center gap-3 mb-3">
          <div class="w-10 h-10 rounded-xl bg-surface-200 dark:bg-surface-700" />
          <div class="flex-1 space-y-2">
            <div class="h-4 bg-surface-200 dark:bg-surface-700 rounded w-20" />
            <div class="h-3 bg-surface-200 dark:bg-surface-700 rounded w-32" />
          </div>
          <div class="h-6 bg-surface-200 dark:bg-surface-700 rounded w-24" />
        </div>
        <div class="flex gap-2">
          <div class="h-5 bg-surface-200 dark:bg-surface-700 rounded-full w-14" />
          <div class="h-5 bg-surface-200 dark:bg-surface-700 rounded-full w-16" />
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="transactions.length === 0" class="card py-16 text-center">
      <div class="w-20 h-20 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-surface-100 to-surface-200 dark:from-surface-700 dark:to-surface-800 flex items-center justify-center">
        <svg class="w-10 h-10 text-surface-300 dark:text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12H9.75m3 0h-3m-2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
      </div>
      <p class="text-surface-500 dark:text-surface-400 font-medium mb-1">
        {{ hasActiveFilters ? '没有找到匹配的账单' : '暂无账单记录' }}
      </p>
      <p class="text-xs text-surface-400 dark:text-surface-500 mb-5">
        {{ hasActiveFilters ? '试试调整筛选条件' : '点击下方按钮开始记账' }}
      </p>
      <button v-if="hasActiveFilters" @click="clearFilters" class="btn-secondary text-sm mr-2">清除筛选</button>
      <button @click="openModal()" class="btn-primary text-sm">记一笔</button>
    </div>

    <!-- Transaction Groups -->
    <div v-else class="space-y-4">
      <div v-for="group in groupedTransactions" :key="group.date" class="space-y-2">
        <!-- Date header -->
        <div class="flex items-center gap-3 px-1">
          <span class="text-xs font-semibold text-surface-400 dark:text-surface-500 uppercase tracking-wide">
            {{ group.label }}
          </span>
          <div class="flex-1 h-px bg-surface-100 dark:bg-surface-700/50" />
          <span class="text-xs text-surface-400 dark:text-surface-500">
            {{ group.items.length }}笔
          </span>
        </div>

        <!-- Cards -->
        <div class="space-y-2">
          <div
            v-for="item in group.items"
            :key="item.id"
            class="card group hover:shadow-lg dark:hover:shadow-brand-500/5 transition-all duration-200 cursor-pointer"
            @click="openModal(item)"
          >
            <div class="p-4">
              <div class="flex items-start gap-3.5">
                <!-- Category icon -->
                <div
                  class="w-11 h-11 rounded-xl flex items-center justify-center text-lg flex-shrink-0 transition-transform group-hover:scale-105"
                  :class="item.type === 'income'
                    ? 'bg-emerald-50 dark:bg-emerald-900/20'
                    : 'bg-rose-50 dark:bg-rose-900/20'"
                >
                  {{ getCategoryIcon(item.category?.name) }}
                </div>

                <!-- Info -->
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 mb-0.5">
                    <span class="font-semibold text-surface-900 dark:text-white text-sm truncate">
                      {{ item.category?.name || '未分类' }}
                    </span>
                    <span
                      v-if="item.ai_generated"
                      class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400"
                    >
                      <svg class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                      </svg>
                      AI
                    </span>
                  </div>
                  <p class="text-xs text-surface-400 dark:text-surface-500 truncate">
                    <template v-if="item.merchant">{{ item.merchant }} &middot; </template>
                    {{ item.description || item.note || '无描述' }}
                  </p>
                </div>

                <!-- Amount -->
                <div class="text-right flex-shrink-0">
                  <p
                    class="font-bold text-base"
                    :class="item.type === 'income' ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'"
                  >
                    {{ item.type === 'income' ? '+' : '-' }}{{ formatAmount(item.amount) }}
                  </p>
                  <p class="text-[11px] text-surface-400 dark:text-surface-500 mt-0.5">
                    {{ formatTime(item.created_at || item.date) }}
                  </p>
                </div>
              </div>

              <!-- Tags row -->
              <div class="flex items-center gap-1.5 mt-2.5 ml-[52px]">
                <span
                  class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium"
                  :class="item.type === 'income'
                    ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400'
                    : 'bg-rose-50 dark:bg-rose-900/20 text-rose-600 dark:text-rose-400'"
                >
                  {{ item.type === 'income' ? '收入' : '支出' }}
                </span>
                <span v-if="item.merchant" class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400">
                  {{ item.merchant }}
                </span>
                <span v-if="item.receipt_image" class="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-md text-[10px] font-medium bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400">
                  <svg class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5" />
                  </svg>
                  小票
                </span>

                <!-- Actions (visible on hover) -->
                <div class="ml-auto flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    @click.stop="openModal(item)"
                    class="p-1.5 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700 text-surface-400 hover:text-brand-500 transition-colors"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                    </svg>
                  </button>
                  <button
                    @click.stop="showDeleteConfirm = item"
                    class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-surface-400 hover:text-red-500 transition-colors"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="pagination.pages > 1" class="flex items-center justify-center gap-1.5 pt-2">
        <button
          @click="pagination.page = Math.max(1, pagination.page - 1); loadTransactions()"
          :disabled="pagination.page <= 1"
          class="w-9 h-9 rounded-lg text-sm font-medium transition-all disabled:opacity-30 text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-700"
        >
          <svg class="w-4 h-4 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
        </button>
        <template v-for="page in pagination.pages" :key="page">
          <button
            v-if="page === 1 || page === pagination.pages || Math.abs(page - pagination.page) <= 1"
            @click="pagination.page = page; loadTransactions()"
            class="w-9 h-9 rounded-lg text-sm font-medium transition-all duration-200"
            :class="page === pagination.page
              ? 'bg-brand-600 text-white shadow-md shadow-brand-500/20'
              : 'text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-700'"
          >
            {{ page }}
          </button>
          <span
            v-else-if="page === pagination.page - 2 || page === pagination.page + 2"
            class="w-6 text-center text-surface-400 text-sm"
          >...</span>
        </template>
        <button
          @click="pagination.page = Math.min(pagination.pages, pagination.page + 1); loadTransactions()"
          :disabled="pagination.page >= pagination.pages"
          class="w-9 h-9 rounded-lg text-sm font-medium transition-all disabled:opacity-30 text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-700"
        >
          <svg class="w-4 h-4 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Edit Modal -->
    <Transition name="fade">
      <div v-if="showModal" class="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
        <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" @click="closeModal" />
        <Transition name="slide-up" appear>
          <div class="relative w-full sm:max-w-lg bg-white dark:bg-surface-800 sm:rounded-2xl rounded-t-2xl shadow-2xl border border-surface-200 dark:border-surface-700 max-h-[90vh] overflow-y-auto">
            <!-- Header -->
            <div class="sticky top-0 bg-white dark:bg-surface-800 z-10 flex items-center justify-between p-5 pb-3 border-b border-surface-100 dark:border-surface-700">
              <h2 class="text-lg font-bold text-surface-900 dark:text-white">
                {{ editingTransaction ? '编辑账单' : '新增账单' }}
              </h2>
              <button @click="closeModal" class="p-2 rounded-xl hover:bg-surface-100 dark:hover:bg-surface-700 text-surface-400 transition-colors">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form @submit.prevent="handleSubmit" class="p-5 pt-4 space-y-4">
              <!-- Type Toggle -->
              <div class="flex gap-2 p-1 bg-surface-100 dark:bg-surface-700 rounded-xl">
                <button
                  type="button"
                  @click="form.type = 'expense'"
                  class="flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200"
                  :class="form.type === 'expense'
                    ? 'bg-white dark:bg-surface-600 text-rose-600 dark:text-rose-400 shadow-sm'
                    : 'text-surface-400 hover:text-surface-600 dark:hover:text-surface-300'"
                >
                  支出
                </button>
                <button
                  type="button"
                  @click="form.type = 'income'"
                  class="flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200"
                  :class="form.type === 'income'
                    ? 'bg-white dark:bg-surface-600 text-emerald-600 dark:text-emerald-400 shadow-sm'
                    : 'text-surface-400 hover:text-surface-600 dark:hover:text-surface-300'"
                >
                  收入
                </button>
              </div>

              <!-- Amount -->
              <div>
                <label class="text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5 block">金额</label>
                <div class="relative">
                  <span class="absolute left-4 top-1/2 -translate-y-1/2 text-surface-400 font-bold text-lg">¥</span>
                  <input
                    v-model="form.amount"
                    type="number"
                    step="0.01"
                    min="0"
                    class="w-full pl-10 pr-4 py-3 bg-surface-50 dark:bg-surface-700/50 border border-surface-200 dark:border-surface-600 rounded-xl text-2xl font-bold text-surface-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-all"
                    placeholder="0.00"
                    autofocus
                  />
                </div>
              </div>

              <!-- Category -->
              <div>
                <label class="text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5 block">分类</label>
                <select
                  v-model="form.category_id"
                  class="w-full px-4 py-2.5 bg-surface-50 dark:bg-surface-700/50 border border-surface-200 dark:border-surface-600 rounded-xl text-sm text-surface-800 dark:text-surface-200 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-all"
                >
                  <option value="">选择分类</option>
                  <option v-for="cat in filteredCategories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
                </select>
              </div>

              <!-- Date -->
              <div>
                <label class="text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5 block">日期</label>
                <input
                  v-model="form.date"
                  type="date"
                  class="w-full px-4 py-2.5 bg-surface-50 dark:bg-surface-700/50 border border-surface-200 dark:border-surface-600 rounded-xl text-sm text-surface-800 dark:text-surface-200 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-all"
                />
              </div>

              <!-- Description -->
              <div>
                <label class="text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5 block">描述</label>
                <input
                  v-model="form.description"
                  type="text"
                  class="w-full px-4 py-2.5 bg-surface-50 dark:bg-surface-700/50 border border-surface-200 dark:border-surface-600 rounded-xl text-sm text-surface-800 dark:text-surface-200 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-all"
                  placeholder="可选描述"
                />
              </div>

              <!-- Note -->
              <div>
                <label class="text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5 block">备注</label>
                <textarea
                  v-model="form.note"
                  rows="2"
                  class="w-full px-4 py-2.5 bg-surface-50 dark:bg-surface-700/50 border border-surface-200 dark:border-surface-600 rounded-xl text-sm text-surface-800 dark:text-surface-200 placeholder-surface-400 resize-none focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-all"
                  placeholder="可选备注"
                />
              </div>

              <!-- Actions -->
              <div class="flex gap-3 pt-2 pb-1">
                <button type="submit" class="flex-1 btn-primary py-3 text-sm font-semibold">
                  {{ editingTransaction ? '保存修改' : '确认添加' }}
                </button>
                <button type="button" @click="closeModal" class="flex-1 btn-secondary py-3 text-sm font-semibold">
                  取消
                </button>
              </div>
            </form>
          </div>
        </Transition>
      </div>
    </Transition>

    <!-- Delete Confirm -->
    <Transition name="fade">
      <div v-if="showDeleteConfirm" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" @click="showDeleteConfirm = null" />
        <Transition name="scale" appear>
          <div class="relative w-full max-w-sm bg-white dark:bg-surface-800 rounded-2xl shadow-2xl border border-surface-200 dark:border-surface-700 p-6 text-center">
            <div class="w-14 h-14 mx-auto mb-4 rounded-2xl bg-red-50 dark:bg-red-900/20 flex items-center justify-center">
              <svg class="w-7 h-7 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
              </svg>
            </div>
            <h3 class="text-lg font-bold text-surface-900 dark:text-white mb-1">确认删除</h3>
            <p class="text-sm text-surface-500 dark:text-surface-400 mb-1">
              {{ showDeleteConfirm.category?.name || '未分类' }}
              &middot;
              <span :class="showDeleteConfirm.type === 'income' ? 'text-emerald-500' : 'text-rose-500'">
                {{ showDeleteConfirm.type === 'income' ? '+' : '-' }}{{ formatAmount(showDeleteConfirm.amount) }}
              </span>
            </p>
            <p class="text-xs text-surface-400 dark:text-surface-500 mb-5">此操作不可撤销</p>
            <div class="flex gap-3">
              <button @click="showDeleteConfirm = null" class="flex-1 btn-secondary py-2.5 text-sm">
                取消
              </button>
              <button @click="confirmDelete" class="flex-1 py-2.5 text-sm font-semibold text-white bg-red-500 hover:bg-red-600 rounded-xl transition-colors">
                确认删除
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.fade-enter-active { transition: opacity 0.2s ease; }
.fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.scale-enter-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.scale-leave-active { transition: all 0.15s ease; }
.scale-enter-from, .scale-leave-to { opacity: 0; transform: scale(0.95); }

.slide-up-enter-active { transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1); }
.slide-up-leave-active { transition: all 0.2s ease; }
.slide-up-enter-from { opacity: 0; transform: translateY(40px); }
.slide-up-leave-to { opacity: 0; transform: translateY(20px); }
</style>
