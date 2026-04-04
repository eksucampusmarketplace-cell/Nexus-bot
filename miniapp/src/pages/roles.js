/**
 * miniapp/src/pages/roles.js
 * Task 4 of 12 — Roles page
 * Extracted from index.html renderRolesPage() and _showRoleModal()
 */

import { EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

const store = useStore;
const getState = store.getState;

const ROLE_PERMISSIONS = [
  { key: 'can_pin',             label: '📌 Pin messages' },
  { key: 'can_warn',            label: '⚠️ Issue warnings' },
  { key: 'can_mute',            label: '🔇 Mute members' },
  { key: 'can_kick',            label: '👢 Kick members' },
  { key: 'can_ban',             label: '🔨 Ban members' },
  { key: 'can_delete_messages', label: '🗑️ Delete messages' },
  { key: 'exempt_automod',      label: '🛡️ Exempt from automod' },
  { key: 'exempt_antiflood',    label: '💨 Exempt from antiflood' },
  { key: 'can_add_filters',     label: '🔍 Manage filters' },
];
const ROLE_COLORS = ['#7c3aed','#0ea5e9','#10b981','#f59e0b','#ef4444','#ec4899','#6366f1','#64748b'];

function _showRoleModal(chatId, existingRole, onSave) {
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:3000;display:flex;align-items:flex-end;justify-content:center;padding:var(--sp-4);';
  const modal = document.createElement('div');
  modal.style.cssText = 'background:var(--bg-card);border-radius:var(--r-xl);padding:var(--sp-5);width:100%;max-width:480px;max-height:80vh;overflow-y:auto;';
  const title = existingRole ? 'Edit Role' : 'New Role';
  const perms = existingRole?.permissions || {};
  const currentColor = existingRole?.color || ROLE_COLORS[0];
  modal.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-4);">
      <h3 style="font-size:var(--text-sm);font-weight:var(--fw-semibold);margin:0;">${title}</h3>
      <button id="role-modal-close" style="background:none;border:none;cursor:pointer;font-size:18px;color:var(--text-muted);">✕</button>
    </div>
    <div style="margin-bottom:var(--sp-3);">
      <label style="font-size:var(--text-xs);color:var(--text-muted);display:block;margin-bottom:4px;">Role Name</label>
      <input type="text" id="role-name-input" class="input" value="${existingRole?.name || ''}" placeholder="e.g. Moderator" maxlength="32">
    </div>
    <div style="margin-bottom:var(--sp-3);">
      <label style="font-size:var(--text-xs);color:var(--text-muted);display:block;margin-bottom:8px;">Color</label>
      <div style="display:flex;gap:var(--sp-2);flex-wrap:wrap;" id="color-swatches">
        ${ROLE_COLORS.map(c => `<div data-color="${c}" style="width:28px;height:28px;border-radius:50%;background:${c};cursor:pointer;border:2px solid ${c===currentColor?'white':'transparent'};transition:border-color .15s;"></div>`).join('')}
      </div>
    </div>
    <div style="margin-bottom:var(--sp-4);">
      <label style="font-size:var(--text-xs);color:var(--text-muted);display:block;margin-bottom:8px;">Permissions</label>
      <div style="display:flex;flex-direction:column;gap:var(--sp-2);">
        ${ROLE_PERMISSIONS.map(p => `<label style="display:flex;align-items:center;gap:var(--sp-2);cursor:pointer;font-size:var(--text-sm);"><input type="checkbox" data-perm="${p.key}" ${perms[p.key] ? 'checked' : ''} style="accent-color:var(--accent);">${p.label}</label>`).join('')}
      </div>
    </div>
    <div style="display:flex;gap:var(--sp-2);">
      <button id="role-save-btn" class="btn btn-primary" style="flex:1;">Save Role</button>
      <button id="role-modal-cancel" class="btn btn-secondary">Cancel</button>
    </div>
    <div id="role-modal-error" style="display:none;color:var(--danger);font-size:var(--text-xs);margin-top:var(--sp-2);"></div>
  `;
  let selectedColor = currentColor;
  modal.querySelectorAll('[data-color]').forEach(swatch => {
    swatch.addEventListener('click', () => {
      selectedColor = swatch.dataset.color;
      modal.querySelectorAll('[data-color]').forEach(s => s.style.borderColor = s.dataset.color === selectedColor ? 'white' : 'transparent');
    });
  });
  const close = () => overlay.remove();
  modal.querySelector('#role-modal-close').addEventListener('click', close);
  modal.querySelector('#role-modal-cancel').addEventListener('click', close);
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
  modal.querySelector('#role-save-btn').addEventListener('click', async () => {
    const name = modal.querySelector('#role-name-input').value.trim();
    const errEl = modal.querySelector('#role-modal-error');
    errEl.style.display = 'none';
    if (!name) { errEl.textContent = 'Role name is required'; errEl.style.display = 'block'; return; }
    const permissions = {};
    modal.querySelectorAll('[data-perm]').forEach(cb => { permissions[cb.dataset.perm] = cb.checked; });
    const saveBtn = modal.querySelector('#role-save-btn');
    saveBtn.textContent = '⏳ Saving...'; saveBtn.disabled = true;
    try {
      await onSave({ name, color: selectedColor, permissions });
      close();
    } catch (e) {
      errEl.textContent = e.message || 'Failed to save role'; errEl.style.display = 'block';
      saveBtn.textContent = 'Save Role'; saveBtn.disabled = false;
    }
  });
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
}

export async function renderRolesPage(container) {
  const state = getState();
  const chatId = state.activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';
  if (!chatId && state.groups && state.groups.length > 0) {
    state.setActiveChatId(state.groups[0].chat_id);
  }
  const finalChatId = getState().activeChatId;
  if (!finalChatId) {
    container.appendChild(EmptyState({ icon: '👑', title: 'Select a group', description: 'Choose a group to manage roles.' }));
    return;
  }
  const header = document.createElement('div');
  header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-4);';
  header.innerHTML = `
    <div>
      <h2 style="font-size:20px;font-weight:700;margin:0;">👑 Roles</h2>
      <p style="color:var(--text-muted);font-size:13px;margin:4px 0 0;">Custom roles and permissions</p>
    </div>
    <button id="new-role-btn" class="btn btn-primary" style="font-size:var(--text-sm);">+ New Role</button>
  `;
  container.appendChild(header);
  header.querySelector('#new-role-btn').addEventListener('click', () => {
    _showRoleModal(finalChatId, null, async (data) => {
      await apiFetch(`/api/groups/${finalChatId}/roles`, { method: 'POST', body: data });
      showToast('Role created!', 'success');
      await renderRolesPage(container);
    });
  });
  const listContainer = document.createElement('div');
  listContainer.innerHTML = '<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading roles...</div>';
  container.appendChild(listContainer);
  try {
    const data = await apiFetch(`/api/groups/${finalChatId}/roles`);
    listContainer.innerHTML = '';
    const roles = data.roles || data || [];
    if (!roles || roles.length === 0) {
      listContainer.appendChild(EmptyState({ icon: '👑', title: 'No roles yet', description: 'Create your first role using the button above.' }));
      return;
    }
    const list = document.createElement('div');
    list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';
    roles.forEach(role => {
      const activePerms = Object.entries(role.permissions || {}).filter(([,v]) => v).map(([k]) => ROLE_PERMISSIONS.find(p => p.key === k)?.label || k);
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:var(--sp-3);padding:var(--sp-3);background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-lg);';
      row.innerHTML = `
        <div style="width:14px;height:14px;border-radius:50%;background:${role.color || '#64748b'};flex-shrink:0;"></div>
        <div style="flex:1;min-width:0;">
          <div style="font-weight:600;font-size:14px;">${role.name || 'Unnamed Role'}</div>
          <div style="font-size:12px;color:var(--text-muted);">${activePerms.length > 0 ? activePerms.slice(0,3).join(' · ') + (activePerms.length > 3 ? ' +' + (activePerms.length-3) : '') : 'No permissions'}</div>
        </div>
        <div style="display:flex;gap:var(--sp-2);">
          <button data-action="edit" style="background:none;border:1px solid var(--border);border-radius:var(--r-lg);padding:4px 10px;font-size:var(--text-xs);cursor:pointer;color:var(--text-primary);">Edit</button>
          <button data-action="delete" style="background:none;border:1px solid var(--danger);border-radius:var(--r-lg);padding:4px 10px;font-size:var(--text-xs);cursor:pointer;color:var(--danger);">Delete</button>
        </div>
      `;
      row.querySelector('[data-action="edit"]').addEventListener('click', () => {
        _showRoleModal(finalChatId, role, async (data) => {
          await apiFetch(`/api/groups/${finalChatId}/roles/${role.id}`, { method: 'PUT', body: data });
          showToast('Role updated!', 'success');
          await renderRolesPage(container);
        });
      });
      row.querySelector('[data-action="delete"]').addEventListener('click', async () => {
        if (!confirm('Delete role "' + role.name + '"?')) return;
        try {
          await apiFetch(`/api/groups/${finalChatId}/roles/${role.id}`, { method: 'DELETE' });
          showToast('Role deleted', 'success');
          await renderRolesPage(container);
        } catch (e) { showToast('Failed: ' + e.message, 'error'); }
      });
      list.appendChild(row);
    });
    listContainer.appendChild(list);
  } catch (err) {
    listContainer.innerHTML = '';
    listContainer.appendChild(EmptyState({ icon: '⚠️', title: 'Failed to load roles', description: err.message || 'The roles feature may not be fully configured yet.' }));
  }
}
