<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, LineChart, BarChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DatasetComponent, TransformComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { renderSafeMarkdown } from '@/utils/safeMarkdown'
import api from '@/utils/api'
import { useUserStore } from '@/stores/user'
import { formatCurrency, formatAmount } from '@/utils/format'

use([
  CanvasRenderer, PieChart, LineChart, BarChart,
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DatasetComponent, TransformComponent
])

const userStore = useUserStore()
const loading = ref(true)
const stats = ref({
  today_expense: 0, yesterday_expense: 0, week_expense: 0,
  month_expense: 0, month_income: 0, month_balance: 0, month_count: 0,
  top_category: { name: '暂无', amount: 0, color: '#6B7280' },
  categories: [], weekly: [],
  trend: { labels: [], income: [], expense: [] },
  recent: []
})

// --- Animated numbers ---
const animToday = ref(0)
const animWeek = ref(0)
const animMonth = ref(0)
const animTopCat = ref(0)
const animMonthIncome = ref(0)
const animMonthBalance = ref(0)

function animateNumber(targetRef, endVal, duration = 1200) {
  const start = 0
  const startTime = performance.now()
  const easeOutCubic = t => 1 - Math.pow(1 - t, 3)
  function step(now) {
    const elapsed = now - startTime
    const progress = Math.min(elapsed / duration, 1)
    targetRef.value = start + (endVal - start) * easeOutCubic(progress)
    if (progress < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

// --- AI analysis ---
const aiAnalysis = ref('')
const aiLoading = ref(false)
const aiError = ref('')

async function loadAiAnalysis() {
  aiLoading.value = true
  aiError.value = ''
  try {
    const cats = stats.value.categories.slice(0, 5).map(c => `${c.name} ${c.amount}元(${c.percentage}%)`).join('、')
    const trend = stats.value.trend
    const recentIncome = trend.income.slice(-3).join(', ')
    const recentExpense = trend.expense.slice(-3).join(', ')
    const prompt = `作为财务分析师，分析以下消费数据并给出建议：
本月支出${stats.value.month_expense}元，收入${stats.value.month_income}元，结余${stats.value.month_balance}元。
今日支出${stats.value.today_expense}元，本周支出${stats.value.week_expense}元。
本月最大消费分类：${stats.value.top_category.name} ${stats.value.top_category.amount}元。
分类明细：${cats}。
近3月收入趋势：${recentIncome}，支出趋势：${recentExpense}。
请给出：1.消费结构分析 2.节省建议 3.异常消费预警（如有）4.财务健康评分(1-10)。用中文回答，使用markdown格式。`

    const res = await api.post('/ai/analyze', { prompt })
    if (res.data?.analysis) {
      aiAnalysis.value = renderSafeMarkdown(res.data.analysis)
    } else if (res.data?.reply) {
      aiAnalysis.value = renderSafeMarkdown(res.data.reply)
    } else {
      generateLocalAnalysis()
    }
  } catch {
    generateLocalAnalysis()
  } finally {
    aiLoading.value = false
  }
}

function generateLocalAnalysis() {
  const s = stats.value
  const savingsRate = s.month_income > 0 ? ((s.month_balance / s.month_income) * 100).toFixed(1) : 0
  const topPct = s.top_category.percentage || 0
  let analysis = `## 📊 本月财务分析\n\n`
  analysis += `### 消费结构\n`
  analysis += `- 本月总支出 **${formatCurrency(s.month_expense)}**，收入 **${formatCurrency(s.month_income)}**\n`
  analysis += `- 储蓄率 **${savingsRate}%**${savingsRate > 30 ? '，表现优秀！' : savingsRate > 10 ? '，尚可改善' : '，偏低，建议控制支出'}\n`
  analysis += `- 最大支出分类：**${s.top_category.name}** 占比 ${topPct}%\n\n`
  analysis += `### 💡 节省建议\n`
  if (topPct > 40) analysis += `- ⚠️ **${s.top_category.name}** 支出占比过高(${topPct}%)，建议设定月度预算上限\n`
  if (s.today_expense > s.week_expense / 7 * 2) analysis += `- 今日支出(${formatCurrency(s.today_expense)})高于周均值，注意控制日消费\n`
  analysis += `- 建议将收入的 20% 用于储蓄或投资\n`
  analysis += `- 使用 50/30/20 法则：50%必要、30%想要、20%储蓄\n\n`
  analysis += `### ⚡ 异常检测\n`
  const avgDaily = s.month_expense / new Date().getDate()
  if (s.today_expense > avgDaily * 3) {
    analysis += `- 🔴 今日支出(${formatCurrency(s.today_expense)})是日均(${formatCurrency(avgDaily)})的 ${(s.today_expense / avgDaily).toFixed(1)}倍，属于异常消费\n`
  } else {
    analysis += `- ✅ 未检测到明显异常消费\n`
  }
  const score = Math.min(10, Math.max(1, Math.round(5 + parseFloat(savingsRate) / 10 - (topPct > 50 ? 2 : 0))))
  analysis += `\n### 🏆 财务健康评分：**${score}/10**`
  aiAnalysis.value = renderSafeMarkdown(analysis)
}

// --- ECharts options ---
const categoryPieOption = computed(() => {
  const data = stats.value.categories.slice(0, 8).map(c => ({
    name: c.name, value: c.amount, itemStyle: { color: c.color }
  }))
  return {
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)', backgroundColor: 'rgba(15,23,42,0.95)', borderColor: 'rgba(99,102,241,0.3)', textStyle: { color: '#e2e8f0' } },
    legend: { show: false },
    series: [{
      type: 'pie', radius: ['48%', '75%'], center: ['50%', '50%'],
      avoidLabelOverlap: false, itemStyle: { borderRadius: 6, borderColor: 'transparent', borderWidth: 2 },
      label: { show: false }, emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold', color: '#e2e8f0' }, scaleSize: 8 },
      labelLine: { show: false },
      data, animationType: 'scale', animationEasing: 'elasticOut', animationDelay: idx => idx * 100
    }]
  }
})

const trendLineOption = computed(() => {
  const labels = stats.value.trend.labels.map(l => { const p = l.split('-'); return `${p[1]}月` })
  return {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(15,23,42,0.95)', borderColor: 'rgba(99,102,241,0.3)', textStyle: { color: '#e2e8f0' },
      axisPointer: { type: 'cross', crossStyle: { color: '#374151' } } },
    legend: { data: ['收入', '支出'], textStyle: { color: '#94a3b8' }, right: 0, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: labels, boundaryGap: false, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(51,65,85,0.5)' } }, axisLabel: { color: '#94a3b8', formatter: v => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v } },
    series: [
      { name: '收入', type: 'line', smooth: true, symbol: 'circle', symbolSize: 6, lineStyle: { width: 3, color: '#10b981' },
        itemStyle: { color: '#10b981' }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(16,185,129,0.25)' }, { offset: 1, color: 'rgba(16,185,129,0)' }] } },
        data: stats.value.trend.income, animationDuration: 1500, animationEasing: 'cubicOut' },
      { name: '支出', type: 'line', smooth: true, symbol: 'circle', symbolSize: 6, lineStyle: { width: 3, color: '#f43f5e' },
        itemStyle: { color: '#f43f5e' }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(244,63,94,0.25)' }, { offset: 1, color: 'rgba(244,63,94,0)' }] } },
        data: stats.value.trend.expense, animationDuration: 1500, animationEasing: 'cubicOut', animationDelay: 300 }
    ]
  }
})

const weeklyBarOption = computed(() => {
  const days = stats.value.weekly
  const today = days.findIndex(d => d.is_today)
  const maxVal = Math.max(...days.map(d => d.amount), 1)
  return {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(15,23,42,0.95)', borderColor: 'rgba(99,102,241,0.3)', textStyle: { color: '#e2e8f0' },
      formatter: params => `${params[0].name}<br/>支出: <b>¥${params[0].value.toLocaleString()}</b>` },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: days.map(d => d.label), axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(51,65,85,0.5)' } }, axisLabel: { color: '#94a3b8' } },
    series: [{
      type: 'bar', barWidth: '45%', itemStyle: {
        borderRadius: [6, 6, 0, 0],
        color: params => {
          if (params.dataIndex === today) return { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#818cf8' }, { offset: 1, color: '#6366f1' }] }
          if (params.value === maxVal && params.value > 0) return { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#fb923c' }, { offset: 1, color: '#f97316' }] }
          return { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(99,102,241,0.7)' }, { offset: 1, color: 'rgba(99,102,241,0.4)' }] }
        }
      },
      data: days.map(d => d.amount), animationDuration: 1200, animationEasing: 'cubicOut', animationDelay: idx => idx * 80
    }]
  }
})

// --- Savings rate ---
const savingsRate = computed(() => {
  if (stats.value.month_income === 0) return 0
  return ((stats.value.month_balance / stats.value.month_income) * 100).toFixed(1)
})

const savingsRateColor = computed(() => {
  const r = parseFloat(savingsRate.value)
  if (r >= 30) return 'text-emerald-400'
  if (r >= 10) return 'text-amber-400'
  return 'text-rose-400'
})

// --- Stat cards ---
const statCards = computed(() => [
  { label: '今日支出', value: animToday, raw: stats.value.today_expense, color: 'cyan', icon: 'today', trend: stats.value.yesterday_expense > 0 ? ((stats.value.today_expense - stats.value.yesterday_expense) / stats.value.yesterday_expense * 100).toFixed(1) : 0 },
  { label: '本周支出', value: animWeek, raw: stats.value.week_expense, color: 'violet', icon: 'week' },
  { label: '本月支出', value: animMonth, raw: stats.value.month_expense, color: 'rose', icon: 'month' },
  { label: '最大分类', value: animTopCat, raw: stats.value.top_category.amount, color: 'amber', icon: 'category', catName: stats.value.top_category.name }
])

// formatAmount 已从 @/utils/format 导入

function formatDate(dateStr) {
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

// --- Recent transactions timeline ---
const recentTransactions = computed(() => stats.value.recent.slice(0, 8))

// --- Load data ---
async function loadData() {
  loading.value = true
  try {
    const res = await api.get('/dashboard/statistics')
    stats.value = res.data
    await nextTick()
    animateNumber(animToday, stats.value.today_expense)
    animateNumber(animWeek, stats.value.week_expense)
    animateNumber(animMonth, stats.value.month_expense)
    animateNumber(animTopCat, stats.value.top_category.amount)
    animateNumber(animMonthIncome, stats.value.month_income)
    animateNumber(animMonthBalance, stats.value.month_balance)
    loadAiAnalysis()
  } catch (e) {
    console.error('Dashboard load failed:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => loadData())
</script>

<template>
  <div class="min-h-screen bg-slate-900 p-3 sm:p-4 md:p-6 lg:p-8">
    <!-- Header -->
    <div class="mb-5 sm:mb-8">
      <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-4">
        <div>
          <h1 class="text-xl sm:text-2xl lg:text-3xl font-bold text-white tracking-tight">
            <span class="hidden sm:inline">Welcome back, </span><span class="sm:hidden">Hi, </span><span class="bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">{{ userStore.user?.username }}</span>
          </h1>
          <p class="text-slate-400 mt-0.5 sm:mt-1 text-xs sm:text-sm">企业级财务智能分析平台</p>
        </div>
        <router-link to="/ai-accounting" class="inline-flex items-center justify-center gap-1.5 sm:gap-2 px-4 sm:px-5 py-2 sm:py-2.5 bg-gradient-to-r from-indigo-500 to-violet-600 text-white rounded-xl text-xs sm:text-sm font-medium hover:shadow-lg hover:shadow-indigo-500/25 transition-all duration-300">
          <svg class="w-3.5 h-3.5 sm:w-4 sm:h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>
          AI 记账
        </router-link>
      </div>
    </div>

    <!-- Loading -->
    <template v-if="loading">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        <div v-for="i in 4" :key="i" class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5 animate-pulse">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-xl bg-slate-700" />
            <div class="h-4 bg-slate-700 rounded w-20" />
          </div>
          <div class="h-8 bg-slate-700 rounded w-32 mb-2" />
          <div class="h-3 bg-slate-700 rounded w-16" />
        </div>
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div class="lg:col-span-2 bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5 h-80 animate-pulse" />
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5 h-80 animate-pulse" />
      </div>
    </template>

    <template v-else>
      <!-- Stat Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5 mb-5 sm:mb-8">
        <div v-for="(card, idx) in statCards" :key="card.label"
          class="group relative bg-slate-800/80 border border-slate-700/60 rounded-xl sm:rounded-2xl p-3 sm:p-5 hover:border-slate-600/80 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-black/20 overflow-hidden"
          :style="{ animationDelay: `${idx * 100}ms` }">
          <!-- Glow effect -->
          <div class="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"
            :class="{
              'bg-gradient-to-br from-cyan-500/5 to-transparent': card.color === 'cyan',
              'bg-gradient-to-br from-violet-500/5 to-transparent': card.color === 'violet',
              'bg-gradient-to-br from-rose-500/5 to-transparent': card.color === 'rose',
              'bg-gradient-to-br from-amber-500/5 to-transparent': card.color === 'amber'
            }" />
          <div class="relative">
            <div class="flex items-center justify-between mb-2 sm:mb-3">
              <div class="w-8 h-8 sm:w-10 sm:h-10 rounded-lg sm:rounded-xl flex items-center justify-center"
                :class="{
                  'bg-cyan-500/10 text-cyan-400': card.color === 'cyan',
                  'bg-violet-500/10 text-violet-400': card.color === 'violet',
                  'bg-rose-500/10 text-rose-400': card.color === 'rose',
                  'bg-amber-500/10 text-amber-400': card.color === 'amber'
                }">
                <!-- Today icon -->
                <svg v-if="card.icon === 'today'" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <!-- Week icon -->
                <svg v-if="card.icon === 'week'" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" /></svg>
                <!-- Month icon -->
                <svg v-if="card.icon === 'month'" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" /></svg>
                <!-- Category icon -->
                <svg v-if="card.icon === 'category'" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" /><path stroke-linecap="round" stroke-linejoin="round" d="M6 6h.008v.008H6V6z" /></svg>
              </div>
              <!-- Trend badge -->
              <div v-if="card.trend !== undefined && card.icon === 'today'" class="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium"
                :class="card.trend > 0 ? 'bg-rose-500/10 text-rose-400' : 'bg-emerald-500/10 text-emerald-400'">
                <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path v-if="card.trend > 0" stroke-linecap="round" stroke-linejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" />
                  <path v-else stroke-linecap="round" stroke-linejoin="round" d="M19.5 4.5l-15 15m0 0h11.25m-11.25 0V8.25" />
                </svg>
                {{ Math.abs(card.trend) }}%
              </div>
            </div>
            <p class="text-slate-400 text-xs sm:text-sm font-medium mb-0.5 sm:mb-1">{{ card.label }}</p>
            <p class="text-lg sm:text-2xl font-bold text-white tracking-tight">
              <span v-if="card.icon !== 'category'">{{ formatCurrency(card.raw) }}</span>
              <span v-else>
                <span class="text-sm sm:text-lg">{{ card.catName }}</span>
                <span class="text-xs sm:text-base text-slate-400 ml-1 sm:ml-2">{{ formatCurrency(card.raw) }}</span>
              </span>
            </p>
          </div>
          <!-- Decorative gradient orb -->
          <div class="absolute -right-6 -bottom-6 w-24 h-24 rounded-full opacity-[0.07] group-hover:opacity-[0.12] transition-opacity duration-500 group-hover:scale-110"
            :class="{
              'bg-gradient-to-br from-cyan-400 to-cyan-600': card.color === 'cyan',
              'bg-gradient-to-br from-violet-400 to-violet-600': card.color === 'violet',
              'bg-gradient-to-br from-rose-400 to-rose-600': card.color === 'rose',
              'bg-gradient-to-br from-amber-400 to-amber-600': card.color === 'amber'
            }" />
        </div>
      </div>

      <!-- Charts Row -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-3 sm:gap-5 mb-5 sm:mb-8">
        <!-- Trend Line Chart -->
        <div class="lg:col-span-2 bg-slate-800/80 border border-slate-700/60 rounded-xl sm:rounded-2xl p-3 sm:p-5">
          <div class="flex items-center justify-between mb-3 sm:mb-5">
            <div>
              <h3 class="text-sm sm:text-base font-semibold text-white">收支趋势</h3>
              <p class="text-[10px] sm:text-xs text-slate-400 mt-0.5">近6个月收入与支出走势</p>
            </div>
            <div class="flex items-center gap-3 sm:gap-4">
              <div class="flex items-center gap-1 sm:gap-1.5"><div class="w-2 h-2 rounded-full bg-emerald-500" /><span class="text-[10px] sm:text-xs text-slate-400">收入</span></div>
              <div class="flex items-center gap-1 sm:gap-1.5"><div class="w-2 h-2 rounded-full bg-rose-500" /><span class="text-[10px] sm:text-xs text-slate-400">支出</span></div>
            </div>
          </div>
          <div class="h-[200px] sm:h-[280px]">
            <v-chart v-if="stats.trend.labels.length" :option="trendLineOption" autoresize class="w-full h-full" />
            <div v-else class="h-full flex items-center justify-center text-slate-500 text-sm">暂无数据</div>
          </div>
        </div>

        <!-- Category Pie Chart -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl sm:rounded-2xl p-3 sm:p-5">
          <div class="mb-3 sm:mb-5">
            <h3 class="text-sm sm:text-base font-semibold text-white">支出分类</h3>
            <p class="text-[10px] sm:text-xs text-slate-400 mt-0.5">本月占比分布</p>
          </div>
          <div class="h-[160px] sm:h-[200px] relative">
            <v-chart v-if="stats.categories.length" :option="categoryPieOption" autoresize class="w-full h-full" />
            <div v-else class="h-full flex items-center justify-center text-slate-500 text-sm">暂无数据</div>
            <!-- Center label -->
            <div v-if="stats.month_expense > 0" class="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div class="text-center">
                <p class="text-[10px] text-slate-500 uppercase tracking-wider">Total</p>
                <p class="text-lg font-bold text-white">{{ formatCurrency(stats.month_expense) }}</p>
              </div>
            </div>
          </div>
          <!-- Legend -->
          <div class="mt-4 space-y-2 max-h-[140px] overflow-y-auto scrollbar-thin">
            <div v-for="cat in stats.categories.slice(0, 6)" :key="cat.name"
              class="flex items-center justify-between text-sm group">
              <div class="flex items-center gap-2">
                <div class="w-2.5 h-2.5 rounded-full flex-shrink-0" :style="{ backgroundColor: cat.color }" />
                <span class="text-slate-400 group-hover:text-slate-200 transition-colors">{{ cat.name }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-slate-300 font-medium">{{ formatCurrency(cat.amount) }}</span>
                <span class="text-xs text-slate-500 w-10 text-right">{{ cat.percentage }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Bottom Row: Weekly + AI + Recent -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-3 sm:gap-5">
        <!-- Weekly Bar Chart -->
        <div class="lg:col-span-4 bg-slate-800/80 border border-slate-700/60 rounded-xl sm:rounded-2xl p-3 sm:p-5">
          <div class="mb-3 sm:mb-5">
            <h3 class="text-sm sm:text-base font-semibold text-white">本周消费</h3>
            <p class="text-[10px] sm:text-xs text-slate-400 mt-0.5">周一至周日支出对比</p>
          </div>
          <div class="h-[180px] sm:h-[220px]">
            <v-chart v-if="stats.weekly.length" :option="weeklyBarOption" autoresize class="w-full h-full" />
            <div v-else class="h-full flex items-center justify-center text-slate-500 text-sm">暂无数据</div>
          </div>
          <!-- Weekly summary -->
          <div class="mt-4 pt-4 border-t border-slate-700/50 flex items-center justify-between">
            <span class="text-sm text-slate-400">本周合计</span>
            <span class="text-sm font-semibold text-white">{{ formatCurrency(stats.week_expense) }}</span>
          </div>
        </div>

        <!-- AI Analysis -->
        <div class="lg:col-span-4 bg-slate-800/80 border border-slate-700/60 rounded-xl sm:rounded-2xl p-3 sm:p-5 flex flex-col">
          <div class="flex items-center justify-between mb-3 sm:mb-4">
            <div class="flex items-center gap-2">
              <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center flex-shrink-0">
                <svg class="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>
              </div>
              <div>
                <h3 class="text-sm sm:text-base font-semibold text-white">AI 分析</h3>
                <p class="text-[10px] text-indigo-400">Powered by DeepSeek</p>
              </div>
            </div>
            <button @click="loadAiAnalysis" class="p-2 rounded-lg hover:bg-slate-700/50 text-slate-400 hover:text-white transition-colors" :disabled="aiLoading">
              <svg class="w-4 h-4" :class="{ 'animate-spin': aiLoading }" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" /></svg>
            </button>
          </div>
          <!-- AI content -->
          <div class="flex-1 overflow-y-auto max-h-[260px] pr-1">
            <div v-if="aiLoading" class="space-y-3">
              <div class="flex items-center gap-3 text-slate-400 text-sm">
                <div class="flex gap-1">
                  <div class="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style="animation-delay: 0ms" />
                  <div class="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style="animation-delay: 150ms" />
                  <div class="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style="animation-delay: 300ms" />
                </div>
                AI 正在分析您的财务数据...
              </div>
              <div class="space-y-2">
                <div class="h-3 bg-slate-700/50 rounded w-full animate-pulse" />
                <div class="h-3 bg-slate-700/50 rounded w-4/5 animate-pulse" />
                <div class="h-3 bg-slate-700/50 rounded w-3/5 animate-pulse" />
              </div>
            </div>
            <div v-else-if="aiError" class="text-sm text-rose-400">{{ aiError }}</div>
            <div v-else-if="aiAnalysis" class="ai-content text-sm text-slate-300 leading-relaxed" v-html="aiAnalysis" />
            <div v-else class="text-sm text-slate-500 text-center py-8">点击刷新按钮获取 AI 分析</div>
          </div>
          <!-- Savings rate mini card -->
          <div class="mt-4 pt-4 border-t border-slate-700/50">
            <div class="flex items-center justify-between">
              <span class="text-sm text-slate-400">储蓄率</span>
              <span class="text-lg font-bold" :class="savingsRateColor">{{ savingsRate }}%</span>
            </div>
            <div class="mt-2 h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
              <div class="h-full rounded-full transition-all duration-1000 ease-out"
                :class="parseFloat(savingsRate) >= 30 ? 'bg-emerald-500' : parseFloat(savingsRate) >= 10 ? 'bg-amber-500' : 'bg-rose-500'"
                :style="{ width: `${Math.min(parseFloat(savingsRate), 100)}%` }" />
            </div>
          </div>
        </div>

        <!-- Recent Transactions Timeline -->
        <div class="lg:col-span-4 bg-slate-800/80 border border-slate-700/60 rounded-xl sm:rounded-2xl p-3 sm:p-5">
          <div class="flex items-center justify-between mb-3 sm:mb-4">
            <h3 class="text-sm sm:text-base font-semibold text-white">最近交易</h3>
            <router-link to="/transactions" class="text-[10px] sm:text-xs text-indigo-400 hover:text-indigo-300 transition-colors">查看全部</router-link>
          </div>

          <div v-if="recentTransactions.length === 0" class="flex flex-col items-center justify-center py-12">
            <div class="w-12 h-12 rounded-xl bg-slate-700/50 flex items-center justify-center mb-3">
              <svg class="w-6 h-6 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12H9.75m0 0H7.5m2.25 0v3" /></svg>
            </div>
            <p class="text-slate-500 text-sm">暂无交易记录</p>
          </div>

          <div v-else class="space-y-0 relative">
            <!-- Timeline line -->
            <div class="absolute left-[19px] top-2 bottom-2 w-px bg-slate-700/50" />
            <div v-for="item in recentTransactions" :key="item.id"
              class="flex items-start gap-3 py-2.5 relative group">
              <!-- Timeline dot -->
              <div class="w-[10px] h-[10px] rounded-full flex-shrink-0 mt-1.5 z-10 border-2"
                :class="item.type === 'income' ? 'bg-emerald-500 border-emerald-400' : 'bg-rose-500 border-rose-400'" />
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between">
                  <p class="text-sm font-medium text-slate-200 truncate">{{ item.category?.name || '未分类' }}</p>
                  <span class="text-sm font-semibold flex-shrink-0 ml-2"
                    :class="item.type === 'income' ? 'text-emerald-400' : 'text-rose-400'">
                    {{ item.type === 'income' ? '+' : '-' }}{{ formatCurrency(item.amount) }}
                  </span>
                </div>
                <p class="text-[11px] text-slate-500 mt-0.5">{{ formatDate(item.date) }}{{ item.description ? ` · ${item.description}` : '' }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* AI markdown content styling */
.ai-content :deep(h2) {
  font-size: 0.95rem;
  font-weight: 600;
  color: #e2e8f0;
  margin: 0.75rem 0 0.5rem;
}
.ai-content :deep(h3) {
  font-size: 0.85rem;
  font-weight: 600;
  color: #cbd5e1;
  margin: 0.5rem 0 0.35rem;
}
.ai-content :deep(p) {
  margin: 0.25rem 0;
}
.ai-content :deep(ul), .ai-content :deep(ol) {
  padding-left: 1.25rem;
  margin: 0.25rem 0;
}
.ai-content :deep(li) {
  margin: 0.2rem 0;
}
.ai-content :deep(strong) {
  color: #f1f5f9;
  font-weight: 600;
}
.ai-content :deep(code) {
  background: rgba(51, 65, 85, 0.5);
  padding: 0.1rem 0.35rem;
  border-radius: 0.25rem;
  font-size: 0.8rem;
}

/* Scrollbar */
.scrollbar-thin::-webkit-scrollbar {
  width: 4px;
}
.scrollbar-thin::-webkit-scrollbar-track {
  background: transparent;
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background: rgba(100, 116, 139, 0.3);
  border-radius: 4px;
}
.scrollbar-thin::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 116, 139, 0.5);
}

/* Chart container scrollbar */
.overflow-y-auto::-webkit-scrollbar {
  width: 4px;
}
.overflow-y-auto::-webkit-scrollbar-track {
  background: transparent;
}
.overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(100, 116, 139, 0.3);
  border-radius: 4px;
}
</style>
