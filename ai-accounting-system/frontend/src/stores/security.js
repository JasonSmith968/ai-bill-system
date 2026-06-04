import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { hasPermission, hasAnyPermission } from '@/utils/permissions'

export const useSecurityStore = defineStore('security', () => {
  const role = ref('')
  const permissions = ref([])
  const totpEnabled = ref(false)

  const isOwner = computed(() => role.value === 'owner')
  const isAdmin = computed(() => ['owner', 'admin'].includes(role.value))
  const isViewer = computed(() => role.value === 'viewer')

  function hasPerm(codename) {
    return hasPermission(permissions.value, codename)
  }

  function hasAnyPerm(codenames) {
    return hasAnyPermission(permissions.value, codenames)
  }

  function loadFromUser(user) {
    if (!user) {
      role.value = ''
      permissions.value = []
      totpEnabled.value = false
      return
    }
    role.value = user.role || ''
    permissions.value = user.permissions || []
    totpEnabled.value = user.totp_enabled || false
  }

  function reset() {
    role.value = ''
    permissions.value = []
    totpEnabled.value = false
  }

  return {
    role,
    permissions,
    totpEnabled,
    isOwner,
    isAdmin,
    isViewer,
    hasPerm,
    hasAnyPerm,
    loadFromUser,
    reset,
  }
})
