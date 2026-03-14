/**
 * miniapp/lib/bulk_actions.js
 *
 * Bulk member action system.
 * Activates when any MemberRow checkbox is ticked.
 * Shows floating action bar at bottom of screen.
 * Actions: ban, mute, approve, unapprove, warn, kick
 *
 * Usage:
 *   import { BulkActionManager } from './bulk_actions.js';
 *   const bam = new BulkActionManager(store);
 *   bam.register(memberRowEl, memberId);
 *   // Automatically shows bar when selections made
 */

import { showToast } from './components.js?v=1.6.0';
import { apiFetch } from './api.js?v=1.6.0';

export class BulkActionManager {
  constructor(store) {
    this._store     = store;
    this._selected  = new Set();
    this._bar       = null;
    this._callbacks = {};
  }

  onAction(action, fn) { this._callbacks[action] = fn; return this; }

  select(memberId) {
    this._selected.add(memberId);
    this._update();
  }

  deselect(memberId) {
    this._selected.delete(memberId);
    this._update();
  }

  clearAll() {
    this._selected.clear();
    this._update();
    document.querySelectorAll('.member-checkbox').forEach(cb => cb.checked = false);
  }

  _update() {
    if (this._selected.size === 0) {
      this._bar?.remove();
      this._bar = null;
    } else {
      if (!this._bar) this._createBar();
      this._bar.querySelector('#bulk-count').textContent =
        `${this._selected.size} selected`;
    }
  }

  _createBar() {
    this._bar = document.createElement('div');
    this._bar.style.cssText = `
      position:fixed;
      bottom:calc(var(--bottomnav-h) + 12px);
      left:50%;transform:translateX(-50%);
      background:var(--bg-elevated);
      border:1px solid var(--border);
      border-radius:var(--r-2xl);
      padding:var(--sp-3) var(--sp-4);
      display:flex;align-items:center;gap:var(--sp-3);
      box-shadow:var(--shadow-xl);
      z-index:200;
      animation:scale-in var(--dur-normal) var(--ease-out);
      white-space:nowrap;
    `;
    this._bar.innerHTML = `
      <span id="bulk-count" style="font-size:var(--text-sm);
        font-weight:var(--fw-semibold);color:var(--accent)">0 selected</span>
      <div style="width:1px;height:20px;background:var(--border)"></div>
      ${[
        { id: 'ban',       icon: '🚫', label: 'Ban',       color: 'var(--danger)'  },
        { id: 'mute',      icon: '🔇', label: 'Mute',      color: 'var(--warning)' },
        { id: 'kick',      icon: '👢', label: 'Kick',      color: 'var(--warning)' },
        { id: 'approve',   icon: '✅', label: 'Approve',   color: 'var(--success)' },
        { id: 'unapprove', icon: '❌', label: 'Unapprove', color: 'var(--danger)'  },
      ].map(a => `
        <button data-bulk="${a.id}" title="${a.label}" style="
          background:none;border:none;cursor:pointer;
          font-size:20px;padding:4px;border-radius:var(--r-sm);
          color:${a.color};transition:background var(--dur-fast);
        ">${a.icon}</button>
      `).join('')}
      <div style="width:1px;height:20px;background:var(--border)"></div>
      <button id="bulk-cancel" style="
        background:none;border:none;cursor:pointer;
        font-size:var(--text-sm);color:var(--text-muted);padding:4px;
      ">Cancel</button>
    `;

    this._bar.querySelectorAll('[data-bulk]').forEach(btn => {
      btn.onclick = () => this._execute(btn.dataset.bulk);
      btn.onmouseenter = () => btn.style.background = 'var(--bg-hover)';
      btn.onmouseleave = () => btn.style.background = 'none';
    });
    this._bar.querySelector('#bulk-cancel').onclick = () => this.clearAll();
    document.body.appendChild(this._bar);
  }

  async _execute(action) {
    const ids = Array.from(this._selected);
    const chatId = this._store.getState().activeChatId;

    try {
      const data = await apiFetch(`/api/groups/${chatId}/members/bulk`, {
        method: 'POST',
        body: JSON.stringify({ action, user_ids: ids }),
      });
      showToast(`${action} applied to ${ids.length} members`, 'success');
      this._callbacks[action]?.(ids, data);
    } catch (e) {
      showToast(`Action failed: ${e.message}`, 'error');
    }
    this.clearAll();
  }
}
