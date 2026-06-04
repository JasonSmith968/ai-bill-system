<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const form = ref({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})
const loading = ref(false)
const error = ref('')
const showPassword = ref(false)
const registered = ref(false)

const passwordChecks = computed(() => {
  const p = form.value.password
  return {
    length: p.length >= 8,
    letter: /[A-Za-z]/.test(p),
    number: /[0-9]/.test(p),
    match: p.length > 0 && p === form.value.confirmPassword
  }
})

async function handleRegister() {
  if (!form.value.username || !form.value.email || !form.value.password) {
    error.value = '请填写所有必填字段'
    return
  }
  if (form.value.password !== form.value.confirmPassword) {
    error.value = '两次输入的密码不一致'
    return
  }
  if (form.value.password.length < 8) {
    error.value = '密码长度不能少于8位'
    return
  }
  if (!/[A-Za-z]/.test(form.value.password) || !/[0-9]/.test(form.value.password)) {
    error.value = '密码必须包含字母和数字'
    return
  }

  loading.value = true
  error.value = ''

  try {
    await userStore.register(form.value.username, form.value.email, form.value.password)
    registered.value = true
  } catch (err) {
    error.value = err.response?.data?.error || '注册失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center relative overflow-hidden bg-surface-50 dark:bg-surface-900 p-6">
    <!-- Background -->
    <div class="absolute inset-0 pointer-events-none">
      <div class="absolute -top-40 -left-40 w-96 h-96 bg-violet-200/30 dark:bg-violet-900/20 rounded-full blur-3xl animate-float" />
      <div class="absolute -bottom-40 -right-40 w-96 h-96 bg-brand-200/30 dark:bg-brand-900/20 rounded-full blur-3xl animate-float" style="animation-delay: -3s" />
    </div>

    <div class="w-full max-w-[440px] relative z-10">
      <!-- Logo -->
      <div class="flex items-center gap-3 mb-8 justify-center">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 flex items-center justify-center shadow-glow">
          <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <span class="text-xl font-bold text-gradient">AI 智能记账</span>
      </div>

      <!-- Registration success -->
      <div v-if="registered" class="card p-8 text-center">
        <div class="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
          </svg>
        </div>
        <h2 class="text-xl font-bold text-surface-900 dark:text-white mb-2">注册成功！</h2>
        <p class="text-surface-500 dark:text-surface-400 mb-6">
          验证邮件已发送到您的邮箱，请查收并完成验证。
        </p>
        <router-link to="/login" class="btn-primary inline-flex items-center gap-2">
          前往登录
        </router-link>
      </div>

      <!-- Registration form -->
      <div v-else class="card p-8">
        <div class="mb-8 text-center">
          <h2 class="text-2xl font-bold text-surface-900 dark:text-white mb-2">创建账号</h2>
          <p class="text-surface-500 dark:text-surface-400">注册后即可开始智能记账</p>
        </div>

        <Transition name="slide-up">
          <div v-if="error" class="mb-6 flex items-center gap-3 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
            <svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
            <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
          </div>
        </Transition>

        <form @submit.prevent="handleRegister" class="space-y-5">
          <div>
            <label class="label">用户名</label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                <svg class="w-5 h-5 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                </svg>
              </div>
              <input v-model="form.username" type="text" class="input-field pl-11" placeholder="请输入用户名" autocomplete="username" />
            </div>
          </div>

          <div>
            <label class="label">邮箱</label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                <svg class="w-5 h-5 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                </svg>
              </div>
              <input v-model="form.email" type="email" class="input-field pl-11" placeholder="请输入邮箱" autocomplete="email" />
            </div>
          </div>

          <div>
            <label class="label">密码</label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                <svg class="w-5 h-5 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                </svg>
              </div>
              <input v-model="form.password" :type="showPassword ? 'text' : 'password'" class="input-field pl-11 pr-11" placeholder="至少8位，包含字母和数字" autocomplete="new-password" />
              <button type="button" @click="showPassword = !showPassword" class="absolute inset-y-0 right-0 pr-3.5 flex items-center text-surface-400 hover:text-surface-600">
                <svg v-if="showPassword" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" /></svg>
                <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
              </button>
            </div>
            <!-- Password strength hints -->
            <div v-if="form.password" class="flex flex-wrap gap-x-3 gap-y-1 mt-1.5">
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
            <label class="label">确认密码</label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                <svg class="w-5 h-5 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                </svg>
              </div>
              <input v-model="form.confirmPassword" type="password" class="input-field pl-11" placeholder="再次输入密码" autocomplete="new-password" />
            </div>
          </div>

          <button type="submit" class="w-full btn-primary py-3 text-base" :disabled="loading">
            <span v-if="loading" class="flex items-center justify-center gap-2">
              <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
              注册中...
            </span>
            <span v-else>创建账号</span>
          </button>
        </form>

        <div class="mt-8 text-center">
          <p class="text-surface-500 dark:text-surface-400">
            已有账号？
            <router-link to="/login" class="font-semibold text-brand-600 dark:text-brand-400 hover:text-brand-500 transition-colors">立即登录</router-link>
          </p>
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