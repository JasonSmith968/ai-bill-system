import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useToastStore = defineStore('toast', () => {
  const toasts = ref([])
  let nextId = 0

  function show(message, type = 'info', duration = 4000) {
    const id = nextId++
    toasts.value.push({ id, message, type })

    if (duration > 0) {
      setTimeout(() => remove(id), duration)
    }
    return id
  }

  function success(message, duration = 3000) {
    return show(message, 'success', duration)
  }

  function error(message, duration = 5000) {
    return show(message, 'error', duration)
  }

  function warning(message, duration = 4000) {
    return show(message, 'warning', duration)
  }

  function info(message, duration = 3000) {
    return show(message, 'info', duration)
  }

  function remove(id) {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }

  function clear() {
    toasts.value = []
  }

  return {
    toasts,
    show,
    success,
    error,
    warning,
    info,
    remove,
    clear
  }
})
