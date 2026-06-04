<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useUserStore } from '@/stores/user'
import { useSecurityStore } from '@/stores/security'
import { useToastStore } from '@/stores/toast'
import api from '@/utils/api'

const userStore = useUserStore()
const securityStore = useSecurityStore()
const toast = useToastStore()

const activeTab = ref('profile')
const avatarInput = ref(null)
const profileForm = reactive({ username: '', email: '', phone: '' })
const passwordForm = reactive({ old_password: '', new_password: '', confirm_password: '' })
const stats = ref({ total_income: 0, total_expense: 0, month_count: 0 })
const loading = ref(false)
const profileMsg = ref('')
const passwordMsg = ref('')

// Sessions
const sessions = ref([])
const sessionsLoading = ref(false)

// Login history
const history = ref([])
const historyLoading = ref(false)
const historyPage = ref(1)
const historyTotal = ref(0)
const historyPages = ref(0)

// 2FA
const twoFaSetup = ref(null)  // { secret, qr_code }
const twoFaCode = ref('')
const twoFaLoading = ref(false)
const backupCodes = ref([])

// Subscription
const subscription = ref(null)
const plan = ref(null)
const usage = ref(null)
const subscriptionLoading = ref(false)

onMounted(async () => {
  await loadStats()
  initProfileForm()
})

watch(() => userStore.user, () => initProfileForm(), { deep: true })

function initProfileForm() {
  if (userStore.user) {
    profileForm.username = userStore.user.username
    profileForm.email = userStore.user.email
    profileForm.phone = userStore.user.phone || ''
  }
}

async function loadStats() {
  try {
    const { data } = await api.get('/dashboard/summary')
    stats.value = {
      total_income: data.total.income,
      total_expense: data.total.expense,
      month_count: data.month.count
    }
  } catch (e) { console.error(e) }
}

// ---- Profile ----
async function updateProfile() {
  loading.value = true
  profileMsg.value = ''
  try {
    await userStore.updateProfile(profileForm)
    profileMsg.value = 'success'
    toast.success('个人资料已更新')
  } catch (e) {
    profileMsg.value = e.response?.data?.error || '更新失败'
  } finally { loading.value = false }
}

// ---- Avatar ----
function triggerAvatarUpload() {
  avatarInput.value?.click()
}

async function handleAvatarChange(e) {
  const file = e.target.files[0]
  if (!file) return

  if (file.size > 2 * 1024 * 1024) {
    toast.error('图片大小不能超过 2MB')
    return
  }

  try {
    await userStore.uploadAvatar(file)
    toast.success('头像上传成功')
  } catch (err) {
    toast.error(err.response?.data?.error || '头像上传失败')
  }
  e.target.value = ''
}

async function removeAvatar() {
  try {
    await userStore.deleteAvatar()
    toast.success('头像已删除')
  } catch (err) {
    toast.error('删除失败')
  }
}

// ---- Password ----
async function changePassword() {
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    passwordMsg.value = '两次输入的密码不一致'
    return
  }
  if (passwordForm.new_password.length < 8) {
    passwordMsg.value = '密码长度不能少于8位'
    return
  }

  loading.value = true
  passwordMsg.value = ''
  try {
    await userStore.changePassword(passwordForm.old_password, passwordForm.new_password)
    passwordMsg.value = 'success'
    toast.success('密码修改成功，请重新登录')
    passwordForm.old_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
  } catch (e) {
    passwordMsg.value = e.response?.data?.error || '修改失败'
  } finally { loading.value = false }
}

// ---- Sessions ----
async function loadSessions() {
  sessionsLoading.value = true
  try {
    sessions.value = await userStore.getSessions()
  } catch (e) { console.error(e) }
  finally { sessionsLoading.value = false }
}

async function revokeSession(id) {
  try {
    await userStore.revokeSession(id)
    sessions.value = sessions.value.filter(s => s.id !== id)
    toast.success('设备已退出')
  } catch (e) {
    toast.error('操作失败')
  }
}

async function logoutAllDevices() {
  try {
    await userStore.logoutAllDevices()
    toast.success('所有设备已退出')
  } catch (e) {
    toast.error('操作失败')
  }
}

// ---- Login History ----
async function loadHistory(page = 1) {
  historyLoading.value = true
  try {
    const data = await userStore.getLoginHistory(page)
    history.value = data.history
    historyTotal.value = data.total
    historyPages.value = data.pages
    historyPage.value = page
  } catch (e) { console.error(e) }
  finally { historyLoading.value = false }
}

// ---- 2FA ----
async function setup2FA() {
  twoFaLoading.value = true
  try {
    const { data } = await api.post('/auth/2fa/setup')
    twoFaSetup.value = data
    twoFaCode.value = ''
  } catch (e) {
    toast.error(e.response?.data?.error || '初始化失败')
  } finally { twoFaLoading.value = false }
}

async function verify2FASetup() {
  if (!twoFaCode.value || twoFaCode.value.length !== 6) {
    toast.error('请输入6位验证码')
    return
  }
  twoFaLoading.value = true
  try {
    const { data } = await api.post('/auth/2fa/verify', { code: twoFaCode.value })
    backupCodes.value = data.backup_codes || []
    twoFaSetup.value = null
    twoFaCode.value = ''
    await userStore.loadUser()
    toast.success('二步验证已启用')
  } catch (e) {
    toast.error(e.response?.data?.error || '验证失败')
  } finally { twoFaLoading.value = false }
}

async function disable2FA() {
  const code = prompt('请输入当前验证码以禁用二步验证:')
  if (!code) return
  twoFaLoading.value = true
  try {
    await api.post('/auth/2fa/disable', { code })
    await userStore.loadUser()
    toast.success('二步验证已禁用')
  } catch (e) {
    toast.error(e.response?.data?.error || '禁用失败')
  } finally { twoFaLoading.value = false }
}

function cancel2FASetup() {
  twoFaSetup.value = null
  twoFaCode.value = ''
}

// ---- Tab switching ----
function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'security') {
    loadSessions()
    loadHistory()
  }
  if (tab === 'subscription') {
    loadSubscription()
  }
}

// ---- Subscription ----
async function loadSubscription() {
  subscriptionLoading.value = true
  try {
    const [subRes, usageRes] = await Promise.all([
      api.get('/billing/subscription'),
      api.get('/billing/usage')
    ])
    subscription.value = subRes.data.subscription
    plan.value = subRes.data.plan
    usage.value = usageRes.data.usage
  } catch (e) {
    console.error(e)
  } finally {
    subscriptionLoading.value = false
  }
}

async function cancelSubscription() {
  if (!confirm('确定要取消订阅吗？Pro 权益将持续到当前计费周期结束。')) return
  try {
    await api.post('/billing/cancel')
    toast.success('订阅已取消')
    loadSubscription()
  } catch (e) {
    toast.error(e.response?.data?.error || '取消失败')
  }
}

function formatAmount(n) {
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(n)
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="animate-fade-in max-w-4xl mx-auto space-y-6">
    <!-- Profile Header -->
    <div class="card p-0 overflow-hidden">
      <div class="h-24 bg-gradient-to-r from-brand-500 to-violet-500" />
      <div class="px-6 pb-6 -mt-10">
        <div class="flex items-end gap-4 mb-4">
          <!-- Avatar -->
          <div class="relative group cursor-pointer" @click="triggerAvatarUpload">
            <img
              v-if="userStore.user?.avatar"
              :src="userStore.user.avatar"
              class="w-20 h-20 rounded-2xl object-cover shadow-lg border-4 border-white dark:border-surface-800"
            />
            <div
              v-else
              class="w-20 h-20 rounded-2xl bg-gradient-to-br from-brand-400 to-violet-400 flex items-center justify-center text-3xl font-bold text-white shadow-lg border-4 border-white dark:border-surface-800"
            >
              {{ userStore.user?.username?.charAt(0).toUpperCase() }}
            </div>
            <!-- Hover overlay -->
            <div class="absolute inset-0 rounded-2xl bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              <svg class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z" />
              </svg>
            </div>
            <input ref="avatarInput" type="file" accept="image/png,image/jpeg,image/webp" class="hidden" @change="handleAvatarChange" />
          </div>
          <div class="pb-1 flex-1">
            <h2 class="text-xl font-bold text-surface-900 dark:text-white">{{ userStore.user?.username }}</h2>
            <p class="text-sm text-surface-500 dark:text-surface-400">{{ userStore.user?.email }}</p>
          </div>
          <button
            v-if="userStore.user?.avatar"
            @click="removeAvatar"
            class="text-xs text-surface-400 hover:text-red-500 transition-colors pb-1"
          >
            删除头像
          </button>
        </div>

        <!-- Stats -->
        <div class="grid grid-cols-3 gap-4 mt-4">
          <div class="text-center p-3 rounded-xl bg-surface-50 dark:bg-surface-700/30">
            <p class="text-lg font-bold text-emerald-600 dark:text-emerald-400">{{ formatAmount(stats.total_income) }}</p>
            <p class="text-xs text-surface-500 mt-0.5">累计收入</p>
          </div>
          <div class="text-center p-3 rounded-xl bg-surface-50 dark:bg-surface-700/30">
            <p class="text-lg font-bold text-rose-600 dark:text-rose-400">{{ formatAmount(stats.total_expense) }}</p>
            <p class="text-xs text-surface-500 mt-0.5">累计支出</p>
          </div>
          <div class="text-center p-3 rounded-xl bg-surface-50 dark:bg-surface-700/30">
            <p class="text-lg font-bold text-violet-600 dark:text-violet-400">{{ stats.month_count || 0 }}</p>
            <p class="text-xs text-surface-500 mt-0.5">本月记录</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Email verification banner -->
    <div
      v-if="userStore.user && !userStore.user.email_verified"
      class="card p-4 flex items-center gap-4 border-l-4 border-amber-400 bg-amber-50 dark:bg-amber-900/10"
    >
      <svg class="w-5 h-5 text-amber-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
      </svg>
      <p class="text-sm text-amber-700 dark:text-amber-400 flex-1">您的邮箱尚未验证，部分功能可能受限。</p>
      <button
        @click="userStore.resendVerification(); toast.success('验证邮件已发送')"
        class="text-sm font-medium text-amber-700 dark:text-amber-400 hover:underline whitespace-nowrap"
      >
        发送验证邮件
      </button>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 p-1 bg-surface-100 dark:bg-surface-800 rounded-xl">
      <button
        @click="switchTab('profile')"
        class="flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all"
        :class="activeTab === 'profile'
          ? 'bg-white dark:bg-surface-700 text-surface-900 dark:text-white shadow-sm'
          : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'"
      >
        个人资料
      </button>
      <button
        @click="switchTab('security')"
        class="flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all"
        :class="activeTab === 'security'
          ? 'bg-white dark:bg-surface-700 text-surface-900 dark:text-white shadow-sm'
          : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'"
      >
        安全设置
      </button>
      <button
        @click="switchTab('subscription')"
        class="flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all"
        :class="activeTab === 'subscription'
          ? 'bg-white dark:bg-surface-700 text-surface-900 dark:text-white shadow-sm'
          : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'"
      >
        订阅管理
      </button>
    </div>

    <!-- Tab: Profile -->
    <div v-if="activeTab === 'profile'" class="card">
      <h3 class="text-base font-semibold text-surface-900 dark:text-white mb-5 flex items-center gap-2">
        <svg class="w-5 h-5 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>
        个人信息
      </h3>

      <Transition name="slide-up">
        <div v-if="profileMsg" class="mb-4 p-3 rounded-xl text-sm flex items-center gap-2"
             :class="profileMsg === 'success' ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400' : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'">
          <svg v-if="profileMsg === 'success'" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
          <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" /></svg>
          {{ profileMsg === 'success' ? '更新成功' : profileMsg }}
        </div>
      </Transition>

      <form @submit.prevent="updateProfile" class="space-y-4">
        <div><label class="label">用户名</label><input v-model="profileForm.username" type="text" class="input-field" /></div>
        <div><label class="label">邮箱</label><input v-model="profileForm.email" type="email" class="input-field" /></div>
        <div><label class="label">手机号</label><input v-model="profileForm.phone" type="tel" class="input-field" placeholder="可选" /></div>
        <button type="submit" class="btn-primary" :disabled="loading">{{ loading ? '保存中...' : '保存修改' }}</button>
      </form>
    </div>

    <!-- Tab: Security -->
    <div v-if="activeTab === 'security'" class="space-y-6">
      <!-- Password change -->
      <div class="card">
        <h3 class="text-base font-semibold text-surface-900 dark:text-white mb-5 flex items-center gap-2">
          <svg class="w-5 h-5 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" /></svg>
          修改密码
        </h3>

        <Transition name="slide-up">
          <div v-if="passwordMsg" class="mb-4 p-3 rounded-xl text-sm flex items-center gap-2"
               :class="passwordMsg === 'success' ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400' : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'">
            <svg v-if="passwordMsg === 'success'" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
            <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" /></svg>
            {{ passwordMsg === 'success' ? '密码修改成功' : passwordMsg }}
          </div>
        </Transition>

        <form @submit.prevent="changePassword" class="space-y-4">
          <div><label class="label">旧密码</label><input v-model="passwordForm.old_password" type="password" class="input-field" /></div>
          <div><label class="label">新密码</label><input v-model="passwordForm.new_password" type="password" class="input-field" placeholder="至少8位，包含字母和数字" /></div>
          <div><label class="label">确认新密码</label><input v-model="passwordForm.confirm_password" type="password" class="input-field" /></div>
          <button type="submit" class="btn-primary" :disabled="loading">{{ loading ? '修改中...' : '修改密码' }}</button>
        </form>
      </div>

      <!-- 2FA -->
      <div class="card">
        <h3 class="text-base font-semibold text-surface-900 dark:text-white mb-5 flex items-center gap-2">
          <svg class="w-5 h-5 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" /></svg>
          二步验证 (2FA)
        </h3>

        <!-- Already enabled -->
        <div v-if="securityStore.totpEnabled && !twoFaSetup" class="space-y-4">
          <div class="flex items-center gap-3 p-4 rounded-xl bg-emerald-50 dark:bg-emerald-900/10 border border-emerald-200 dark:border-emerald-800">
            <svg class="w-5 h-5 text-emerald-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <p class="text-sm text-emerald-700 dark:text-emerald-400">二步验证已启用，您的账号受到额外保护。</p>
          </div>
          <button
            @click="disable2FA"
            :disabled="twoFaLoading"
            class="py-2 px-4 rounded-xl text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors text-sm"
          >
            禁用二步验证
          </button>
        </div>

        <!-- Setup in progress -->
        <div v-else-if="twoFaSetup" class="space-y-4">
          <p class="text-sm text-surface-600 dark:text-surface-400">
            使用身份验证器 App（如 Google Authenticator、Authy）扫描下方二维码：
          </p>
          <div class="flex justify-center p-4 bg-white rounded-xl">
            <img :src="twoFaSetup.qr_code" alt="2FA QR Code" class="w-48 h-48" />
          </div>
          <div class="text-center">
            <p class="text-xs text-surface-400 mb-1">或手动输入密钥：</p>
            <code class="text-sm font-mono bg-surface-100 dark:bg-surface-700 px-3 py-1 rounded">{{ twoFaSetup.secret }}</code>
          </div>
          <div>
            <label class="label">输入验证码确认</label>
            <input
              v-model="twoFaCode"
              type="text"
              inputmode="numeric"
              maxlength="6"
              class="input-field text-center text-xl tracking-[0.5em]"
              placeholder="000000"
            />
          </div>
          <div class="flex gap-3">
            <button
              @click="verify2FASetup"
              :disabled="twoFaLoading"
              class="flex-1 btn-primary"
            >
              {{ twoFaLoading ? '验证中...' : '确认启用' }}
            </button>
            <button
              @click="cancel2FASetup"
              class="px-4 py-2 rounded-xl text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors text-sm"
            >
              取消
            </button>
          </div>
        </div>

        <!-- Not enabled -->
        <div v-else class="space-y-4">
          <p class="text-sm text-surface-600 dark:text-surface-400">
            启用二步验证后，登录时需要输入身份验证器 App 生成的验证码，为您的账号增加一层安全保障。
          </p>
          <button
            @click="setup2FA"
            :disabled="twoFaLoading"
            class="btn-primary"
          >
            {{ twoFaLoading ? '初始化中...' : '启用二步验证' }}
          </button>
        </div>

        <!-- Backup codes display -->
        <div v-if="backupCodes.length > 0" class="mt-4 p-4 rounded-xl bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800">
          <p class="text-sm font-medium text-amber-800 dark:text-amber-300 mb-2">请保存以下备用码（仅显示一次）：</p>
          <div class="grid grid-cols-2 gap-2">
            <code v-for="code in backupCodes" :key="code" class="text-sm font-mono text-amber-700 dark:text-amber-400">{{ code }}</code>
          </div>
          <p class="text-xs text-amber-600 dark:text-amber-500 mt-2">当您无法使用身份验证器时，可以使用备用码登录。</p>
        </div>
      </div>

      <!-- Active sessions -->
      <div class="card">
        <h3 class="text-base font-semibold text-surface-900 dark:text-white mb-5 flex items-center gap-2">
          <svg class="w-5 h-5 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25" /></svg>
          活跃设备
        </h3>

        <div v-if="sessionsLoading" class="flex items-center justify-center py-8">
          <svg class="animate-spin w-6 h-6 text-brand-500" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>

        <div v-else-if="sessions.length === 0" class="text-center py-8 text-surface-400 text-sm">
          暂无活跃设备
        </div>

        <div v-else class="space-y-3">
          <div
            v-for="s in sessions"
            :key="s.id"
            class="flex items-center gap-3 p-3 rounded-xl"
            :class="s.is_current ? 'bg-brand-50 dark:bg-brand-900/10 border border-brand-200 dark:border-brand-800' : 'bg-surface-50 dark:bg-surface-700/30'"
          >
            <div class="w-10 h-10 rounded-lg flex items-center justify-center"
                 :class="s.is_current ? 'bg-brand-100 dark:bg-brand-900/30' : 'bg-surface-100 dark:bg-surface-600/30'">
              <svg class="w-5 h-5" :class="s.is_current ? 'text-brand-600 dark:text-brand-400' : 'text-surface-500'" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25" />
              </svg>
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-surface-800 dark:text-surface-200 truncate">
                {{ s.device_info || '未知设备' }}
              </p>
              <p class="text-xs text-surface-400">
                {{ s.ip_address }} · {{ formatTime(s.created_at) }}
                <span v-if="s.is_current" class="text-brand-500 font-medium"> · 当前设备</span>
              </p>
            </div>
            <button
              v-if="!s.is_current"
              @click="revokeSession(s.id)"
              class="text-xs text-surface-400 hover:text-red-500 transition-colors px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
            >
              退出
            </button>
          </div>

          <button
            v-if="sessions.length > 1"
            @click="logoutAllDevices"
            class="w-full mt-2 py-2 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition-colors"
          >
            退出所有其他设备
          </button>
        </div>
      </div>

      <!-- Login history -->
      <div class="card">
        <h3 class="text-base font-semibold text-surface-900 dark:text-white mb-5 flex items-center gap-2">
          <svg class="w-5 h-5 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          登录历史
        </h3>

        <div v-if="historyLoading" class="flex items-center justify-center py-8">
          <svg class="animate-spin w-6 h-6 text-brand-500" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>

        <div v-else-if="history.length === 0" class="text-center py-8 text-surface-400 text-sm">
          暂无登录记录
        </div>

        <div v-else>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-xs text-surface-400 border-b border-surface-100 dark:border-surface-700">
                  <th class="pb-2 font-medium">时间</th>
                  <th class="pb-2 font-medium">IP</th>
                  <th class="pb-2 font-medium">设备</th>
                  <th class="pb-2 font-medium">状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="h in history" :key="h.id" class="border-b border-surface-50 dark:border-surface-700/50">
                  <td class="py-2.5 text-surface-600 dark:text-surface-300">{{ formatTime(h.login_at) }}</td>
                  <td class="py-2.5 text-surface-500 dark:text-surface-400 font-mono text-xs">{{ h.ip_address }}</td>
                  <td class="py-2.5 text-surface-500 dark:text-surface-400">
                    {{ h.browser }} / {{ h.os }}
                  </td>
                  <td class="py-2.5">
                    <span v-if="h.success" class="text-xs px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400">成功</span>
                    <span v-else class="text-xs px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/20 text-red-600 dark:text-red-400">
                      {{ h.failure_reason === 'wrong_password' ? '密码错误' : h.failure_reason === 'account_locked' ? '账号锁定' : '失败' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div v-if="historyPages > 1" class="flex items-center justify-between mt-4 pt-3 border-t border-surface-100 dark:border-surface-700">
            <p class="text-xs text-surface-400">共 {{ historyTotal }} 条记录</p>
            <div class="flex gap-1">
              <button
                @click="loadHistory(historyPage - 1)"
                :disabled="historyPage <= 1"
                class="px-3 py-1 text-xs rounded-lg transition-colors"
                :class="historyPage <= 1 ? 'text-surface-300 cursor-not-allowed' : 'text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-700'"
              >
                上一页
              </button>
              <span class="px-3 py-1 text-xs text-surface-400">{{ historyPage }} / {{ historyPages }}</span>
              <button
                @click="loadHistory(historyPage + 1)"
                :disabled="historyPage >= historyPages"
                class="px-3 py-1 text-xs rounded-lg transition-colors"
                :class="historyPage >= historyPages ? 'text-surface-300 cursor-not-allowed' : 'text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-700'"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab: Subscription -->
    <div v-if="activeTab === 'subscription'" class="space-y-6">
      <div v-if="subscriptionLoading" class="card flex items-center justify-center py-12">
        <svg class="animate-spin w-8 h-8 text-brand-500" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>

      <template v-else>
        <!-- Current Plan -->
        <div class="card">
          <h3 class="text-base font-semibold text-surface-900 dark:text-white mb-5 flex items-center gap-2">
            <svg class="w-5 h-5 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" />
            </svg>
            当前套餐
          </h3>

          <div class="flex items-center justify-between p-4 rounded-xl bg-surface-50 dark:bg-surface-700/30">
            <div>
              <h4 class="text-lg font-bold text-surface-900 dark:text-white">
                {{ plan?.display_name || '免费版' }}
              </h4>
              <p v-if="subscription" class="text-sm text-surface-500 dark:text-surface-400 mt-1">
                {{ subscription.billing_cycle === 'yearly' ? '年付' : '月付' }}
                · 到期时间：{{ subscription.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : '-' }}
              </p>
              <p v-else class="text-sm text-surface-500 dark:text-surface-400 mt-1">
                基础功能，每月 50 次 AI 调用
              </p>
            </div>
            <span
              class="px-3 py-1.5 rounded-full text-sm font-bold"
              :class="plan?.name === 'pro'
                ? 'bg-gradient-to-r from-brand-500 to-violet-500 text-white'
                : 'bg-surface-200 dark:bg-surface-600 text-surface-600 dark:text-surface-300'"
            >
              {{ plan?.name === 'pro' ? 'PRO' : 'FREE' }}
            </span>
          </div>

          <div class="mt-4 flex gap-3">
            <button
              v-if="plan?.name !== 'pro'"
              @click="$router.push('/pricing')"
              class="flex-1 py-2.5 px-4 rounded-xl bg-gradient-to-r from-brand-500 to-violet-500 text-white font-medium shadow-lg shadow-brand-500/25 hover:shadow-xl transition-all duration-200"
            >
              升级到 Pro
            </button>
            <button
              v-if="subscription"
              @click="cancelSubscription"
              class="py-2.5 px-4 rounded-xl text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors text-sm"
            >
              取消订阅
            </button>
          </div>
        </div>

        <!-- Usage Summary -->
        <div v-if="usage" class="card">
          <h3 class="text-base font-semibold text-surface-900 dark:text-white mb-5 flex items-center gap-2">
            <svg class="w-5 h-5 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
            </svg>
            本月用量
          </h3>

          <div class="space-y-4">
            <!-- AI Calls -->
            <div>
              <div class="flex justify-between text-sm mb-2">
                <span class="text-surface-600 dark:text-surface-400">AI 调用次数</span>
                <span class="font-medium text-surface-900 dark:text-white">
                  {{ usage.calls_used }} / {{ usage.calls_limit }}
                </span>
              </div>
              <div class="h-2 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :class="usage.calls_pct >= 90 ? 'bg-red-500' : usage.calls_pct >= 70 ? 'bg-yellow-500' : 'bg-green-500'"
                  :style="{ width: `${Math.min(100, usage.calls_pct)}%` }"
                />
              </div>
            </div>

            <!-- Tokens -->
            <div>
              <div class="flex justify-between text-sm mb-2">
                <span class="text-surface-600 dark:text-surface-400">Token 消耗</span>
                <span class="font-medium text-surface-900 dark:text-white">
                  {{ (usage.tokens_used / 1000).toFixed(0) }}K / {{ (usage.tokens_limit / 1000).toFixed(0) }}K
                </span>
              </div>
              <div class="h-2 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :class="usage.tokens_pct >= 90 ? 'bg-red-500' : usage.tokens_pct >= 70 ? 'bg-yellow-500' : 'bg-green-500'"
                  :style="{ width: `${Math.min(100, usage.tokens_pct)}%` }"
                />
              </div>
            </div>
          </div>

          <button
            @click="$router.push('/usage')"
            class="w-full mt-4 py-2.5 text-sm text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900/20 rounded-xl transition-colors"
          >
            查看详细用量
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.slide-up-enter-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.slide-up-leave-active { transition: all 0.2s ease; }
.slide-up-enter-from, .slide-up-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
