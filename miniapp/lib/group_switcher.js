/**
 * miniapp/lib/group_switcher.js
 *
 * Multi-group switcher in topbar.
 * Shows current group name + dropdown of all groups.
 * Switching group reloads all store slices for new chat_id.
 * Persists last active group in sessionStorage.
 *
 * Usage:
 *   import { GroupSwitcher } from './group_switcher.js';
 *   const switcher = new GroupSwitcher(topbarEl, store);
 *   await switcher.init();
 */

import { showToast } from './components.js';
import { apiFetch } from './api.js';

export class GroupSwitcher {
  constructor(containerEl, store) {
    this._container = containerEl;
    this._store     = store;
    this._groups    = [];
    this._active    = null;
    this._el        = null;
  }

  async init() {
    let data = {};
    try {
      data = await apiFetch('/api/me');
      this._store.setState({ userContext: data });
    } catch (e) {
      console.error('[GroupSwitcher] Failed to load /api/me:', e.message);
      // Show error in group switcher
      this._renderError('Failed to load groups');
      return;
    }
    
    // Support multiple API response formats
    // groups (old format), admin_groups/mod_groups (new format), or fallback to empty
    this._groups = [
      ...(data.admin_groups || []),
      ...(data.mod_groups || []),
      ...(data.groups || []),
    ];
    
    // Remove duplicates by chat_id
    const seen = new Set();
    this._groups = this._groups.filter(g => {
      if (seen.has(g.chat_id)) return false;
      seen.add(g.chat_id);
      return true;
    });
    
    this._store.setState({ 
      groups: this._groups,
      bot_info: data.bot_info,
      userContext: data.user || data
    });
    
    const saved = sessionStorage.getItem('active_group');
    this._active = this._groups.find(g => String(g.chat_id) === String(saved))
                || this._groups[0]
                || null;
    this._render();
    if (this._active) {
      this._store.getState().setActiveChatId(this._active.chat_id);
      this._store.setState({ activeGroup: this._active });
    }
  }

  _renderError(message) {
    if (this._el) this._el.remove();
    const wrap = document.createElement('div');
    wrap.style.cssText = `
      display:flex;align-items:center;gap:var(--sp-2);
      padding:var(--sp-2) var(--sp-3);
      border-radius:var(--r-lg);border:1px solid var(--border);
      background:var(--bg-input);
      min-width:0;
      color:var(--text-muted);
      font-size:var(--text-sm);
    `;
    wrap.innerHTML = `<span>⚠️ ${message}</span>`;
    this._el = wrap;
    this._container.insertBefore(wrap, this._container.firstChild);
  }

  _render() {
    if (this._el) this._el.remove();
    const wrap = document.createElement('div');
    wrap.style.cssText = `
      display:flex;align-items:center;gap:var(--sp-2);
      cursor:pointer;padding:var(--sp-2) var(--sp-3);
      border-radius:var(--r-lg);border:1px solid var(--border);
      background:var(--bg-input);
      min-width:0;max-width:200px;
      transition:background var(--dur-fast);
      position:relative;
      flex-shrink:0;
    `;
    wrap.onmouseenter = () => wrap.style.background = 'var(--bg-hover)';
    wrap.onmouseleave = () => wrap.style.background = 'var(--bg-input)';

    if (this._active) {
      wrap.innerHTML = `
        <span style="font-size:18px">💬</span>
        <span style="font-size:var(--text-sm);font-weight:var(--fw-medium);
                     white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1">
          ${this._active.title || 'Group'}
        </span>
        <span style="color:var(--text-muted);font-size:12px">▾</span>
      `;
      wrap.onclick = () => this._openDropdown(wrap);
    } else if (this._groups.length === 0) {
      wrap.innerHTML = `
        <span style="font-size:18px">💬</span>
        <span style="color:var(--text-muted);font-size:var(--text-sm);white-space:nowrap;">No groups available</span>
      `;
      wrap.style.cursor = 'default';
    } else {
      wrap.innerHTML = `<span style="color:var(--text-muted);font-size:var(--text-sm)">Select group</span>`;
      wrap.onclick = () => this._openDropdown(wrap);
    }

    this._el = wrap;
    this._container.insertBefore(wrap, this._container.firstChild);
  }

  _openDropdown(anchor) {
    const existing = document.querySelector('#group-dropdown');
    if (existing) { existing.remove(); return; }

    const dropdown = document.createElement('div');
    const rect     = anchor.getBoundingClientRect();
    dropdown.id    = 'group-dropdown';
    dropdown.style.cssText = `
      position:fixed;
      top:${rect.bottom + 8}px;
      left:${rect.left}px;
      width:${Math.max(rect.width, 220)}px;
      background:var(--bg-elevated);
      border:1px solid var(--border);
      border-radius:var(--r-xl);
      box-shadow:var(--shadow-xl);
      z-index:500;
      overflow:hidden;
      animation:scale-in var(--dur-normal) var(--ease-out);
    `;

    this._groups.forEach(group => {
      const item = document.createElement('div');
      const isActive = group.chat_id === this._active?.chat_id;
      item.style.cssText = `
        display:flex;align-items:center;gap:var(--sp-3);
        padding:var(--sp-3) var(--sp-4);
        cursor:pointer;
        background:${isActive ? 'var(--accent-dim)' : 'transparent'};
        transition:background var(--dur-fast);
      `;
      item.innerHTML = `
        <span style="font-size:18px">💬</span>
        <div style="flex:1;min-width:0">
          <div style="font-size:var(--text-sm);font-weight:var(--fw-medium);
                      white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
            ${group.title}
          </div>
          <div style="font-size:var(--text-xs);color:var(--text-muted)">
            ${group.member_count?.toLocaleString() || ''} members
          </div>
        </div>
        ${isActive ? '<span style="color:var(--accent)">✓</span>' : ''}
      `;
      item.onmouseenter = () => { if (!isActive) item.style.background = 'var(--bg-hover)'; };
      item.onmouseleave = () => { if (!isActive) item.style.background = 'transparent'; };
      item.onclick = () => {
        this._switchTo(group);
        dropdown.remove();
      };
      dropdown.appendChild(item);
    });

    document.body.appendChild(dropdown);
    setTimeout(() => {
      document.addEventListener('click', () => dropdown.remove(), { once: true });
    }, 0);
  }

  _switchTo(group) {
    this._active = group;
    sessionStorage.setItem('active_group', group.chat_id);
    this._store.getState().setActiveChatId(group.chat_id);
    this._store.setState({ activeGroup: group });
    this._render();
    showToast(`Switched to ${group.title}`, 'info', 2000);
    
    // Trigger a page refresh to reload data for new group
    const activePage = this._store.getState().activePage;
    if (activePage && activePage !== 'dashboard') {
      // Reload current page data
      window.dispatchEvent(new CustomEvent('group-changed', { detail: group }));
    }
  }
}
