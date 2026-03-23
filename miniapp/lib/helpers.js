/**
 * miniapp/lib/helpers.js
 * 
 * Shared helper utilities used across multiple pages.
 */

/**
 * Get emoji for a moderation action type
 * @param {string} action - Action type (ban, mute, warn, etc.)
 * @returns {string} Emoji character
 */
export function getActionEmoji(action) {
  const emojis = {
    'ban': '\u{1F6AB}',
    'unban': '\u2705',
    'mute': '\u{1F507}',
    'unmute': '\u{1F50A}',
    'warn': '\u26A0\uFE0F',
    'kick': '\u{1F462}',
    'purge': '\u{1F9F9}',
    'join': '\u{1F44B}',
    'leave': '\u{1F44B}',
    'promote': '\u2B50',
    'demote': '\u{1F53D}',
    'settings': '\u2699\uFE0F',
  };
  return emojis[action] || '\u{1F4CB}';
}

/**
 * Format an action string for display (snake_case -> Title Case)
 * @param {string} action - Action string
 * @returns {string} Formatted action string
 */
export function formatAction(action) {
  return action?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) || action;
}

/**
 * Format a timestamp into a relative time string
 * @param {string|number} timestamp - ISO date string or Unix timestamp
 * @returns {string} Relative time string (e.g. "5m ago", "2h ago")
 */
export function formatTime(timestamp) {
  const date = new Date(timestamp);
  const diff = new Date() - date;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
  return date.toLocaleDateString();
}

/**
 * Escape HTML entities in a string to prevent XSS
 * @param {string} text - Raw text
 * @returns {string} HTML-safe string
 */
export function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}
