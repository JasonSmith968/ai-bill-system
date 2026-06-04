<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import api from '@/utils/api'

const router = useRouter()
const userStore = useUserStore()

const plans = ref([])
const loading = ref(true)
const billingCycle = ref('monthly')
const selectedPlan = ref(null)
const showPaymentModal = ref(false)
const processing = ref(false)

const fetchPlans = async () => {
  try {
    const { data } = await api.get('/billing/plans')
    plans.value = data.plans
  } catch (e) {
    console.error('Failed to fetch plans:', e)
  } finally {
    loading.value = false
  }
}

const getPrice = (plan) => {
  if (billingCycle.value === 'yearly') {
    return plan.price_yearly
  }
  return plan.price_monthly
}

const getMonthlyPrice = (plan) => {
  if (billingCycle.value === 'yearly') {
    return (plan.price_yearly / 12).toFixed(1)
  }
  return plan.price_monthly
}

const yearlyDiscount = (plan) => {
  if (plan.price_monthly === 0) return 0
  return Math.round((1 - plan.price_yearly / (plan.price_monthly * 12)) * 100)
}

const selectPlan = (plan) => {
  if (plan.name === 'free') return
  selectedPlan.value = plan
  showPaymentModal.value = true
}

const processPayment = async (method) => {
  if (!selectedPlan.value) return
  processing.value = true

  try {
    const { data } = await api.post('/billing/checkout', {
      plan_id: selectedPlan.value.id,
      billing_cycle: billingCycle.value,
      payment_method: method
    })

    if (method === 'stripe' && data.checkout_url) {
      window.location.href = data.checkout_url
    } else if (method === 'alipay' && data.payment_url) {
      window.location.href = data.payment_url
    }
  } catch (e) {
    console.error('Payment failed:', e)
    alert(e.response?.data?.error || '支付创建失败，请重试')
  } finally {
    processing.value = false
    showPaymentModal.value = false
  }
}

const currentPlan = computed(() => userStore.user?.plan_name || 'free')

onMounted(fetchPlans)
</script>

<template>
  <div class="min-h-screen bg-gradient-to-b from-surface-50 to-white dark:from-surface-900 dark:to-surface-800">
    <!-- Header -->
    <div class="text-center py-16 px-4">
      <h1 class="text-4xl font-bold text-surface-900 dark:text-white mb-4">
        选择适合你的套餐
      </h1>
      <p class="text-lg text-surface-500 dark:text-surface-400 max-w-2xl mx-auto">
        解锁全部 AI 功能，让智能助手帮你更好地管理财务
      </p>

      <!-- Billing Cycle Toggle -->
      <div class="mt-8 inline-flex items-center bg-surface-100 dark:bg-surface-700 rounded-xl p-1">
        <button
          @click="billingCycle = 'monthly'"
          class="px-6 py-2.5 rounded-lg text-sm font-medium transition-all duration-200"
          :class="billingCycle === 'monthly'
            ? 'bg-white dark:bg-surface-600 text-surface-900 dark:text-white shadow-sm'
            : 'text-surface-500 dark:text-surface-400 hover:text-surface-700 dark:hover:text-surface-300'"
        >
          月付
        </button>
        <button
          @click="billingCycle = 'yearly'"
          class="px-6 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 relative"
          :class="billingCycle === 'yearly'
            ? 'bg-white dark:bg-surface-600 text-surface-900 dark:text-white shadow-sm'
            : 'text-surface-500 dark:text-surface-400 hover:text-surface-700 dark:hover:text-surface-300'"
        >
          年付
          <span class="absolute -top-2 -right-2 px-2 py-0.5 bg-green-500 text-white text-xs rounded-full font-bold">
            省23%
          </span>
        </button>
      </div>
    </div>

    <!-- Plans Grid -->
    <div class="max-w-5xl mx-auto px-4 pb-20">
      <div v-if="loading" class="flex justify-center py-20">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-500"></div>
      </div>

      <div v-else class="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
        <div
          v-for="plan in plans"
          :key="plan.id"
          class="relative rounded-2xl border-2 transition-all duration-300 hover:shadow-xl"
          :class="plan.name === 'pro'
            ? 'border-brand-500 bg-white dark:bg-surface-800 shadow-lg shadow-brand-500/10'
            : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800'"
        >
          <!-- Popular Badge -->
          <div v-if="plan.name === 'pro'" class="absolute -top-4 left-1/2 -translate-x-1/2">
            <span class="px-4 py-1.5 bg-gradient-to-r from-brand-500 to-violet-500 text-white text-sm font-bold rounded-full shadow-lg">
              最受欢迎
            </span>
          </div>

          <div class="p-8">
            <!-- Plan Header -->
            <div class="mb-6">
              <h3 class="text-2xl font-bold text-surface-900 dark:text-white">
                {{ plan.display_name }}
              </h3>
              <p class="mt-2 text-surface-500 dark:text-surface-400">
                {{ plan.name === 'free' ? '适合刚开始记账的用户' : '适合需要深度分析的用户' }}
              </p>
            </div>

            <!-- Price -->
            <div class="mb-8">
              <div class="flex items-baseline gap-1">
                <span class="text-4xl font-bold text-surface-900 dark:text-white">
                  ¥{{ getMonthlyPrice(plan) }}
                </span>
                <span class="text-surface-500 dark:text-surface-400">/月</span>
              </div>
              <p v-if="billingCycle === 'yearly'" class="mt-1 text-sm text-surface-500 dark:text-surface-400">
                年付 ¥{{ plan.price_yearly }}
                <span class="text-green-500 font-medium">省{{ yearlyDiscount(plan) }}%</span>
              </p>
              <p v-if="plan.name === 'free'" class="mt-1 text-sm text-green-500 font-medium">
                永久免费
              </p>
            </div>

            <!-- Features -->
            <ul class="space-y-3 mb-8">
              <li
                v-for="(feature, i) in plan.features"
                :key="i"
                class="flex items-start gap-3"
              >
                <svg class="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                <span class="text-surface-700 dark:text-surface-300">{{ feature }}</span>
              </li>
            </ul>

            <!-- CTA Button -->
            <button
              v-if="plan.name === 'free'"
              disabled
              class="w-full py-3 px-6 rounded-xl font-medium transition-all duration-200"
              :class="currentPlan === 'free'
                ? 'bg-surface-100 dark:bg-surface-700 text-surface-500 dark:text-surface-400 cursor-default'
                : 'bg-surface-100 dark:bg-surface-700 text-surface-500 dark:text-surface-400'"
            >
              {{ currentPlan === 'free' ? '当前套餐' : '免费使用' }}
            </button>
            <button
              v-else
              @click="selectPlan(plan)"
              class="w-full py-3 px-6 rounded-xl font-medium transition-all duration-200 transform hover:scale-[1.02]"
              :class="currentPlan === 'pro'
                ? 'bg-surface-100 dark:bg-surface-700 text-surface-500 dark:text-surface-400 cursor-default'
                : 'bg-gradient-to-r from-brand-500 to-violet-500 text-white shadow-lg shadow-brand-500/25 hover:shadow-xl hover:shadow-brand-500/30'"
            >
              {{ currentPlan === 'pro' ? '当前套餐' : '立即升级' }}
            </button>
          </div>
        </div>
      </div>

      <!-- FAQ Section -->
      <div class="mt-20 max-w-3xl mx-auto">
        <h2 class="text-2xl font-bold text-center text-surface-900 dark:text-white mb-10">
          常见问题
        </h2>
        <div class="space-y-6">
          <div class="bg-white dark:bg-surface-800 rounded-xl p-6 border border-surface-200 dark:border-surface-700">
            <h3 class="font-semibold text-surface-900 dark:text-white mb-2">免费版有什么限制？</h3>
            <p class="text-surface-600 dark:text-surface-400">
              免费版每月可使用 50 次 AI 记账功能，100,000 Token 额度。包含基础记账、Dashboard 数据概览等核心功能。
            </p>
          </div>
          <div class="bg-white dark:bg-surface-800 rounded-xl p-6 border border-surface-200 dark:border-surface-700">
            <h3 class="font-semibold text-surface-900 dark:text-white mb-2">可以随时取消订阅吗？</h3>
            <p class="text-surface-600 dark:text-surface-400">
              可以，您可以随时取消订阅。取消后，您的 Pro 权益将持续到当前计费周期结束。
            </p>
          </div>
          <div class="bg-white dark:bg-surface-800 rounded-xl p-6 border border-surface-200 dark:border-surface-700">
            <h3 class="font-semibold text-surface-900 dark:text-white mb-2">支持哪些支付方式？</h3>
            <p class="text-surface-600 dark:text-surface-400">
              我们支持 Stripe（信用卡/借记卡）和支付宝两种支付方式，安全便捷。
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Payment Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showPaymentModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="showPaymentModal = false"></div>
          <div class="relative bg-white dark:bg-surface-800 rounded-2xl shadow-2xl max-w-md w-full p-8">
            <button
              @click="showPaymentModal = false"
              class="absolute top-4 right-4 p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
            >
              <svg class="w-5 h-5 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            <h3 class="text-xl font-bold text-surface-900 dark:text-white mb-2">
              选择支付方式
            </h3>
            <p class="text-surface-500 dark:text-surface-400 mb-6">
              {{ selectedPlan?.display_name }} · {{ billingCycle === 'yearly' ? '年付' : '月付' }} · ¥{{ getPrice(selectedPlan) }}
            </p>

            <div class="space-y-3">
              <button
                @click="processPayment('stripe')"
                :disabled="processing"
                class="w-full flex items-center justify-center gap-3 py-4 px-6 rounded-xl border-2 border-surface-200 dark:border-surface-700 hover:border-brand-500 dark:hover:border-brand-500 transition-all duration-200 disabled:opacity-50"
              >
                <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none">
                  <rect x="2" y="5" width="20" height="14" rx="3" stroke="currentColor" stroke-width="2"/>
                  <path d="M2 10h20" stroke="currentColor" stroke-width="2"/>
                  <path d="M6 14h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <span class="font-medium text-surface-900 dark:text-white">信用卡 / 借记卡</span>
              </button>

              <button
                @click="processPayment('alipay')"
                :disabled="processing"
                class="w-full flex items-center justify-center gap-3 py-4 px-6 rounded-xl border-2 border-surface-200 dark:border-surface-700 hover:border-blue-500 dark:hover:border-blue-500 transition-all duration-200 disabled:opacity-50"
              >
                <svg class="w-6 h-6 text-blue-500" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M21.422 15.358c-1.452-.616-3.018-1.336-4.704-2.168.644-1.34 1.148-2.816 1.504-4.416h-4.08V6.998h5.056V5.878h-5.056V3.126H12.21c-.26 0-.476.216-.476.476v2.276H6.678v1.12h5.056v1.776H7.39v1.12h9.168c-.296 1.252-.7 2.412-1.212 3.456-2.008-.848-4.252-1.572-6.692-2.156-2.44.584-4.684 1.308-6.692 2.156C-.408 14.46-.8 12.46.54 10.14c1.34-2.32 3.68-3.96 6.56-4.64 2.88-.68 5.84-.36 8.24.84 2.4 1.2 4.04 3.16 4.64 5.44.6 2.28.16 4.76-1.2 6.64-1.36 1.88-3.52 3.04-5.92 3.28-2.4.24-4.72-.44-6.4-1.84-1.68-1.4-2.52-3.44-2.28-5.56.08-.72.28-1.4.56-2.04"/>
                </svg>
                <span class="font-medium text-surface-900 dark:text-white">支付宝</span>
              </button>
            </div>

            <p v-if="processing" class="mt-4 text-center text-sm text-surface-500 dark:text-surface-400">
              正在创建支付订单...
            </p>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
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
