<script setup>
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
</script>

<template>
  <Transition name="fade">
    <div
      v-if="appStore.loading"
      class="fixed inset-0 z-[9998] flex items-center justify-center bg-white/60 dark:bg-surface-900/60 backdrop-blur-sm"
    >
      <div class="flex flex-col items-center gap-3">
        <div class="relative w-12 h-12">
          <div class="absolute inset-0 rounded-full border-4 border-surface-200 dark:border-surface-700" />
          <div class="absolute inset-0 rounded-full border-4 border-transparent border-t-brand-500 animate-spin" />
        </div>
        <p v-if="appStore.loadingText" class="text-sm font-medium text-surface-600 dark:text-surface-400">
          {{ appStore.loadingText }}
        </p>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.fade-enter-active { transition: opacity 0.2s ease; }
.fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
