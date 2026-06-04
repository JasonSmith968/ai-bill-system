<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useThemeStore } from '@/stores/theme'

const router = useRouter()
const userStore = useUserStore()
const themeStore = useThemeStore()

const form = ref({
  username: '',
  password: ''
})
const twoFaCode = ref('')
const loading = ref(false)
const error = ref('')
const showPassword = ref(false)

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    error.value = '请填写用户名和密码'
    return
  }

  loading.value = true
  error.value = ''

  try {
    const data = await userStore.login(form.value.username, form.value.password)
    if (data.requires_2fa) {
      // Show 2FA input
    } else {
      router.push('/')
    }
  } catch (err) {
    error.value = err.response?.data?.error || '登录失败，请重试'
  } finally {
    loading.value = false
  }
}

async function handleVerify2FA() {
  if (!twoFaCode.value || twoFaCode.value.length !== 6) {
    error.value = '请输入6位验证码'
    return
  }

  loading.value = true
  error.value = ''

  try {
    await userStore.verify2FA(twoFaCode.value)
    router.push('/')
  } catch (err) {
    error.value = err.response?.data?.error || '验证码错误'
  } finally {
    loading.value = false
  }
}

function cancel2FA() {
  userStore.cancel2FA()
  twoFaCode.value = ''
  error.value = ''
}
</script>

<template>
  <div class="min-h-screen flex relative overflow-hidden bg-surface-50 dark:bg-surface-900">
    <!-- Background decoration -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div class="absolute -top-40 -right-40 w-96 h-96 bg-brand-200/30 dark:bg-brand-900/20 rounded-full blur-3xl animate-float" />
      <div class="absolute -bottom-40 -left-40 w-96 h-96 bg-violet-200/30 dark:bg-violet-900/20 rounded-full blur-3xl animate-float" style="animation-delay: -3s" />
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-brand-100/20 dark:bg-brand-900/10 rounded-full blur-3xl" />
    </div>

    <!-- Left panel - hidden on mobile -->
    <div class="hidden lg:flex lg:w-1/2 xl:w-[55%] relative items-center justify-center p-12">
      <div class="max-w-lg">
        <div class="flex items-center gap-3 mb-8">
          <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-brand-500 to-violet-500 flex items-center justify-center shadow-glow-lg">
            <svg class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <span class="text-2xl font-bold text-gradient">AI 智能记账</span>
        </div>

        <h1 class="text-4xl xl:text-5xl font-bold text-surface-900 dark:text-white leading-tight mb-6">
          让 AI 帮你<br/>
          <span class="text-gradient">管理每一笔收支</span>
        </h1>

        <p class="text-lg text-surface-500 dark:text-surface-400 leading-relaxed mb-10">
          只需一句话，AI 自动识别金额、分类、类型。<br/>
          智能统计分析，让财务管理变得简单高效。
        </p>

        <div class="flex items-center gap-6">
          <div class="flex items-center gap-2">
            <div class="w-8 h-8 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
              <svg class="w-4 h-4 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </div>
            <span class="text-sm text-surface-600 dark:text-surface-400">AI 智能识别</span>
          </div>
          <div class="flex items-center gap-2">
            <div class="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
              <svg class="w-4 h-4 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
              </svg>
            </div>
            <span class="text-sm text-surface-600 dark:text-surface-400">数据可视化</span>
          </div>
          <div class="flex items-center gap-2">
            <div class="w-8 h-8 rounded-full bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center">
              <svg class="w-4 h-4 text-violet-600 dark:text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            </div>
            <span class="text-sm text-surface-600 dark:text-surface-400">安全可靠</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Right panel - Login form -->
    <div class="flex-1 flex items-center justify-center p-6 relative z-10">
      <div class="w-full max-w-[420px]">
        <!-- Mobile logo -->
        <div class="flex items-center gap-3 mb-8 lg:hidden">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 flex items-center justify-center shadow-glow">
            <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <span class="text-xl font-bold text-gradient">AI 智能记账</span>
        </div>

        <div class="card p-8">
          <!-- 2FA Verification -->
          <template v-if="userStore.pendingTwoFa">
            <div class="mb-8">
              <h2 class="text-2xl font-bold text-surface-900 dark:text-white mb-2">二步验证</h2>
              <p class="text-surface-500 dark:text-surface-400">请输入身份验证器 App 中的6位验证码</p>
            </div>

            <Transition name="slide-up">
              <div v-if="error" class="mb-6 flex items-center gap-3 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
                <svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
                <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
              </div>
            </Transition>

            <form @submit.prevent="handleVerify2FA" class="space-y-5">
              <div>
                <label class="label">验证码</label>
                <input
                  v-model="twoFaCode"
                  type="text"
                  inputmode="numeric"
                  maxlength="6"
                  class="input-field text-center text-2xl tracking-[0.5em]"
                  placeholder="000000"
                  autocomplete="one-time-code"
                  autofocus
                />
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
                  验证中...
                </span>
                <span v-else>验证</span>
              </button>
            </form>

            <div class="mt-6 text-center">
              <button @click="cancel2FA" class="text-sm text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 transition-colors">
                返回登录
              </button>
            </div>
          </template>

          <!-- Normal Login Form -->
          <template v-else>
          <div class="mb-8">
            <h2 class="text-2xl font-bold text-surface-900 dark:text-white mb-2">欢迎回来</h2>
            <p class="text-surface-500 dark:text-surface-400">登录您的账号继续使用</p>
          </div>

          <!-- Error -->
          <Transition name="slide-up">
            <div v-if="error" class="mb-6 flex items-center gap-3 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
              <svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
            </div>
          </Transition>

          <form @submit.prevent="handleLogin" class="space-y-5">
            <div>
              <label class="label">用户名 / 邮箱</label>
              <div class="relative">
                <div class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                  <svg class="w-5 h-5 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                  </svg>
                </div>
                <input
                  v-model="form.username"
                  type="text"
                  class="input-field pl-11"
                  placeholder="请输入用户名或邮箱"
                  autocomplete="username"
                />
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
                <input
                  v-model="form.password"
                  :type="showPassword ? 'text' : 'password'"
                  class="input-field pl-11 pr-11"
                  placeholder="请输入密码"
                  autocomplete="current-password"
                />
                <button
                  type="button"
                  @click="showPassword = !showPassword"
                  class="absolute inset-y-0 right-0 pr-3.5 flex items-center text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
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
              <div class="flex items-center justify-end mt-1.5">
                <router-link to="/forgot-password" class="text-sm text-brand-600 dark:text-brand-400 hover:underline">
                  忘记密码?
                </router-link>
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
                登录中...
              </span>
              <span v-else>登录</span>
            </button>
          </form>

          <div class="mt-8 text-center">
            <p class="text-surface-500 dark:text-surface-400">
              还没有账号？
              <router-link to="/register" class="font-semibold text-brand-600 dark:text-brand-400 hover:text-brand-500 transition-colors">
                立即注册
              </router-link>
            </p>
          </div>
          </template>
        </div>

        <p class="mt-6 text-center text-xs text-surface-400 dark:text-surface-500">
          登录即表示您同意我们的服务条款和隐私政策
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.slide-up-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-up-leave-active {
  transition: all 0.2s ease;
}
.slide-up-enter-from, .slide-up-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>