<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useThemeStore } from '@/stores/theme'
import { useSecurityStore } from '@/stores/security'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const themeStore = useThemeStore()
const securityStore = useSecurityStore()

const sidebarOpen = ref(false)
const collapsed = ref(false)

const menuItems = [
  {
    name: '仪表盘',
    path: '/',
    icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" /></svg>`
  },
  {
    name: '收支记录',
    path: '/transactions',
    icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z" /></svg>`
  },
  {
    name: 'AI 记账',
    path: '/ai-accounting',
    icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" /></svg>`
  },
  {
    name: '财务分析',
    path: '/analytics',
    icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" /></svg>`
  },
  {
    name: 'AI 分析',
    path: '/ai-insights',
    icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" /></svg>`
  },
  {
    name: '月度报告',
    path: '/monthly-report',
    icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>`
  },
  {
    name: 'BI 数据中心',
    path: '/bi',
    icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" /></svg>`
  },
  {
    name: '报告中心',
    path: '/report-center',
    icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>`
  },
  {
    name: 'AI 财务助手',
    path: '/chat',
    icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" /></svg>`
  },
  {
    name: 'AI 记账 Agent',
    path: '/ai-agent',
    icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" /></svg>`
  },
  {
    name: 'Agent 协作',
    path: '/multi-agent',
    icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" /></svg>`
  },
  {
    name: '用量统计',
    path: '/usage',
    icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" /></svg>`
  },
  {
    name: '个人中心',
    path: '/profile',
    icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>`
  },
]

const adminMenuItems = computed(() => {
  const items = []
  if (securityStore.hasPerm('user:list')) {
    items.push({
      name: '管理后台',
      path: '/admin',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" /></svg>`
    })
  }
  if (securityStore.hasPerm('audit:read')) {
    items.push({
      name: '审计日志',
      path: '/audit-logs',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>`
    })
  }
  return items
})

const sidebarWidth = computed(() => collapsed.value ? 'w-[72px]' : 'w-64')

async function handleLogout() {
  await userStore.logoutServer()
  router.push('/login')
}
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-surface-50 dark:bg-surface-900">
    <!-- Desktop Sidebar -->
    <aside
      class="hidden lg:flex lg:flex-col transition-all duration-300 ease-in-out bg-white dark:bg-surface-800 border-r border-surface-200/80 dark:border-surface-700/50"
      :class="sidebarWidth"
    >
      <!-- Logo -->
      <div class="flex items-center h-16 px-4 border-b border-surface-100 dark:border-surface-700/50" :class="collapsed ? 'justify-center' : 'gap-3'">
        <div class="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 flex items-center justify-center flex-shrink-0 shadow-glow">
          <svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <span v-if="!collapsed" class="text-lg font-bold text-gradient whitespace-nowrap">AI 智能记账</span>
      </div>

      <!-- Nav -->
      <nav class="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 group relative"
          :class="route.path === item.path
            ? 'bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400 shadow-sm'
            : 'text-surface-500 dark:text-surface-400 hover:bg-surface-50 dark:hover:bg-surface-700/50 hover:text-surface-800 dark:hover:text-surface-200'"
          :title="collapsed ? item.name : ''"
        >
          <div v-if="route.path === item.path" class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-brand-500 rounded-r-full" />
          <span v-html="item.icon" class="flex-shrink-0" />
          <span v-if="!collapsed" class="text-sm font-medium">{{ item.name }}</span>
        </router-link>

        <div v-if="adminMenuItems.length > 0" class="pt-4 mt-4 border-t border-surface-100 dark:border-surface-700/50">
          <p v-if="!collapsed" class="px-3 mb-2 text-xs font-semibold text-surface-400 dark:text-surface-500 uppercase tracking-wider">管理</p>
          <router-link
            v-for="item in adminMenuItems"
            :key="item.path"
            :to="item.path"
            class="flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200"
            :class="route.path === item.path
              ? 'bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400 shadow-sm'
              : 'text-surface-500 dark:text-surface-400 hover:bg-surface-50 dark:hover:bg-surface-700/50 hover:text-surface-800 dark:hover:text-surface-200'"
          >
            <span v-html="item.icon" class="flex-shrink-0" />
            <span v-if="!collapsed" class="text-sm font-medium">{{ item.name }}</span>
          </router-link>
        </div>
      </nav>

      <!-- Collapse toggle -->
      <div class="px-3 py-2">
        <button
          @click="collapsed = !collapsed"
          class="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700/50 transition-all duration-200"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 transition-transform duration-300" :class="collapsed ? 'rotate-180' : ''">
            <path stroke-linecap="round" stroke-linejoin="round" d="M18.75 19.5l-7.5-7.5 7.5-7.5m-6 15L5.25 12l7.5-7.5" />
          </svg>
          <span v-if="!collapsed" class="text-xs font-medium">收起</span>
        </button>
      </div>

      <!-- User -->
      <div class="p-3 border-t border-surface-100 dark:border-surface-700/50">
        <div class="flex items-center gap-3 px-3 py-2 rounded-xl" :class="collapsed ? 'justify-center' : ''">
          <img
            v-if="userStore.user?.avatar"
            :src="userStore.user.avatar"
            class="w-8 h-8 rounded-full object-cover flex-shrink-0"
          />
          <div v-else class="w-8 h-8 rounded-full bg-gradient-to-br from-brand-400 to-violet-400 flex items-center justify-center flex-shrink-0">
            <span class="text-xs font-bold text-white">
              {{ userStore.user?.username?.charAt(0).toUpperCase() }}
            </span>
          </div>
          <div v-if="!collapsed" class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <p class="text-sm font-semibold text-surface-800 dark:text-surface-200 truncate">{{ userStore.user?.username }}</p>
              <span
                v-if="securityStore.role === 'owner'"
                class="px-1.5 py-0.5 text-[10px] font-bold bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 rounded-full"
              >
                Owner
              </span>
              <span
                v-else-if="securityStore.role === 'admin'"
                class="px-1.5 py-0.5 text-[10px] font-bold bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded-full"
              >
                Admin
              </span>
              <span
                v-if="userStore.user?.plan_name === 'pro'"
                class="px-1.5 py-0.5 text-[10px] font-bold bg-gradient-to-r from-brand-500 to-violet-500 text-white rounded-full"
              >
                PRO
              </span>
            </div>
            <p class="text-xs text-surface-400 dark:text-surface-500 truncate">{{ userStore.user?.email }}</p>
          </div>
        </div>
      </div>
    </aside>

    <!-- Mobile Sidebar Overlay -->
    <Transition name="fade">
      <div
        v-if="sidebarOpen"
        class="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden"
        @click="sidebarOpen = false"
      />
    </Transition>

    <!-- Mobile Sidebar -->
    <Transition name="slide-left">
      <aside
        v-if="sidebarOpen"
        class="fixed inset-y-0 left-0 w-[280px] max-w-[80vw] bg-white dark:bg-surface-800 z-50 flex flex-col shadow-xl lg:hidden"
      >
        <div class="flex items-center justify-between h-16 px-4 border-b border-surface-100 dark:border-surface-700/50">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 flex items-center justify-center shadow-glow">
              <svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span class="text-lg font-bold text-gradient">AI 智能记账</span>
          </div>
          <button @click="sidebarOpen = false" class="p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700">
            <svg class="w-5 h-5 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <nav class="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          <router-link
            v-for="item in [...menuItems, ...adminMenuItems]"
            :key="item.path"
            :to="item.path"
            @click="sidebarOpen = false"
            class="flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200"
            :class="route.path === item.path
              ? 'bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400'
              : 'text-surface-500 dark:text-surface-400 hover:bg-surface-50 dark:hover:bg-surface-700/50'"
          >
            <span v-html="item.icon" class="flex-shrink-0" />
            <span class="text-sm font-medium">{{ item.name }}</span>
          </router-link>
        </nav>
      </aside>
    </Transition>

    <!-- Main Content -->
    <div class="flex-1 flex flex-col overflow-hidden min-w-0">
      <!-- Top Bar -->
      <header class="h-16 flex items-center justify-between px-4 lg:px-8 bg-white/80 dark:bg-surface-800/80 backdrop-blur-xl border-b border-surface-200/60 dark:border-surface-700/40 sticky top-0 z-30">
        <div class="flex items-center gap-3">
          <button
            @click="sidebarOpen = true"
            class="lg:hidden p-2 -ml-2 rounded-xl hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
          >
            <svg class="w-5 h-5 text-surface-600 dark:text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
          <h2 class="text-base font-semibold text-surface-800 dark:text-surface-200 hidden sm:block">
            {{ menuItems.find(i => i.path === route.path)?.name || adminMenuItems.find(i => i.path === route.path)?.name || '仪表盘' }}
          </h2>
        </div>

        <div class="flex items-center gap-2">
          <button
            @click="themeStore.toggleTheme"
            class="p-2 rounded-xl hover:bg-surface-100 dark:hover:bg-surface-700 transition-all duration-200"
            :title="themeStore.isDark ? '切换亮色' : '切换暗色'"
          >
            <svg v-if="themeStore.isDark" class="w-5 h-5 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
            </svg>
            <svg v-else class="w-5 h-5 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
            </svg>
          </button>

          <button
            @click="handleLogout"
            class="flex items-center gap-2 px-3 py-2 text-sm font-medium text-surface-500 dark:text-surface-400 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition-all duration-200"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
            </svg>
            <span class="hidden sm:inline">退出</span>
          </button>
        </div>
      </header>

      <!-- Page Content -->
      <main class="flex-1 overflow-y-auto overflow-x-hidden">
        <div class="p-3 sm:p-4 lg:p-8 max-w-7xl mx-auto w-full min-w-0 pb-20 sm:pb-8 lg:pb-8">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.slide-left-enter-active, .slide-left-leave-active {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-left-enter-from, .slide-left-leave-to {
  transform: translateX(-100%);
}
</style>