<template>
  <BaseChart :option="chartOption" :loading="loading" :height="height" />
</template>

<script setup>
import { computed } from 'vue'
import BaseChart from './BaseChart.vue'

const props = defineProps({
  categories: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
  height: { type: String, default: '350px' }
})

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    backgroundColor: 'rgba(15,23,42,0.95)',
    borderColor: 'rgba(100,116,139,0.2)',
    textStyle: { color: '#e2e8f0', fontSize: 12 },
    formatter: p => {
      const mom = p.data.mom_change_pct || 0
      const arrow = mom > 0 ? '↑' : mom < 0 ? '↓' : '→'
      const color = mom > 0 ? '#f43f5e' : mom < 0 ? '#10b981' : '#94a3b8'
      return `<div style="font-weight:600">${p.name}</div>
        <div>金额: <b>¥${Number(p.value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</b></div>
        <div>占比: ${p.percent.toFixed(1)}%</div>
        <div>环比: <span style="color:${color}">${arrow} ${Math.abs(mom).toFixed(1)}%</span></div>`
    }
  },
  legend: {
    orient: 'vertical',
    right: 10,
    top: 'center',
    textStyle: { color: '#94a3b8', fontSize: 11 },
    itemWidth: 10,
    itemHeight: 10,
    itemGap: 8,
    formatter: name => {
      const cat = props.categories.find(c => c.name === name)
      if (!cat) return name
      const mom = cat.mom_change_pct || 0
      const arrow = mom > 0 ? '↑' : mom < 0 ? '↓' : ''
      return `${name}  ¥${cat.amount >= 10000 ? (cat.amount / 10000).toFixed(1) + 'w' : cat.amount.toFixed(0)}${arrow}`
    }
  },
  series: [{
    type: 'pie',
    radius: ['42%', '68%'],
    center: ['35%', '50%'],
    avoidLabelOverlap: true,
    label: { show: false },
    emphasis: {
      label: { show: true, fontSize: 14, fontWeight: 'bold', color: '#e2e8f0' },
      itemStyle: { shadowBlur: 20, shadowColor: 'rgba(0,0,0,0.4)' }
    },
    data: props.categories.map(c => ({
      name: c.name,
      value: c.amount,
      mom_change_pct: c.mom_change_pct || 0,
      itemStyle: { color: c.color || undefined }
    })),
    itemStyle: { borderColor: '#0f172a', borderWidth: 2 }
  }],
  graphic: props.total ? [{
    type: 'text',
    left: '28%',
    top: '42%',
    style: {
      text: '总支出',
      fill: '#94a3b8',
      fontSize: 12,
      textAlign: 'center'
    }
  }, {
    type: 'text',
    left: '28%',
    top: '50%',
    style: {
      text: `¥${props.total >= 10000 ? (props.total / 10000).toFixed(2) + 'w' : props.total.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`,
      fill: '#e2e8f0',
      fontSize: 18,
      fontWeight: 'bold',
      textAlign: 'center'
    }
  }] : []
}))
</script>
