<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  callChain: { type: Array, default: () => [] }
})

const expanded = ref(null)

const agentConfig = {
  ocr: { label: 'OCR Agent', color: '#06b6d4', bg: 'bg-cyan-500/10', border: 'border-cyan-500/30', icon: 'camera' },
  finance: { label: 'Finance Agent', color: '#6366f1', bg: 'bg-indigo-500/10', border: 'border-indigo-500/30', icon: 'calculator' },
  risk: { label: 'Risk Agent', color: '#f59e0b', bg: 'bg-amber-500/10', border: 'border-amber-500/30', icon: 'shield' },
  recommendation: { label: 'Recommendation Agent', color: '#10b981', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', icon: 'lightbulb' },
  tax: { label: 'Tax Agent', color: '#8b5cf6', bg: 'bg-violet-500/10', border: 'border-violet-500/30', icon: 'receipt' },
  budget: { label: 'Budget Agent', color: '#ec4899', bg: 'bg-pink-500/10', border: 'border-pink-500/30', icon: 'wallet' },
  investment: { label: 'Investment Agent', color: '#14b8a6', bg: 'bg-teal-500/10', border: 'border-teal-500/30', icon: 'chart' },
  report: { label: 'Report Agent', color: '#f97316', bg: 'bg-orange-500/10', border: 'border-orange-500/30', icon: 'document' },
}

function getAgent(name) {
  return agentConfig[name] || { label: name, color: '#94a3b8', bg: 'bg-slate-500/10', border: 'border-slate-500/30', icon: 'cpu' }
}

const agentIcons = {
  camera: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" /><path stroke-linecap="round" stroke-linejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z" /></svg>`,
  calculator: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 15.75V18m-7.5-6.75h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25v-.008zm2.498-6.75h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007v-.008zm2.504-6.75h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008v-.008zm2.498-6.75h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008v-.008zM8.25 6h7.5v2.25h-7.5V6zM12 2.25c-1.892 0-3.758.11-5.593.322C5.307 2.7 4.5 3.65 4.5 4.757V19.5a2.25 2.25 0 002.25 2.25h10.5a2.25 2.25 0 002.25-2.25V4.757c0-1.108-.806-2.057-1.907-2.185A48.507 48.507 0 0012 2.25z" /></svg>`,
  shield: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" /></svg>`,
  lightbulb: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" /></svg>`,
  cpu: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 6.75v10.5a2.25 2.25 0 002.25 2.25z" /></svg>`,
  receipt: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>`,
  wallet: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 12a2.25 2.25 0 00-2.25-2.25H15a3 3 0 11-6 0H5.25A2.25 2.25 0 003 12m18 0v6a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 18v-6m18 0V9M3 12V9m18 0a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 9m18 0V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v3" /></svg>`,
  chart: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" /></svg>`,
  document: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>`,
  wrench: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="M11.42 15.17l-5.1-5.1m0 0L11.42 4.97m-5.1 5.1H21M3 12a9 9 0 1118 0 9 9 0 01-18 0z" /></svg>`,
}

function isWorkflowStep(step) {
  return step.type === 'workflow_step' || step.step
}

function isToolCall(step) {
  return step.type === 'tool_call' || step.tool
}

function getStepLabel(step) {
  if (isToolCall(step)) return step.tool || 'Tool'
  if (isWorkflowStep(step)) return step.step || step.agent || 'Step'
  return step.agent || 'Agent'
}

function getStatusColor(status) {
  if (status === 'ok' || status === 'success') return '#10b981'
  if (status === 'running') return '#6366f1'
  if (status === 'skipped') return '#94a3b8'
  return '#ef4444'
}
</script>

<template>
  <div v-if="callChain.length > 0" class="agent-chain-container">
    <div class="flex items-center gap-2 mb-3">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 text-slate-400">
        <path stroke-linecap="round" stroke-linejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
      </svg>
      <span class="text-sm font-medium text-slate-300">Agent 调用链</span>
      <span class="text-xs text-slate-500">{{ callChain.length }} 步</span>
    </div>

    <div class="flex items-start gap-0 overflow-x-auto pb-2">
      <div v-for="(step, i) in callChain" :key="i" class="flex items-start flex-shrink-0">
        <!-- Connector arrow -->
        <div v-if="i > 0" class="flex items-center pt-5 px-1">
          <svg class="w-6 h-4 text-slate-600" viewBox="0 0 24 16" fill="none">
            <path d="M0 8h20m-4-4l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>

        <!-- Agent/Workflow/Tool node -->
        <div
          class="chain-node rounded-xl p-3 min-w-[140px] cursor-pointer transition-all duration-200 hover:scale-[1.02]"
          :class="[
            isToolCall(step) ? 'bg-slate-700/30 border-slate-600/30' : getAgent(step.agent || step.agent_name).bg,
            isToolCall(step) ? '' : getAgent(step.agent || step.agent_name).border,
            step.status === 'error' || step.status === 'failed' ? 'border-red-500/50 bg-red-500/10' : ''
          ]"
          :style="{ border: `1px solid ${step.status === 'error' || step.status === 'failed' ? '#ef4444' : isToolCall(step) ? '#475569' : getAgent(step.agent || step.agent_name).color}33` }"
          @click="expanded = expanded === i ? null : i"
        >
          <div class="flex items-center gap-2 mb-1.5">
            <!-- Tool icon -->
            <span v-if="isToolCall(step)" v-html="agentIcons.wrench" class="text-slate-400"></span>
            <!-- Agent icon -->
            <span v-else v-html="agentIcons[getAgent(step.agent || step.agent_name).icon]" :style="{ color: step.status === 'error' || step.status === 'failed' ? '#ef4444' : getAgent(step.agent || step.agent_name).color }"></span>
            <span class="text-xs font-semibold" :style="{ color: isToolCall(step) ? '#94a3b8' : (step.status === 'error' || step.status === 'failed' ? '#ef4444' : getAgent(step.agent || step.agent_name).color) }">
              {{ isToolCall(step) ? step.tool : (step.step || getAgent(step.agent || step.agent_name).label) }}
            </span>
          </div>

          <div class="flex items-center gap-2">
            <span class="text-[10px] font-mono text-slate-400">{{ (step.duration_ms || 0).toFixed(0) }}ms</span>
            <span v-if="step.status === 'ok' || step.status === 'success'" class="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-medium">OK</span>
            <span v-else-if="step.status === 'running'" class="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 font-medium">RUN</span>
            <span v-else-if="step.status === 'skipped'" class="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-500/20 text-slate-400 font-medium">SKIP</span>
            <span v-else class="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400 font-medium">FAIL</span>
          </div>

          <!-- Expanded details -->
          <Transition name="fade">
            <div v-if="expanded === i" class="mt-2 pt-2 border-t border-slate-700/50">
              <div v-if="step.input_keys?.length" class="mb-1">
                <span class="text-[10px] text-slate-500 block">输入:</span>
                <span v-for="k in step.input_keys" :key="k" class="text-[10px] px-1 py-0.5 rounded bg-slate-700/50 text-cyan-400 mr-1">{{ k }}</span>
              </div>
              <div v-if="step.output_keys?.length" class="mb-1">
                <span class="text-[10px] text-slate-500 block">输出:</span>
                <span v-for="k in step.output_keys" :key="k" class="text-[10px] px-1 py-0.5 rounded bg-slate-700/50 text-emerald-400 mr-1">{{ k }}</span>
              </div>
              <div v-if="step.params" class="mb-1">
                <span class="text-[10px] text-slate-500 block">参数:</span>
                <span class="text-[10px] text-slate-400">{{ step.params }}</span>
              </div>
              <div v-if="step.data_keys?.length">
                <span class="text-[10px] text-slate-500 block">数据键:</span>
                <span v-for="k in step.data_keys" :key="k" class="text-[10px] px-1 py-0.5 rounded bg-slate-700/50 text-amber-400 mr-1">{{ k }}</span>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
