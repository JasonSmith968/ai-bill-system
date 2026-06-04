<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const isOnline = ref(navigator.onLine)
const showBanner = ref(false)
let hideTimer = null

function handleOnline() {
  isOnline.value = true
  showBanner.value = true
  clearTimeout(hideTimer)
  hideTimer = setTimeout(() => { showBanner.value = false }, 3000)
}

function handleOffline() {
  isOnline.value = false
  showBanner.value = true
  clearTimeout(hideTimer)
}

onMounted(() => {
  window.addEventListener('online', handleOnline)
  window.addEventListener('offline', handleOffline)
})

onUnmounted(() => {
  window.removeEventListener('online', handleOnline)
  window.removeEventListener('offline', handleOffline)
  clearTimeout(hideTimer)
})
</script>

<template>
  <Transition name="slide-down">
    <div v-if="showBanner && !isOnline" class="fixed top-0 left-0 right-0 z-[9997] bg-red-500 text-white px-4 py-2 text-center text-sm font-medium shadow-lg">
      <div class="flex items-center justify-center gap-2">
        <svg class="w-4 h-4 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3" />
        </svg>
        网络连接已断开，请检查网络设置
      </div>
    </div>
    <div v-else-if="showBanner && isOnline" class="fixed top-0 left-0 right-0 z-[9997] bg-emerald-500 text-white px-4 py-2 text-center text-sm font-medium shadow-lg">
      <div class="flex items-center justify-center gap-2">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
        </svg>
        网络已恢复连接
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.slide-down-enter-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.slide-down-leave-active { transition: all 0.2s ease; }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; transform: translateY(-100%); }
</style>
