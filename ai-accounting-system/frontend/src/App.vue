<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import GlobalToast from '@/components/GlobalToast.vue'
import GlobalLoading from '@/components/GlobalLoading.vue'
import NetworkStatus from '@/components/NetworkStatus.vue'

const themeStore = useThemeStore()
const userStore = useUserStore()
const appStore = useAppStore()

function handleOnline() { appStore.setOnline(true) }
function handleOffline() { appStore.setOnline(false) }

onMounted(() => {
  themeStore.initTheme()
  userStore.loadUser()
  window.addEventListener('online', handleOnline)
  window.addEventListener('offline', handleOffline)
})

onUnmounted(() => {
  window.removeEventListener('online', handleOnline)
  window.removeEventListener('offline', handleOffline)
})
</script>

<template>
  <div :class="{ 'dark': themeStore.isDark }">
    <div class="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors duration-200">
      <router-view />
    </div>
    <GlobalToast />
    <GlobalLoading />
    <NetworkStatus />
  </div>
</template>
