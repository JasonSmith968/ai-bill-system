<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '@/utils/api'
import { formatCurrency } from '@/utils/format'

const transactions = ref([])
const categories = ref([])
const loading = ref(true)
const showModal = ref(false)
const editingTransaction = ref(null)

const filters = ref({
  type: '',
  category_id: '',
  start_date: '',
  end_date: '',
  keyword: ''
})

const pagination = ref({
  page: 1,
  per_page: 20,
  total: 0,
  pages: 0
})

const form = ref({
  type: 'expense',
  amount: '',
  category_id: '',
  description: '',
  note: '',
  date: new Date().toISOString().split('T')[0]
})

onMounted(async () => {
  await Promise.all([loadTransactions(), loadCategories()])
})

async function loadTransactions() {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      per_page: pagination.value.per_page,
      ...filters.value
    }
    const response = await api.get('/transactions', { params })
    transactions.value = response.data.transactions
    pagination.value.total = response.data.total
    pagination.value.pages = response.data.pages
  } catch (error) {
    console.error('加载交易记录失败:', error)
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  try {
    const response = await api.get('/transactions/categories')
    categories.value = response.data.categories
  } catch (error) {
    console.error('加载分类失败:', error)
  }
}

function openModal(transaction = null) {
  editingTransaction.value = transaction
  if (transaction) {
    form.value = {
      type: transaction.type,
      amount: transaction.amount,
      category_id: transaction.category_id || '',
      description: transaction.description,
      note: transaction.note,
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
    alert('请填写必要信息')
    return
  }
  try {
    if (editingTransaction.value) {
      await api.put(`/transactions/${editingTransaction.value.id}`, form.value)
    } else {
      await api.post('/transactions', form.value)
    }
    closeModal()
    await loadTransactions()
  } catch (error) {
    alert(error.response?.data?.error || '操作失败')
  }
}

async function deleteTransaction(id) {
  if (!confirm('确定要删除这条记录吗？')) return
  try {
    await api.delete(`/transactions/${id}`)
    await loadTransactions()
  } catch (error) {
    alert('删除失败')
  }
}

// formatCurrency 已从 @/utils/format 导入

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function formatDateFull(dateStr) {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const filteredCategories = computed(() => {
  return categories.value.filter(c => c.type === form.value.type)
})

const hasActiveFilters = computed(() => {
  return filters.value.type || filters.value.start_date || filters.value.end_date || filters.value.keyword
})

function clearFilters() {
  filters.value = { type: '', category_id: '', start_date: '', end_date: '', keyword: '' }
  loadTransactions()
}
</script>

<template>
  <div class="animate-fade-in space-y-4 sm:space-y-6">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
      <div>
        <h1 class="text-xl sm:text-2xl font-bold text-surface-900 dark:text-white">收支记录</h1>
        <p class="text-surface-500 dark:text-surface-400 text-xs sm:text-sm mt-0.5">共 {{ pagination.total }} 条记录</p>
      </div>
      <button @click="openModal()" class="btn-primary flex items-center justify-center gap-1.5 sm:gap-2 text-sm sm:text-base py-2 sm:py-2.5">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
        添加记录
      </button>
    </div>

    <!-- Filters -->
    <div class="card p-3 sm:p-4">
      <div class="flex flex-wrap items-center gap-2 sm:gap-3">
        <select v-model="filters.type" @change="loadTransactions" class="input-field w-auto min-w-[80px] sm:min-w-[100px] py-1.5 sm:py-2 text-sm">
          <option value="">全部类型</option>
          <option value="income">收入</option>
          <option value="expense">支出</option>
        </select>
        <input v-model="filters.start_date" type="date" class="input-field w-auto text-sm py-1.5 sm:py-2 min-w-0" @change="loadTransactions" />
        <input v-model="filters.end_date" type="date" class="input-field w-auto text-sm py-1.5 sm:py-2 min-w-0" @change="loadTransactions" />
        <div class="relative flex-1 min-w-[120px] sm:min-w-[160px]">
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
          <input v-model="filters.keyword" type="text" class="input-field pl-9 py-1.5 sm:py-2 text-sm w-full" placeholder="搜索..." @keyup.enter="loadTransactions" />
        </div>
        <button v-if="hasActiveFilters" @click="clearFilters" class="btn-ghost text-sm py-1.5 sm:py-2 whitespace-nowrap">
          清除筛选
        </button>
      </div>
    </div>

    <!-- Transaction List -->
    <div class="card overflow-hidden">
      <!-- Loading -->
      <div v-if="loading" class="p-8">
        <div class="space-y-4">
          <div v-for="i in 5" :key="i" class="flex items-center gap-4 animate-pulse">
            <div class="w-10 h-10 rounded-xl bg-surface-200 dark:bg-surface-700" />
            <div class="flex-1 space-y-2">
              <div class="h-4 bg-surface-200 dark:bg-surface-700 rounded w-24" />
              <div class="h-3 bg-surface-200 dark:bg-surface-700 rounded w-32" />
            </div>
            <div class="h-5 bg-surface-200 dark:bg-surface-700 rounded w-20" />
          </div>
        </div>
      </div>

      <!-- Empty -->
      <div v-else-if="transactions.length === 0" class="py-12 sm:py-16 text-center px-4">
        <div class="w-12 h-12 sm:w-16 sm:h-16 mx-auto mb-3 sm:mb-4 rounded-2xl bg-surface-100 dark:bg-surface-700 flex items-center justify-center max-w-[80px]">
          <svg class="w-6 h-6 sm:w-8 sm:h-8 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9zm3.75 11.625a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
          </svg>
        </div>
        <p class="text-surface-500 dark:text-surface-400 mb-3 text-sm sm:text-base">暂无交易记录</p>
        <button @click="openModal()" class="btn-primary text-sm">添加第一笔</button>
      </div>

      <!-- Desktop Table -->
      <div v-else>
        <div class="hidden md:block overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-surface-100 dark:border-surface-700/50">
                <th class="text-left py-3 px-5 text-xs font-semibold text-surface-400 dark:text-surface-500 uppercase tracking-wider">日期</th>
                <th class="text-left py-3 px-5 text-xs font-semibold text-surface-400 dark:text-surface-500 uppercase tracking-wider">类型</th>
                <th class="text-left py-3 px-5 text-xs font-semibold text-surface-400 dark:text-surface-500 uppercase tracking-wider">分类</th>
                <th class="text-left py-3 px-5 text-xs font-semibold text-surface-400 dark:text-surface-500 uppercase tracking-wider">描述</th>
                <th class="text-right py-3 px-5 text-xs font-semibold text-surface-400 dark:text-surface-500 uppercase tracking-wider">金额</th>
                <th class="text-right py-3 px-5 text-xs font-semibold text-surface-400 dark:text-surface-500 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-surface-100 dark:divide-surface-700/50">
              <tr
                v-for="item in transactions"
                :key="item.id"
                class="group hover:bg-surface-50 dark:hover:bg-surface-700/30 transition-colors"
              >
                <td class="py-3.5 px-5 text-sm text-surface-600 dark:text-surface-400">{{ formatDateFull(item.date) }}</td>
                <td class="py-3.5 px-5">
                  <span :class="item.type === 'income' ? 'tag-income' : 'tag-expense'">
                    {{ item.type === 'income' ? '收入' : '支出' }}
                  </span>
                </td>
                <td class="py-3.5 px-5 text-sm font-medium text-surface-800 dark:text-surface-200">{{ item.category?.name || '未分类' }}</td>
                <td class="py-3.5 px-5 text-sm text-surface-500 dark:text-surface-400 max-w-[200px] truncate">{{ item.description || '-' }}</td>
                <td class="py-3.5 px-5 text-sm font-semibold text-right"
                    :class="item.type === 'income' ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'">
                  {{ item.type === 'income' ? '+' : '-' }}{{ formatCurrency(item.amount) }}
                </td>
                <td class="py-3.5 px-5 text-right">
                  <div class="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button @click="openModal(item)" class="p-1.5 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600 text-surface-400 hover:text-brand-600 transition-colors">
                      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" /></svg>
                    </button>
                    <button @click="deleteTransaction(item.id)" class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-surface-400 hover:text-red-500 transition-colors">
                      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Mobile Cards -->
        <div class="md:hidden divide-y divide-surface-100 dark:divide-surface-700/50">
          <div
            v-for="item in transactions"
            :key="item.id"
            class="p-4 hover:bg-surface-50 dark:hover:bg-surface-700/30 transition-colors"
          >
            <div class="flex items-start justify-between mb-2">
              <div class="flex items-center gap-2">
                <span :class="item.type === 'income' ? 'tag-income' : 'tag-expense'">
                  {{ item.type === 'income' ? '收入' : '支出' }}
                </span>
                <span class="text-xs text-surface-400">{{ formatDate(item.date) }}</span>
              </div>
              <span class="font-semibold"
                    :class="item.type === 'income' ? 'text-emerald-600' : 'text-rose-600'">
                {{ item.type === 'income' ? '+' : '-' }}{{ formatAmount(item.amount) }}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-surface-800 dark:text-surface-200 text-sm">{{ item.category?.name || '未分类' }}</p>
                <p class="text-xs text-surface-400 mt-0.5">{{ item.description || '-' }}</p>
              </div>
              <div class="flex gap-1">
                <button @click="openModal(item)" class="p-1.5 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600 text-surface-400">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" /></svg>
                </button>
                <button @click="deleteTransaction(item.id)" class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-surface-400 hover:text-red-500">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Pagination -->
        <div v-if="pagination.pages > 1" class="flex items-center justify-center gap-2 p-4 border-t border-surface-100 dark:border-surface-700/50">
          <button
            v-for="page in pagination.pages"
            :key="page"
            @click="pagination.page = page; loadTransactions()"
            class="w-9 h-9 rounded-lg text-sm font-medium transition-all duration-200"
            :class="page === pagination.page
              ? 'bg-brand-600 text-white shadow-md shadow-brand-500/20'
              : 'text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700'"
          >
            {{ page }}
          </button>
        </div>
      </div>
    </div>

    <!-- Modal -->
    <Transition name="fade">
      <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="fixed inset-0 bg-black/40 backdrop-blur-sm" @click="closeModal" />
        <Transition name="scale" appear>
          <div class="relative bg-white dark:bg-surface-800 rounded-2xl shadow-xl w-full max-w-md p-6 border border-surface-200 dark:border-surface-700">
            <div class="flex items-center justify-between mb-6">
              <h2 class="text-lg font-bold text-surface-900 dark:text-white">
                {{ editingTransaction ? '编辑记录' : '添加记录' }}
              </h2>
              <button @click="closeModal" class="p-1.5 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700 text-surface-400">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>

            <form @submit.prevent="handleSubmit" class="space-y-4">
              <!-- Type Toggle -->
              <div class="flex gap-2 p-1 bg-surface-100 dark:bg-surface-700 rounded-xl">
                <button
                  type="button"
                  @click="form.type = 'expense'"
                  class="flex-1 py-2 rounded-lg text-sm font-medium transition-all duration-200"
                  :class="form.type === 'expense'
                    ? 'bg-white dark:bg-surface-600 text-rose-600 dark:text-rose-400 shadow-sm'
                    : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'"
                >
                  支出
                </button>
                <button
                  type="button"
                  @click="form.type = 'income'"
                  class="flex-1 py-2 rounded-lg text-sm font-medium transition-all duration-200"
                  :class="form.type === 'income'
                    ? 'bg-white dark:bg-surface-600 text-emerald-600 dark:text-emerald-400 shadow-sm'
                    : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'"
                >
                  收入
                </button>
              </div>

              <div>
                <label class="label">金额</label>
                <div class="relative">
                  <span class="absolute left-4 top-1/2 -translate-y-1/2 text-surface-400 font-medium">¥</span>
                  <input v-model="form.amount" type="number" step="0.01" class="input-field pl-8 text-lg font-semibold" placeholder="0.00" />
                </div>
              </div>

              <div>
                <label class="label">分类</label>
                <select v-model="form.category_id" class="input-field">
                  <option value="">请选择分类</option>
                  <option v-for="cat in filteredCategories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
                </select>
              </div>

              <div>
                <label class="label">日期</label>
                <input v-model="form.date" type="date" class="input-field" />
              </div>

              <div>
                <label class="label">描述</label>
                <input v-model="form.description" type="text" class="input-field" placeholder="可选" />
              </div>

              <div>
                <label class="label">备注</label>
                <textarea v-model="form.note" class="input-field resize-none" rows="2" placeholder="可选" />
              </div>

              <div class="flex gap-3 pt-2">
                <button type="submit" class="flex-1 btn-primary py-3">
                  {{ editingTransaction ? '保存修改' : '添加记录' }}
                </button>
                <button type="button" @click="closeModal" class="flex-1 btn-secondary py-3">取消</button>
              </div>
            </form>
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
</style>