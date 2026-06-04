<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import api from '@/utils/api'

const router = useRouter()
const userStore = useUserStore()

const usage = ref(null)
const plan = ref(null)
const subscription = ref(null)
const history = ref([])
const loading = ref(true)
const resetDate = ref('')

const fetchUsage = async () => {
  try {
    const { data } = await api.get('/billing/usage')
    usage.value = data.usage
    plan.value = data.plan
    subscription.value = data.subscription
    resetDate.value = data.reset_date
  } catch (e) {
    console.error('Failed to fetch usage:', e)
  }
}

const fetchHistory = async () => {
  try {
    const { data } = await api.get('/billing/usage/history')
    history.value = data.history
  } catch (e) {
    console.error('Failed to fetch history:', e)
  }
}

onMounted(async () => {
  await Promise.all([fetchUsage(), fetchHistory()])
  loading.value = false
})

const callsPercent = computed(() => {
  if (!usage.value) return 0
  return Math.min(100, usage.value.calls_pct)
})

const tokensPercent = computed(() => {
  if (!usage.value) return 0
  return Math.min(100, usage.value.tokens_pct)
})

const daysUntilReset = computed(() => {
  if (!resetDate.value) return 0
  const reset = new Date(resetDate.value)
  const now = new Date()
  return Math.ceil((reset - now) / (1000 * 60 * 60 * 24))
})

const getProgressColor = (percent) => {
  if (percent >= 90) return 'text-red-500'
  if (percent >= 70) return 'text-yellow-500'
  return 'text-green-500'
}

const getProgressBg = (percent) => {
  if (percent >= 90) return 'bg-red-500'
  if (percent >= 70) return 'bg-yellow-500'
  return 'bg-green-500'
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-surface-900 dark:text-white">用量统计</h1>
        <p class="text-surface-500 dark:text-surface-400 mt-1">查看本月 AI 功能使用情况</p>
      </div>
      <button
        @click="router.push('/pricing')"
        class="px-4 py-2 rounded-xl bg-gradient-to-r from-brand-500 to-violet-500 text-white font-medium shadow-lg shadow-brand-500/25 hover:shadow-xl transition-all duration-200"
      >
        {{ plan?.name === 'pro' ? '管理订阅' : '升级套餐' }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-20">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-500"></div>
    </div>

    <template v-else>
      <!-- Plan Card -->
      <div class="bg-white dark:bg-surface-800 rounded-2xl border border-surface-200 dark:border-surface-700 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-surface-500 dark:text-surface-400">当前套餐</p>
            <h3 class="text-2xl font-bold text-surface-900 dark:text-white mt-1">
              {{ plan?.display_name || '免费版' }}
            </h3>
          </div>
          <div
            class="px-4 py-2 rounded-full text-sm font-medium"
            :class="plan?.name === 'pro'
              ? 'bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400'
              : 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400'"
          >
            {{ plan?.name === 'pro' ? 'Pro' : 'Free' }}
          </div>
        </div>
        <div v-if="subscription" class="mt-4 pt-4 border-t border-surface-100 dark:border-surface-700 grid grid-cols-2 gap-4">
          <div>
            <p class="text-sm text-surface-500 dark:text-surface-400">计费周期</p>
            <p class="font-medium text-surface-900 dark:text-white">
              {{ subscription.billing_cycle === 'yearly' ? '年付' : '月付' }}
            </p>
          </div>
          <div>
            <p class="text-sm text-surface-500 dark:text-surface-400">到期时间</p>
            <p class="font-medium text-surface-900 dark:text-white">
              {{ subscription.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : '-' }}
            </p>
          </div>
        </div>
      </div>

      <!-- Usage Cards -->
      <div class="grid md:grid-cols-2 gap-6">
        <!-- AI Calls -->
        <div class="bg-white dark:bg-surface-800 rounded-2xl border border-surface-200 dark:border-surface-700 p-6">
          <div class="flex items-center justify-between mb-4">
            <h4 class="font-semibold text-surface-900 dark:text-white">AI 调用次数</h4>
            <span :class="getProgressColor(callsPercent)" class="text-sm font-medium">
              {{ callsPercent }}%
            </span>
          </div>

          <!-- Ring Chart -->
          <div class="flex justify-center my-6">
            <div class="relative w-32 h-32">
              <svg class="w-32 h-32 transform -rotate-90" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="52" fill="none" stroke-width="12"
                  class="stroke-surface-100 dark:stroke-surface-700" />
                <circle cx="60" cy="60" r="52" fill="none" stroke-width="12"
                  :class="getProgressColor(callsPercent).replace('text-', 'stroke-')"
                  stroke-linecap="round"
                  :stroke-dasharray="`${callsPercent * 3.267} 326.7`"
                  class="transition-all duration-1000 ease-out" />
              </svg>
              <div class="absolute inset-0 flex flex-col items-center justify-center">
                <span class="text-2xl font-bold text-surface-900 dark:text-white">
                  {{ usage?.calls_used || 0 }}
                </span>
                <span class="text-xs text-surface-500 dark:text-surface-400">
                  / {{ usage?.calls_limit || 0 }}
                </span>
              </div>
            </div>
          </div>

          <div class="text-center">
            <p class="text-sm text-surface-500 dark:text-surface-400">
              剩余 <span class="font-medium text-surface-900 dark:text-white">{{ usage?.calls_remaining || 0 }}</span> 次
            </p>
          </div>
        </div>

        <!-- Token Usage -->
        <div class="bg-white dark:bg-surface-800 rounded-2xl border border-surface-200 dark:border-surface-700 p-6">
          <div class="flex items-center justify-between mb-4">
            <h4 class="font-semibold text-surface-900 dark:text-white">Token 消耗</h4>
            <span :class="getProgressColor(tokensPercent)" class="text-sm font-medium">
              {{ tokensPercent }}%
            </span>
          </div>

          <!-- Ring Chart -->
          <div class="flex justify-center my-6">
            <div class="relative w-32 h-32">
              <svg class="w-32 h-32 transform -rotate-90" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="52" fill="none" stroke-width="12"
                  class="stroke-surface-100 dark:stroke-surface-700" />
                <circle cx="60" cy="60" r="52" fill="none" stroke-width="12"
                  :class="getProgressColor(tokensPercent).replace('text-', 'stroke-')"
                  stroke-linecap="round"
                  :stroke-dasharray="`${tokensPercent * 3.267} 326.7`"
                  class="transition-all duration-1000 ease-out" />
              </svg>
              <div class="absolute inset-0 flex flex-col items-center justify-center">
                <span class="text-lg font-bold text-surface-900 dark:text-white">
                  {{ usage?.tokens_used ? (usage.tokens_used / 1000).toFixed(0) : 0 }}K
                </span>
                <span class="text-xs text-surface-500 dark:text-surface-400">
                  / {{ usage?.tokens_limit ? (usage.tokens_limit / 1000).toFixed(0) : 0 }}K
                </span>
              </div>
            </div>
          </div>

          <div class="text-center">
            <p class="text-sm text-surface-500 dark:text-surface-400">
              剩余 <span class="font-medium text-surface-900 dark:text-white">{{ usage?.tokens_remaining ? (usage.tokens_remaining / 1000).toFixed(0) : 0 }}K</span> Token
            </p>
          </div>
        </div>
      </div>

      <!-- Reset Info -->
      <div class="bg-white dark:bg-surface-800 rounded-2xl border border-surface-200 dark:border-surface-700 p-6">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 rounded-xl bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center">
            <svg class="w-6 h-6 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <h4 class="font-semibold text-surface-900 dark:text-white">额度重置</h4>
            <p class="text-sm text-surface-500 dark:text-surface-400">
              额度将在 <span class="font-medium text-surface-900 dark:text-white">{{ daysUntilReset }} 天后</span> ({{ resetDate }}) 重置
            </p>
          </div>
        </div>
      </div>

      <!-- History -->
      <div v-if="history.length > 0" class="bg-white dark:bg-surface-800 rounded-2xl border border-surface-200 dark:border-surface-700 overflow-hidden">
        <div class="px-6 py-4 border-b border-surface-100 dark:border-surface-700">
          <h4 class="font-semibold text-surface-900 dark:text-white">历史用量</h4>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="bg-surface-50 dark:bg-surface-700/50">
                <th class="px-6 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">月份</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">AI 调用</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">Token 消耗</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">使用率</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-surface-100 dark:divide-surface-700">
              <tr v-for="item in history" :key="item.period" class="hover:bg-surface-50 dark:hover:bg-surface-700/50 transition-colors">
                <td class="px-6 py-4 text-sm font-medium text-surface-900 dark:text-white">{{ item.period }}</td>
                <td class="px-6 py-4 text-sm text-surface-600 dark:text-surface-400">
                  {{ item.calls_used }} / {{ item.calls_limit }}
                </td>
                <td class="px-6 py-4 text-sm text-surface-600 dark:text-surface-400">
                  {{ (item.tokens_used / 1000).toFixed(0) }}K / {{ (item.tokens_limit / 1000).toFixed(0) }}K
                </td>
                <td class="px-6 py-4">
                  <div class="w-24 h-2 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
                    <div
                      class="h-full rounded-full transition-all duration-500"
                      :class="getProgressBg(item.calls_pct)"
                      :style="{ width: `${Math.min(100, item.calls_pct)}%` }"
                    />
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
