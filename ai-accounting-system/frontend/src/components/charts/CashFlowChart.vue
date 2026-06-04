<template>
  <BaseChart :option="chartOption" :loading="loading" :height="height" />
</template>

<script setup>
import { computed } from 'vue'
import BaseChart from './BaseChart.vue'

const props = defineProps({
  labels: { type: Array, default: () => [] },
  income: { type: Array, default: () => [] },
  expense: { type: Array, default: () => [] },
  net: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  height: { type: String, default: '350px' }
})

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(15,23,42,0.95)',
    borderColor: 'rgba(100,116,139,0.2)',
    textStyle: { color: '#e2e8f0', fontSize: 12 },
    formatter: params => {
      let tip = `<div style="font-weight:600;margin-bottom:4px">${params[0].axisValue}</div>`
      params.forEach(p => {
        const val = Number(p.value)
        const color = p.seriesName === '净现金流' ? (val >= 0 ? '#10b981' : '#f43f5e') : undefined
        const style = color ? `color:${color}` : ''
        tip += `<div>${p.marker} ${p.seriesName}: <b style="${style}">¥${val.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</b></div>`
      })
      return tip
    }
  },
  legend: {
    data: ['收入', '支出', '净现金流'],
    textStyle: { color: '#94a3b8' },
    top: 0
  },
  grid: { left: 60, right: 60, top: 40, bottom: 30 },
  xAxis: {
    type: 'category',
    data: props.labels,
    axisLine: { lineStyle: { color: 'rgba(100,116,139,0.2)' } },
    axisLabel: { color: '#94a3b8', fontSize: 11 }
  },
  yAxis: [
    {
      type: 'value',
      name: '金额',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(100,116,139,0.08)' } },
      axisLabel: {
        color: '#94a3b8',
        fontSize: 11,
        formatter: v => v >= 10000 ? (v / 10000).toFixed(1) + 'w' : v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v
      }
    },
    {
      type: 'value',
      name: '净现金流',
      axisLine: { show: false },
      splitLine: { show: false },
      axisLabel: {
        color: '#94a3b8',
        fontSize: 11,
        formatter: v => v >= 10000 ? (v / 10000).toFixed(1) + 'w' : v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v
      }
    }
  ],
  series: [
    {
      name: '收入',
      type: 'bar',
      barWidth: '30%',
      data: props.income,
      itemStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: '#10b981' },
            { offset: 1, color: 'rgba(16,185,129,0.4)' }
          ]
        },
        borderRadius: [4, 4, 0, 0]
      }
    },
    {
      name: '支出',
      type: 'bar',
      barWidth: '30%',
      data: props.expense,
      itemStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: '#f43f5e' },
            { offset: 1, color: 'rgba(244,63,94,0.4)' }
          ]
        },
        borderRadius: [4, 4, 0, 0]
      }
    },
    {
      name: '净现金流',
      type: 'line',
      yAxisIndex: 1,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      data: props.net,
      itemStyle: { color: '#f59e0b' },
      lineStyle: { width: 2, color: '#f59e0b' },
      markLine: {
        silent: true,
        lineStyle: { color: 'rgba(100,116,139,0.3)', type: 'dashed' },
        data: [{ yAxis: 0 }],
        label: { show: false }
      }
    }
  ]
}))
</script>
