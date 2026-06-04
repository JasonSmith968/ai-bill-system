import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'
import { useSecurityStore } from '@/stores/security'

export const useUserStore = defineStore('user', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')
  const refreshToken = ref(localStorage.getItem('refreshToken') || '')
  const pendingTwoFa = ref(false)
  const tempToken = ref('')

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => {
    if (!user.value) return false
    return ['owner', 'admin'].includes(user.value.role) || user.value.is_admin || false
  })

  async function loadUser() {
    if (!token.value) return

    try {
      const response = await api.get('/auth/me')
      user.value = response.data.user
      const securityStore = useSecurityStore()
      securityStore.loadFromUser(response.data.user)
    } catch (error) {
      console.error('加载用户信息失败:', error)
      logout()
    }
  }

  async function login(username, password) {
    const response = await api.post('/auth/login', { username, password })
    const data = response.data

    // 2FA required — store temp token and wait for verification
    if (data.requires_2fa) {
      pendingTwoFa.value = true
      tempToken.value = data.temp_token
      return data
    }

    _applyTokens(data)
    return data
  }

  async function verify2FA(code) {
    const response = await api.post('/auth/login/verify-2fa', {
      temp_token: tempToken.value,
      code,
    })
    const data = response.data

    pendingTwoFa.value = false
    tempToken.value = ''
    _applyTokens(data)
    return data
  }

  function cancel2FA() {
    pendingTwoFa.value = false
    tempToken.value = ''
  }

  function _applyTokens(data) {
    token.value = data.access_token
    refreshToken.value = data.refresh_token
    user.value = data.user

    localStorage.setItem('token', data.access_token)
    localStorage.setItem('refreshToken', data.refresh_token)

    if (data.user) {
      const securityStore = useSecurityStore()
      securityStore.loadFromUser(data.user)
    }
  }

  async function register(username, email, password) {
    const response = await api.post('/auth/register', { username, email, password })
    return response.data
  }

  function logout() {
    user.value = null
    token.value = ''
    refreshToken.value = ''
    pendingTwoFa.value = false
    tempToken.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    const securityStore = useSecurityStore()
    securityStore.reset()
  }

  async function logoutServer() {
    try {
      await api.post('/auth/logout', {
        refresh_token: localStorage.getItem('refreshToken')
      })
    } catch (_) { /* ignore */ }
    logout()
  }

  async function logoutAllDevices() {
    const response = await api.post('/auth/logout', { revoke_all: true })
    logout()
    return response.data
  }

  async function updateProfile(data) {
    const response = await api.put('/auth/me', data)
    user.value = response.data.user
    return response.data
  }

  async function changePassword(oldPassword, newPassword) {
    const response = await api.put('/auth/password', {
      old_password: oldPassword,
      new_password: newPassword
    })
    return response.data
  }

  async function uploadAvatar(file) {
    const formData = new FormData()
    formData.append('image', file)
    const response = await api.post('/auth/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    user.value = response.data.user
    return response.data
  }

  async function deleteAvatar() {
    const response = await api.delete('/auth/avatar')
    user.value = response.data.user
    return response.data
  }

  async function getSessions() {
    const response = await api.get('/auth/sessions')
    return response.data.sessions
  }

  async function revokeSession(sessionId) {
    const response = await api.delete(`/auth/sessions/${sessionId}`)
    return response.data
  }

  async function getLoginHistory(page = 1) {
    const response = await api.get(`/auth/login-history?page=${page}`)
    return response.data
  }

  async function forgotPassword(email) {
    const response = await api.post('/auth/forgot-password', { email })
    return response.data
  }

  async function resetPassword(token, newPassword) {
    const response = await api.post('/auth/reset-password', {
      token,
      new_password: newPassword
    })
    return response.data
  }

  async function verifyEmail(token) {
    const response = await api.get(`/auth/verify-email?token=${token}`)
    if (response.data.user) {
      user.value = response.data.user
    }
    return response.data
  }

  async function resendVerification() {
    const response = await api.post('/auth/resend-verification')
    return response.data
  }

  return {
    user,
    token,
    refreshToken,
    isLoggedIn,
    isAdmin,
    pendingTwoFa,
    tempToken,
    loadUser,
    login,
    verify2FA,
    cancel2FA,
    register,
    logout,
    logoutServer,
    logoutAllDevices,
    updateProfile,
    changePassword,
    uploadAvatar,
    deleteAvatar,
    getSessions,
    revokeSession,
    getLoginHistory,
    forgotPassword,
    resetPassword,
    verifyEmail,
    resendVerification
  }
})
