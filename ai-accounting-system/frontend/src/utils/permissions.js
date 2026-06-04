/**
 * Permission constants and helper utilities for RBAC.
 */

export const PERMISSIONS = {
  // User management
  USER_LIST: 'user:list',
  USER_READ: 'user:read',
  USER_UPDATE_STATUS: 'user:update_status',
  USER_ASSIGN_ROLE: 'user:assign_role',

  // Transactions
  TRANSACTION_READ: 'transaction:read',
  TRANSACTION_CREATE: 'transaction:create',
  TRANSACTION_UPDATE: 'transaction:update',
  TRANSACTION_DELETE: 'transaction:delete',

  // AI
  AI_CALL: 'ai:call',
  AI_AGENT: 'ai:agent',

  // Categories
  CATEGORY_MANAGE: 'category:manage',

  // Subscription
  SUBSCRIPTION_MANAGE: 'subscription:manage',

  // Reports
  REPORT_EXPORT: 'report:export',

  // Audit
  AUDIT_READ: 'audit:read',

  // System
  SYSTEM_CONFIG: 'system:config',
}

export const ROLES = {
  OWNER: 'owner',
  ADMIN: 'admin',
  MEMBER: 'member',
  VIEWER: 'viewer',
}

/**
 * Check if a permission list includes a specific permission.
 */
export function hasPermission(userPermissions, codename) {
  if (!userPermissions || !Array.isArray(userPermissions)) return false
  return userPermissions.includes(codename)
}

/**
 * Check if user has ANY of the listed permissions.
 */
export function hasAnyPermission(userPermissions, codenames) {
  if (!codenames || !Array.isArray(codenames)) return false
  return codenames.some(c => hasPermission(userPermissions, c))
}

/**
 * Check if user has ALL of the listed permissions.
 */
export function hasAllPermissions(userPermissions, codenames) {
  if (!codenames || !Array.isArray(codenames)) return false
  return codenames.every(c => hasPermission(userPermissions, c))
}
