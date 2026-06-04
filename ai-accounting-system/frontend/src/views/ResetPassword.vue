<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const userStore = useUserStore()

const token = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const error = ref('')
const success = ref(false)
const showPassword = ref(false)

const passwordChecks = computed(() => {
  const p = newPassword.value
  return {
    length: p.length >= 8,
    letter: /[A-Za-z]/.test(p),
    number: /[0-9]/.test(p)
  }
})

onMounted(() => {
  token.value = route.query.token || ''
  if (!token.value) {
    error.value = '缺少重置令牌'
  }
})

async function handleSubmit() {
  if (!token.value) {
    error.value = '缺少重置令牌'
    return
  }
  if (!newPassword.value) {
    error.value = '请输入新密码'
    return
  }
  if (newPassword.value.length < 8) {
    error.value = '密码长度不能少于8位'
    return
  }
  if (!/[A-Za-z]/.test(newPassword.value) || !/[0-9]/.test(newPassword.value)) {
    error.value = '密码必须包含字母和数字'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }

  loading.value = true
  error.value = ''

  try {
    await userStore.resetPassword(token.value, newPassword.value)
    success.value = true
  } catch (err) {
    error.value = err.response?.data?.error || '重置失败，请重试'
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
      <div v-if="success" class="card p-8 text-center">
        <div class="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h2 class="text-xl font-bold text-surface-900 dark:text-white mb-2">密码重置成功</h2>
        <p class="text-surface-500 dark:text-surface-400 mb-6">您的密码已成功重置，请使用新密码登录。</p>
        <router-link to="/login" class="btn-primary inline-flex items-center gap-2">
          前往登录
        </router-link>
      </div>

      <!-- Form -->
      <div v-else class="card p-8">
        <div class="mb-8">
          <h2 class="text-2xl font-bold text-surface-900 dark:text-white mb-2">重置密码</h2>
          <p class="text-surface-500 dark:text-surface-400">请输入您的新密码</p>
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
            <label class="label">新密码</label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                <svg class="w-5 h-5 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                </svg>
              </div>
              <input
                v-model="newPassword"
                :type="showPassword ? 'text' : 'password'"
                class="input-field pl-11 pr-11"
                placeholder="至少8位，包含字母和数字"
                autocomplete="new-password"
              />
              <button
                type="button"
                @click="showPassword = !showPassword"
                class="absolute inset-y-0 right-0 pr-3.5 flex items-center text-surface-400 hover:text-surface-600"
              >
                <svg v-if="showPassword" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                </svg>
                <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </button>
            </div>
            <!-- Password strength hints -->
            <div v-if="newPassword" class="flex flex-wrap gap-x-3 gap-y-1 mt-1.5">
              <span class="text-xs" :class="passwordChecks.length ? 'text-emerald-500' : 'text-surface-400'">
                {{ passwordChecks.length ? '✓' : '○' }} 8位以上
              </span>
              <span class="text-xs" :class="passwordChecks.letter ? 'text-emerald-500' : 'text-surface-400'">
                {{ passwordChecks.letter ? '✓' : '○' }} 包含字母
              </span>
              <span class="text-xs" :class="passwordChecks.number ? 'text-emerald-500' : 'text-surface-400'">
                {{ passwordChecks.number ? '✓' : '○' }} 包含数字
              </span>
            </div>
          </div>

          <div>
            <label class="label">确认新密码</label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                <svg class="w-5 h-5 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                </svg>
              </div>
              <input
                v-model="confirmPassword"
                type="password"
                class="input-field pl-11"
                placeholder="再次输入新密码"
                autocomplete="new-password"
              />
            </div>
          </div>

          <button
            type="submit"
            class="w-full btn-primary py-3 text-base"
            :disabled="loading || !token"
          >
            <span v-if="loading" class="flex items-center justify-center gap-2">
              <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              重置中...
            </span>
            <span v-else>重置密码</span>
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
