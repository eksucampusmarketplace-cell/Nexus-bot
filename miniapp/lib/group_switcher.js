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

import { showToast } from './components.js?v=1.6.0';
import { apiFetch } from './api.js?v=1.6.0';

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
      // Initial data loaded — full setState is done after groups are computed below
      console.log('[GroupSwitcher] Received user data:', {
        admin_groups: data.admin_groups?.length || 0,
        mod_groups: data.mod_groups?.length || 0,
        member_groups: data.member_groups?.length || 0,
        groups: data.groups?.length || 0,
        is_sudo: data.is_sudo,
        role: data.role
      });
    } catch (e) {
      console.error('[GroupSwitcher] Failed to load /api/me:', e.message);
      return;
    }

    // Gather groups - only include admin/mod groups (not member_groups)
    // Users can only manage groups where they have admin or mod permissions
    const adminGroups = data.admin_groups || [];
    const modGroups = data.mod_groups || [];
    const allGroups = data.groups || [];

    console.log('[GroupSwitcher] Group breakdown:', {
      admin: adminGroups.length,
      mod: modGroups.length,
      manageable: allGroups.length
    });

    // Merge admin/mod groups only (exclude member_groups)
    const groupMap = new Map();
    [...adminGroups, ...modGroups, ...allGroups].forEach(g => {
      if (g && g.chat_id && !groupMap.has(g.chat_id)) {
        groupMap.set(g.chat_id, g);
      }
    });

    this._groups = Array.from(groupMap.values());

    console.log('[GroupSwitcher] Final groups list:', this._groups.length, 'groups',
      this._groups.map(g => `${g.title} (${g.chat_id})`));

    // Single setState call with all fields (prevents overwriting userContext)
    this._store.setState({
      userContext: data,          // Full /api/me response
      user: data.user,
      is_sudo: data.is_sudo,
      role: data.role,
      bot_info: data.bot_info,
      groups: this._groups,
    });

    // Try to restore saved group or use first available
    const saved = sessionStorage.getItem('active_group');
    this._active = this._groups.find(g => g.chat_id == saved)
                || this._groups[0]
                || null;

    console.log('[GroupSwitcher] Active group:', this._active?.title || 'None');

    this._render();

    if (this._active) {
      this._store.getState().setActiveChatId(this._active.chat_id);
      this._store.setState({ activeGroup: this._active });
    }
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
    } else {
      wrap.innerHTML = `<span style="color:var(--text-muted);font-size:var(--text-sm)">No groups</span>`;
    }

    wrap.onclick = () => this._openDropdown(wrap);
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
    this._store.getState().setActiveChatId(group.chat_id);  // Single write — store handles persistence
    this._render();
    showToast(`Switched to ${group.title}`, 'info', 2000);
  }
}
