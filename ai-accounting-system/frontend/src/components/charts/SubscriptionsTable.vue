<template>
  <div class="subscriptions-table">
    <div v-if="loading" class="table-skeleton">
      <div v-for="i in 4" :key="i" class="skeleton-row"></div>
    </div>
    <table v-else-if="subscriptions.length" class="w-full text-sm">
      <thead>
        <tr class="border-b border-slate-700/50">
          <th class="text-left py-2 px-3 text-slate-400 font-medium">名称</th>
          <th class="text-right py-2 px-3 text-slate-400 font-medium">金额</th>
          <th class="text-center py-2 px-3 text-slate-400 font-medium">频率</th>
          <th class="text-right py-2 px-3 text-slate-400 font-medium">月费</th>
          <th class="text-right py-2 px-3 text-slate-400 font-medium">年费</th>
          <th class="text-center py-2 px-3 text-slate-400 font-medium">状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="sub in subscriptions" :key="sub.description"
            class="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
          <td class="py-2.5 px-3 text-slate-200">{{ sub.description }}</td>
          <td class="py-2.5 px-3 text-right text-slate-200 font-mono">
            ¥{{ sub.amount.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}
          </td>
          <td class="py-2.5 px-3 text-center text-slate-400">
            {{ frequencyLabel(sub.frequency) }}
          </td>
          <td class="py-2.5 px-3 text-right text-slate-200 font-mono">
            ¥{{ sub.monthly_cost.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}
          </td>
          <td class="py-2.5 px-3 text-right text-slate-200 font-mono">
            ¥{{ sub.annual_cost.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}
          </td>
          <td class="py-2.5 px-3 text-center">
            <span :class="statusClass(sub)" class="inline-block px-2 py-0.5 rounded-full text-xs font-medium">
              {{ statusLabel(sub) }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty-state">
      <p class="text-slate-500 text-sm">暂未检测到订阅消费</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  subscriptions: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

function frequencyLabel(freq) {
  const map = { monthly: '月付', weekly: '周付', yearly: '年付', quarterly: '季付' }
  return map[freq] || freq || '未知'
}

function statusLabel(sub) {
  if (sub.waste_type === 'unused') return '疑似未用'
  if (sub.waste_type === 'expensive') return '偏高'
  if (sub.risk === 'high') return '高风险'
  if (sub.risk === 'medium') return '中风险'
  return '正常'
}

function statusClass(sub) {
  if (sub.waste_type === 'unused' || sub.risk === 'high') return 'bg-red-500/20 text-red-400'
  if (sub.waste_type === 'expensive' || sub.risk === 'medium') return 'bg-amber-500/20 text-amber-400'
  return 'bg-emerald-500/20 text-emerald-400'
}
</script>

<style scoped>
.subscriptions-table {
  width: 100%;
}
.table-skeleton {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.skeleton-row {
  height: 36px;
  background: rgba(30, 41, 59, 0.5);
  border-radius: 6px;
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.7; }
}
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 120px;
}
</style>
