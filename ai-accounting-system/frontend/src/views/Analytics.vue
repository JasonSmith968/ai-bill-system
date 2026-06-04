<script setup>
import { ref, onMounted, computed, onUnmounted, shallowRef } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, LineChart, BarChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DatasetComponent, TransformComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import api from '@/utils/api'

use([
  CanvasRenderer, PieChart, LineChart, BarChart,
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DatasetComponent, TransformComponent
])

const loading = ref(true)
const summary = ref({
  month: { income: 0, expense: 0, balance: 0, count: 0 },
  total: { income: 0, expense: 0 },
  today: { count: 0, expense: 0 },
  week: { expense: 0 }
})
const trendData = ref({ labels: [], income: [], expense: [] })
const categoryStats = ref({ categories: [], total: 0 })
const weeklyData = ref({ days: [] })

let refreshTimer = null

onMounted(async () => {
  await loadAll()
  refreshTimer = setInterval(silentRefresh, 30000)
})

onUnmounted(() => {
  clearInterval(refreshTimer)
})

async function loadAll() {
  loading.value = true
  try {
    const [s, t, c, w] = await Promise.all([
      api.get('/dashboard/summary'),
      api.get('/dashboard/trend?months=6'),
      api.get('/dashboard/category-stats?type=expense'),
      api.get('/dashboard/weekly')
    ])
    summary.value = s.data
    trendData.value = t.data
    categoryStats.value = c.data
    weeklyData.value = w.data
  } catch (e) {
    console.error('Analytics load failed', e)
  } finally {
    loading.value = false
  }
}

async function silentRefresh() {
  try {
    const [s, t, c, w] = await Promise.all([
      api.get('/dashboard/summary'),
      api.get('/dashboard/trend?months=6'),
      api.get('/dashboard/category-stats?type=expense'),
      api.get('/dashboard/weekly')
    ])
    summary.value = s.data
    trendData.value = t.data
    categoryStats.value = c.data
    weeklyData.value = w.data
  } catch (e) { /* silent */ }
}

// --- Formatters ---
function fmt(n) {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtFull(n) {
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// --- Top category ---
const topCategory = computed(() => {
  const cats = categoryStats.value.categories
  if (!cats.length) return { name: '暂无', amount: 0, percentage: 0 }
  return cats[0]
})

// --- Stat cards ---
const statCards = computed(() => [
  {
    title: '本月支出',
    value: `¥${fmt(summary.value.month.expense)}`,
    sub: `共 ${summary.value.month.count} 笔`,
    gradient: 'from-rose-500/10 to-pink-500/10 dark:from-rose-500/20 dark:to-pink-500/20',
    iconBg: 'bg-rose-100 dark:bg-rose-900/30',
    iconColor: 'text-rose-600 dark:text-rose-400',
    border: 'border-rose-200/60 dark:border-rose-800/40',
    accent: 'text-rose-600 dark:text-rose-400',
    icon: 'M2.25 6L9 12.75l4.286-4.286a11.948 11.948 0 014.306 6.43l.776 2.898m0 0l3.182-5.511m-3.182 5.51l-5.511-3.181'
  },
  {
    title: '本周支出',
    value: `¥${fmt(summary.value.week.expense)}`,
    sub: '周一至周日',
    gradient: 'from-amber-500/10 to-orange-500/10 dark:from-amber-500/20 dark:to-orange-500/20',
    iconBg: 'bg-amber-100 dark:bg-amber-900/30',
    iconColor: 'text-amber-600 dark:text-amber-400',
    border: 'border-amber-200/60 dark:border-amber-800/40',
    accent: 'text-amber-600 dark:text-amber-400',
    icon: 'M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5'
  },
  {
    title: '今日支出',
    value: `¥${fmt(summary.value.today.expense)}`,
    sub: `${summary.value.today.count} 笔记录`,
    gradient: 'from-blue-500/10 to-cyan-500/10 dark:from-blue-500/20 dark:to-cyan-500/20',
    iconBg: 'bg-blue-100 dark:bg-blue-900/30',
    iconColor: 'text-blue-600 dark:text-blue-400',
    border: 'border-blue-200/60 dark:border-blue-800/40',
    accent: 'text-blue-600 dark:text-blue-400',
    icon: 'M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z'
  },
  {
    title: '最大消费',
    value: topCategory.value.name,
    sub: topCategory.value.amount > 0 ? `¥${fmt(topCategory.value.amount)} · ${topCategory.value.percentage}%` : '暂无数据',
    gradient: 'from-violet-500/10 to-purple-500/10 dark:from-violet-500/20 dark:to-purple-500/20',
    iconBg: 'bg-violet-100 dark:bg-violet-900/30',
    iconColor: 'text-violet-600 dark:text-violet-400',
    border: 'border-violet-200/60 dark:border-violet-800/40',
    accent: 'text-violet-600 dark:text-violet-400',
    icon: 'M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z'
  }
])

// --- ECharts: Category Pie ---
const pieOption = shallowRef({})
const pieTotal = computed(() => categoryStats.value.total)

function buildPieOption() {
  const cats = categoryStats.value.categories.slice(0, 8)
  if (!cats.length) return {}
  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15,23,42,0.95)',
      borderColor: 'rgba(100,116,139,0.2)',
      textStyle: { color: '#e2e8f0', fontSize: 13 },
      formatter: (p) => `<b>${p.name}</b><br/>¥${Number(p.value).toLocaleString()}<br/>占比 ${p.percent}%`
    },
    legend: { show: false },
    series: [{
      type: 'pie',
      radius: ['48%', '75%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 6,
        borderColor: 'transparent',
        borderWidth: 2
      },
      label: { show: false },
      emphasis: {
        label: { show: false },
        itemStyle: {
          shadowBlur: 20,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0,0,0,0.3)'
        }
      },
      labelLine: { show: false },
      data: cats.map(c => ({
        name: c.name,
        value: c.amount,
        itemStyle: { color: c.color || '#6366f1' }
      })),
      animationType: 'scale',
      animationEasing: 'elasticOut',
      animationDelay: (idx) => idx * 80
    }]
  }
}

// --- ECharts: Monthly Trend Line ---
const trendOption = shallowRef({})

function buildTrendOption() {
  const labels = trendData.value.labels.map(l => {
    const parts = l.split('-')
    return `${parts[1]}月`
  })
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15,23,42,0.95)',
      borderColor: 'rgba(100,116,139,0.2)',
      textStyle: { color: '#e2e8f0', fontSize: 13 },
      axisPointer: { type: 'cross', crossStyle: { color: '#64748b' } },
      formatter: (params) => {
        let s = `<b>${params[0].axisValue}</b><br/>`
        params.forEach(p => {
          const color = p.seriesIndex === 0 ? '#10b981' : '#f43f5e'
          s += `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px;"></span>${p.seriesName}: ¥${Number(p.value).toLocaleString()}<br/>`
        })
        return s
      }
    },
    legend: {
      top: 0,
      right: 0,
      textStyle: { color: '#94a3b8', fontSize: 12 },
      itemWidth: 12, itemHeight: 12, itemGap: 20,
      data: [
        { name: '收入', icon: 'circle' },
        { name: '支出', icon: 'circle' }
      ]
    },
    grid: { left: 12, right: 12, top: 40, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: 'rgba(100,116,139,0.15)' } },
      axisTick: { show: false },
      axisLabel: { color: '#94a3b8', fontSize: 12 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(100,116,139,0.08)', type: 'dashed' } },
      axisLabel: {
        color: '#94a3b8', fontSize: 11,
        formatter: v => v >= 10000 ? (v / 10000) + 'w' : v >= 1000 ? (v / 1000) + 'k' : v
      }
    },
    series: [
      {
        name: '收入',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        showSymbol: true,
        lineStyle: { width: 3, color: '#10b981' },
        itemStyle: { color: '#10b981', borderWidth: 2, borderColor: '#fff' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(16,185,129,0.25)' },
              { offset: 1, color: 'rgba(16,185,129,0.02)' }
            ]
          }
        },
        data: trendData.value.income,
        animationDuration: 1500,
        animationEasing: 'cubicOut'
      },
      {
        name: '支出',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        showSymbol: true,
        lineStyle: { width: 3, color: '#f43f5e' },
        itemStyle: { color: '#f43f5e', borderWidth: 2, borderColor: '#fff' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(244,63,94,0.25)' },
              { offset: 1, color: 'rgba(244,63,94,0.02)' }
            ]
          }
        },
        data: trendData.value.expense,
        animationDuration: 1500,
        animationEasing: 'cubicOut',
        animationDelay: 200
      }
    ]
  }
}

// --- ECharts: Weekly Bar ---
const barOption = shallowRef({})

function buildBarOption() {
  const days = weeklyData.value.days || []
  if (!days.length) return {}
  const maxVal = Math.max(...days.map(d => d.amount), 1)
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15,23,42,0.95)',
      borderColor: 'rgba(100,116,139,0.2)',
      textStyle: { color: '#e2e8f0', fontSize: 13 },
      formatter: (params) => {
        const p = params[0]
        return `<b>${p.name}</b><br/>支出: ¥${Number(p.value).toLocaleString()}`
      }
    },
    grid: { left: 12, right: 12, top: 16, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: days.map(d => d.label),
      axisLine: { lineStyle: { color: 'rgba(100,116,139,0.15)' } },
      axisTick: { show: false },
      axisLabel: {
        color: (val, idx) => days[idx]?.is_today ? '#6366f1' : '#94a3b8',
        fontWeight: (val, idx) => days[idx]?.is_today ? 'bold' : 'normal',
        fontSize: 12
      }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(100,116,139,0.08)', type: 'dashed' } },
      axisLabel: {
        color: '#94a3b8', fontSize: 11,
        formatter: v => v >= 10000 ? (v / 10000) + 'w' : v >= 1000 ? (v / 1000) + 'k' : v
      }
    },
    series: [{
      type: 'bar',
      barWidth: '45%',
      data: days.map(d => ({
        value: d.amount,
        itemStyle: {
          color: d.is_today
            ? { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#818cf8' }, { offset: 1, color: '#6366f1' }] }
            : d.amount > maxVal * 0.7
              ? { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#f97316' }, { offset: 1, color: '#f59e0b' }] }
              : { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#60a5fa' }, { offset: 1, color: '#3b82f6' }] },
          borderRadius: [6, 6, 0, 0]
        }
      })),
      animationDuration: 1200,
      animationEasing: 'elasticOut',
      animationDelay: (idx) => idx * 100
    }]
  }
}

// Build all chart options when data loads
import { watch } from 'vue'

watch([summary, trendData, categoryStats, weeklyData], () => {
  pieOption.value = buildPieOption()
  trendOption.value = buildTrendOption()
  barOption.value = buildBarOption()
}, { deep: true })
</script>

<template>
  <div class="animate-fade-in space-y-5 max-w-5xl mx-auto">

    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-surface-900 dark:text-white">财务分析</h1>
        <p class="text-sm text-surface-400 dark:text-surface-500 mt-0.5">AI 驱动的智能财务洞察</p>
      </div>
      <div class="flex items-center gap-2 text-xs text-surface-400">
        <span class="relative flex h-2 w-2">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
        </span>
        实时更新
      </div>
    </div>

    <!-- Loading -->
    <template v-if="loading">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div v-for="i in 4" :key="i" class="card animate-pulse p-4">
          <div class="h-3 bg-surface-200 dark:bg-surface-700 rounded w-16 mb-3"></div>
          <div class="h-7 bg-surface-200 dark:bg-surface-700 rounded w-24 mb-2"></div>
          <div class="h-3 bg-surface-200 dark:bg-surface-700 rounded w-20"></div>
        </div>
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div v-for="i in 3" :key="i" class="card animate-pulse" style="height: 320px;">
          <div class="h-full bg-surface-100 dark:bg-surface-800 rounded-xl"></div>
        </div>
      </div>
    </template>

    <template v-else>
      <!-- Stat Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div
          v-for="(card, idx) in statCards"
          :key="card.title"
          class="relative overflow-hidden rounded-2xl border transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 cursor-default"
          :class="[card.border, `bg-gradient-to-br ${card.gradient}`]"
        >
          <div class="p-4">
            <div class="flex items-center gap-2.5 mb-3">
              <div class="w-9 h-9 rounded-xl flex items-center justify-center" :class="card.iconBg">
                <svg class="w-4.5 h-4.5" :class="card.iconColor" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" :d="card.icon" />
                </svg>
              </div>
              <span class="text-xs font-medium text-surface-500 dark:text-surface-400">{{ card.title }}</span>
            </div>
            <p class="text-xl font-bold text-surface-900 dark:text-white tracking-tight">{{ card.value }}</p>
            <p class="text-[11px] text-surface-400 dark:text-surface-500 mt-1">{{ card.sub }}</p>
          </div>
          <!-- Decorative -->
          <div class="absolute -right-3 -bottom-3 w-16 h-16 rounded-full opacity-[0.06]" :class="card.gradient"></div>
        </div>
      </div>

      <!-- Charts Row 1: Trend (full width) -->
      <div class="card p-5">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="text-sm font-semibold text-surface-900 dark:text-white">收支趋势</h3>
            <p class="text-xs text-surface-400 mt-0.5">近6个月收入 vs 支出</p>
          </div>
        </div>
        <div class="h-[280px]">
          <v-chart v-if="trendData.labels.length" :option="trendOption" autoresize />
          <div v-else class="h-full flex items-center justify-center text-surface-400 text-sm">暂无数据</div>
        </div>
      </div>

      <!-- Charts Row 2: Pie + Bar -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Category Pie -->
        <div class="card p-5">
          <div class="flex items-center justify-between mb-2">
            <div>
              <h3 class="text-sm font-semibold text-surface-900 dark:text-white">支出分类</h3>
              <p class="text-xs text-surface-400 mt-0.5">本月分类占比</p>
            </div>
          </div>
          <div class="flex items-center gap-4">
            <div class="w-[180px] h-[180px] relative flex-shrink-0">
              <v-chart v-if="categoryStats.categories.length" :option="pieOption" autoresize />
              <div v-else class="h-full flex items-center justify-center text-surface-400 text-xs">暂无数据</div>
              <!-- Center label -->
              <div v-if="pieTotal > 0" class="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div class="text-center">
                  <p class="text-[10px] text-surface-400">总计</p>
                  <p class="text-base font-bold text-surface-900 dark:text-white">¥{{ fmt(pieTotal) }}</p>
                </div>
              </div>
            </div>
            <!-- Legend -->
            <div class="flex-1 space-y-2 min-w-0">
              <div
                v-for="cat in categoryStats.categories.slice(0, 6)"
                :key="cat.name"
                class="flex items-center justify-between text-xs"
              >
                <div class="flex items-center gap-2 min-w-0">
                  <div class="w-2.5 h-2.5 rounded-full flex-shrink-0" :style="{ backgroundColor: cat.color }"></div>
                  <span class="text-surface-600 dark:text-surface-400 truncate">{{ cat.name }}</span>
                </div>
                <div class="flex items-center gap-2 flex-shrink-0">
                  <span class="font-medium text-surface-800 dark:text-surface-200">{{ cat.percentage }}%</span>
                  <span class="text-surface-400">¥{{ fmt(cat.amount) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Weekly Bar -->
        <div class="card p-5">
          <div class="flex items-center justify-between mb-2">
            <div>
              <h3 class="text-sm font-semibold text-surface-900 dark:text-white">本周消费</h3>
              <p class="text-xs text-surface-400 mt-0.5">每日支出对比</p>
            </div>
            <span class="text-xs font-medium text-surface-500">
              合计 ¥{{ fmt(summary.week.expense) }}
            </span>
          </div>
          <div class="h-[200px]">
            <v-chart v-if="weeklyData.days?.length" :option="barOption" autoresize />
            <div v-else class="h-full flex items-center justify-center text-surface-400 text-sm">暂无数据</div>
          </div>
        </div>
      </div>

      <!-- Category Detail List -->
      <div class="card p-5">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-semibold text-surface-900 dark:text-white">分类明细</h3>
          <span class="text-xs text-surface-400">本月支出排行</span>
        </div>
        <div v-if="categoryStats.categories.length" class="space-y-3">
          <div
            v-for="(cat, idx) in categoryStats.categories"
            :key="cat.name"
            class="flex items-center gap-3"
          >
            <span class="w-5 text-xs text-surface-400 text-center font-medium">{{ idx + 1 }}</span>
            <div class="w-8 h-8 rounded-lg flex items-center justify-center text-sm" :style="{ backgroundColor: cat.color + '20' }">
              <span :style="{ color: cat.color }">{{ cat.icon || '📋' }}</span>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm font-medium text-surface-800 dark:text-surface-200">{{ cat.name }}</span>
                <span class="text-sm font-semibold text-surface-900 dark:text-white">¥{{ fmtFull(cat.amount) }}</span>
              </div>
              <div class="h-1.5 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-700 ease-out"
                  :style="{ width: cat.percentage + '%', backgroundColor: cat.color }"
                ></div>
              </div>
            </div>
            <span class="text-xs text-surface-400 w-12 text-right">{{ cat.percentage }}%</span>
          </div>
        </div>
        <div v-else class="py-8 text-center text-surface-400 text-sm">暂无分类数据</div>
      </div>

      <!-- Bottom Summary -->
      <div class="grid grid-cols-2 gap-3">
        <div class="card p-4 text-center">
          <p class="text-xs text-surface-400 mb-1">本月收入</p>
          <p class="text-xl font-bold text-emerald-600 dark:text-emerald-400">¥{{ fmt(summary.month.income) }}</p>
        </div>
        <div class="card p-4 text-center">
          <p class="text-xs text-surface-400 mb-1">本月结余</p>
          <p class="text-xl font-bold" :class="summary.month.balance >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'">
            {{ summary.month.balance >= 0 ? '+' : '' }}¥{{ fmt(summary.month.balance) }}
          </p>
        </div>
      </div>
    </template>
  </div>
</template>
