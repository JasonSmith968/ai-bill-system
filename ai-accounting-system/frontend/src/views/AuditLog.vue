<script setup>
import { ref, onMounted } from 'vue'
import api from '@/utils/api'

const logs = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const pages = ref(0)

// Filters
const filters = ref({
  action: '',
  resource_type: '',
  user_id: '',
})

const actionTypes = [
  { value: '', label: '全部操作' },
  { value: 'user.login', label: '用户登录' },
  { value: 'user.login_2fa', label: '2FA 登录' },
  { value: 'user.logout_all', label: '退出所有设备' },
  { value: 'user.password_changed', label: '修改密码' },
  { value: 'user.2fa_enabled', label: '启用 2FA' },
  { value: 'user.2fa_disabled', label: '禁用 2FA' },
  { value: 'user.backup_codes_regenerated', label: '重置备用码' },
  { value: 'user.backup_code_used', label: '使用备用码' },
]

const resourceTypes = [
  { value: '', label: '全部资源' },
  { value: 'user', label: '用户' },
  { value: 'transaction', label: '交易' },
  { value: 'subscription', label: '订阅' },
  { value: 'system', label: '系统' },
]

onMounted(() => loadLogs())

async function loadLogs(p = 1) {
  loading.value = true
  try {
    const params = { page: p, per_page: 50 }
    if (filters.value.action) params.action = filters.value.action
    if (filters.value.resource_type) params.resource_type = filters.value.resource_type
    if (filters.value.user_id) params.user_id = filters.value.user_id

    const { data } = await api.get('/admin/audit-logs/', { params })
    logs.value = data.logs
    total.value = data.total
    pages.value = data.pages
    page.value = p
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  loadLogs(1)
}

function clearFilters() {
  filters.value = { action: '', resource_type: '', user_id: '' }
  loadLogs(1)
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN')
}

function actionLabel(action) {
  const found = actionTypes.find(a => a.value === action)
  return found ? found.label : action
}
</script>

<template>
  <div class="animate-fade-in space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-surface-900 dark:text-white">审计日志</h1>
      <span class="text-sm text-surface-400">共 {{ total }} 条记录</span>
    </div>

    <!-- Filters -->
    <div class="card p-4">
      <div class="flex flex-wrap gap-3 items-end">
        <div>
          <label class="label text-xs">操作类型</label>
          <select v-model="filters.action" class="input-field text-sm py-2">
            <option v-for="t in actionTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </div>
        <div>
          <label class="label text-xs">资源类型</label>
          <select v-model="filters.resource_type" class="input-field text-sm py-2">
            <option v-for="t in resourceTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </div>
        <div>
          <label class="label text-xs">用户 ID</label>
          <input v-model="filters.user_id" type="text" class="input-field text-sm py-2 w-32" placeholder="可选" />
        </div>
        <button @click="applyFilters" class="btn-primary text-sm py-2">筛选</button>
        <button @click="clearFilters" class="text-sm text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 px-3 py-2">重置</button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-16">
      <svg class="animate-spin w-8 h-8 text-brand-500" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </div>

    <!-- Empty -->
    <div v-else-if="logs.length === 0" class="card text-center py-16 text-surface-400">
      暂无审计日志
    </div>

    <!-- Table -->
    <div v-else class="card p-0 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs text-surface-400 bg-surface-50 dark:bg-surface-800/50 border-b border-surface-100 dark:border-surface-700">
              <th class="px-4 py-3 font-medium">时间</th>
              <th class="px-4 py-3 font-medium">操作</th>
              <th class="px-4 py-3 font-medium">用户 ID</th>
              <th class="px-4 py-3 font-medium">资源</th>
              <th class="px-4 py-3 font-medium">IP</th>
              <th class="px-4 py-3 font-medium">请求 ID</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="log in logs"
              :key="log.id"
              class="border-b border-surface-50 dark:border-surface-700/50 hover:bg-surface-50 dark:hover:bg-surface-800/30 transition-colors"
            >
              <td class="px-4 py-3 text-surface-600 dark:text-surface-300 whitespace-nowrap">{{ formatTime(log.created_at) }}</td>
              <td class="px-4 py-3">
                <span class="px-2 py-1 text-xs rounded-full bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400 font-medium">
                  {{ actionLabel(log.action) }}
                </span>
              </td>
              <td class="px-4 py-3 text-surface-500 dark:text-surface-400 font-mono text-xs">{{ log.user_id || '-' }}</td>
              <td class="px-4 py-3 text-surface-500 dark:text-surface-400 text-xs">
                {{ log.resource_type }}{{ log.resource_id ? `#${log.resource_id}` : '' }}
              </td>
              <td class="px-4 py-3 text-surface-500 dark:text-surface-400 font-mono text-xs">{{ log.ip_address || '-' }}</td>
              <td class="px-4 py-3 text-surface-400 font-mono text-xs">{{ log.request_id || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div v-if="pages > 1" class="flex items-center justify-between px-4 py-3 border-t border-surface-100 dark:border-surface-700">
        <p class="text-xs text-surface-400">共 {{ total }} 条</p>
        <div class="flex gap-1">
          <button
            @click="loadLogs(page - 1)"
            :disabled="page <= 1"
            class="px-3 py-1 text-xs rounded-lg transition-colors"
            :class="page <= 1 ? 'text-surface-300 cursor-not-allowed' : 'text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-700'"
          >
            上一页
          </button>
          <span class="px-3 py-1 text-xs text-surface-400">{{ page }} / {{ pages }}</span>
          <button
            @click="loadLogs(page + 1)"
            :disabled="page >= pages"
            class="px-3 py-1 text-xs rounded-lg transition-colors"
            :class="page >= pages ? 'text-surface-300 cursor-not-allowed' : 'text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-700'"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
