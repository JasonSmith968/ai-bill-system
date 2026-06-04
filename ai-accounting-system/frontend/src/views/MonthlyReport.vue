<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, LineChart, BarChart, GaugeChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DatasetComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { renderSafeMarkdown } from '@/utils/safeMarkdown'
import api from '@/utils/api'
import { useUserStore } from '@/stores/user'

use([CanvasRenderer, PieChart, LineChart, BarChart, GaugeChart,
  TitleComponent, TooltipComponent, LegendComponent, GridComponent, DatasetComponent])

const userStore = useUserStore()
const loading = ref(false)
const exportingPdf = ref(false)
const exportingExcel = ref(false)
const aiLoading = ref(false)
const aiAnalysis = ref('')
const reportData = ref(null)
const showShareModal = ref(false)

// Month selector
const today = new Date()
const selectedYear = ref(today.getFullYear())
const selectedMonth = ref(today.getMonth() + 1)
const monthDropdownOpen = ref(false)

const monthOptions = computed(() => {
  const opts = []
  const now = new Date()
  for (let i = 0; i < 12; i++) {
    let y = now.getFullYear(), m = now.getMonth() + 1 - i
    if (m <= 0) { y--; m += 12 }
    opts.push({ year: y, month: m, label: `${y}年${m}月` })
  }
  return opts
})
const selectedLabel = computed(() => `${selectedYear.value}年${selectedMonth.value}月`)

function selectMonth(opt) {
  selectedYear.value = opt.year
  selectedMonth.value = opt.month
  monthDropdownOpen.value = false
  loadReport()
}

// Close dropdown on outside click
function closeDropdown(e) {
  if (!e.target.closest('.month-dropdown')) monthDropdownOpen.value = false
}

// Animated numbers
const animIncome = ref(0)
const animExpense = ref(0)
const animBalance = ref(0)
const animAvgDaily = ref(0)

function animateNum(target, end, dur = 1000) {
  const start = 0, t0 = performance.now()
  const ease = t => 1 - Math.pow(1 - t, 3)
  function tick(now) {
    const p = Math.min((now - t0) / dur, 1)
    target.value = start + (end - start) * ease(p)
    if (p < 1) requestAnimationFrame(tick)
  }
  requestAnimationFrame(tick)
}

// Load report
async function loadReport() {
  loading.value = true
  aiAnalysis.value = ''
  try {
    const res = await api.get('/reports/monthly', {
      params: { year: selectedYear.value, month: selectedMonth.value }
    })
    reportData.value = res.data
    await nextTick()
    const s = res.data.summary
    animateNum(animIncome, s.income)
    animateNum(animExpense, s.expense)
    animateNum(animBalance, s.balance)
    animateNum(animAvgDaily, s.avg_daily)
  } catch (e) {
    console.error('Report load failed:', e)
  } finally {
    loading.value = false
  }
}

// AI Analysis with streaming
async function loadAiAnalysis() {
  if (!reportData.value) return
  aiLoading.value = true
  aiAnalysis.value = ''
  try {
    const token = localStorage.getItem('token')
    const resp = await fetch(`/api/reports/ai-analysis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ year: selectedYear.value, month: selectedMonth.value })
    })
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const d = line.slice(6).trim()
        if (d === '[DONE]') { aiLoading.value = false; return }
        try {
          const p = JSON.parse(d)
          if (p.content) aiAnalysis.value += p.content
        } catch {}
      }
    }
  } catch {
    aiAnalysis.value = '*AI 分析生成失败，请稍后重试。*'
  } finally {
    aiLoading.value = false
  }
}

// Computed data
const s = computed(() => reportData.value?.summary || {})
const comp = computed(() => reportData.value?.comparison || {})
const cats = computed(() => reportData.value?.categories || [])
const risk = computed(() => reportData.value?.risk || {})
const anomalies = computed(() => reportData.value?.anomalies || [])
const txns = computed(() => reportData.value?.transactions || [])
const weekly = computed(() => reportData.value?.weekly || [])

// ECharts: category pie
const pieOpt = computed(() => {
  if (!cats.value.length) return {}
  return {
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)', backgroundColor: 'rgba(15,23,42,0.95)', borderColor: 'rgba(99,102,241,0.3)', textStyle: { color: '#e2e8f0' } },
    series: [{
      type: 'pie', radius: ['44%', '72%'], center: ['50%', '50%'],
      itemStyle: { borderRadius: 6, borderColor: 'rgba(15,23,42,0.8)', borderWidth: 2 },
      label: { show: false }, emphasis: { label: { show: true, fontSize: 12, fontWeight: 'bold', color: '#e2e8f0' } },
      labelLine: { show: false },
      data: cats.value.slice(0, 8).map(c => ({ name: c.name, value: c.amount, itemStyle: { color: c.color } }))
    }]
  }
})

// ECharts: daily trend (income + expense)
const trendOpt = computed(() => {
  const d = reportData.value?.daily_trend
  if (!d?.length) return {}
  const inc = reportData.value?.daily_income_trend || []
  return {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(15,23,42,0.95)', borderColor: 'rgba(99,102,241,0.3)', textStyle: { color: '#e2e8f0' } },
    legend: { data: ['支出', '收入'], textStyle: { color: '#94a3b8' }, right: 0, top: 0, textStyle: { fontSize: 11 } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: d.map(x => x.day), boundaryGap: false, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8', interval: 4 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(51,65,85,0.4)' } }, axisLabel: { color: '#94a3b8', formatter: v => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v } },
    series: [
      { name: '支出', type: 'line', smooth: true, symbol: 'none', lineStyle: { width: 2.5, color: '#f43f5e' },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(244,63,94,0.2)' }, { offset: 1, color: 'rgba(244,63,94,0)' }] } },
        data: d.map(x => x.amount), animationDuration: 1500 },
      { name: '收入', type: 'line', smooth: true, symbol: 'none', lineStyle: { width: 2.5, color: '#10b981' },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(16,185,129,0.15)' }, { offset: 1, color: 'rgba(16,185,129,0)' }] } },
        data: inc.map(x => x.amount), animationDuration: 1500, animationDelay: 200 }
    ]
  }
})

// ECharts: weekly bar
const weeklyOpt = computed(() => {
  if (!weekly.value.length) return {}
  return {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(15,23,42,0.95)', borderColor: 'rgba(99,102,241,0.3)', textStyle: { color: '#e2e8f0' } },
    legend: { data: ['支出', '收入'], textStyle: { color: '#94a3b8', fontSize: 11 }, right: 0, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: weekly.value.map(w => w.label), axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(51,65,85,0.4)' } }, axisLabel: { color: '#94a3b8' } },
    series: [
      { name: '支出', type: 'bar', barWidth: '30%', itemStyle: { borderRadius: [4,4,0,0], color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#f43f5e' }, { offset: 1, color: '#f43f5e66' }] } },
        data: weekly.value.map(w => w.expense), animationDuration: 1000 },
      { name: '收入', type: 'bar', barWidth: '30%', itemStyle: { borderRadius: [4,4,0,0], color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#10b981' }, { offset: 1, color: '#10b98166' }] } },
        data: weekly.value.map(w => w.income), animationDuration: 1000, animationDelay: 150 }
    ]
  }
})

// ECharts: risk gauge
const gaugeOpt = computed(() => {
  const score = risk.value.score || 0
  const color = score <= 25 ? '#10b981' : score <= 45 ? '#22d3ee' : score <= 65 ? '#f59e0b' : score <= 80 ? '#f97316' : '#ef4444'
  return {
    series: [{
      type: 'gauge', startAngle: 200, endAngle: -20, min: 0, max: 100,
      pointer: { show: false },
      progress: { show: true, width: 16, roundCap: true, itemStyle: { color } },
      axisLine: { lineStyle: { width: 16, color: [[1, '#1e293b']] } },
      axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
      detail: { valueAnimation: true, fontSize: 28, fontWeight: 'bold', color, formatter: '{value}', offsetCenter: [0, '10%'] },
      title: { show: true, offsetCenter: [0, '45%'], fontSize: 12, color: '#94a3b8' },
      data: [{ value: score, name: risk.value.label || '评估中' }],
      animationDuration: 1500, animationEasing: 'cubicOut'
    }]
  }
})

// Helpers
function fmtMoney(v) {
  if (v == null) return '0.00'
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function fmtPct(v) { return Number(v || 0).toFixed(1) }
function fmtDate(d) { const dt = new Date(d); return `${dt.getMonth()+1}/${dt.getDate()}` }

// Export PDF
async function exportPdf() {
  exportingPdf.value = true
  try {
    const html2pdf = (await import('html2pdf.js')).default
    const el = document.getElementById('report-print-area')
    await html2pdf().set({
      margin: [8, 8, 8, 8],
      filename: `财务月报_${selectedYear.value}_${String(selectedMonth.value).padStart(2,'0')}.pdf`,
      image: { type: 'jpeg', quality: 0.95 },
      html2canvas: { scale: 2, useCORS: true, letterRendering: true },
      jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
      pagebreak: { mode: ['avoid-all', 'css'] }
    }).from(el).save()
  } catch (e) {
    alert('PDF 导出失败: ' + e.message)
  } finally { exportingPdf.value = false }
}

// Export Excel
async function exportExcel() {
  exportingExcel.value = true
  try {
    const res = await api.get('/reports/export/excel', {
      params: { year: selectedYear.value, month: selectedMonth.value },
      responseType: 'blob'
    })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `report_${selectedYear.value}_${String(selectedMonth.value).padStart(2,'0')}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch { alert('Excel 导出失败') }
  finally { exportingExcel.value = false }
}

// Screenshot
async function shareScreenshot() {
  try {
    const html2canvas = (await import('html2canvas')).default
    const el = document.getElementById('report-print-area')
    const canvas = await html2canvas(el, { backgroundColor: '#0f172a', scale: 2 })
    canvas.toBlob(blob => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `report_${selectedYear.value}_${String(selectedMonth.value).padStart(2,'0')}.png`
      a.click()
      URL.revokeObjectURL(url)
    })
  } catch (e) { alert('截图失败: ' + e.message) }
}

const renderedAi = computed(() => aiAnalysis.value ? renderSafeMarkdown(aiAnalysis.value) : '')

onMounted(() => {
  loadReport()
  document.addEventListener('click', closeDropdown)
})
</script>

<template>
  <div class="min-h-screen bg-slate-900 p-4 md:p-6 lg:p-8">
    <!-- ======== TOP BAR ======== -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-white tracking-tight">月度财务报告</h1>
        <p class="text-slate-400 text-xs mt-1">AI 驱动的深度财务分析</p>
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <!-- Month selector -->
        <div class="month-dropdown relative">
          <button @click.stop="monthDropdownOpen = !monthDropdownOpen"
            class="flex items-center gap-2 px-4 py-2 bg-slate-800 border border-slate-700/60 rounded-xl text-white text-sm font-medium hover:border-indigo-500/50 transition-colors">
            <svg class="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" /></svg>
            {{ selectedLabel }}
            <svg class="w-4 h-4 text-slate-400 transition-transform" :class="{ 'rotate-180': monthDropdownOpen }" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>
          </button>
          <div v-if="monthDropdownOpen"
            class="absolute right-0 top-full mt-1 w-44 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl z-50 py-1 max-h-64 overflow-y-auto">
            <button v-for="opt in monthOptions" :key="`${opt.year}-${opt.month}`"
              @click="selectMonth(opt)"
              class="w-full text-left px-4 py-2 text-sm transition-colors"
              :class="opt.year === selectedYear && opt.month === selectedMonth ? 'text-indigo-400 bg-indigo-500/10' : 'text-slate-300 hover:bg-slate-700/50'">
              {{ opt.label }}
            </button>
          </div>
        </div>
        <!-- Actions -->
        <button @click="exportPdf" :disabled="exportingPdf || loading"
          class="flex items-center gap-1.5 px-3.5 py-2 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl text-xs font-medium hover:bg-rose-500/20 transition-all disabled:opacity-40">
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>
          {{ exportingPdf ? '生成中...' : 'PDF' }}
        </button>
        <button @click="exportExcel" :disabled="exportingExcel || loading"
          class="flex items-center gap-1.5 px-3.5 py-2 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl text-xs font-medium hover:bg-emerald-500/20 transition-all disabled:opacity-40">
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>
          {{ exportingExcel ? '导出中...' : 'Excel' }}
        </button>
        <button @click="shareScreenshot"
          class="flex items-center gap-1.5 px-3.5 py-2 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-xl text-xs font-medium hover:bg-indigo-500/20 transition-all">
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z" /></svg>
          截图
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-40">
      <div class="text-center">
        <div class="w-12 h-12 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mx-auto mb-4" />
        <p class="text-slate-400 text-sm">正在生成月度报告...</p>
      </div>
    </div>

    <!-- ======== REPORT CONTENT ======== -->
    <div v-else-if="reportData" id="report-print-area">
      <!-- REPORT HEADER -->
      <div class="relative overflow-hidden bg-gradient-to-r from-slate-800 via-slate-800 to-indigo-950 border border-slate-700/60 rounded-2xl p-6 md:p-8 mb-6">
        <div class="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full -translate-y-1/2 translate-x-1/2" />
        <div class="relative flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <svg class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z" /></svg>
            </div>
            <div>
              <h2 class="text-xl font-bold text-white">{{ selectedLabel }} 财务报告</h2>
              <p class="text-xs text-slate-400 mt-0.5">{{ userStore.user?.username }} · 生成于 {{ new Date().toLocaleDateString('zh-CN') }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span class="px-3 py-1.5 rounded-lg text-xs font-semibold"
              :class="s.savings_rate >= 30 ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : s.savings_rate >= 10 ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'">
              储蓄率 {{ fmtPct(s.savings_rate) }}%
            </span>
            <span class="px-3 py-1.5 rounded-lg text-xs font-semibold"
              :class="s.balance >= 0 ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'">
              {{ s.balance >= 0 ? '盈余' : '超支' }} ¥{{ fmtMoney(Math.abs(s.balance)) }}
            </span>
          </div>
        </div>
      </div>

      <!-- SUMMARY CARDS (5 cards) -->
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-4 group hover:border-slate-600 transition-colors">
          <p class="text-[11px] text-slate-500 font-medium uppercase tracking-wider mb-1">总收入</p>
          <p class="text-xl font-bold text-emerald-400">¥{{ fmtMoney(animIncome) }}</p>
          <div class="flex items-center gap-1 mt-1.5">
            <svg v-if="comp.income_change >= 0" class="w-3 h-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" /></svg>
            <svg v-else class="w-3 h-3 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 4.5l-15 15m0 0h11.25m-11.25 0V8.25" /></svg>
            <span class="text-[10px]" :class="comp.income_change >= 0 ? 'text-emerald-400' : 'text-rose-400'">{{ Math.abs(comp.income_change_pct || 0) }}%</span>
            <span class="text-[10px] text-slate-600">环比</span>
          </div>
        </div>
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-4 group hover:border-slate-600 transition-colors">
          <p class="text-[11px] text-slate-500 font-medium uppercase tracking-wider mb-1">总支出</p>
          <p class="text-xl font-bold text-rose-400">¥{{ fmtMoney(animExpense) }}</p>
          <div class="flex items-center gap-1 mt-1.5">
            <svg v-if="comp.expense_change <= 0" class="w-3 h-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 4.5l-15 15m0 0h11.25m-11.25 0V8.25" /></svg>
            <svg v-else class="w-3 h-3 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" /></svg>
            <span class="text-[10px]" :class="comp.expense_change <= 0 ? 'text-emerald-400' : 'text-rose-400'">{{ Math.abs(comp.expense_change_pct || 0) }}%</span>
            <span class="text-[10px] text-slate-600">环比</span>
          </div>
        </div>
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-4 group hover:border-slate-600 transition-colors">
          <p class="text-[11px] text-slate-500 font-medium uppercase tracking-wider mb-1">结余</p>
          <p class="text-xl font-bold" :class="s.balance >= 0 ? 'text-indigo-400' : 'text-rose-400'">¥{{ fmtMoney(animBalance) }}</p>
          <p class="text-[10px] text-slate-600 mt-1.5">{{ s.count }} 笔交易</p>
        </div>
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-4 group hover:border-slate-600 transition-colors">
          <p class="text-[11px] text-slate-500 font-medium uppercase tracking-wider mb-1">日均支出</p>
          <p class="text-xl font-bold text-cyan-400">¥{{ fmtMoney(animAvgDaily) }}</p>
          <p class="text-[10px] text-slate-600 mt-1.5">单笔均 ¥{{ fmtMoney(s.avg_transaction) }}</p>
        </div>
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-4 group hover:border-slate-600 transition-colors">
          <p class="text-[11px] text-slate-500 font-medium uppercase tracking-wider mb-1">收入笔数</p>
          <p class="text-xl font-bold text-amber-400">{{ s.income_count || 0 }}</p>
          <p class="text-[10px] text-slate-600 mt-1.5">收入来源</p>
        </div>
      </div>

      <!-- RISK + CHARTS ROW -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 mb-6">
        <!-- Risk Score -->
        <div class="lg:col-span-3 bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5 flex flex-col items-center justify-center">
          <h3 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">财务健康评分</h3>
          <div class="w-48 h-40">
            <v-chart v-if="reportData" :option="gaugeOpt" autoresize class="w-full h-full" />
          </div>
          <div class="text-center mt-2">
            <span class="text-sm font-bold"
              :class="risk.level === 'excellent' ? 'text-emerald-400' : risk.level === 'good' ? 'text-cyan-400' : risk.level === 'moderate' ? 'text-amber-400' : risk.level === 'warning' ? 'text-orange-400' : 'text-rose-400'">
              {{ risk.label }}
            </span>
            <p class="text-[10px] text-slate-500 mt-1">综合评估: {{ risk.score }}/100</p>
          </div>
        </div>

        <!-- Daily Trend -->
        <div class="lg:col-span-5 bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5">
          <div class="flex items-center justify-between mb-3">
            <div>
              <h3 class="text-sm font-semibold text-white">收支趋势</h3>
              <p class="text-[10px] text-slate-500">每日收入与支出走势</p>
            </div>
            <div class="flex items-center gap-3">
              <div class="flex items-center gap-1"><div class="w-2 h-2 rounded-full bg-rose-500" /><span class="text-[10px] text-slate-400">支出</span></div>
              <div class="flex items-center gap-1"><div class="w-2 h-2 rounded-full bg-emerald-500" /><span class="text-[10px] text-slate-400">收入</span></div>
            </div>
          </div>
          <div class="h-[220px]">
            <v-chart v-if="reportData.daily_trend?.length" :option="trendOpt" autoresize class="w-full h-full" />
            <div v-else class="h-full flex items-center justify-center text-slate-600 text-sm">暂无数据</div>
          </div>
        </div>

        <!-- Category Pie -->
        <div class="lg:col-span-4 bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5">
          <div class="mb-3">
            <h3 class="text-sm font-semibold text-white">支出分类</h3>
            <p class="text-[10px] text-slate-500">本月消费结构</p>
          </div>
          <div class="flex items-center gap-4">
            <div class="w-[160px] h-[160px] flex-shrink-0 relative">
              <v-chart v-if="cats.length" :option="pieOpt" autoresize class="w-full h-full" />
              <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div class="text-center">
                  <p class="text-[9px] text-slate-500 uppercase">Total</p>
                  <p class="text-sm font-bold text-white">¥{{ fmtMoney(s.expense) }}</p>
                </div>
              </div>
            </div>
            <div class="flex-1 space-y-1.5 min-w-0">
              <div v-for="c in cats.slice(0, 6)" :key="c.name" class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full flex-shrink-0" :style="{ background: c.color }" />
                <span class="text-[11px] text-slate-400 truncate flex-1">{{ c.name }}</span>
                <span class="text-[11px] text-slate-300 font-medium">{{ c.percentage }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- CATEGORY DETAIL + WEEKLY -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
        <!-- Category bars -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5">
          <h3 class="text-sm font-semibold text-white mb-4">分类明细排行</h3>
          <div class="space-y-3">
            <div v-for="(c, i) in cats" :key="c.name" class="group">
              <div class="flex items-center justify-between mb-1">
                <div class="flex items-center gap-2">
                  <span class="text-[10px] text-slate-600 w-4 text-right">{{ i + 1 }}</span>
                  <div class="w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold" :style="{ background: c.color + '20', color: c.color }">
                    {{ c.icon || c.name[0] }}
                  </div>
                  <span class="text-xs text-slate-300">{{ c.name }}</span>
                </div>
                <div class="flex items-center gap-3">
                  <span class="text-[10px] text-slate-500">{{ c.count }}笔</span>
                  <span class="text-xs font-semibold text-white">¥{{ fmtMoney(c.amount) }}</span>
                </div>
              </div>
              <div class="ml-8 h-1.5 bg-slate-700/40 rounded-full overflow-hidden">
                <div class="h-full rounded-full transition-all duration-1000 ease-out" :style="{ width: c.percentage + '%', background: `linear-gradient(90deg, ${c.color}, ${c.color}88)` }" />
              </div>
            </div>
            <div v-if="!cats.length" class="py-8 text-center text-slate-600 text-xs">暂无分类数据</div>
          </div>
        </div>

        <!-- Weekly bar chart -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5">
          <h3 class="text-sm font-semibold text-white mb-1">周度对比</h3>
          <p class="text-[10px] text-slate-500 mb-3">各周收入与支出对比</p>
          <div class="h-[260px]">
            <v-chart v-if="weekly.length" :option="weeklyOpt" autoresize class="w-full h-full" />
            <div v-else class="h-full flex items-center justify-center text-slate-600 text-sm">暂无数据</div>
          </div>
        </div>
      </div>

      <!-- ANOMALY ALERTS + SAVINGS TIPS -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
        <!-- Anomaly alerts -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5">
          <div class="flex items-center gap-2 mb-4">
            <div class="w-7 h-7 rounded-lg bg-rose-500/10 flex items-center justify-center">
              <svg class="w-4 h-4 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>
            </div>
            <h3 class="text-sm font-semibold text-white">风险预警</h3>
          </div>
          <div class="space-y-3">
            <div v-for="a in anomalies" :key="a.title"
              class="flex items-start gap-3 p-3 rounded-xl"
              :class="a.severity === 'high' ? 'bg-rose-500/5 border border-rose-500/10' : a.severity === 'medium' ? 'bg-amber-500/5 border border-amber-500/10' : 'bg-slate-700/30 border border-slate-700/30'">
              <div class="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                :class="a.severity === 'high' ? 'bg-rose-500/20' : a.severity === 'medium' ? 'bg-amber-500/20' : 'bg-slate-600/30'">
                <svg v-if="a.severity === 'high'" class="w-3 h-3 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>
                <svg v-else class="w-3 h-3 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" /></svg>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-xs font-semibold" :class="a.severity === 'high' ? 'text-rose-300' : 'text-amber-300'">{{ a.title }}</p>
                <p class="text-[11px] text-slate-400 mt-0.5">{{ a.detail }}</p>
              </div>
            </div>
            <div v-if="!anomalies.length" class="flex items-center gap-3 p-3 bg-emerald-500/5 border border-emerald-500/10 rounded-xl">
              <div class="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center">
                <svg class="w-3 h-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
              </div>
              <p class="text-xs text-emerald-300">本月消费结构健康，未检测到明显异常</p>
            </div>
          </div>
        </div>

        <!-- Quick savings tips -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5">
          <div class="flex items-center gap-2 mb-4">
            <div class="w-7 h-7 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <svg class="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" /></svg>
            </div>
            <h3 class="text-sm font-semibold text-white">节省建议</h3>
          </div>
          <div class="space-y-3">
            <div v-for="(tip, i) in [
              { icon: '📊', title: '预算法则', desc: '使用 50/30/20 法则：50% 必要支出、30% 个人消费、20% 储蓄投资', color: 'indigo' },
              { icon: '🎯', title: '消费上限', desc: cats.length ? `建议将${cats[0]?.name}类月支出控制在 ¥${fmtMoney(cats[0]?.amount * 0.8)}` : '设定各分类月度预算上限', color: 'violet' },
              { icon: '📝', title: '记账习惯', desc: '保持每日记账，每周复盘一次消费结构', color: 'cyan' },
              { icon: '🏦', title: '应急基金', desc: '目标建立 3-6 个月生活费的应急储备金', color: 'amber' }
            ]" :key="i"
              class="flex items-start gap-3 p-3 bg-slate-700/20 border border-slate-700/30 rounded-xl hover:border-slate-600/50 transition-colors">
              <span class="text-base mt-0.5">{{ tip.icon }}</span>
              <div>
                <p class="text-xs font-semibold text-slate-200">{{ tip.title }}</p>
                <p class="text-[11px] text-slate-400 mt-0.5">{{ tip.desc }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- AI ANALYSIS -->
      <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5 mb-6">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>
            </div>
            <div>
              <h3 class="text-sm font-semibold text-white">AI 深度分析</h3>
              <p class="text-[10px] text-indigo-400">Powered by DeepSeek · 流式生成</p>
            </div>
          </div>
          <button @click="loadAiAnalysis" :disabled="aiLoading"
            class="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-500 to-violet-600 text-white rounded-xl text-xs font-medium hover:shadow-lg hover:shadow-indigo-500/25 transition-all disabled:opacity-50">
            <svg class="w-3.5 h-3.5" :class="{ 'animate-spin': aiLoading }" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" /></svg>
            {{ aiLoading ? '分析中...' : '生成 AI 分析' }}
          </button>
        </div>
        <div v-if="aiLoading && !aiAnalysis" class="space-y-3 py-6">
          <div class="flex items-center gap-3 text-slate-400 text-sm">
            <div class="flex gap-1">
              <div class="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style="animation-delay:0ms" />
              <div class="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style="animation-delay:150ms" />
              <div class="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style="animation-delay:300ms" />
            </div>
            正在深度分析您的财务数据...
          </div>
        </div>
        <div v-else-if="aiAnalysis" class="ai-content text-sm text-slate-300 leading-relaxed" v-html="renderedAi" />
        <div v-else class="text-center py-10 text-slate-600 text-sm">
          <p>点击上方按钮，AI 将基于您的财务数据生成深度分析报告</p>
        </div>
      </div>

      <!-- TRANSACTIONS TABLE -->
      <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5 mb-6">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-semibold text-white">交易明细</h3>
          <span class="text-[10px] text-slate-500">最近 {{ txns.length }} 笔</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="border-b border-slate-700/50">
                <th class="text-left py-2.5 text-[10px] text-slate-500 font-medium uppercase tracking-wider">日期</th>
                <th class="text-left py-2.5 text-[10px] text-slate-500 font-medium uppercase tracking-wider">类型</th>
                <th class="text-left py-2.5 text-[10px] text-slate-500 font-medium uppercase tracking-wider">分类</th>
                <th class="text-left py-2.5 text-[10px] text-slate-500 font-medium uppercase tracking-wider">描述</th>
                <th class="text-right py-2.5 text-[10px] text-slate-500 font-medium uppercase tracking-wider">金额</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in txns" :key="t.id" class="border-b border-slate-700/20 hover:bg-slate-700/20 transition-colors">
                <td class="py-2.5 text-slate-400">{{ fmtDate(t.date) }}</td>
                <td class="py-2.5">
                  <span class="px-2 py-0.5 rounded text-[10px] font-medium"
                    :class="t.type === 'income' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'">
                    {{ t.type === 'income' ? '收入' : '支出' }}
                  </span>
                </td>
                <td class="py-2.5 text-slate-300">{{ t.category?.name || '未分类' }}</td>
                <td class="py-2.5 text-slate-400 max-w-[180px] truncate">{{ t.description || '-' }}</td>
                <td class="py-2.5 text-right font-semibold" :class="t.type === 'income' ? 'text-emerald-400' : 'text-rose-400'">
                  {{ t.type === 'income' ? '+' : '-' }}¥{{ fmtMoney(t.amount) }}
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="!txns.length" class="py-10 text-center text-slate-600 text-xs">暂无交易记录</div>
        </div>
      </div>

      <!-- FOOTER -->
      <div class="text-center py-6 border-t border-slate-700/30">
        <p class="text-[10px] text-slate-600">AI 智能记账系统 · {{ selectedLabel }} 月度报告 · {{ new Date().toLocaleString('zh-CN') }}</p>
      </div>
    </div>

    <!-- Empty -->
    <div v-else class="flex flex-col items-center justify-center py-40">
      <p class="text-slate-500 text-sm mb-4">暂无报告数据</p>
      <button @click="loadReport" class="px-4 py-2 bg-indigo-500 text-white rounded-xl text-sm">重新加载</button>
    </div>
  </div>
</template>

<style scoped>
.ai-content :deep(h2) { font-size: 0.95rem; font-weight: 600; color: #e2e8f0; margin: 1rem 0 0.5rem; padding-bottom: 0.3rem; border-bottom: 1px solid rgba(51,65,85,0.5); }
.ai-content :deep(h2:first-child) { margin-top: 0; }
.ai-content :deep(h3) { font-size: 0.85rem; font-weight: 600; color: #cbd5e1; margin: 0.6rem 0 0.3rem; }
.ai-content :deep(p) { margin: 0.25rem 0; }
.ai-content :deep(ul), .ai-content :deep(ol) { padding-left: 1.2rem; margin: 0.25rem 0; }
.ai-content :deep(li) { margin: 0.15rem 0; }
.ai-content :deep(strong) { color: #f1f5f9; font-weight: 600; }
.ai-content :deep(blockquote) { border-left: 3px solid #6366f1; padding-left: 0.75rem; margin: 0.5rem 0; color: #94a3b8; font-style: italic; }
.ai-content :deep(code) { background: rgba(51,65,85,0.5); padding: 0.1rem 0.3rem; border-radius: 0.2rem; font-size: 0.8rem; }
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(100,116,139,0.3); border-radius: 4px; }
</style>
