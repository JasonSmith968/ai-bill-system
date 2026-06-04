<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  show: Boolean,
  quota: Object
})

const emit = defineEmits(['close'])
const router = useRouter()

const isCallsExceeded = computed(() => props.quota?.error === 'calls_exceeded')
const isTokensExceeded = computed(() => props.quota?.error === 'tokens_exceeded')

const title = computed(() => {
  if (isCallsExceeded.value) return 'AI 调用次数已用尽'
  if (isTokensExceeded.value) return 'Token 额度已用尽'
  return '额度不足'
})

const description = computed(() => {
  if (isCallsExceeded.value) {
    return `本月 ${props.quota?.calls_used || 0} / ${props.quota?.calls_limit || 0} 次已使用`
  }
  if (isTokensExceeded.value) {
    return `本月 ${((props.quota?.tokens_used || 0) / 1000).toFixed(0)}K / ${((props.quota?.tokens_limit || 0) / 1000).toFixed(0)}K Token 已使用`
  }
  return props.quota?.message || '额度已用尽'
})

const handleUpgrade = () => {
  emit('close')
  router.push('/pricing')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="$emit('close')"></div>
        <div class="relative bg-white dark:bg-surface-800 rounded-2xl shadow-2xl max-w-sm w-full p-8 text-center">
          <!-- Icon -->
          <div class="w-16 h-16 mx-auto mb-6 rounded-full bg-red-50 dark:bg-red-900/20 flex items-center justify-center">
            <svg class="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>

          <!-- Title -->
          <h3 class="text-xl font-bold text-surface-900 dark:text-white mb-2">
            {{ title }}
          </h3>

          <!-- Description -->
          <p class="text-surface-600 dark:text-surface-400 mb-6">
            {{ description }}
          </p>

          <!-- Progress -->
          <div class="mb-6">
            <div class="h-3 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
              <div
                class="h-full bg-red-500 rounded-full transition-all duration-500"
                :style="{ width: '100%' }"
              />
            </div>
          </div>

          <!-- Reset Info -->
          <p v-if="quota?.reset_date" class="text-sm text-surface-500 dark:text-surface-400 mb-6">
            额度将在 {{ new Date(quota.reset_date).toLocaleDateString() }} 重置
          </p>

          <!-- Actions -->
          <div class="space-y-3">
            <button
              @click="handleUpgrade"
              class="w-full py-3 px-6 rounded-xl bg-gradient-to-r from-brand-500 to-violet-500 text-white font-medium shadow-lg shadow-brand-500/25 hover:shadow-xl transition-all duration-200"
            >
              升级到 Pro 版
            </button>
            <button
              @click="$emit('close')"
              class="w-full py-3 px-6 rounded-xl text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
            >
              稍后再说
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active {
  transition: all 0.3s ease;
}
.modal-enter-from, .modal-leave-to {
  opacity: 0;
}
.modal-enter-from > div:last-child,
.modal-leave-to > div:last-child {
  transform: scale(0.95);
}
</style>
