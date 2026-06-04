<template>
  <div class="report-center p-6 space-y-6">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold text-slate-100">报告中心</h1>
      <p class="text-slate-400 text-sm mt-1">生成和管理财务报告</p>
    </div>

    <!-- Generate Section -->
    <div class="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
      <h3 class="text-sm font-medium text-slate-400 mb-4">生成报告</h3>
      <div class="flex flex-wrap items-end gap-4">
        <div>
          <label class="block text-xs text-slate-500 mb-1">报告类型</label>
          <select v-model="reportType"
                  class="bg-slate-700 text-slate-200 text-sm rounded-lg px-3 py-2 border border-slate-600 focus:border-blue-500 focus:outline-none">
            <option value="weekly">周报</option>
            <option value="monthly">月报</option>
            <option value="custom">自定义</option>
          </select>
        </div>
        <button @click="generateReport" :disabled="generating"
                class="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
          <span v-if="generating">生成中...</span>
          <span v-else>生成报告</span>
        </button>
      </div>
      <p v-if="generateError" class="text-red-400 text-xs mt-2">{{ generateError }}</p>
    </div>

    <!-- Task List -->
    <div class="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-medium text-slate-400">报告列表</h3>
        <button @click="loadTasks" class="text-xs text-slate-500 hover:text-slate-300 transition-colors">
          刷新
        </button>
      </div>

      <div v-if="tasksLoading" class="space-y-3">
        <div v-for="i in 3" :key="i" class="h-16 bg-slate-800 rounded-lg animate-pulse"></div>
      </div>

      <table v-else-if="tasks.length" class="w-full text-sm">
        <thead>
          <tr class="border-b border-slate-700/50">
            <th class="text-left py-2 px-3 text-slate-400 font-medium">类型</th>
            <th class="text-left py-2 px-3 text-slate-400 font-medium">任务ID</th>
            <th class="text-center py-2 px-3 text-slate-400 font-medium">状态</th>
            <th class="text-left py-2 px-3 text-slate-400 font-medium">创建时间</th>
            <th class="text-right py-2 px-3 text-slate-400 font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasks" :key="task.task_id"
              class="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
            <td class="py-2.5 px-3 text-slate-200">
              {{ reportTypeLabel(task.result?.report_type) }}
            </td>
            <td class="py-2.5 px-3 text-slate-400 font-mono text-xs">
              {{ task.task_id?.slice(0, 12) }}...
            </td>
            <td class="py-2.5 px-3 text-center">
              <span :class="statusBadgeClass(task.status)"
                    class="inline-block px-2 py-0.5 rounded-full text-xs font-medium">
                {{ statusLabel(task.status) }}
              </span>
            </td>
            <td class="py-2.5 px-3 text-slate-400 text-xs">
              {{ formatTime(task.created_at) }}
            </td>
            <td class="py-2.5 px-3 text-right">
              <div v-if="task.status === 'success' && task.result" class="flex items-center justify-end gap-2">
                <a v-if="task.result.pdf_path"
                   :href="`/api/uploads/${task.result.pdf_path}`" target="_blank"
                   class="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded text-xs transition-colors">
                  PDF
                </a>
                <a v-if="task.result.xlsx_path"
                   :href="`/api/uploads/${task.result.xlsx_path}`" target="_blank"
                   class="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded text-xs transition-colors">
                  Excel
                </a>
              </div>
              <span v-else-if="task.status === 'running'" class="text-xs text-blue-400">
                处理中...
              </span>
              <span v-else-if="task.status === 'failed'" class="text-xs text-red-400" :title="task.error">
                失败
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-else class="text-center py-12 text-slate-500 text-sm">
        暂无报告，点击上方按钮生成
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/utils/api'

const reportType = ref('monthly')
const generating = ref(false)
const generateError = ref('')
const tasks = ref([])
const tasksLoading = ref(true)
let pollTimer = null

async function generateReport() {
  generating.value = true
  generateError.value = ''
  try {
    await api.post('/bi/report/generate', { report_type: reportType.value })
    setTimeout(loadTasks, 1000)
  } catch (e) {
    generateError.value = e.response?.data?.error || '生成失败，请稍后重试'
  } finally {
    generating.value = false
  }
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    const res = await api.get('/tasks', { params: { task_type: 'report' } })
    tasks.value = res.data.tasks || res.data || []
  } catch (e) {
    console.error('Load tasks failed:', e)
  } finally {
    tasksLoading.value = false
  }
}

function reportTypeLabel(type) {
  const map = { weekly: '周报', monthly: '月报', custom: '自定义报告' }
  return map[type] || '报告'
}

function statusLabel(status) {
  const map = { pending: '等待中', running: '生成中', success: '已完成', failed: '失败' }
  return map[status] || status
}

function statusBadgeClass(status) {
  if (status === 'success') return 'bg-emerald-500/20 text-emerald-400'
  if (status === 'running') return 'bg-blue-500/20 text-blue-400'
  if (status === 'failed') return 'bg-red-500/20 text-red-400'
  return 'bg-slate-500/20 text-slate-400'
}

function formatTime(ts) {
  if (!ts) return '-'
  return new Date(ts).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// Poll for running tasks
function startPolling() {
  pollTimer = setInterval(() => {
    const hasRunning = tasks.value.some(t => t.status === 'running' || t.status === 'pending')
    if (hasRunning) loadTasks()
  }, 5000)
}

onMounted(() => {
  loadTasks()
  startPolling()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.report-center {
  max-width: 1200px;
  margin: 0 auto;
}
</style>
