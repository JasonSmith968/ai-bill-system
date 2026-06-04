<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import api from '@/utils/api'

const router = useRouter()
const route = useRoute()

const status = ref('loading')
const message = ref('')

const verifyPayment = async () => {
  const sessionId = route.query.session_id

  if (!sessionId) {
    status.value = 'error'
    message.value = '缺少支付会话信息'
    return
  }

  try {
    const { data } = await api.post('/billing/checkout/success', {
      session_id: sessionId
    })

    if (data.status === 'success') {
      status.value = 'success'
      message.value = data.message || '订阅激活成功'
    } else {
      status.value = 'pending'
      message.value = data.message || '支付处理中'
    }
  } catch (e) {
    status.value = 'error'
    message.value = e.response?.data?.error || '支付验证失败'
  }
}

onMounted(() => {
  verifyPayment()
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-b from-surface-50 to-white dark:from-surface-900 dark:to-surface-800 p-4">
    <div class="max-w-md w-full text-center">
      <!-- Loading -->
      <div v-if="status === 'loading'" class="space-y-6">
        <div class="w-20 h-20 mx-auto rounded-full bg-brand-50 dark:bg-brand-900/20 flex items-center justify-center">
          <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-brand-500"></div>
        </div>
        <h2 class="text-2xl font-bold text-surface-900 dark:text-white">正在验证支付...</h2>
        <p class="text-surface-500 dark:text-surface-400">请稍候，我们正在确认您的支付</p>
      </div>

      <!-- Success -->
      <div v-else-if="status === 'success'" class="space-y-6">
        <div class="w-20 h-20 mx-auto rounded-full bg-green-50 dark:bg-green-900/20 flex items-center justify-center animate-bounce-in">
          <svg class="w-10 h-10 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 class="text-2xl font-bold text-surface-900 dark:text-white">支付成功！</h2>
        <p class="text-surface-600 dark:text-surface-400">{{ message }}</p>
        <p class="text-surface-500 dark:text-surface-500">感谢您的订阅，Pro 版功能已解锁</p>

        <div class="pt-4 space-y-3">
          <button
            @click="router.push('/')"
            class="w-full py-3 px-6 rounded-xl bg-gradient-to-r from-brand-500 to-violet-500 text-white font-medium shadow-lg shadow-brand-500/25 hover:shadow-xl transition-all duration-200"
          >
            开始使用 Pro 功能
          </button>
          <button
            @click="router.push('/usage')"
            class="w-full py-3 px-6 rounded-xl text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
          >
            查看用量详情
          </button>
        </div>
      </div>

      <!-- Pending -->
      <div v-else-if="status === 'pending'" class="space-y-6">
        <div class="w-20 h-20 mx-auto rounded-full bg-yellow-50 dark:bg-yellow-900/20 flex items-center justify-center">
          <svg class="w-10 h-10 text-yellow-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h2 class="text-2xl font-bold text-surface-900 dark:text-white">支付处理中</h2>
        <p class="text-surface-600 dark:text-surface-400">{{ message }}</p>
        <p class="text-surface-500 dark:text-surface-500">请稍候刷新页面查看状态</p>

        <button
          @click="router.push('/')"
          class="w-full py-3 px-6 rounded-xl bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 font-medium hover:bg-surface-200 dark:hover:bg-surface-600 transition-colors"
        >
          返回首页
        </button>
      </div>

      <!-- Error -->
      <div v-else class="space-y-6">
        <div class="w-20 h-20 mx-auto rounded-full bg-red-50 dark:bg-red-900/20 flex items-center justify-center">
          <svg class="w-10 h-10 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h2 class="text-2xl font-bold text-surface-900 dark:text-white">支付验证失败</h2>
        <p class="text-surface-600 dark:text-surface-400">{{ message }}</p>

        <div class="pt-4 space-y-3">
          <button
            @click="router.push('/pricing')"
            class="w-full py-3 px-6 rounded-xl bg-gradient-to-r from-brand-500 to-violet-500 text-white font-medium shadow-lg shadow-brand-500/25 hover:shadow-xl transition-all duration-200"
          >
            返回定价页
          </button>
          <button
            @click="router.push('/')"
            class="w-full py-3 px-6 rounded-xl text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
          >
            返回首页
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes bounce-in {
  0% { transform: scale(0); opacity: 0; }
  50% { transform: scale(1.1); }
  100% { transform: scale(1); opacity: 1; }
}
.animate-bounce-in {
  animation: bounce-in 0.5s ease-out;
}
</style>
