<template>
  <BaseChart :option="chartOption" :loading="loading" :height="height" />
</template>

<script setup>
import { computed } from 'vue'
import BaseChart from './BaseChart.vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  height: { type: String, default: '280px' }
})

const chartOption = computed(() => {
  const year = new Date().getFullYear()
  const maxVal = Math.max(...props.data.map(d => d[1]), 1)

  return {
    tooltip: {
      backgroundColor: 'rgba(15,23,42,0.95)',
      borderColor: 'rgba(100,116,139,0.2)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: p => {
        if (!p.data || !p.data[0]) return ''
        const [date, amount] = p.data
        const level = amount === 0 ? '无消费' : amount > maxVal * 0.7 ? '高额消费' : amount > maxVal * 0.3 ? '中等消费' : '正常'
        return `<div style="font-weight:600">${date}</div><div>支出: ¥${Number(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</div><div>${level}</div>`
      }
    },
    visualMap: {
      show: true,
      min: 0,
      max: maxVal,
      orient: 'horizontal',
      left: 'center',
      bottom: 10,
      textStyle: { color: '#94a3b8', fontSize: 10 },
      inRange: {
        color: ['#1e293b', '#064e3b', '#059669', '#f59e0b', '#ef4444']
      },
      itemWidth: 12,
      itemHeight: 120
    },
    calendar: {
      top: 30,
      left: 50,
      right: 20,
      bottom: 60,
      cellSize: ['auto', 16],
      range: String(year),
      itemStyle: {
        borderWidth: 2,
        borderColor: '#0f172a'
      },
      yearLabel: { show: false },
      dayLabel: {
        nameMap: ['日', '一', '二', '三', '四', '五', '六'],
        color: '#94a3b8',
        fontSize: 10
      },
      monthLabel: {
        nameMap: 'ZH',
        color: '#94a3b8',
        fontSize: 10
      },
      splitLine: { lineStyle: { color: 'rgba(100,116,139,0.15)' } }
    },
    series: [{
      type: 'heatmap',
      coordinateSystem: 'calendar',
      data: props.data
    }]
  }
})
</script>
