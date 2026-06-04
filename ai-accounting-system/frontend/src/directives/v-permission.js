import { useSecurityStore } from '@/stores/security'

/**
 * v-permission directive
 *
 * Usage:
 *   v-permission="'transaction:create'"        — single permission
 *   v-permission="['transaction:create', 'transaction:update']"  — ANY of these
 *
 * Elements without the required permission are removed from the DOM.
 */
export const vPermission = {
  mounted(el, binding) {
    checkPermission(el, binding)
  },
  updated(el, binding) {
    checkPermission(el, binding)
  },
}

function checkPermission(el, binding) {
  const securityStore = useSecurityStore()
  const value = binding.value

  if (!value) return

  const required = Array.isArray(value) ? value : [value]
  const hasIt = required.some(p => securityStore.hasPerm(p))

  if (!hasIt) {
    el.parentNode?.removeChild(el)
  }
}
