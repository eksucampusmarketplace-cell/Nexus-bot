/**
 * miniapp/lib/notifications.js
 *
 * In-app notification center.
 * Stores last 100 notifications in memory.
 * Shows unread badge on bell icon.
 * Opens as BottomSheet with full feed.
 *
 * Notification types:
 *   member_action, bot_action, settings_change,
 *   payment, expiry, system
 *
 * Usage:
 *   import { NotificationCenter } from './notifications.js';
 *   const nc = new NotificationCenter(bellButtonEl);
 *   nc.push({ type: 'bot_action', title: 'User banned', body: '@user123 banned for spam' });
 */

import { BottomSheet } from './components.js?v=1.5.0';

const TYPE_ICONS = {
  member_action:   '👤',
  bot_action:      '🤖',
  settings_change: '⚙️',
  payment:         '⭐',
  expiry:          '⏰',
  system:          '🔔',
};

export class NotificationCenter {
  constructor(bellEl) {
    this._items   = [];
    this._unread  = 0;
    this._bell    = bellEl;
    this._badge   = null;
    this._sheet   = null;
    this._open    = false;
    this._setupBell();
  }

  push(notification) {
    const item = {
      id:        crypto.randomUUID(),
      type:      notification.type || 'system',
      title:     notification.title || '',
      body:      notification.body  || '',
      time:      new Date(),
      read:      false,
      chat_id:   notification.chat_id,
    };
    this._items.unshift(item);
    if (this._items.length > 100) this._items.pop();
    this._unread++;
    this._updateBadge();
    if (this._open) this._render();
    return item;
  }

  markAllRead() {
    this._items.forEach(i => i.read = true);
    this._unread = 0;
    this._updateBadge();
    if (this._open) this._render();
  }

  _setupBell() {
    this._badge = document.createElement('span');
    this._badge.style.cssText = `
      position:absolute;top:-4px;right:-4px;
      min-width:16px;height:16px;
      background:var(--danger);color:white;
      border-radius:var(--r-full);
      font-size:10px;font-weight:var(--fw-bold);
      display:none;align-items:center;justify-content:center;
      padding:0 4px;
    `;
    this._bell.style.position = 'relative';
    this._bell.appendChild(this._badge);
    this._bell.addEventListener('click', () => this._toggle());
  }

  _toggle() {
    if (this._open) {
      this._sheet?.close();
      this._open = false;
    } else {
      this._openSheet();
    }
  }

  _openSheet() {
    this._open = true;
    this.markAllRead();
    const content = document.createElement('div');
    this._contentEl = content;
    this._render();
    this._sheet = BottomSheet({
      title:   '🔔 Notifications',
      content,
      onClose: () => { this._open = false; },
    });
  }

  _render() {
    if (!this._contentEl) return;
    if (this._items.length === 0) {
      this._contentEl.innerHTML = `
        <div style="text-align:center;padding:var(--sp-8) 0;color:var(--text-muted)">
          <div style="font-size:32px;margin-bottom:var(--sp-2)">🔕</div>
          <div style="font-size:var(--text-sm)">No notifications yet</div>
        </div>
      `;
      return;
    }
    this._contentEl.innerHTML = '';
    this._items.forEach(item => {
      const row = document.createElement('div');
      row.style.cssText = `
        display:flex;gap:var(--sp-3);padding:var(--sp-3) 0;
        border-bottom:1px solid var(--border);
        opacity:${item.read ? '0.7' : '1'};
      `;
      row.innerHTML = `
        <span style="font-size:20px;flex-shrink:0">${TYPE_ICONS[item.type]||'🔔'}</span>
        <div style="flex:1;min-width:0">
          <div style="font-size:var(--text-sm);font-weight:var(--fw-medium)">${item.title}</div>
          <div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:2px">${item.body}</div>
          <div style="font-size:var(--text-xs);color:var(--text-disabled);margin-top:4px">
            ${_timeAgo(item.time)}
          </div>
        </div>
      `;
      this._contentEl.appendChild(row);
    });
  }

  _updateBadge() {
    this._badge.style.display = this._unread > 0 ? 'flex' : 'none';
    this._badge.textContent   = this._unread > 99 ? '99+' : this._unread;
  }
}

function _timeAgo(date) {
  const s = Math.round((Date.now() - date) / 1000);
  if (s < 60)   return 'just now';
  if (s < 3600) return `${Math.round(s/60)}m ago`;
  if (s < 86400)return `${Math.round(s/3600)}h ago`;
  return `${Math.round(s/86400)}d ago`;
}
