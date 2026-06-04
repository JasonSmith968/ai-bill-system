<template>
  <BaseChart :option="chartOption" :loading="loading" :height="height" />
</template>

<script setup>
import { computed } from 'vue'
import BaseChart from './BaseChart.vue'

const props = defineProps({
  categories: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  height: { type: String, default: '300px' }
})

function gaugeColor(pct) {
  if (pct >= 100) return '#ef4444'
  if (pct >= 80) return '#f59e0b'
  return '#10b981'
}

const chartOption = computed(() => {
  const cats = props.categories.slice(0, 4)
  const cols = cats.length <= 2 ? cats.length : 2
  const rows = Math.ceil(cats.length / cols)

  const series = cats.map((cat, i) => {
    const col = i % cols
    const row = Math.floor(i / cols)
    const cx = (col + 0.5) / cols * 100
    const cy = (row + 0.5) / rows * 100
    const pct = cat.utilization || 0
    const radius = cats.length <= 2 ? 70 : 55

    return {
      type: 'gauge',
      center: [`${cx}%`, `${cy}%`],
      radius: `${radius}%`,
      startAngle: 220,
      endAngle: -40,
      min: 0,
      max: Math.max(cat.suggested * 1.5, cat.spent * 1.2, 100),
      splitNumber: 5,
      axisLine: {
        lineStyle: {
          width: 12,
          color: [[pct / 100, gaugeColor(pct)], [1, 'rgba(100,116,139,0.15)']]
        }
      },
      pointer: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      title: {
        offsetCenter: [0, '30%'],
        fontSize: 12,
        color: '#94a3b8'
      },
      detail: {
        offsetCenter: [0, '-10%'],
        fontSize: 16,
        fontWeight: 'bold',
        color: gaugeColor(pct),
        formatter: `{value}%`
      },
      data: [{
        value: Math.round(pct),
        name: cat.name
      }]
    }
  })

  return {
    series
  }
})
</script>
