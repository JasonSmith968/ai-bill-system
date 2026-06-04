<template>
  <div class="base-chart" :style="{ height: height }">
    <div v-if="loading" class="chart-skeleton">
      <div class="skeleton-pulse"></div>
    </div>
    <v-chart
      v-else
      :option="option"
      :autoresize="autoresize"
      :theme="theme"
      class="chart-canvas"
    />
  </div>
</template>

<script setup>
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import {
  PieChart, LineChart, BarChart, GaugeChart,
  HeatmapChart, ScatterChart
} from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DatasetComponent, TransformComponent,
  VisualMapComponent, CalendarComponent, MarkLineComponent,
  MarkAreaComponent, DataZoomComponent
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  PieChart, LineChart, BarChart, GaugeChart, HeatmapChart, ScatterChart,
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DatasetComponent, TransformComponent,
  VisualMapComponent, CalendarComponent, MarkLineComponent,
  MarkAreaComponent, DataZoomComponent
])

defineProps({
  option: { type: Object, required: true },
  loading: { type: Boolean, default: false },
  height: { type: String, default: '300px' },
  autoresize: { type: Boolean, default: true },
  theme: { type: String, default: 'dark' }
})
</script>

<style scoped>
.base-chart {
  position: relative;
  width: 100%;
}
.chart-canvas {
  width: 100%;
  height: 100%;
}
.chart-skeleton {
  width: 100%;
  height: 100%;
  background: rgba(30, 41, 59, 0.5);
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}
.skeleton-pulse {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(100, 116, 139, 0.15) 50%,
    transparent 100%
  );
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
</style>
