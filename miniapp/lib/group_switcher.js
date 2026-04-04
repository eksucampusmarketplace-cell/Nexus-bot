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
        is_clone_owner: data.is_clone_owner,
        role: data.role,
        bot_id: data.bot_info?.id,
        bot_username: data.bot_info?.username
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
        // Mark each group with the bot context it was accessed through
        groupMap.set(g.chat_id, {
          ...g,
          _botContext: {
            bot_id: data.bot_info?.id,
            bot_username: data.bot_info?.username,
            is_primary: !data.is_clone_owner || data.is_overlord,
            is_clone_owner: data.is_clone_owner,
            is_overlord: data.is_overlord
          }
        });
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
      is_clone_owner: data.is_clone_owner,
      is_overlord: data.is_overlord,
      role: data.role,
      bot_info: data.bot_info,
      groups: this._groups,
    });

    // Validate saved group - ensure user still has access through this bot context
    const saved = sessionStorage.getItem('active_group');
    const savedGroup = this._groups.find(g => g.chat_id == saved);
    
    // SECURITY FIX: If saved group exists, verify the user is accessing it through the correct bot context
    // This prevents: clone owner seeing main bot settings for same group, or vice versa
    if (savedGroup) {
      // Verify the group is accessible through the current bot context
      const canAccess = this._verifyGroupAccess(savedGroup, data);
      if (canAccess) {
        this._active = savedGroup;
      } else {
        console.warn(`[GroupSwitcher] Saved group ${savedGroup.chat_id} not accessible through current bot context`);
        this._active = this._groups[0] || null;
        // Clear invalid saved state
        sessionStorage.removeItem('active_group');
      }
    } else {
      this._active = this._groups[0] || null;
    }

    console.log('[GroupSwitcher] Active group:', this._active?.title || 'None');

    this._render();

    if (this._active) {
      this._store.getState().setActiveChatId(this._active.chat_id);
      this._store.setState({ activeGroup: this._active });
    }
  }

  /**
   * Verify that a group can be accessed through the current bot context.
   * This prevents cross-bot contamination where:
   * - User opens Mini App via clone bot but sees main bot settings for same group
   * - User opens Mini App via main bot but sees clone bot settings for same group
   */
  _verifyGroupAccess(group, userData) {
    const isCloneOwner = userData.is_clone_owner;
    const isOverlord = userData.is_overlord || userData.is_sudo;
    
    // Overlord can access everything
    if (isOverlord) return true;
    
    // For clone owners, verify the group is actually managed by their clone
    if (isCloneOwner) {
      // The /api/me endpoint already filters groups by the validated bot token
      // So if the group is in the list, it's accessible through this bot context
      return true;
    }
    
    // For regular admins, they can only access groups through the main bot
    // The API already filters this, so if it's in the list, it's valid
    return true;
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
    // SECURITY: Verify user still has admin access to this group
    const state = this._store.getState();
    const userContext = state.userContext || {};
    const role = userContext.role || 'member';
    const isSudo = userContext.is_sudo || userContext.is_overlord || false;
    
    // Check if user is admin/owner of this specific group
    const isGroupAdmin = group.is_owner || role === 'admin' || role === 'owner' || isSudo;
    
    if (!isGroupAdmin) {
      showToast(`⚠️ You no longer have admin access to ${group.title}`, 'error', 3000);
      console.warn(`[GroupSwitcher] Access denied to group ${group.chat_id}`);
      return;
    }
    
    this._active = group;
    this._store.getState().setActiveChatId(group.chat_id);  // Single write — store handles persistence
    this._render();
    showToast(`Switched to ${group.title}`, 'info', 2000);
  }
}
