<template>
  <div class="bi-dashboard p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">BI 数据中心</h1>
        <p class="text-slate-400 text-sm mt-1">全面财务分析与智能洞察</p>
      </div>
      <div class="flex items-center gap-3">
        <span v-if="lastUpdated" class="text-xs text-slate-500">
          更新于 {{ lastUpdated }}
        </span>
        <button @click="loadAll" :disabled="loading"
                class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg text-sm transition-colors disabled:opacity-50">
          <span v-if="loading">加载中...</span>
          <span v-else>刷新数据</span>
        </button>
      </div>
    </div>

    <!-- Row 1: Health Score -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-1 bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
        <h3 class="text-sm font-medium text-slate-400 mb-4">财务健康评分</h3>
        <div class="flex items-center justify-center">
          <BaseChart :option="healthGaugeOption" :loading="loading" height="220px" />
        </div>
        <div v-if="bi.health && !loading" class="mt-4 space-y-2">
          <p v-for="rec in bi.health.recommendations?.slice(0, 3)" :key="rec"
             class="text-xs text-slate-400 flex items-start gap-2">
            <span class="text-amber-400 mt-0.5">•</span>{{ rec }}
          </p>
        </div>
      </div>

      <div class="lg:col-span-2 bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
        <h3 class="text-sm font-medium text-slate-400 mb-4">月度趋势与预测</h3>
        <TrendChart
          :labels="bi.trend?.labels || []"
          :income="bi.trend?.income || []"
          :expense="bi.trend?.expense || []"
          :forecast="bi.forecast"
          :loading="loading"
          height="280px"
        />
      </div>
    </div>

    <!-- Row 2: Cash Flow + Category Composition -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
        <h3 class="text-sm font-medium text-slate-400 mb-4">现金流分析</h3>
        <CashFlowChart
          :labels="bi.cash_flow?.labels || []"
          :income="bi.cash_flow?.income || []"
          :expense="bi.cash_flow?.expense || []"
          :net="bi.cash_flow?.net || []"
          :loading="loading"
          height="300px"
        />
      </div>

      <div class="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
        <h3 class="text-sm font-medium text-slate-400 mb-4">支出分类构成</h3>
        <CategoryPie
          :categories="bi.category_composition?.categories || []"
          :total="categoryTotal"
          :loading="loading"
          height="300px"
        />
      </div>
    </div>

    <!-- Row 3: Anomaly Heatmap + Budget Gauges -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
        <h3 class="text-sm font-medium text-slate-400 mb-4">消费日历热力图</h3>
        <AnomalyHeatmap
          :data="bi.anomalies?.heatmap || []"
          :loading="loading"
          height="240px"
        />
        <div v-if="anomalyList.length" class="mt-4 space-y-2 max-h-40 overflow-y-auto">
          <div v-for="a in anomalyList" :key="a.date + a.amount"
               class="flex items-center gap-3 text-xs p-2 rounded-lg bg-slate-800/80">
            <span :class="a.severity === 'high' ? 'text-red-400' : 'text-amber-400'"
                  class="font-medium w-6 text-center">
              {{ a.severity === 'high' ? '高' : '中' }}
            </span>
            <span class="text-slate-400 w-20">{{ a.date }}</span>
            <span class="text-slate-300 flex-1">{{ a.category }}</span>
            <span class="text-slate-200 font-mono">¥{{ a.amount?.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}</span>
          </div>
        </div>
      </div>

      <div class="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
        <h3 class="text-sm font-medium text-slate-400 mb-4">预算风险监控</h3>
        <BudgetGauge
          :categories="budgetCategories"
          :loading="loading"
          height="260px"
        />
      </div>
    </div>

    <!-- Row 4: Subscriptions -->
    <div class="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-medium text-slate-400">订阅消费分析</h3>
        <span v-if="subscriptionWaste > 0" class="text-xs text-red-400 font-mono">
          年浪费: ¥{{ subscriptionWaste.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}
        </span>
      </div>
      <SubscriptionsTable
        :subscriptions="bi.subscriptions?.subscriptions || []"
        :loading="loading"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '@/utils/api'
import BaseChart from '@/components/charts/BaseChart.vue'
import TrendChart from '@/components/charts/TrendChart.vue'
import CashFlowChart from '@/components/charts/CashFlowChart.vue'
import CategoryPie from '@/components/charts/CategoryPie.vue'
import AnomalyHeatmap from '@/components/charts/AnomalyHeatmap.vue'
import BudgetGauge from '@/components/charts/BudgetGauge.vue'
import SubscriptionsTable from '@/components/charts/SubscriptionsTable.vue'

const loading = ref(true)
const bi = ref({})
const lastUpdated = ref('')
let refreshTimer = null

async function loadAll() {
  loading.value = true
  try {
    const res = await api.get('/bi/overview')
    bi.value = res.data
    lastUpdated.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch (e) {
    console.error('BI overview failed:', e)
  } finally {
    loading.value = false
  }
}

const categoryTotal = computed(() => {
  const cats = bi.value.category_composition?.categories || []
  return cats.reduce((s, c) => s + (c.amount || 0), 0)
})

const anomalyList = computed(() => {
  return (bi.value.anomalies?.anomalies || []).slice(0, 8)
})

const budgetCategories = computed(() => {
  return (bi.value.budget_risk?.categories || []).slice(0, 4)
})

const subscriptionWaste = computed(() => {
  return bi.value.subscriptions?.total_annual_waste || 0
})

const healthGaugeOption = computed(() => {
  const score = bi.value.health?.score || 0
  const level = bi.value.health?.level || '暂无数据'
  const color = score >= 80 ? '#10b981' : score >= 60 ? '#f59e0b' : score >= 40 ? '#f97316' : '#ef4444'

  return {
    series: [{
      type: 'gauge',
      startAngle: 220,
      endAngle: -40,
      min: 0,
      max: 100,
      radius: '90%',
      axisLine: {
        lineStyle: {
          width: 18,
          color: [[score / 100, color], [1, 'rgba(100,116,139,0.15)']]
        }
      },
      pointer: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      title: {
        offsetCenter: [0, '35%'],
        fontSize: 13,
        color: '#94a3b8'
      },
      detail: {
        offsetCenter: [0, '-5%'],
        fontSize: 36,
        fontWeight: 'bold',
        color: color,
        formatter: '{value}'
      },
      data: [{ value: score, name: level }]
    }]
  }
})

onMounted(() => {
  loadAll()
  refreshTimer = setInterval(loadAll, 60000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.bi-dashboard {
  max-width: 1400px;
  margin: 0 auto;
}
</style>
