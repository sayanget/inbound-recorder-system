/**
 * Utility functions for formatting data
 */

/**
 * Format number with thousand separators
 * @param {number} num - Number to format
 * @returns {string} Formatted number
 */
export const formatNumber = (num) => {
    if (num === null || num === undefined) return '0'
    return num.toLocaleString('zh-CN')
}

/**
 * Format number to 10,000 units (万)
 * @param {number} num - Number to format
 * @param {number} decimals - Decimal places
 * @returns {string} Formatted number with unit
 */
export const formatToWan = (num, decimals = 1) => {
    if (num === null || num === undefined) return '0万'
    const wan = num / 10000
    return wan.toFixed(decimals) + '万'
}

/**
 * Format date to locale string
 * @param {string|Date} date - Date to format
 * @param {string} locale - Locale string
 * @returns {string} Formatted date
 */
export const formatDate = (date, locale = 'zh-CN') => {
    if (!date) return ''
    const d = new Date(date)
    return d.toLocaleDateString(locale)
}

/**
 * Format percentage
 * @param {number} value - Value to format
 * @param {number} decimals - Decimal places
 * @returns {string} Formatted percentage
 */
export const formatPercentage = (value, decimals = 2) => {
    if (value === null || value === undefined) return '0%'
    return value.toFixed(decimals) + '%'
}
