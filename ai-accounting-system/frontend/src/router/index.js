import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useSecurityStore } from '@/stores/security'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { guest: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { guest: true }
  },
  {
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('@/views/ForgotPassword.vue'),
    meta: { guest: true }
  },
  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: () => import('@/views/ResetPassword.vue'),
    meta: { guest: true }
  },
  {
    path: '/verify-email',
    name: 'VerifyEmail',
    component: () => import('@/views/VerifyEmail.vue'),
    meta: { guest: true }
  },
  {
    path: '/pricing',
    name: 'Pricing',
    component: () => import('@/views/Pricing.vue')
  },
  {
    path: '/billing-success',
    name: 'BillingSuccess',
    component: () => import('@/views/BillingSuccess.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue')
      },
      {
        path: 'transactions',
        name: 'Transactions',
        component: () => import('@/views/BillList.vue')
      },
      {
        path: 'ai-accounting',
        name: 'AiAccounting',
        component: () => import('@/views/AiAccounting.vue')
      },
      {
        path: 'analytics',
        name: 'Analytics',
        component: () => import('@/views/Analytics.vue')
      },
      {
        path: 'ai-insights',
        name: 'AiInsights',
        component: () => import('@/views/AiInsights.vue')
      },
      {
        path: 'monthly-report',
        name: 'MonthlyReport',
        component: () => import('@/views/MonthlyReport.vue')
      },
      {
        path: 'bi',
        name: 'BiDashboard',
        component: () => import('@/views/BiDashboard.vue')
      },
      {
        path: 'report-center',
        name: 'ReportCenter',
        component: () => import('@/views/ReportCenter.vue')
      },
      {
        path: 'chat',
        name: 'ChatAssistant',
        component: () => import('@/views/ChatAssistant.vue')
      },
      {
        path: 'ai-agent',
        name: 'AiAgent',
        component: () => import('@/views/AiAgent.vue')
      },
      {
        path: 'multi-agent',
        name: 'MultiAgent',
        component: () => import('@/views/MultiAgent.vue')
      },
      {
        path: 'usage',
        name: 'Usage',
        component: () => import('@/views/UsageDashboard.vue')
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/Profile.vue')
      },
      {
        path: 'admin',
        name: 'Admin',
        component: () => import('@/views/Admin.vue'),
        meta: { permission: 'user:list' }
      },
      {
        path: 'audit-logs',
        name: 'AuditLogs',
        component: () => import('@/views/AuditLog.vue'),
        meta: { permission: 'audit:read' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  const securityStore = useSecurityStore()

  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next('/login')
  } else if (to.meta.guest && userStore.isLoggedIn) {
    next('/')
  } else if (to.meta.permission && !securityStore.hasPerm(to.meta.permission)) {
    next('/')
  } else if (to.meta.requiresAdmin && !userStore.isAdmin) {
    next('/')
  } else {
    next()
  }
})

export default router