<script setup>
import { computed } from 'vue'
import { useSecurityStore } from '@/stores/security'

const props = defineProps({
  permission: { type: [String, Array], default: null },
  role: { type: [String, Array], default: null },
})

const securityStore = useSecurityStore()

const allowed = computed(() => {
  if (props.permission) {
    const perms = Array.isArray(props.permission) ? props.permission : [props.permission]
    return perms.some(p => securityStore.hasPerm(p))
  }
  if (props.role) {
    const roles = Array.isArray(props.role) ? props.role : [props.role]
    return roles.includes(securityStore.role)
  }
  return true
})
</script>

<template>
  <slot v-if="allowed" />
</template>
