/**
 * 统一金额格式化工具函数
 * 所有金额展示必须使用此函数，禁止直接 toLocaleString 或手动拼接
 */

/**
 * 格式化金额为 ¥XX.XX 格式
 * @param {any} value - 金额值（可能是 number/string/null/undefined/object）
 * @returns {string} 格式化后的金额字符串，如 ¥0.00、¥123.45
 */
export function formatCurrency(value) {
  // 处理 null/undefined/空字符串
  if (value === null || value === undefined || value === '') {
    return '¥0.00'
  }

  // 如果是对象，尝试取 amount 字段
  if (typeof value === 'object') {
    if (value.amount !== undefined) {
      return formatCurrency(value.amount)
    }
    return '¥0.00'
  }

  // 转为数字
  const num = Number(value)
  if (isNaN(num)) {
    return '¥0.00'
  }

  return '¥' + num.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

/**
 * 格式化金额为简短格式（大数字显示为万）
 * @param {any} value - 金额值
 * @returns {string} 如 0.00、123.45、1.23万
 */
export function formatAmount(value) {
  if (value === null || value === undefined || value === '') {
    return '0.00'
  }

  if (typeof value === 'object') {
    if (value.amount !== undefined) {
      return formatAmount(value.amount)
    }
    return '0.00'
  }

  const num = Number(value)
  if (isNaN(num)) {
    return '0.00'
  }

  if (num >= 10000) {
    return `${(num / 10000).toFixed(2)}万`
  }
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/**
 * 格式化金额为带符号格式（+¥XX.XX 或 -¥XX.XX）
 * @param {any} value - 金额值
 * @param {string} type - 'income' 或 'expense'
 * @returns {string}
 */
export function formatSignedAmount(value, type) {
  const formatted = formatCurrency(value)
  if (type === 'income') return `+${formatted}`
  if (type === 'expense') return `-${formatted}`
  return formatted
}
