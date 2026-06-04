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
  forecast: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  height: { type: String, default: '350px' }
})

const chartOption = computed(() => {
  const allLabels = [...props.labels]
  const allIncome = [...props.income]
  const allExpense = [...props.expense]

  if (props.forecast) {
    allLabels.push(props.forecast.label || '预测')
    allIncome.push(null)
    allExpense.push(null)
  }

  const series = [
    {
      name: '收入',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      data: allIncome,
      itemStyle: { color: '#10b981' },
      lineStyle: { width: 2 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(16,185,129,0.25)' },
            { offset: 1, color: 'rgba(16,185,129,0.02)' }
          ]
        }
      }
    },
    {
      name: '支出',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      data: allExpense,
      itemStyle: { color: '#f43f5e' },
      lineStyle: { width: 2 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(244,63,94,0.25)' },
            { offset: 1, color: 'rgba(244,63,94,0.02)' }
          ]
        }
      }
    }
  ]

  if (props.forecast) {
    const lastIdx = props.labels.length - 1
    series.push({
      name: '预测支出',
      type: 'line',
      smooth: true,
      symbol: 'diamond',
      symbolSize: 8,
      lineStyle: { type: 'dashed', color: '#f43f5e', width: 2 },
      itemStyle: { color: '#f43f5e' },
      data: Array(allLabels.length).fill(null).map((_, i) =>
        i === lastIdx ? props.expense[lastIdx] : i === allLabels.length - 1 ? props.forecast.predicted_expense : null
      ),
      markArea: props.forecast.confidence ? {
        silent: true,
        data: [[
          {
            yAxis: props.forecast.predicted_expense * (1 - props.forecast.confidence),
            itemStyle: { color: 'rgba(244,63,94,0.08)' }
          },
          {
            yAxis: props.forecast.predicted_expense * (1 + props.forecast.confidence)
          }
        ]]
      } : undefined
    })
    series.push({
      name: '预测收入',
      type: 'line',
      smooth: true,
      symbol: 'diamond',
      symbolSize: 8,
      lineStyle: { type: 'dashed', color: '#10b981', width: 2 },
      itemStyle: { color: '#10b981' },
      data: Array(allLabels.length).fill(null).map((_, i) =>
        i === lastIdx ? props.income[lastIdx] : i === allLabels.length - 1 ? props.forecast.predicted_income : null
      )
    })
  }

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15,23,42,0.95)',
      borderColor: 'rgba(100,116,139,0.2)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: params => {
        let tip = `<div style="font-weight:600;margin-bottom:4px">${params[0].axisValue}</div>`
        params.forEach(p => {
          if (p.value != null) {
            tip += `<div>${p.marker} ${p.seriesName}: <b>¥${Number(p.value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</b></div>`
          }
        })
        return tip
      }
    },
    legend: {
      data: ['收入', '支出', ...(props.forecast ? ['预测支出', '预测收入'] : [])],
      textStyle: { color: '#94a3b8' },
      top: 0
    },
    grid: { left: 60, right: 20, top: 40, bottom: 30 },
    xAxis: {
      type: 'category',
      data: allLabels,
      axisLine: { lineStyle: { color: 'rgba(100,116,139,0.2)' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(100,116,139,0.08)' } },
      axisLabel: {
        color: '#94a3b8',
        fontSize: 11,
        formatter: v => v >= 10000 ? (v / 10000).toFixed(1) + 'w' : v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v
      }
    },
    series
  }
})
</script>
