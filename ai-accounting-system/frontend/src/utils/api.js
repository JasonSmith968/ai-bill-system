import axios from 'axios'
import { useUserStore } from '@/stores/user'
import { useToastStore } from '@/stores/toast'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 刷新锁 - 防止多个请求同时触发刷新
let isRefreshing = false
let failedQueue = []

function processQueue(error, token = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    error ? reject(error) : resolve(token)
  })
  failedQueue = []
}

// Request interceptor - attach token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor - handle errors and token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Network error (no response)
    if (!error.response) {
      try {
        const toast = useToastStore()
        toast.error('网络连接失败，请检查网络设置')
      } catch (_) { /* store not ready */ }
      return Promise.reject(error)
    }

    const { status, data } = error.response

    // Token refresh flow for 401
    if (status === 401 && !originalRequest._retry) {
      // 如果正在刷新，排队等待
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then(token => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return api(originalRequest)
        }).catch(err => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const refreshToken = localStorage.getItem('refreshToken')
        if (!refreshToken) throw new Error('No refresh token')

        const response = await axios.post('/api/auth/refresh', {
          refresh_token: refreshToken
        })

        const { access_token, refresh_token } = response.data

        // 同步更新 localStorage 和 Pinia store
        localStorage.setItem('token', access_token)
        localStorage.setItem('refreshToken', refresh_token)

        try {
          const userStore = useUserStore()
          userStore.token = access_token
          userStore.refreshToken = refresh_token
        } catch (_) { /* store not ready */ }

        // 处理排队的请求
        processQueue(null, access_token)

        originalRequest.headers.Authorization = `Bearer ${access_token}`
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        const userStore = useUserStore()
        userStore.logout()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // Show error toast for non-silent errors
    if (status !== 401) {
      try {
        const toast = useToastStore()
        const message = data?.error || _statusMessage(status)

        if (status >= 500) {
          toast.error('服务器错误，请稍后重试')
        } else if (status === 429) {
          toast.warning('请求过于频繁，请稍后再试')
        } else if (status === 403) {
          toast.error(message || '权限不足')
        } else if (status >= 400 && message) {
          toast.error(message)
        }
      } catch (_) { /* store not ready */ }
    }

    return Promise.reject(error)
  }
)

function _statusMessage(status) {
  const messages = {
    400: '请求参数错误',
    403: '权限不足',
    404: '资源不存在',
    405: '请求方法不允许',
    429: '请求过于频繁',
    500: '服务器内部错误',
    502: '网关错误',
    503: '服务不可用',
  }
  return messages[status] || '未知错误'
}

export default api
