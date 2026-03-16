/**
 * miniapp/src/pages/moderation.js
 *
 * Moderation management page with 4 tabs:
 * Members | Actions | Warns | Filters
 * (Locks tab removed — locks are handled in AutoMod page)
 */

import { Card, Toggle, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';

const store = useStore;
const getState = store.getState;

let _sseSource = null;

export async function renderModerationPage(container) {
  const chatId = getState().activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '🛡️',
      title: 'Select a group',
      description: 'Choose a group to manage moderation settings.'
    }));
    return;
  }

  const header = document.createElement('div');
  header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-4);';
  header.innerHTML = `
    <div>
      <h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">🛡️ Moderation</h2>
      <p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">Manage moderation rules and actions</p>
    </div>
    <div id="sse-status" style="display:flex;align-items:center;gap:var(--sp-2);font-size:var(--text-xs);color:var(--text-muted);">
      <span id="sse-dot" style="width:8px;height:8px;border-radius:50%;background:var(--text-disabled);display:inline-block;"></span>
      <span id="sse-label">Offline</span>
    </div>
  `;
  container.appendChild(header);

  // Tabs: Members, Actions, Warns, Filters (Locks removed)
  const tabs = ['Members', 'Actions', 'Warns', 'Filters'];
  const tabBar = document.createElement('div');
  tabBar.style.cssText = 'display:flex;gap:var(--sp-1);margin-bottom:var(--sp-4);background:var(--bg-input);padding:4px;border-radius:var(--r-xl);overflow-x:auto;';
  tabs.forEach((t, i) => {
    const btn = document.createElement('button');
    btn.textContent = t;
    btn.dataset.tab = t.toLowerCase();
    btn.style.cssText = `flex:1;padding:var(--sp-2) var(--sp-3);border:none;border-radius:var(--r-lg);font-size:var(--text-sm);font-weight:var(--fw-medium);cursor:pointer;white-space:nowrap;transition:all var(--dur-fast);background:${i===0?'var(--bg-card)':'transparent'};color:${i===0?'var(--text-primary)':'var(--text-muted)'};`;
    btn.onclick = () => switchTab(t.toLowerCase(), container, chatId);
    tabBar.appendChild(btn);
  });
  container.appendChild(tabBar);

  const content = document.createElement('div');
  content.id = 'mod-tab-content';
  container.appendChild(content);

  await switchTab('members', container, chatId);
  _connectSSE(chatId);
}

function switchTab(tab, container, chatId) {
  container.querySelectorAll('[data-tab]').forEach(btn => {
    const isActive = btn.dataset.tab === tab;
    btn.style.background = isActive ? 'var(--bg-card)' : 'transparent';
    btn.style.color = isActive ? 'var(--text-primary)' : 'var(--text-muted)';
  });

  const content = document.getElementById('mod-tab-content');
  if (!content) return;
  content.innerHTML = '';

  switch (tab) {
    case 'members': return _renderMembersTab(content, chatId);
    case 'actions': return _renderActionsTab(content, chatId);
    case 'warns':   return _renderWarnsTab(content, chatId);
    case 'filters': return _renderFiltersTab(content, chatId);
  }
}

async function _renderMembersTab(container, chatId) {
  container.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading members...</div>`;

  try {
    console.debug('[Moderation] Loading members from /api/groups/' + chatId + '/members');
    const members = await apiFetch(`/api/groups/${chatId}/members`);
    console.debug('[Moderation] Members loaded:', members);
    container.innerHTML = '';

    const list = document.createElement('div');
    list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';

    if (!members || members.length === 0) {
      container.appendChild(EmptyState({ icon: '👥', title: 'No members', description: 'No members found in this group.' }));
      return;
    }

    members.forEach(m => {
      list.appendChild(_buildMemberCard(m, chatId));
    });

    container.appendChild(list);
  } catch (e) {
    console.error('[Moderation] Failed to load members:', e);
    container.innerHTML = '';
    container.appendChild(EmptyState({ icon: '⚠️', title: 'Failed to load', description: e.message }));
  }
}

function _buildMemberCard(m, chatId) {
  const trustColor = m.trust_score >= 70 ? 'var(--success)' : m.trust_score >= 40 ? 'var(--warning)' : 'var(--danger)';
  const warnCount = Array.isArray(m.warns) ? m.warns.length : (m.warns || 0);
  const initials = (m.first_name || m.username || '?')[0].toUpperCase();

  const card = document.createElement('div');
  card.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-3);';

  const statusChips = [];
  if (m.is_muted) statusChips.push(`<span style="padding:2px 8px;border-radius:var(--r-full);background:var(--warning);color:white;font-size:var(--text-xs);">🔇 Muted</span>`);
  if (m.is_banned) statusChips.push(`<span style="padding:2px 8px;border-radius:var(--r-full);background:var(--danger);color:white;font-size:var(--text-xs);">🚫 Banned</span>`);
  if (warnCount > 0) statusChips.push(`<span style="padding:2px 8px;border-radius:var(--r-full);background:var(--warning);color:white;font-size:var(--text-xs);">⚠️ ${warnCount} Warn${warnCount > 1 ? 's' : ''}</span>`);
  if (m.is_admin) statusChips.push(`<span style="padding:2px 8px;border-radius:var(--r-full);background:var(--accent);color:white;font-size:var(--text-xs);">${m.is_owner ? '👑 Owner' : '⭐ Admin'}</span>`);

  card.innerHTML = `
    <div style="display:flex;align-items:flex-start;gap:var(--sp-3);">
      <div style="width:40px;height:40px;border-radius:50%;background:var(--accent);color:white;display:flex;align-items:center;justify-content:center;font-weight:var(--fw-bold);font-size:var(--text-lg);flex-shrink:0;">${initials}</div>
      <div style="flex:1;min-width:0;">
        <div style="display:flex;align-items:center;gap:var(--sp-2);flex-wrap:wrap;">
          <span style="font-weight:var(--fw-semibold);font-size:var(--text-sm);">${m.first_name || m.username || 'Unknown'}</span>
          ${m.username ? `<span style="color:var(--text-muted);font-size:var(--text-xs);">@${m.username}</span>` : ''}
          ${statusChips.join('')}
        </div>
        <div style="display:flex;align-items:center;gap:var(--sp-2);margin-top:4px;">
          <span style="font-size:var(--text-xs);color:var(--text-muted);">Trust:</span>
          <div style="flex:1;height:4px;background:var(--bg-overlay);border-radius:2px;max-width:80px;">
            <div style="height:100%;border-radius:2px;background:${trustColor};width:${m.trust_score || 50}%;"></div>
          </div>
          <span style="font-size:var(--text-xs);color:${trustColor};">${m.trust_score || 50}</span>
        </div>
      </div>
    </div>
    <div class="member-actions" style="display:flex;gap:var(--sp-2);margin-top:var(--sp-2);flex-wrap:wrap;"></div>
    <div class="member-input-area" style="margin-top:var(--sp-2);display:none;"></div>
  `;

  const actionsRow = card.querySelector('.member-actions');
  const inputArea = card.querySelector('.member-input-area');

  const actionBtns = [
    { label: '⚠️ Warn', action: 'warn', style: 'background:var(--warning);color:white;' },
    { label: '🔇 Mute', action: 'mute', style: 'background:var(--bg-overlay);' },
    { label: '👢 Kick', action: 'kick', style: 'background:var(--bg-overlay);' },
    { label: '🚫 Ban', action: 'ban', style: 'background:var(--danger);color:white;' },
    { label: 'ℹ️ Info', action: 'info', style: 'background:var(--bg-overlay);' },
  ];

  actionBtns.forEach(({ label, action, style }) => {
    const btn = document.createElement('button');
    btn.textContent = label;
    btn.style.cssText = `padding:var(--sp-1) var(--sp-3);border-radius:var(--r-full);border:1px solid var(--border);font-size:var(--text-xs);cursor:pointer;${style}`;
    btn.onclick = () => _handleMemberAction(action, m, chatId, inputArea, card);
    actionsRow.appendChild(btn);
  });

  return card;
}

async function _handleMemberAction(action, member, chatId, inputArea, card) {
  inputArea.style.display = 'block';
  inputArea.innerHTML = '';

  if (action === 'info') {
    _showUserProfilePanel(member.user_id, chatId, member);
    inputArea.style.display = 'none';
    return;
  }

  if (action === 'warn') {
    inputArea.innerHTML = `
      <div style="display:flex;gap:var(--sp-2);">
        <input type="text" class="input action-reason" placeholder="Reason (optional)" style="flex:1;">
        <button class="btn btn-primary action-confirm" style="font-size:var(--text-xs);">Warn</button>
        <button class="btn btn-secondary action-cancel" style="font-size:var(--text-xs);">✕</button>
      </div>
    `;
    inputArea.querySelector('.action-confirm').onclick = async () => {
      const reason = inputArea.querySelector('.action-reason').value.trim();
      try {
        await apiFetch(`/api/groups/${chatId}/warnings`, {
          method: 'POST',
          validate: false,
          body: { user_id: member.user_id, reason: reason || 'Warned via Mini App' }
        });
        showToast('Warning issued', 'success');
        inputArea.style.display = 'none';
      } catch (e) { _handleActionError(e); }
    };
  } else if (action === 'mute') {
    inputArea.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:var(--sp-2);">
        <div style="display:flex;gap:var(--sp-2);flex-wrap:wrap;">
          ${['10m','1h','12h','1d','7d'].map(d => `<button class="btn btn-secondary duration-btn" data-dur="${d}" style="font-size:var(--text-xs);padding:var(--sp-1) var(--sp-2);">${d}</button>`).join('')}
        </div>
        <div style="display:flex;gap:var(--sp-2);">
          <input type="text" class="input action-reason" placeholder="Reason (optional)" style="flex:1;">
          <button class="btn btn-primary action-confirm" style="font-size:var(--text-xs);">Mute</button>
          <button class="btn btn-secondary action-cancel" style="font-size:var(--text-xs);">✕</button>
        </div>
      </div>
    `;
    let selectedDuration = '1h';
    inputArea.querySelectorAll('.duration-btn').forEach(b => {
      b.onclick = () => {
        selectedDuration = b.dataset.dur;
        inputArea.querySelectorAll('.duration-btn').forEach(x => x.style.background = 'var(--bg-overlay)');
        b.style.background = 'var(--accent)';
        b.style.color = 'white';
      };
    });
    inputArea.querySelector('.action-confirm').onclick = async () => {
      const reason = inputArea.querySelector('.action-reason').value.trim();
      try {
        await apiFetch(`/api/groups/${chatId}/mutes`, {
          method: 'POST',
          validate: false,
          body: { user_id: member.user_id, reason: reason || 'Muted via Mini App', duration: selectedDuration }
        });
        showToast('User muted', 'success');
        inputArea.style.display = 'none';
      } catch (e) { _handleActionError(e); }
    };
  } else if (action === 'kick') {
    inputArea.innerHTML = `
      <div style="display:flex;align-items:center;gap:var(--sp-2);">
        <span style="font-size:var(--text-sm);">Kick this user?</span>
        <button class="btn btn-danger action-confirm" style="font-size:var(--text-xs);">Kick</button>
        <button class="btn btn-secondary action-cancel" style="font-size:var(--text-xs);">✕</button>
      </div>
    `;
    inputArea.querySelector('.action-confirm').onclick = async () => {
      try {
        await apiFetch(`/api/groups/${chatId}/actions/kick`, {
          method: 'POST',
          validate: false,
          body: { user_id: member.user_id }
        });
        showToast('User kicked', 'success');
        card.remove();
      } catch (e) { _handleActionError(e); }
    };
  } else if (action === 'ban') {
    inputArea.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:var(--sp-2);">
        <div style="display:flex;gap:var(--sp-2);">
          <input type="text" class="input action-reason" placeholder="Reason (optional)" style="flex:1;">
          <button class="btn btn-danger action-confirm" style="font-size:var(--text-xs);">Ban</button>
          <button class="btn btn-secondary action-cancel" style="font-size:var(--text-xs);">✕</button>
        </div>
      </div>
    `;
    inputArea.querySelector('.action-confirm').onclick = async () => {
      const reason = inputArea.querySelector('.action-reason').value.trim();
      try {
        await apiFetch(`/api/groups/${chatId}/bans`, {
          method: 'POST',
          validate: false,
          body: { user_id: member.user_id, reason: reason || 'Banned via Mini App' }
        });
        showToast('User banned', 'success');
        card.remove();
      } catch (e) { _handleActionError(e); }
    };
  }

  inputArea.querySelector('.action-cancel')?.addEventListener('click', () => {
    inputArea.style.display = 'none';
    inputArea.innerHTML = '';
  });
}

function _showUserProfilePanel(userId, chatId, memberData) {
  const existing = document.getElementById('user-profile-panel');
  if (existing) existing.remove();

  const panel = document.createElement('div');
  panel.id = 'user-profile-panel';
  panel.style.cssText = 'position:fixed;top:0;right:0;width:320px;height:100vh;background:var(--bg-card);border-left:1px solid var(--border);z-index:1000;overflow-y:auto;display:flex;flex-direction:column;transition:transform .3s;';

  const member = memberData || {};
  const initials = (member.first_name || member.username || '?')[0].toUpperCase();
  const trustColor = member.trust_score >= 70 ? 'var(--success)' : member.trust_score >= 40 ? 'var(--warning)' : 'var(--danger)';
  const warnCount = Array.isArray(member.warns) ? member.warns.length : (member.warns || 0);

  panel.innerHTML = `
    <div style="padding:var(--sp-4);border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;">
      <span style="font-weight:var(--fw-bold);">User Profile</span>
      <button id="close-profile" style="background:none;border:none;cursor:pointer;font-size:20px;color:var(--text-muted);">✕</button>
    </div>
    <div style="padding:var(--sp-4);">
      <div style="text-align:center;margin-bottom:var(--sp-4);">
        <div style="width:64px;height:64px;border-radius:50%;background:var(--accent);color:white;display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:var(--fw-bold);margin:0 auto var(--sp-2);">${initials}</div>
        <div style="font-weight:var(--fw-bold);font-size:var(--text-lg);">${member.first_name || member.username || 'Unknown'}</div>
        ${member.username ? `<div style="color:var(--text-muted);font-size:var(--text-sm);">@${member.username}</div>` : ''}
        <div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:4px;cursor:pointer;" onclick="navigator.clipboard.writeText('${userId}');showToast && showToast('ID copied', 'success');">ID: <code>${userId}</code> 📋</div>
      </div>
      <div style="display:flex;flex-direction:column;gap:var(--sp-3);">
        <div style="background:var(--bg-input);border-radius:var(--r-lg);padding:var(--sp-3);">
          <div style="font-size:var(--text-xs);color:var(--text-muted);margin-bottom:var(--sp-2);">STATS</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-2);">
            <div><div style="font-size:var(--text-xs);color:var(--text-muted);">Messages</div><div style="font-weight:var(--fw-semibold);">${member.message_count || 0}</div></div>
            <div><div style="font-size:var(--text-xs);color:var(--text-muted);">Warnings</div><div style="font-weight:var(--fw-semibold);color:${warnCount > 0 ? 'var(--warning)' : 'inherit'};">${warnCount}</div></div>
          </div>
          <div style="margin-top:var(--sp-2);">
            <div style="font-size:var(--text-xs);color:var(--text-muted);margin-bottom:4px;">Trust Score</div>
            <div style="height:8px;background:var(--bg-overlay);border-radius:4px;">
              <div style="height:100%;border-radius:4px;background:${trustColor};width:${member.trust_score || 50}%;"></div>
            </div>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:var(--sp-2);" id="profile-actions">
          ${!member.is_muted ? `<button class="btn btn-secondary profile-action" data-action="mute" style="font-size:var(--text-sm);">🔇 Mute</button>` : `<button class="btn btn-secondary profile-action" data-action="unmute" style="font-size:var(--text-sm);">🔊 Unmute</button>`}
          ${!member.is_banned ? `<button class="btn btn-danger profile-action" data-action="ban" style="font-size:var(--text-sm);">🚫 Ban</button>` : `<button class="btn btn-secondary profile-action" data-action="unban" style="font-size:var(--text-sm);">✅ Unban</button>`}
          <button class="btn btn-secondary profile-action" data-action="warn" style="font-size:var(--text-sm);">⚠️ Warn</button>
          <button class="btn btn-secondary profile-action" data-action="kick" style="font-size:var(--text-sm);">👢 Kick</button>
        </div>
      </div>
    </div>
  `;

  panel.querySelector('#close-profile').onclick = () => panel.remove();

  panel.querySelectorAll('.profile-action').forEach(btn => {
    btn.onclick = async () => {
      const action = btn.dataset.action;
      try {
        if (action === 'warn') {
          await apiFetch(`/api/groups/${chatId}/warnings`, {
            method: 'POST',
            validate: false,
            body: { user_id: userId }
          });
          showToast('Warning issued', 'success');
        } else if (action === 'mute') {
          await apiFetch(`/api/groups/${chatId}/mutes`, {
            method: 'POST',
            validate: false,
            body: { user_id: userId, duration: '1h' }
          });
          showToast('User muted', 'success');
        } else if (action === 'unmute') {
          await apiFetch(`/api/groups/${chatId}/mutes/${userId}`, {
            method: 'DELETE',
            validate: false
          });
          showToast('User unmuted', 'success');
        } else if (action === 'ban') {
          await apiFetch(`/api/groups/${chatId}/bans`, {
            method: 'POST',
            validate: false,
            body: { user_id: userId, reason: 'Banned via Mini App' }
          });
          showToast('User banned', 'success');
        } else if (action === 'unban') {
          await apiFetch(`/api/groups/${chatId}/bans/${userId}`, {
            method: 'DELETE',
            validate: false
          });
          showToast('User unbanned', 'success');
        } else if (action === 'kick') {
          await apiFetch(`/api/groups/${chatId}/actions/kick`, {
            method: 'POST',
            validate: false,
            body: { user_id: userId }
          });
          showToast('User kicked', 'success');
        }
        panel.remove();
      } catch (e) {
        _handleActionError(e);
      }
    };
  });

  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.3);z-index:999;';
  overlay.onclick = () => { panel.remove(); overlay.remove(); };

  document.body.appendChild(overlay);
  document.body.appendChild(panel);
}

async function _renderActionsTab(container, chatId) {
  container.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading actions...</div>`;

  try {
    console.debug('[Moderation] Loading mod-log from /api/groups/' + chatId + '/mod-log?limit=50');
    const logs = await apiFetch(`/api/groups/${chatId}/mod-log?limit=50`);
    console.debug('[Moderation] Mod-log loaded:', logs);
    container.innerHTML = '';

    const header = document.createElement('div');
    header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-3);';
    header.innerHTML = `
      <span style="font-weight:var(--fw-semibold);">Recent Moderation Actions</span>
      <button id="export-logs-btn" class="btn btn-secondary" style="font-size:var(--text-xs);padding:var(--sp-2) var(--sp-3);">⬇️ Export CSV</button>
    `;
    container.appendChild(header);

    const feed = document.createElement('div');
    feed.id = 'mod-actions-feed';
    feed.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';

    const logList = Array.isArray(logs) ? logs : (logs.logs || []);

    if (logList.length === 0) {
      feed.appendChild(EmptyState({ icon: '✅', title: 'No recent actions', description: 'Moderation actions will appear here.' }));
    } else {
      logList.forEach(log => feed.appendChild(_buildActionRow(log)));
    }

    container.appendChild(feed);

    document.getElementById('export-logs-btn')?.addEventListener('click', () => _exportLogsCSV(logList));
  } catch (e) {
    console.error('[Moderation] Failed to load actions:', e);
    container.innerHTML = '';
    container.appendChild(EmptyState({ icon: '⚠️', title: 'Failed to load', description: e.message }));
  }
}

function _buildActionRow(log) {
  const emojis = { ban:'🔨', unban:'✅', mute:'🔇', unmute:'🔊', warn:'⚠️', kick:'👢', purge:'🧹', join:'👋', leave:'👋' };
  const colors = { ban:'var(--danger)', unban:'var(--success)', mute:'var(--warning)', warn:'var(--warning)', kick:'var(--danger)' };
  const action = log.action || 'unknown';

  const row = document.createElement('div');
  row.style.cssText = `display:flex;align-items:center;gap:var(--sp-3);padding:var(--sp-3);background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-lg);`;
  row.innerHTML = `
    <span style="font-size:18px;">${emojis[action] || '📋'}</span>
    <div style="flex:1;min-width:0;">
      <div style="display:flex;align-items:center;gap:var(--sp-2);">
        <span style="font-size:var(--text-xs);font-weight:var(--fw-bold);padding:2px 8px;border-radius:var(--r-full);background:${colors[action] || 'var(--bg-overlay)'};color:white;">${action.toUpperCase()}</span>
        <span style="font-size:var(--text-sm);font-weight:var(--fw-medium);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${log.target_name || log.target_username || log.target_id || 'Unknown'}</span>
      </div>
      <div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:2px;">
        by ${log.admin_name || log.admin_username || 'System'}${log.reason ? ` · "${log.reason}"` : ''}
      </div>
    </div>
    <span style="font-size:var(--text-xs);color:var(--text-muted);white-space:nowrap;">${_timeAgo(log.done_at || log.timestamp || log.created_at)}</span>
  `;
  return row;
}

function _exportLogsCSV(logs) {
  const rows = [['Action', 'Target', 'Admin', 'Reason', 'Time']];
  logs.forEach(l => rows.push([l.action, l.target_name || l.target_username || l.target_id, l.admin_name || l.admin_username || 'System', l.reason || '', l.done_at || l.timestamp || l.created_at || '']));
  const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'mod-logs.csv'; a.click();
  URL.revokeObjectURL(url);
}

async function _renderWarnsTab(container, chatId) {
  container.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading warn settings...</div>`;

  let warnSettings = { warn_max: 3, warn_action: 'mute_24h', warn_expiry: 'never' };
  try {
    console.debug('[Moderation] Loading warn-settings from /api/groups/' + chatId + '/warn-settings');
    const res = await apiFetch(`/api/groups/${chatId}/warn-settings`);
    console.debug('[Moderation] Warn-settings loaded:', res);
    warnSettings = {
      warn_max: res.warn_max || 3,
      warn_action: res.warn_action || 'mute_24h',
      warn_expiry: res.warn_expiry || 'never',
    };
  } catch (e) {
    console.error('[Moderation] Failed to load warn-settings:', e);
  }

  container.innerHTML = '';

  const settingsCard = Card({ title: '⚠️ Warning Settings', subtitle: 'Configure automated warning actions' });
  settingsCard.insertAdjacentHTML('beforeend', `
    <div style="display:flex;flex-direction:column;gap:var(--sp-3);">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <span style="font-size:var(--text-sm);">Max warnings before action</span>
        <input type="number" id="warn-max-input" class="input" value="${warnSettings.warn_max}" min="1" max="10"
          style="width:5rem;padding:var(--sp-2) var(--sp-3);text-align:right;">
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <span style="font-size:var(--text-sm);">Action on max warns</span>
        <select id="warn-action-select" class="input" style="width:10rem;">
          <option value="mute_1h" ${warnSettings.warn_action==='mute_1h'?'selected':''}>Mute 1h</option>
          <option value="mute_12h" ${warnSettings.warn_action==='mute_12h'?'selected':''}>Mute 12h</option>
          <option value="mute_24h" ${warnSettings.warn_action==='mute_24h'?'selected':''}>Mute 24h</option>
          <option value="kick" ${warnSettings.warn_action==='kick'?'selected':''}>Kick</option>
          <option value="ban" ${warnSettings.warn_action==='ban'?'selected':''}>Ban</option>
          <option value="ban_permanent" ${warnSettings.warn_action==='ban_permanent'?'selected':''}>Permanent Ban</option>
        </select>
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <span style="font-size:var(--text-sm);">Warning expiry</span>
        <select id="warn-expiry-select" class="input" style="width:10rem;">
          <option value="never" ${warnSettings.warn_expiry==='never'?'selected':''}>Never</option>
          <option value="7d" ${warnSettings.warn_expiry==='7d'?'selected':''}>7 days</option>
          <option value="30d" ${warnSettings.warn_expiry==='30d'?'selected':''}>30 days</option>
          <option value="90d" ${warnSettings.warn_expiry==='90d'?'selected':''}>90 days</option>
        </select>
      </div>
      <button id="save-warn-settings-btn" class="btn btn-primary" style="align-self:flex-end;">Save Settings</button>
    </div>
  `);
  container.appendChild(settingsCard);

  settingsCard.querySelector('#save-warn-settings-btn').addEventListener('click', async () => {
    const max = parseInt(settingsCard.querySelector('#warn-max-input').value) || 3;
    const action = settingsCard.querySelector('#warn-action-select').value;
    const expiry = settingsCard.querySelector('#warn-expiry-select').value;
    try {
      await apiFetch(`/api/groups/${chatId}/warn-settings`, {
        method: 'PUT',
        validate: false,
        body: { warn_max: max, warn_action: action, warn_expiry: expiry }
      });
      showToast('Warn settings saved', 'success');
    } catch (e) {
      showToast('Failed to save: ' + e.message, 'error');
    }
  });

  // Load warned users
  const warningsCard = Card({ title: '⚠️ Warned Users', subtitle: 'Users with active warnings' });
  warningsCard.insertAdjacentHTML('beforeend', `<div id="warned-users-list" style="display:flex;flex-direction:column;gap:var(--sp-2);"><div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);">Loading...</div></div>`);
  container.appendChild(warningsCard);

  try {
    console.debug('[Moderation] Loading warnings from /api/groups/' + chatId + '/warnings');
    const warnedUsers = await apiFetch(`/api/groups/${chatId}/warnings`);
    console.debug('[Moderation] Warnings loaded:', warnedUsers);
    const warnedList = warningsCard.querySelector('#warned-users-list');
    warnedList.innerHTML = '';

    if (!warnedUsers || warnedUsers.length === 0) {
      warnedList.innerHTML = '<div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);">No warned users</div>';
    } else {
      warnedUsers.forEach(w => {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:var(--sp-3);background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-lg);';
        row.innerHTML = `
          <div>
            <div style="font-weight:var(--fw-semibold);font-size:var(--text-sm);">${w.first_name || w.username || 'Unknown'}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">${w.count} warnings</div>
          </div>
          <button class="btn btn-secondary reset-warn-btn" style="font-size:var(--text-xs);padding:var(--sp-1) var(--sp-2);" data-user-id="${w.user_id}">Reset</button>
        `;
        row.querySelector('.reset-warn-btn').onclick = async () => {
          try {
            await apiFetch(`/api/groups/${chatId}/warnings/${w.user_id}/all`, {
              method: 'DELETE',
              validate: false
            });
            showToast('Warnings reset', 'success');
            row.remove();
          } catch (e) {
            showToast('Failed: ' + e.message, 'error');
          }
        };
        warnedList.appendChild(row);
      });
    }
  } catch (e) {
    console.error('[Moderation] Failed to load warnings:', e);
    warningsCard.querySelector('#warned-users-list').innerHTML = '<div style="text-align:center;padding:var(--sp-4);color:var(--danger);">Failed to load warnings</div>';
  }
}

async function _renderFiltersTab(container, chatId) {
  container.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading filters...</div>`;

  let filters = [];
  let blacklist = [];
  try {
    console.debug('[Moderation] Loading filters and blacklist');
    [filters, blacklist] = await Promise.all([
      apiFetch(`/api/groups/${chatId}/filters`).then(r => Array.isArray(r) ? r : []).catch(() => []),
      apiFetch(`/api/groups/${chatId}/blacklist`).then(r => r?.words || []).catch(() => []),
    ]);
    console.debug('[Moderation] Filters loaded:', filters, 'Blacklist loaded:', blacklist);
  } catch (_) {}

  container.innerHTML = '';

  // Keyword Auto-Replies
  const filtersCard = Card({ title: '🔑 Keyword Auto-Replies', subtitle: 'Respond automatically to specific keywords' });

  const filtersList = document.createElement('div');
  filtersList.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);margin-bottom:var(--sp-3);';

  const renderFilters = (items) => {
    filtersList.innerHTML = '';
    if (items.length === 0) {
      filtersList.innerHTML = '<div style="color:var(--text-muted);font-size:var(--text-sm);text-align:center;padding:var(--sp-2);">No keyword filters yet</div>';
      return;
    }
    items.forEach(f => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:var(--sp-2);padding:var(--sp-2) var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);';

      const reply = f.reply_content || '';
      const hasButtons = reply.includes('---');
      const truncated = reply.slice(0, 60) + (reply.length > 60 ? '…' : '');

      row.innerHTML = `
        <span style="font-size:var(--text-xs);font-weight:var(--fw-bold);padding:2px 8px;background:var(--accent);color:white;border-radius:var(--r-full);">${f.keyword}</span>
        <span style="color:var(--text-muted);font-size:var(--text-xs);">→</span>
        <span style="flex:1;font-size:var(--text-sm);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${reply.replace(/"/g, '&quot;')}">
          ${hasButtons ? '🔘 ' : ''}${truncated}
        </span>
        <button data-id="${f.id}" style="color:var(--danger); border:1px solid var(--danger); background:none; border-radius:4px; padding:2px 6px; cursor:pointer; font-size:14px; display:flex; align-items:center; justify-content:center;">🗑️</button>
      `;
      row.querySelector('[data-id]').onclick = async () => {
        try {
          await apiFetch(`/api/groups/${chatId}/filters/${f.id}`, { method: 'DELETE', validate: false });
          filters = filters.filter(x => x.id !== f.id);
          renderFilters(filters);
          showToast('Filter removed', 'success');
        } catch (e) { showToast('Failed: ' + e.message, 'error'); }
      };
      filtersList.appendChild(row);
    });
  };

  renderFilters(filters);

  const addFilterRow = document.createElement('div');
  addFilterRow.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';
  // Use textarea for response to support multiline and button syntax
  addFilterRow.innerHTML = `
    <div style="display:flex;gap:var(--sp-2);">
      <input type="text" id="filter-keyword" class="input" placeholder="Keyword" style="flex:1;">
      <button id="add-filter-btn" class="btn btn-primary" style="white-space:nowrap;">Add</button>
    </div>
    <textarea id="filter-response" class="input" placeholder="Response text. Supports HTML/Markdown.\nAdd buttons after --- on new lines:\n---\n[Button Label](https://example.com)" rows="3" style="width:100%;resize:vertical;"></textarea>
    <div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:4px;">
      💡 Tip: Use [Label](URL) for each button. Separate multiple button rows with a blank line.
    </div>
  `;

  filtersCard.appendChild(filtersList);
  filtersCard.appendChild(addFilterRow);
  container.appendChild(filtersCard);

  setTimeout(() => {
    filtersCard.querySelector('#add-filter-btn')?.addEventListener('click', async () => {
      const keyword = filtersCard.querySelector('#filter-keyword').value.trim().toLowerCase();
      const response = filtersCard.querySelector('#filter-response').value.trim();
      if (!keyword || !response) { showToast('Keyword and response required', 'error'); return; }
      try {
        const newFilter = await apiFetch(`/api/groups/${chatId}/filters`, {
          method: 'POST',
          validate: false,
          body: { keyword, reply_content: response }
        });
        filters.push({ keyword, reply_content: response, id: newFilter?.id || Date.now() });
        renderFilters(filters);
        filtersCard.querySelector('#filter-keyword').value = '';
        filtersCard.querySelector('#filter-response').value = '';
        showToast('Filter added', 'success');
      } catch (e) { showToast('Failed: ' + e.message, 'error'); }
    });
  }, 0);

  // Word Blacklist
  const blacklistCard = Card({ title: '🚫 Word Blacklist', subtitle: 'Automatically act on these words' });

  const chipsContainer = document.createElement('div');
  chipsContainer.id = 'blacklist-chips';
  chipsContainer.style.cssText = 'display:flex;flex-wrap:wrap;gap:var(--sp-2);margin-bottom:var(--sp-3);min-height:32px;';

  const renderChips = (words) => {
    chipsContainer.innerHTML = '';
    words.forEach(word => {
      const chip = document.createElement('span');
      chip.style.cssText = 'display:inline-flex;align-items:center;gap:4px;padding:4px 10px;background:var(--bg-overlay);border:1px solid var(--border);border-radius:var(--r-full);font-size:var(--text-xs);';
      chip.innerHTML = `${word} <button onclick="this.parentElement.remove();window._removeBlacklistWord('${chatId}','${word}')" style="background:none;border:none;cursor:pointer;color:var(--text-muted);padding:0;font-size:14px;line-height:1;">&times;</button>`;
      chipsContainer.appendChild(chip);
    });
  };

  renderChips(blacklist);

  const addRow = document.createElement('div');
  addRow.style.cssText = 'display:flex;gap:var(--sp-2);';
  addRow.innerHTML = `
    <input type="text" id="blacklist-input" class="input" placeholder="Type a word and press Enter" style="flex:1;">
    <button id="add-blacklist-btn" class="btn btn-secondary">Add</button>
  `;

  const addWord = async () => {
    const input = blacklistCard.querySelector('#blacklist-input');
    const word = input.value.trim().toLowerCase();
    if (!word) return;
    try {
      await apiFetch(`/api/groups/${chatId}/blacklist`, {
        method: 'POST',
        validate: false,
        body: { word }
      });
      blacklist.push(word);
      renderChips(blacklist);
      input.value = '';
      showToast('Word added', 'success');
    } catch (e) {
      showToast('Failed: ' + e.message, 'error');
    }
  };

  blacklistCard.appendChild(chipsContainer);
  blacklistCard.appendChild(addRow);

  container.appendChild(blacklistCard);

  setTimeout(() => {
    blacklistCard.querySelector('#add-blacklist-btn')?.addEventListener('click', addWord);
    blacklistCard.querySelector('#blacklist-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') addWord(); });
  }, 0);

  window._removeBlacklistWord = async (cid, word) => {
    try {
      await apiFetch(`/api/groups/${cid}/blacklist/${encodeURIComponent(word)}`, {
        method: 'DELETE',
        validate: false
      });
      blacklist = blacklist.filter(w => w !== word);
      showToast('Word removed', 'success');
    } catch (e) {
      showToast('Failed to remove', 'error');
    }
  };
}

function _connectSSE(chatId) {
  if (_sseSource) {
    _sseSource.close();
    _sseSource = null;
  }

  const dot = document.getElementById('sse-dot');
  const label = document.getElementById('sse-label');

  try {
    const token = encodeURIComponent(window.Telegram?.WebApp?.initData || '');
    _sseSource = new EventSource(`/api/events/moderation/${chatId}?token=${token}`);

    // Bug C fix: Use connected/heartbeat events as onopen fallback
    _sseSource.addEventListener('connected', () => {
      if (dot) { dot.style.background = 'var(--success)'; dot.style.animation = 'pulse 1.5s infinite'; }
      if (label) label.textContent = 'Live';
    });

    _sseSource.addEventListener('heartbeat', () => {
      // Keep-alive received, ensure dot is green
      if (dot && dot.style.background !== 'var(--success)') {
        dot.style.background = 'var(--success)';
        dot.style.animation = 'pulse 1.5s infinite';
      }
      if (label && label.textContent !== 'Live') label.textContent = 'Live';
    });

    _sseSource.onopen = () => {
      if (dot) { dot.style.background = 'var(--success)'; dot.style.animation = 'pulse 1.5s infinite'; }
      if (label) label.textContent = 'Live';
    };

    _sseSource.onerror = () => {
      if (dot) { dot.style.background = 'var(--danger)'; dot.style.animation = ''; }
      if (label) label.textContent = 'Reconnecting...';
      setTimeout(() => { if (document.getElementById('sse-dot')) _connectSSE(chatId); }, 5000);
    };

    _sseSource.addEventListener('mod_action', (e) => {
      try {
        const data = JSON.parse(e.data);
        const feed = document.getElementById('mod-actions-feed');
        if (feed) {
          const row = _buildActionRow({ ...data, timestamp: new Date().toISOString() });
          feed.prepend(row);
        }
      } catch (_) {}
    });
  } catch (e) {
    console.warn('[Moderation] SSE connection failed:', e);
  }
}

function _timeAgo(ts) {
  if (!ts) return '';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
  return new Date(ts).toLocaleDateString();
}

/**
 * Human-readable error handler for moderation actions
 */
function _handleActionError(e) {
  const msg = e.message || 'Unknown error';
  console.error('[Moderation] Action failed:', e);

  // Translate common errors to friendly messages
  if (msg.includes('command injection') || msg.includes('restricted keywords')) {
    showToast('Action blocked by input filter — use simpler reason text', 'error');
  } else if (msg.includes('not an admin') || msg.includes('403')) {
    showToast('Bot needs admin rights in this group', 'error');
  } else if (msg.includes('502') || msg.includes('Telegram action failed')) {
    // Extract the part after the last colon if it exists
    const parts = msg.split(':');
    const cleanMsg = parts.length > 1 ? parts[parts.length - 1].trim() : msg;
    showToast('Telegram refused action: ' + cleanMsg, 'error');
  } else if (msg.includes('401') || msg.includes('Unauthorized')) {
    showToast('Session expired — reopen the Mini App', 'error');
  } else {
    showToast('Failed: ' + msg, 'error');
  }
}
