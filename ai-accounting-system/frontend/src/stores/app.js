import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const loading = ref(false)
  const loadingText = ref('')
  const isOnline = ref(navigator.onLine)

  function startLoading(text = '') {
    loading.value = true
    loadingText.value = text
  }

  function stopLoading() {
    loading.value = false
    loadingText.value = ''
  }

  function setOnline(status) {
    isOnline.value = status
  }

  return {
    loading,
    loadingText,
    isOnline,
    startLoading,
    stopLoading,
    setOnline
  }
})
