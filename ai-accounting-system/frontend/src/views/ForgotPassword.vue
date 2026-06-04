<script setup>
import { ref } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const email = ref('')
const loading = ref(false)
const error = ref('')
const sent = ref(false)

async function handleSubmit() {
  if (!email.value) {
    error.value = '请输入邮箱地址'
    return
  }

  loading.value = true
  error.value = ''

  try {
    await userStore.forgotPassword(email.value)
    sent.value = true
  } catch (err) {
    error.value = err.response?.data?.error || '发送失败，请重试'
  } finally {
    loading.value = false
  }
}
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

      <!-- Success state -->
      <div v-if="sent" class="card p-8 text-center">
        <div class="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
          </svg>
        </div>
        <h2 class="text-xl font-bold text-surface-900 dark:text-white mb-2">邮件已发送</h2>
        <p class="text-surface-500 dark:text-surface-400 mb-6">
          如果该邮箱已注册，重置链接将发送到您的邮箱。请查收并点击链接重置密码。
        </p>
        <p class="text-xs text-surface-400 mb-6">没有收到邮件？请检查垃圾邮件文件夹。</p>
        <router-link to="/login" class="btn-primary inline-flex items-center gap-2">
          返回登录
        </router-link>
      </div>

      <!-- Form -->
      <div v-else class="card p-8">
        <div class="mb-8">
          <h2 class="text-2xl font-bold text-surface-900 dark:text-white mb-2">忘记密码</h2>
          <p class="text-surface-500 dark:text-surface-400">输入您的注册邮箱，我们将发送密码重置链接</p>
        </div>

        <Transition name="slide-up">
          <div v-if="error" class="mb-6 flex items-center gap-3 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
            <svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
            <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
          </div>
        </Transition>

        <form @submit.prevent="handleSubmit" class="space-y-5">
          <div>
            <label class="label">邮箱地址</label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                <svg class="w-5 h-5 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                </svg>
              </div>
              <input
                v-model="email"
                type="email"
                class="input-field pl-11"
                placeholder="请输入注册邮箱"
                autocomplete="email"
              />
            </div>
          </div>

          <button
            type="submit"
            class="w-full btn-primary py-3 text-base"
            :disabled="loading"
          >
            <span v-if="loading" class="flex items-center justify-center gap-2">
              <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              发送中...
            </span>
            <span v-else>发送重置链接</span>
          </button>
        </form>

        <div class="mt-8 text-center">
          <router-link to="/login" class="text-sm text-brand-600 dark:text-brand-400 hover:underline flex items-center justify-center gap-1">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
            </svg>
            返回登录
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.slide-up-enter-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.slide-up-leave-active { transition: all 0.2s ease; }
.slide-up-enter-from, .slide-up-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
