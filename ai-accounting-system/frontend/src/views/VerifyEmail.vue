<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const userStore = useUserStore()

const loading = ref(true)
const error = ref('')
const success = ref(false)

onMounted(async () => {
  const token = route.query.token
  if (!token) {
    error.value = '缺少验证令牌'
    loading.value = false
    return
  }

  try {
    await userStore.verifyEmail(token)
    success.value = true
  } catch (err) {
    error.value = err.response?.data?.error || '验证失败，链接可能已过期'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center relative overflow-hidden bg-surface-50 dark:bg-surface-900 p-6">
    <!-- Background -->
    <div class="absolute inset-0 pointer-events-none">
      <div class="absolute -top-40 -right-40 w-96 h-96 bg-brand-200/30 dark:bg-brand-900/20 rounded-full blur-3xl animate-float" />
      <div class="absolute -bottom-40 -left-40 w-96 h-96 bg-violet-200/30 dark:bg-violet-900/20 rounded-full blur-3xl animate-float" style="animation-delay: -3s" />
    </div>

    <div class="w-full max-w-[420px] relative z-10">
      <!-- Logo -->
      <div class="flex items-center gap-3 mb-8 justify-center">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 flex items-center justify-center shadow-glow">
          <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <span class="text-xl font-bold text-gradient">AI 智能记账</span>
      </div>

      <div class="card p-8 text-center">
        <!-- Loading -->
        <div v-if="loading">
          <svg class="animate-spin w-12 h-12 text-brand-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <p class="text-surface-500 dark:text-surface-400">正在验证您的邮箱...</p>
        </div>

        <!-- Success -->
        <div v-else-if="success">
          <div class="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mx-auto mb-4">
            <svg class="w-8 h-8 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 class="text-xl font-bold text-surface-900 dark:text-white mb-2">邮箱验证成功</h2>
          <p class="text-surface-500 dark:text-surface-400 mb-6">您的邮箱已成功验证，现在可以正常使用所有功能。</p>
          <router-link to="/" class="btn-primary inline-flex items-center gap-2">
            进入仪表盘
          </router-link>
        </div>

        <!-- Error -->
        <div v-else>
          <div class="w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mx-auto mb-4">
            <svg class="w-8 h-8 text-red-600 dark:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          </div>
          <h2 class="text-xl font-bold text-surface-900 dark:text-white mb-2">验证失败</h2>
          <p class="text-surface-500 dark:text-surface-400 mb-6">{{ error }}</p>
          <div class="flex flex-col gap-3">
            <router-link to="/login" class="btn-primary inline-flex items-center justify-center gap-2">
              前往登录
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
