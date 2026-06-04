/**
 * Safe Markdown rendering utility.
 *
 * All AI-generated or user-supplied Markdown MUST pass through this module
 * before being rendered via v-html.  This prevents XSS attacks that could
 * be injected through malicious LLM responses or crafted user input.
 *
 * Usage:
 *   import { renderSafeMarkdown } from '@/utils/safeMarkdown'
 *   const html = renderSafeMarkdown(aiResponse)
 *   // then: <div v-html="html" />
 */

import { marked } from 'marked'
import DOMPurify from 'dompurify'

// Configure marked for consistent rendering
marked.setOptions({
  breaks: true,      // Convert \n to <br>
  gfm: true,         // GitHub Flavored Markdown
})

/**
 * Render Markdown to sanitised HTML.
 *
 * @param {string} text - Raw Markdown text (may come from AI or user).
 * @returns {string} Sanitised HTML string safe for v-html.
 */
export function renderSafeMarkdown(text) {
  if (!text || typeof text !== 'string') return ''

  // Step 1: Markdown → HTML
  const rawHtml = marked(text)

  // Step 2: Sanitise with DOMPurify
  const cleanHtml = DOMPurify.sanitize(rawHtml, {
    ALLOWED_TAGS: [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'p', 'br', 'hr',
      'ul', 'ol', 'li',
      'blockquote', 'pre', 'code',
      'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'strong', 'em', 'b', 'i', 'u', 's', 'del',
      'a', 'span', 'div',
      'img',
    ],
    ALLOWED_ATTR: [
      'href', 'target', 'rel', 'src', 'alt', 'title',
      'class', 'id',
      'align', 'valign',
    ],
    // Allow links to open in new tab safely
    ADD_ATTR: ['target'],
  })

  return cleanHtml
}

/**
 * Quick sanitise for plain HTML (non-Markdown).
 * Use when the source is already HTML but still untrusted.
 *
 * @param {string} html - Raw HTML string.
 * @returns {string} Sanitised HTML string.
 */
export function sanitizeHtml(html) {
  if (!html || typeof html !== 'string') return ''
  return DOMPurify.sanitize(html)
}
