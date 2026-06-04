<script setup>
import { ref, computed, onMounted } from 'vue'
import { renderSafeMarkdown } from '@/utils/safeMarkdown'
import api from '@/utils/api'

const loading = ref(false)
const analyzing = ref(false)
const period = ref(3)
const data = ref(null)
const aiContent = ref('')

// Run analysis
async function runAnalysis() {
  loading.value = true
  analyzing.value = true
  aiContent.value = ''
  try {
    const token = localStorage.getItem('token')
    const resp = await fetch(`/api/agent/analyze/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ period: period.value })
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
        try {
          const parsed = JSON.parse(d)
          if (parsed.type === 'data') {
            data.value = parsed.payload
            loading.value = false
          } else if (parsed.type === 'content') {
            aiContent.value += parsed.payload
          } else if (parsed.type === 'done') {
            analyzing.value = false
          } else if (parsed.type === 'error') {
            analyzing.value = false
          }
        } catch {}
      }
    }
  } catch (e) {
    console.error('Agent analysis failed:', e)
  } finally {
    loading.value = false
    analyzing.value = false
  }
}

// Computed
const subs = computed(() => data.value?.subscriptions || [])
const fixed = computed(() => data.value?.fixed_expenses || [])
const anomalies = computed(() => data.value?.anomalies || [])
const highFreq = computed(() => data.value?.high_frequency || [])
const tags = computed(() => data.value?.tag_analysis || [])
const budget = computed(() => data.value?.budget_allocation || [])
const totalExpense = computed(() => data.value?.total_expense || 0)
const monthlyAvg = computed(() => data.value?.monthly_avg_expense || 0)
const subAnnual = computed(() => subs.value.reduce((s, x) => s + x.annual_cost, 0))

function fmt(v) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) }
const renderedAi = computed(() => aiContent.value ? renderSafeMarkdown(aiContent.value) : '')

// Tag colors
const tagColors = { '工作': '#6366f1', '外卖': '#f97316', '娱乐': '#ec4899', '学习': '#06b6d4', '投资': '#10b981' }
function tagColor(tag) { return tagColors[tag] || '#6b7280' }

onMounted(() => runAnalysis())
</script>

<template>
  <div class="min-h-screen bg-slate-900 p-4 md:p-6 lg:p-8">
    <!-- HEADER -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
      <div>
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>
          </div>
          <div>
            <h1 class="text-2xl font-bold text-white">AI 记账 Agent</h1>
            <p class="text-xs text-slate-400">规则引擎 + LLM 混合架构 · 自动分析消费模式</p>
          </div>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <select v-model="period" class="bg-slate-800 border border-slate-700/60 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500/50">
          <option :value="1">近1个月</option>
          <option :value="3">近3个月</option>
          <option :value="6">近6个月</option>
        </select>
        <button @click="runAnalysis" :disabled="loading"
          class="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-500 to-violet-600 text-white rounded-xl text-sm font-medium hover:shadow-lg hover:shadow-indigo-500/25 transition-all disabled:opacity-50">
          <svg class="w-4 h-4" :class="{ 'animate-spin': loading }" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" /></svg>
          {{ loading ? '分析中...' : '重新分析' }}
        </button>
      </div>
    </div>

    <!-- LOADING -->
    <div v-if="loading && !data" class="flex items-center justify-center py-40">
      <div class="text-center">
        <div class="w-14 h-14 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mx-auto mb-4" />
        <p class="text-slate-400 text-sm">Agent 正在分析您的消费数据...</p>
        <p class="text-slate-600 text-xs mt-1">规则引擎扫描 + AI 深度分析</p>
      </div>
    </div>

    <!-- CONTENT -->
    <template v-if="data">
      <!-- SUMMARY STRIP -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-4">
          <p class="text-[10px] text-slate-500 uppercase tracking-wider">分析周期</p>
          <p class="text-lg font-bold text-white mt-1">近 {{ period }} 个月</p>
        </div>
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-4">
          <p class="text-[10px] text-slate-500 uppercase tracking-wider">总支出</p>
          <p class="text-lg font-bold text-rose-400 mt-1">¥{{ fmt(totalExpense) }}</p>
        </div>
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-4">
          <p class="text-[10px] text-slate-500 uppercase tracking-wider">月均支出</p>
          <p class="text-lg font-bold text-amber-400 mt-1">¥{{ fmt(monthlyAvg) }}</p>
        </div>
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-4">
          <p class="text-[10px] text-slate-500 uppercase tracking-wider">订阅年费</p>
          <p class="text-lg font-bold text-violet-400 mt-1">¥{{ fmt(subAnnual) }}</p>
        </div>
      </div>

      <!-- SUBSCRIPTIONS + FIXED -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
        <!-- Subscriptions -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5">
          <div class="flex items-center gap-2 mb-4">
            <div class="w-7 h-7 rounded-lg bg-violet-500/10 flex items-center justify-center">
              <svg class="w-4 h-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" /></svg>
            </div>
            <h3 class="text-sm font-semibold text-white">订阅服务</h3>
            <span class="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400">{{ subs.length }} 个</span>
          </div>
          <div class="space-y-2.5">
            <div v-for="s in subs" :key="s.name"
              class="flex items-center justify-between p-3 bg-slate-700/20 border border-slate-700/30 rounded-xl hover:border-slate-600/50 transition-colors">
              <div class="min-w-0">
                <p class="text-xs font-medium text-slate-200 truncate">{{ s.name }}</p>
                <p class="text-[10px] text-slate-500">{{ s.type }} · {{ s.frequency }} · {{ s.occurrences }}次</p>
              </div>
              <div class="text-right flex-shrink-0 ml-3">
                <p class="text-xs font-semibold text-white">¥{{ fmt(s.amount) }}</p>
                <p class="text-[10px] text-rose-400">年费 ¥{{ fmt(s.annual_cost) }}</p>
              </div>
            </div>
            <div v-if="!subs.length" class="py-6 text-center text-slate-600 text-xs">未检测到订阅服务</div>
          </div>
        </div>

        <!-- Fixed expenses -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5">
          <div class="flex items-center gap-2 mb-4">
            <div class="w-7 h-7 rounded-lg bg-cyan-500/10 flex items-center justify-center">
              <svg class="w-4 h-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" /></svg>
            </div>
            <h3 class="text-sm font-semibold text-white">固定支出</h3>
            <span class="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400">{{ fixed.length }} 项</span>
          </div>
          <div class="space-y-2.5">
            <div v-for="f in fixed" :key="f.name"
              class="flex items-center justify-between p-3 bg-slate-700/20 border border-slate-700/30 rounded-xl">
              <div class="min-w-0">
                <p class="text-xs font-medium text-slate-200 truncate">{{ f.name }}</p>
                <p class="text-[10px] text-slate-500">{{ f.category }} · {{ f.frequency }} · 规律性 {{ (f.regularity * 100).toFixed(0) }}%</p>
              </div>
              <p class="text-xs font-semibold text-white flex-shrink-0 ml-3">¥{{ fmt(f.amount) }}</p>
            </div>
            <div v-if="!fixed.length" class="py-6 text-center text-slate-600 text-xs">未检测到固定支出</div>
          </div>
        </div>
      </div>

      <!-- ANOMALIES + HIGH FREQ -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
        <!-- Anomalies -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5">
          <div class="flex items-center gap-2 mb-4">
            <div class="w-7 h-7 rounded-lg bg-rose-500/10 flex items-center justify-center">
              <svg class="w-4 h-4 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>
            </div>
            <h3 class="text-sm font-semibold text-white">异常消费</h3>
            <span class="ml-auto text-[10px] px-2 py-0.5 rounded-full" :class="anomalies.length ? 'bg-rose-500/10 text-rose-400' : 'bg-emerald-500/10 text-emerald-400'">
              {{ anomalies.length ? anomalies.length + ' 项' : '正常' }}
            </span>
          </div>
          <div class="space-y-2.5">
            <div v-for="a in anomalies.slice(0, 6)" :key="`${a.date}-${a.amount}`"
              class="p-3 rounded-xl border"
              :class="a.severity === 'high' ? 'bg-rose-500/5 border-rose-500/15' : 'bg-amber-500/5 border-amber-500/15'">
              <div class="flex items-center justify-between mb-1">
                <span class="text-xs font-medium" :class="a.severity === 'high' ? 'text-rose-300' : 'text-amber-300'">
                  {{ a.category }}
                </span>
                <span class="text-xs font-bold" :class="a.severity === 'high' ? 'text-rose-400' : 'text-amber-400'">
                  ¥{{ fmt(a.amount) }}
                </span>
              </div>
              <p class="text-[10px] text-slate-400">{{ a.reason }}</p>
              <p class="text-[10px] text-slate-600 mt-1">{{ a.date }} · z-score: {{ a.z_score }}</p>
            </div>
            <div v-if="!anomalies.length" class="flex items-center gap-3 p-3 bg-emerald-500/5 border border-emerald-500/10 rounded-xl">
              <svg class="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              <p class="text-xs text-emerald-300">消费模式正常，未检测到异常</p>
            </div>
          </div>
        </div>

        <!-- High frequency -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5">
          <div class="flex items-center gap-2 mb-4">
            <div class="w-7 h-7 rounded-lg bg-amber-500/10 flex items-center justify-center">
              <svg class="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" /></svg>
            </div>
            <h3 class="text-sm font-semibold text-white">高频消费</h3>
          </div>
          <div class="space-y-2.5">
            <div v-for="h in highFreq" :key="h.category"
              class="p-3 bg-slate-700/20 border border-slate-700/30 rounded-xl">
              <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                  <span class="text-xs font-medium text-slate-200">{{ h.category }}</span>
                  <span class="text-[9px] px-1.5 py-0.5 rounded" :class="h.level === '极高' ? 'bg-rose-500/10 text-rose-400' : 'bg-amber-500/10 text-amber-400'">
                    {{ h.level }}
                  </span>
                </div>
                <span class="text-[10px] text-slate-400">{{ h.count }}次 · 日均{{ h.daily_rate }}次</span>
              </div>
              <div class="flex items-center gap-3">
                <div class="flex-1 h-1.5 bg-slate-700/40 rounded-full overflow-hidden">
                  <div class="h-full rounded-full bg-amber-500" :style="{ width: Math.min(h.daily_rate * 25, 100) + '%' }" />
                </div>
                <span class="text-[10px] text-slate-400 flex-shrink-0">均 ¥{{ fmt(h.avg_amount) }}/笔</span>
              </div>
            </div>
            <div v-if="!highFreq.length" class="py-6 text-center text-slate-600 text-xs">消费频率正常</div>
          </div>
        </div>
      </div>

      <!-- AUTO TAGS + BUDGET -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
        <!-- Auto tags -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5">
          <div class="flex items-center gap-2 mb-4">
            <div class="w-7 h-7 rounded-lg bg-indigo-500/10 flex items-center justify-center">
              <svg class="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" /><path stroke-linecap="round" stroke-linejoin="round" d="M6 6h.008v.008H6V6z" /></svg>
            </div>
            <h3 class="text-sm font-semibold text-white">自动标签</h3>
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            <div v-for="t in tags" :key="t.tag"
              class="p-3 rounded-xl border border-slate-700/30 bg-slate-700/10 hover:border-slate-600/50 transition-colors">
              <div class="flex items-center gap-2 mb-2">
                <div class="w-3 h-3 rounded-full" :style="{ background: tagColor(t.tag) }" />
                <span class="text-xs font-semibold text-slate-200">{{ t.tag }}</span>
              </div>
              <p class="text-[10px] text-slate-400">{{ t.count }} 笔 · ¥{{ fmt(t.total) }}</p>
              <div class="mt-1.5 h-1 bg-slate-700/40 rounded-full overflow-hidden">
                <div class="h-full rounded-full transition-all" :style="{ width: (t.avg_confidence * 100) + '%', background: tagColor(t.tag) }" />
              </div>
              <p class="text-[9px] text-slate-600 mt-1">置信度 {{ (t.avg_confidence * 100).toFixed(0) }}%</p>
            </div>
          </div>
          <div v-if="!tags.length" class="py-6 text-center text-slate-600 text-xs">暂无标签数据</div>
        </div>

        <!-- Budget allocation -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5">
          <div class="flex items-center gap-2 mb-4">
            <div class="w-7 h-7 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <svg class="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" /></svg>
            </div>
            <h3 class="text-sm font-semibold text-white">预算建议</h3>
          </div>
          <div class="space-y-2.5">
            <div v-for="b in budget.slice(0, 6)" :key="b.category"
              class="p-3 bg-slate-700/20 border border-slate-700/30 rounded-xl">
              <div class="flex items-center justify-between mb-1.5">
                <div class="flex items-center gap-2">
                  <div class="w-2.5 h-2.5 rounded-full" :style="{ background: b.color }" />
                  <span class="text-xs text-slate-200">{{ b.category }}</span>
                </div>
                <span class="text-[10px] text-slate-500">{{ b.percentage }}%</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-[10px] text-slate-500">月均</span>
                <span class="text-xs text-slate-300">¥{{ fmt(b.monthly_avg) }}</span>
                <svg class="w-3 h-3 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" /></svg>
                <span class="text-xs font-semibold text-emerald-400">¥{{ fmt(b.suggested_budget) }}</span>
                <span v-if="b.savings_potential > 0" class="text-[9px] text-emerald-500 ml-auto">省 ¥{{ fmt(b.savings_potential) }}</span>
              </div>
            </div>
          </div>
          <div v-if="!budget.length" class="py-6 text-center text-slate-600 text-xs">暂无预算数据</div>
        </div>
      </div>

      <!-- AI EXPLANATION -->
      <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5 mb-6">
        <div class="flex items-center gap-3 mb-4">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>
          </div>
          <div>
            <h3 class="text-sm font-semibold text-white">Agent 深度分析</h3>
            <p class="text-[10px] text-indigo-400">规则引擎 + LLM 混合分析</p>
          </div>
        </div>
        <div v-if="analyzing && !aiContent" class="flex items-center gap-3 py-6 text-slate-400 text-sm">
          <div class="flex gap-1">
            <div class="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style="animation-delay:0ms" />
            <div class="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style="animation-delay:150ms" />
            <div class="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style="animation-delay:300ms" />
          </div>
          AI 正在生成深度分析...
        </div>
        <div v-else-if="aiContent" class="ai-content text-sm text-slate-300 leading-relaxed" v-html="renderedAi" />
        <div v-else class="py-6 text-center text-slate-600 text-sm">点击"重新分析"获取 Agent 分析</div>
      </div>
    </template>
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
.ai-content :deep(blockquote) { border-left: 3px solid #6366f1; padding-left: 0.75rem; margin: 0.5rem 0; color: #94a3b8; }
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(100,116,139,0.3); border-radius: 4px; }
</style>
