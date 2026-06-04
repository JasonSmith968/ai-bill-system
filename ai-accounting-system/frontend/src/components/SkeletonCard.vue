<script setup>
defineProps({
  lines: { type: Number, default: 3 },
  avatar: { type: Boolean, default: false },
  chart: { type: Boolean, default: false },
})
</script>

<template>
  <div class="card animate-pulse">
    <!-- Header -->
    <div v-if="avatar" class="flex items-center gap-3 mb-4">
      <div class="w-10 h-10 rounded-full bg-surface-200 dark:bg-surface-700" />
      <div class="flex-1 space-y-2">
        <div class="h-4 bg-surface-200 dark:bg-surface-700 rounded w-24" />
        <div class="h-3 bg-surface-200 dark:bg-surface-700 rounded w-32" />
      </div>
    </div>

    <!-- Chart placeholder -->
    <div v-if="chart" class="h-48 bg-surface-200 dark:bg-surface-700 rounded-xl mb-4" />

    <!-- Text lines -->
    <div class="space-y-3">
      <div
        v-for="i in lines"
        :key="i"
        class="h-4 bg-surface-200 dark:bg-surface-700 rounded"
        :style="{ width: `${Math.max(40, 100 - i * 15)}%` }"
      />
    </div>
  </div>
</template>
