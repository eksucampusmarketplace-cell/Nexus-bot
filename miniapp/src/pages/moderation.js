/**
 * miniapp/src/pages/moderation.js
 *
 * Full moderation management page with tabs:
 * Members | Actions | Warns | Locks | Filters | Log
 */

import { Card, Toggle, showToast } from '../../lib/components.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';

const store = useStore;

let _sseSource = null;
let _currentChatId = null;

export async function renderModerationPage(container) {
  const chatId = store.getState().activeChatId;
  if (!chatId) {
    container.innerHTML = '<div class="p-4 text-center">Please select a group first.</div>';
    return;
  }

  _currentChatId = chatId;

  container.innerHTML = `
    <div style="padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:var(--sp-4);">
        <h2 style="font-size:20px; font-weight:700; margin:0;">🛡️ Moderation</h2>
        <div id="sse-indicator" style="display:flex; align-items:center; gap:6px; font-size:12px; color:var(--text-muted);">
          <span id="sse-dot" style="width:8px;height:8px;border-radius:50%;background:#ef4444;display:inline-block;"></span>
          <span id="sse-label">Offline</span>
        </div>
      </div>

      <div id="mod-tabs" style="display:flex; gap:8px; margin-bottom:var(--sp-4); overflow-x:auto; padding-bottom:4px; flex-wrap:nowrap;">
        ${['👥 Members','🔨 Actions','⚠️ Warns','🔒 Locks','📋 Filters','📜 Log'].map((t, i) => `
          <button data-tab="${i}" class="mod-tab ${i===0?'active':''}" style="
            flex-shrink:0; padding:6px 14px; border-radius:20px; border:none; cursor:pointer;
            font-size:13px; font-weight:500; transition:all 0.2s;
            background:${i===0?'var(--accent)':'var(--bg-input)'}; 
            color:${i===0?'#000':'var(--text-secondary)'};
          ">${t}</button>
        `).join('')}
      </div>

      <div id="mod-tab-content"></div>
    </div>
  `;

  const tabs = container.querySelectorAll('.mod-tab');
  const tabContent = container.querySelector('#mod-tab-content');

  async function switchTab(idx) {
    tabs.forEach((t, i) => {
      t.style.background = i === idx ? 'var(--accent)' : 'var(--bg-input)';
      t.style.color = i === idx ? '#000' : 'var(--text-secondary)';
    });
    tabContent.innerHTML = '<div style="text-align:center;padding:32px;color:var(--text-muted);">Loading...</div>';
    switch (idx) {
      case 0: await renderMembersTab(tabContent, chatId); break;
      case 1: await renderActionsTab(tabContent, chatId); break;
      case 2: await renderWarnsTab(tabContent, chatId); break;
      case 3: await renderLocksTab(tabContent, chatId); break;
      case 4: await renderFiltersTab(tabContent, chatId); break;
      case 5: await renderLogTab(tabContent, chatId); break;
    }
  }

  tabs.forEach((t, i) => { t.onclick = () => switchTab(i); });
  await switchTab(0);
  connectSSE(chatId, container);
}

// ── SSE ───────────────────────────────────────────────────────────────────────

function connectSSE(chatId, container) {
  if (_sseSource) {
    _sseSource.close();
    _sseSource = null;
  }

  const dot = container.querySelector('#sse-dot');
  const label = container.querySelector('#sse-label');
  if (!dot || !label) return;

  const params = new URLSearchParams({
    chat_id: chatId,
    token: window.Telegram?.WebApp?.initData || '',
  });

  _sseSource = new EventSource(`/api/events?${params}`);

  _sseSource.onopen = () => {
    if (dot) { dot.style.background = '#10b981'; dot.style.animation = 'pulse 2s infinite'; }
    if (label) label.textContent = 'Live';
  };

  _sseSource.onerror = () => {
    if (dot) { dot.style.background = '#ef4444'; dot.style.animation = ''; }
    if (label) label.textContent = 'Offline';
  };

  _sseSource.onmessage = (e) => {
    try {
      const payload = JSON.parse(e.data);
      const data = payload.data || payload;
      const type = payload.type || data.type;
      if (type === 'mod_action') {
        const feed = document.getElementById('mod-actions-feed');
        if (feed) prependActionFeedItem(feed, data);
        const logFeed = document.getElementById('mod-log-feed');
        if (logFeed) prependLogItem(logFeed, data);
      }
      if (type === 'lock_change') {
        const toggle = document.getElementById(`lock-toggle-${data.lock_type}`);
        if (toggle) toggle.checked = data.enabled;
      }
      if (type === 'filter_change') {
        const filterList = document.getElementById('filter-list');
        if (filterList && data.change === 'added') {
          addFilterRow(filterList, data.filter || data, chatId);
        }
        if (filterList && data.change === 'removed') {
          const row = filterList.querySelector(`[data-filter-id="${data.filter_id}"]`);
          if (row) row.remove();
        }
      }
    } catch (_) {}
  };
}

// ── Tab 0: Members ────────────────────────────────────────────────────────────

async function renderMembersTab(container, chatId) {
  container.innerHTML = `
    <div style="margin-bottom:var(--sp-3);">
      <input id="member-search" class="input" placeholder="🔍 Search by name, username, or ID..." style="margin-bottom:var(--sp-3);">
      <div style="display:flex;gap:8px;overflow-x:auto;padding-bottom:4px;">
        ${['All','Admins','Banned','Muted','Warned'].map((f,i) => `
          <button data-filter="${f.toLowerCase()}" class="member-filter-chip ${i===0?'active-chip':''}" style="
            flex-shrink:0;padding:4px 12px;border-radius:20px;border:1px solid var(--border);
            font-size:12px;cursor:pointer;background:${i===0?'var(--accent)':'transparent'};
            color:${i===0?'#000':'var(--text-secondary)'};
          ">${f}</button>
        `).join('')}
      </div>
    </div>
    <div id="members-list" style="display:flex;flex-direction:column;gap:var(--sp-2);">
      <div style="text-align:center;padding:32px;color:var(--text-muted);">Loading members...</div>
    </div>
    <div id="members-pagination" style="display:flex;justify-content:center;gap:8px;margin-top:var(--sp-3);"></div>
  `;

  let currentPage = 1;
  let currentFilter = 'all';
  let searchQuery = '';

  async function loadMembers() {
    const list = container.querySelector('#members-list');
    list.innerHTML = '<div style="text-align:center;padding:32px;color:var(--text-muted);">Loading...</div>';
    try {
      const params = new URLSearchParams({ page: currentPage, limit: 20 });
      if (searchQuery) params.set('search', searchQuery);
      if (currentFilter !== 'all') params.set('filter', currentFilter);
      const res = await apiFetch(`/api/groups/${chatId}/members?${params}`);
      const members = res.members || res.data || [];
      renderMemberList(list, members, chatId);

      const pagination = container.querySelector('#members-pagination');
      pagination.innerHTML = '';
      if (currentPage > 1) {
        const prev = document.createElement('button');
        prev.className = 'btn btn-secondary';
        prev.textContent = '← Prev';
        prev.onclick = () => { currentPage--; loadMembers(); };
        pagination.appendChild(prev);
      }
      if (members.length === 20) {
        const next = document.createElement('button');
        next.className = 'btn btn-secondary';
        next.textContent = 'Next →';
        next.onclick = () => { currentPage++; loadMembers(); };
        pagination.appendChild(next);
      }
    } catch (e) {
      list.innerHTML = `<div style="color:var(--danger);text-align:center;padding:16px;">Failed to load: ${e.message}</div>`;
    }
  }

  let searchTimer = null;
  container.querySelector('#member-search').oninput = (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      searchQuery = e.target.value.trim();
      currentPage = 1;
      loadMembers();
    }, 400);
  };

  container.querySelectorAll('.member-filter-chip').forEach(chip => {
    chip.onclick = () => {
      container.querySelectorAll('.member-filter-chip').forEach(c => {
        c.style.background = 'transparent';
        c.style.color = 'var(--text-secondary)';
        c.classList.remove('active-chip');
      });
      chip.style.background = 'var(--accent)';
      chip.style.color = '#000';
      chip.classList.add('active-chip');
      currentFilter = chip.dataset.filter;
      currentPage = 1;
      loadMembers();
    };
  });

  await loadMembers();
}

function renderMemberList(container, members, chatId) {
  if (!members || members.length === 0) {
    container.innerHTML = '<div style="text-align:center;padding:32px;color:var(--text-muted);">No members found.</div>';
    return;
  }
  container.innerHTML = '';
  members.forEach(m => {
    const card = document.createElement('div');
    card.style.cssText = `
      background:var(--card); border:1px solid var(--border);
      border-radius:var(--r-lg); padding:var(--sp-3);
    `;
    const name = m.first_name || m.full_name || `User ${m.user_id}`;
    const username = m.username ? `@${m.username}` : '';
    const status = m.status || 'member';
    const warnCount = m.warn_count || 0;
    const isMuted = m.is_muted || false;
    const isBanned = m.is_banned || false;

    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
        <div>
          <div style="font-weight:600;font-size:14px;">${escapeHtml(name)} ${username ? `<span style="color:var(--text-muted);font-size:12px;">${escapeHtml(username)}</span>` : ''}</div>
          <div style="font-size:12px;color:var(--text-muted);">${status.charAt(0).toUpperCase() + status.slice(1)}</div>
        </div>
        <div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end;">
          ${warnCount > 0 ? `<span style="font-size:11px;background:rgba(245,158,11,0.15);color:#f59e0b;padding:2px 6px;border-radius:10px;">⚠️ ${warnCount} warns</span>` : ''}
          ${isMuted ? `<span style="font-size:11px;background:rgba(239,68,68,0.15);color:#ef4444;padding:2px 6px;border-radius:10px;">🔇 Muted</span>` : ''}
          ${isBanned ? `<span style="font-size:11px;background:rgba(239,68,68,0.15);color:#ef4444;padding:2px 6px;border-radius:10px;">🚫 Banned</span>` : ''}
        </div>
      </div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;">
        <button class="btn-sm" data-action="warn" data-uid="${m.user_id}" data-name="${escapeHtml(name)}" style="padding:4px 10px;font-size:12px;background:rgba(245,158,11,0.15);color:#f59e0b;border:1px solid rgba(245,158,11,0.3);border-radius:8px;cursor:pointer;">⚠️ Warn</button>
        <button class="btn-sm" data-action="mute" data-uid="${m.user_id}" data-name="${escapeHtml(name)}" style="padding:4px 10px;font-size:12px;background:rgba(99,102,241,0.15);color:#818cf8;border:1px solid rgba(99,102,241,0.3);border-radius:8px;cursor:pointer;">🔇 Mute</button>
        <button class="btn-sm" data-action="kick" data-uid="${m.user_id}" data-name="${escapeHtml(name)}" style="padding:4px 10px;font-size:12px;background:rgba(249,115,22,0.15);color:#fb923c;border:1px solid rgba(249,115,22,0.3);border-radius:8px;cursor:pointer;">👢 Kick</button>
        <button class="btn-sm" data-action="ban" data-uid="${m.user_id}" data-name="${escapeHtml(name)}" style="padding:4px 10px;font-size:12px;background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid rgba(239,68,68,0.3);border-radius:8px;cursor:pointer;">🚫 Ban</button>
      </div>
    `;

    card.querySelectorAll('.btn-sm').forEach(btn => {
      btn.onclick = () => {
        const action = btn.dataset.action;
        const userId = parseInt(btn.dataset.uid);
        const userName = btn.dataset.name;
        showActionModal(chatId, userId, userName, action, card);
      };
    });

    container.appendChild(card);
  });
}

function showActionModal(chatId, userId, userName, action, memberCard) {
  const existing = document.getElementById('mod-action-modal');
  if (existing) existing.remove();

  const needsDuration = action === 'mute' || action === 'ban';
  const modal = document.createElement('div');
  modal.id = 'mod-action-modal';
  modal.style.cssText = `
    position:fixed; inset:0; background:rgba(0,0,0,0.7); z-index:9999;
    display:flex; align-items:center; justify-content:center; padding:16px;
  `;

  const actionEmoji = { warn:'⚠️', mute:'🔇', kick:'👢', ban:'🚫' }[action] || '⚡';
  const actionLabel = action.charAt(0).toUpperCase() + action.slice(1);

  modal.innerHTML = `
    <div style="background:var(--card);border:1px solid var(--border);border-radius:16px;padding:24px;max-width:380px;width:100%;">
      <h3 style="margin:0 0 16px;font-size:18px;">${actionEmoji} ${actionLabel} User</h3>
      <p style="margin:0 0 12px;font-size:14px;color:var(--text-muted);">Target: <strong>${escapeHtml(userName)}</strong></p>
      <div style="margin-bottom:12px;">
        <label style="font-size:13px;color:var(--text-muted);display:block;margin-bottom:4px;">Reason</label>
        <input id="modal-reason" class="input" placeholder="Enter reason..." style="width:100%;box-sizing:border-box;">
      </div>
      ${needsDuration ? `
      <div style="margin-bottom:16px;">
        <label style="font-size:13px;color:var(--text-muted);display:block;margin-bottom:4px;">Duration (optional)</label>
        <input id="modal-duration" class="input" placeholder="e.g. 1h, 30m, 7d (blank = permanent)" style="width:100%;box-sizing:border-box;">
      </div>
      ` : '<div style="margin-bottom:16px;"></div>'}
      <div style="display:flex;gap:8px;">
        <button id="modal-cancel" class="btn btn-secondary" style="flex:1;">Cancel</button>
        <button id="modal-confirm" class="btn btn-danger" style="flex:1;">${actionLabel}</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);
  modal.querySelector('#modal-cancel').onclick = () => modal.remove();
  modal.querySelector('#modal-confirm').onclick = async () => {
    const reason = modal.querySelector('#modal-reason').value.trim() || 'No reason provided';
    const duration = needsDuration ? (modal.querySelector('#modal-duration')?.value.trim() || null) : null;
    modal.remove();
    await executeModAction(chatId, userId, action, reason, duration, memberCard);
  };
  modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
}

async function executeModAction(chatId, userId, action, reason, duration, memberCard) {
  try {
    const body = { user_id: userId, reason };
    if (duration) body.duration = duration;

    const endpoint = action === 'kick'
      ? `/api/groups/${chatId}/actions/kick`
      : action === 'warn'
        ? `/api/groups/${chatId}/warnings`
        : action === 'mute'
          ? `/api/groups/${chatId}/mutes`
          : `/api/groups/${chatId}/bans`;

    await apiFetch(endpoint, { method: 'POST', body: JSON.stringify(body) });
    showToast(`✅ User ${action}ed`, 'success');

    if (memberCard) {
      if (action === 'ban') {
        memberCard.style.opacity = '0.4';
      } else if (action === 'mute') {
        const statusArea = memberCard.querySelector('div:first-child > div:last-child');
        if (statusArea) {
          const badge = document.createElement('span');
          badge.style.cssText = 'font-size:11px;background:rgba(239,68,68,0.15);color:#ef4444;padding:2px 6px;border-radius:10px;';
          badge.textContent = '🔇 Muted';
          statusArea.appendChild(badge);
        }
      }
    }
  } catch (e) {
    showToast(`❌ Failed: ${e.message}`, 'error');
  }
}

// ── Tab 1: Actions (Live Feed) ────────────────────────────────────────────────

async function renderActionsTab(container, chatId) {
  container.innerHTML = `
    <div style="display:flex;gap:8px;overflow-x:auto;margin-bottom:var(--sp-3);padding-bottom:4px;">
      ${['All','Bans','Mutes','Warns','Kicks','Promotes'].map((f, i) => `
        <button data-action-filter="${f.toLowerCase()}" style="
          flex-shrink:0;padding:4px 12px;border-radius:20px;border:1px solid var(--border);
          font-size:12px;cursor:pointer;background:${i===0?'var(--accent)':'transparent'};
          color:${i===0?'#000':'var(--text-secondary)'};
        ">${f}</button>
      `).join('')}
    </div>
    <div id="mod-actions-feed" style="display:flex;flex-direction:column;gap:var(--sp-2);">
      <div style="text-align:center;padding:32px;color:var(--text-muted);">Loading recent actions...</div>
    </div>
  `;

  try {
    const res = await apiFetch(`/api/groups/${chatId}/mod-log?limit=30`);
    const logs = res.data || [];
    const feed = container.querySelector('#mod-actions-feed');
    feed.innerHTML = '';
    if (logs.length === 0) {
      feed.innerHTML = '<div style="text-align:center;padding:32px;color:var(--text-muted);">No recent actions.</div>';
      return;
    }
    logs.forEach(log => prependLogItem(feed, log, false));
  } catch (e) {
    container.querySelector('#mod-actions-feed').innerHTML =
      `<div style="color:var(--danger);text-align:center;padding:16px;">${e.message}</div>`;
  }
}

function prependActionFeedItem(feed, data) {
  const item = createLogItem({
    action: data.action,
    admin_name: data.admin_name,
    target_name: data.target_name,
    reason: data.reason,
    done_at: new Date().toISOString(),
  });
  item.style.borderLeft = '3px solid var(--accent)';
  feed.prepend(item);
}

// ── Tab 2: Warns ──────────────────────────────────────────────────────────────

async function renderWarnsTab(container, chatId) {
  let warnSettings = { max_warns: 3, warn_action: 'mute', warn_duration: '1h', reset_on_kick: true };
  try {
    const res = await apiFetch(`/api/groups/${chatId}/warn-settings`);
    warnSettings = res.data || warnSettings;
  } catch (_) {}

  container.innerHTML = `
    <div style="background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-4);margin-bottom:var(--sp-4);">
      <h3 style="margin:0 0 12px;font-size:16px;">⚠️ Warning Settings</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
        <div>
          <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Max Warnings</label>
          <input id="max-warns-input" type="number" class="input" min="1" max="10" value="${warnSettings.max_warns}" style="width:100%;box-sizing:border-box;">
        </div>
        <div>
          <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Action on Limit</label>
          <select id="warn-action-select" class="input" style="width:100%;box-sizing:border-box;">
            ${['mute','kick','ban','tban'].map(a =>
              `<option value="${a}" ${warnSettings.warn_action===a?'selected':''}>${a.charAt(0).toUpperCase()+a.slice(1)}</option>`
            ).join('')}
          </select>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
        <div>
          <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Duration (tban/tmute)</label>
          <input id="warn-duration-input" class="input" value="${warnSettings.warn_duration}" placeholder="1h" style="width:100%;box-sizing:border-box;">
        </div>
        <div style="display:flex;align-items:flex-end;padding-bottom:2px;">
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px;">
            <input id="reset-on-kick" type="checkbox" ${warnSettings.reset_on_kick?'checked':''}>
            Reset warns on kick
          </label>
        </div>
      </div>
      <button id="save-warn-settings" class="btn btn-primary" style="width:100%;">💾 Save Settings</button>
    </div>

    <div id="active-warnings-list" style="display:flex;flex-direction:column;gap:var(--sp-2);">
      <div style="text-align:center;padding:32px;color:var(--text-muted);">Loading warnings...</div>
    </div>
  `;

  container.querySelector('#save-warn-settings').onclick = async () => {
    try {
      await apiFetch(`/api/groups/${chatId}/warn-settings`, {
        method: 'PUT',
        body: JSON.stringify({
          max_warns: parseInt(container.querySelector('#max-warns-input').value) || 3,
          warn_action: container.querySelector('#warn-action-select').value,
          warn_duration: container.querySelector('#warn-duration-input').value || '1h',
          reset_on_kick: container.querySelector('#reset-on-kick').checked,
        }),
      });
      showToast('✅ Warn settings saved', 'success');
    } catch (e) {
      showToast(`❌ ${e.message}`, 'error');
    }
  };

  try {
    const res = await apiFetch(`/api/groups/${chatId}/warnings?limit=50`);
    const warns = res.data || [];
    const list = container.querySelector('#active-warnings-list');
    list.innerHTML = '';

    const byUser = {};
    warns.forEach(w => {
      if (!byUser[w.user_id]) byUser[w.user_id] = [];
      byUser[w.user_id].push(w);
    });

    if (Object.keys(byUser).length === 0) {
      list.innerHTML = '<div style="text-align:center;padding:32px;color:var(--text-muted);">No active warnings.</div>';
      return;
    }

    Object.entries(byUser).forEach(([userId, userWarns]) => {
      const card = document.createElement('div');
      card.style.cssText = 'background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-3);';
      const maxWarns = warnSettings.max_warns || 3;
      const lastWarn = userWarns[0];
      const userName = lastWarn.target_name || `User ${userId}`;

      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <div style="font-weight:600;font-size:14px;">${escapeHtml(userName)}</div>
          <span style="font-size:13px;font-weight:600;color:#f59e0b;">${userWarns.length}/${maxWarns}</span>
        </div>
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:10px;">
          Last: "${escapeHtml(lastWarn.reason || 'No reason')}"
        </div>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-secondary" style="font-size:12px;padding:4px 10px;" data-action="remove-last" data-uid="${userId}">Remove Last</button>
          <button class="btn btn-secondary" style="font-size:12px;padding:4px 10px;" data-action="reset-all" data-uid="${userId}">Reset All</button>
        </div>
      `;

      card.querySelector('[data-action="remove-last"]').onclick = async () => {
        const lastId = lastWarn.id;
        try {
          await apiFetch(`/api/groups/${chatId}/warnings/${lastId}`, { method: 'DELETE' });
          showToast('✅ Warning removed', 'success');
          card.remove();
        } catch (e) { showToast(`❌ ${e.message}`, 'error'); }
      };

      card.querySelector('[data-action="reset-all"]').onclick = async () => {
        try {
          await apiFetch(`/api/groups/${chatId}/warnings/${userId}/all`, { method: 'DELETE' });
          showToast('✅ All warnings cleared', 'success');
          card.remove();
        } catch (e) { showToast(`❌ ${e.message}`, 'error'); }
      };

      list.appendChild(card);
    });
  } catch (e) {
    container.querySelector('#active-warnings-list').innerHTML =
      `<div style="color:var(--danger);text-align:center;padding:16px;">${e.message}</div>`;
  }
}

// ── Tab 3: Locks ──────────────────────────────────────────────────────────────

async function renderLocksTab(container, chatId) {
  const lockTypes = [
    { id: 'media', label: '📸 Media', desc: 'Photos & videos' },
    { id: 'stickers', label: '🎭 Stickers', desc: 'Sticker messages' },
    { id: 'gifs', label: '🎬 GIFs', desc: 'Animated GIFs' },
    { id: 'links', label: '🔗 Links', desc: 'URLs & text links' },
    { id: 'forwards', label: '↩️ Forwards', desc: 'Forwarded messages' },
    { id: 'polls', label: '📊 Polls', desc: 'Polls & surveys' },
    { id: 'games', label: '🎮 Games', desc: 'Inline games' },
    { id: 'voice', label: '🎙️ Voice', desc: 'Voice messages' },
    { id: 'video_notes', label: '⭕ Video Notes', desc: 'Round video messages' },
    { id: 'contacts', label: '📞 Contacts', desc: 'Contact sharing' },
  ];

  let locks = {};
  try {
    const res = await apiFetch(`/api/groups/${chatId}/locks`);
    locks = res.data || {};
  } catch (_) {}

  container.innerHTML = `
    <div style="background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-4);">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-3);">
        <h3 style="margin:0;font-size:16px;">🔒 Content Locks</h3>
        <div style="display:flex;gap:8px;">
          <button id="lock-all-btn" class="btn btn-secondary" style="font-size:12px;padding:4px 12px;">🔒 All</button>
          <button id="unlock-all-btn" class="btn btn-secondary" style="font-size:12px;padding:4px 12px;">🔓 All</button>
        </div>
      </div>
      <div id="locks-list" style="display:flex;flex-direction:column;gap:8px;"></div>
    </div>
  `;

  const list = container.querySelector('#locks-list');
  let debounceTimer = null;

  function renderLockToggles(lockState) {
    list.innerHTML = '';
    lockTypes.forEach(lock => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);';
      row.innerHTML = `
        <div>
          <div style="font-size:14px;font-weight:500;">${lock.label}</div>
          <div style="font-size:12px;color:var(--text-muted);">${lock.desc}</div>
        </div>
        <label style="position:relative;width:44px;height:24px;cursor:pointer;display:block;">
          <input id="lock-toggle-${lock.id}" type="checkbox" ${lockState[lock.id] ? 'checked' : ''}
            style="opacity:0;width:0;height:0;position:absolute;">
          <span style="
            position:absolute;inset:0;border-radius:12px;
            background:${lockState[lock.id] ? 'var(--accent)' : 'var(--bg-input)'};
            transition:0.3s;border:1px solid var(--border);
          ">
            <span style="
              position:absolute;top:3px;
              left:${lockState[lock.id] ? '23px' : '3px'};
              width:16px;height:16px;border-radius:50%;
              background:${lockState[lock.id] ? '#000' : 'var(--text-muted)'};
              transition:0.3s;
            "></span>
          </span>
        </label>
      `;

      const input = row.querySelector(`#lock-toggle-${lock.id}`);
      input.onchange = () => {
        lockState[lock.id] = input.checked;
        const span = row.querySelector('label span');
        const dot = span.querySelector('span');
        span.style.background = input.checked ? 'var(--accent)' : 'var(--bg-input)';
        dot.style.left = input.checked ? '23px' : '3px';
        dot.style.background = input.checked ? '#000' : 'var(--text-muted)';

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
          try {
            await apiFetch(`/api/groups/${chatId}/locks`, {
              method: 'PUT',
              body: JSON.stringify({ [lock.id]: input.checked }),
            });
            showToast(`${lock.label} ${input.checked ? 'locked' : 'unlocked'}`, 'success');
          } catch (e) {
            input.checked = !input.checked;
            showToast(`❌ ${e.message}`, 'error');
          }
        }, 500);
      };

      list.appendChild(row);
    });
  }

  renderLockToggles(locks);

  container.querySelector('#lock-all-btn').onclick = async () => {
    const allLocked = {};
    lockTypes.forEach(l => allLocked[l.id] = true);
    try {
      await apiFetch(`/api/groups/${chatId}/locks`, {
        method: 'PUT', body: JSON.stringify(allLocked),
      });
      locks = allLocked;
      renderLockToggles(locks);
      showToast('🔒 All content locked', 'success');
    } catch (e) { showToast(`❌ ${e.message}`, 'error'); }
  };

  container.querySelector('#unlock-all-btn').onclick = async () => {
    const allUnlocked = {};
    lockTypes.forEach(l => allUnlocked[l.id] = false);
    try {
      await apiFetch(`/api/groups/${chatId}/locks`, {
        method: 'PUT', body: JSON.stringify(allUnlocked),
      });
      locks = allUnlocked;
      renderLockToggles(locks);
      showToast('🔓 All content unlocked', 'success');
    } catch (e) { showToast(`❌ ${e.message}`, 'error'); }
  };
}

// ── Tab 4: Filters ────────────────────────────────────────────────────────────

async function renderFiltersTab(container, chatId) {
  container.innerHTML = `
    <div style="background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-4);margin-bottom:var(--sp-4);">
      <h3 style="margin:0 0 12px;font-size:16px;">➕ Add Filter</h3>
      <div style="margin-bottom:8px;">
        <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Keyword</label>
        <input id="filter-keyword" class="input" placeholder="e.g. hello" style="width:100%;box-sizing:border-box;">
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Response</label>
        <textarea id="filter-response" class="input" rows="3" placeholder="Hi {mention}! Welcome to {group}." style="width:100%;box-sizing:border-box;resize:vertical;"></textarea>
        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">Variables: {mention} {name} {id} {group}</div>
      </div>
      <button id="add-filter-btn" class="btn btn-primary" style="width:100%;">Add Filter</button>
    </div>

    <div style="margin-bottom:var(--sp-4);">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <h3 style="margin:0;font-size:16px;">📋 Active Filters</h3>
      </div>
      <div id="filter-list" style="display:flex;flex-direction:column;gap:8px;">
        <div style="text-align:center;padding:24px;color:var(--text-muted);">Loading filters...</div>
      </div>
    </div>

    <div style="background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-4);">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <h3 style="margin:0;font-size:16px;">🚫 Blacklist</h3>
        <select id="blacklist-mode-select" class="input" style="width:auto;font-size:12px;padding:4px 8px;">
          ${['delete','warn','mute','kick','ban'].map(m => `<option value="${m}">${m.charAt(0).toUpperCase()+m.slice(1)}</option>`).join('')}
        </select>
      </div>
      <div style="display:flex;gap:8px;margin-bottom:12px;">
        <input id="blacklist-word-input" class="input" placeholder="Add a word..." style="flex:1;">
        <button id="add-blacklist-btn" class="btn btn-danger" style="flex-shrink:0;">Add</button>
      </div>
      <div id="blacklist-chips" style="display:flex;flex-wrap:wrap;gap:6px;min-height:32px;">
        <div style="font-size:12px;color:var(--text-muted);">Loading...</div>
      </div>
    </div>
  `;

  const filterList = container.querySelector('#filter-list');
  const blacklistChips = container.querySelector('#blacklist-chips');

  async function loadFilters() {
    try {
      const res = await apiFetch(`/api/groups/${chatId}/filters`);
      const filters = res.data || [];
      filterList.innerHTML = '';
      if (filters.length === 0) {
        filterList.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-muted);">No filters set.</div>';
        return;
      }
      filters.forEach(f => addFilterRow(filterList, f, chatId));
    } catch (e) {
      filterList.innerHTML = `<div style="color:var(--danger);">${e.message}</div>`;
    }
  }

  async function loadBlacklist() {
    try {
      const res = await apiFetch(`/api/groups/${chatId}/blacklist`);
      const words = res.data || [];
      blacklistChips.innerHTML = '';
      if (words.length === 0) {
        blacklistChips.innerHTML = '<div style="font-size:12px;color:var(--text-muted);">No blacklisted words.</div>';
        return;
      }
      words.forEach(w => {
        const chip = document.createElement('div');
        chip.style.cssText = 'display:flex;align-items:center;gap:4px;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);border-radius:20px;padding:4px 10px;font-size:12px;';
        chip.innerHTML = `<span>${escapeHtml(w.word)}</span><button style="background:none;border:none;cursor:pointer;color:var(--danger);padding:0 0 0 4px;font-size:14px;line-height:1;" data-word="${escapeHtml(w.word)}">×</button>`;
        chip.querySelector('button').onclick = async () => {
          try {
            await apiFetch(`/api/groups/${chatId}/blacklist/${encodeURIComponent(w.word)}`, { method: 'DELETE' });
            chip.remove();
          } catch (e) { showToast(`❌ ${e.message}`, 'error'); }
        };
        blacklistChips.appendChild(chip);
      });
    } catch (_) {
      blacklistChips.innerHTML = '<div style="font-size:12px;color:var(--text-muted);">Failed to load.</div>';
    }
  }

  container.querySelector('#add-filter-btn').onclick = async () => {
    const keyword = container.querySelector('#filter-keyword').value.trim();
    const response = container.querySelector('#filter-response').value.trim();
    if (!keyword || !response) {
      showToast('❌ Keyword and response required', 'error');
      return;
    }
    try {
      await apiFetch(`/api/groups/${chatId}/filters`, {
        method: 'POST', body: JSON.stringify({ keyword, response }),
      });
      container.querySelector('#filter-keyword').value = '';
      container.querySelector('#filter-response').value = '';
      showToast('✅ Filter added', 'success');
      await loadFilters();
    } catch (e) { showToast(`❌ ${e.message}`, 'error'); }
  };

  container.querySelector('#add-blacklist-btn').onclick = async () => {
    const word = container.querySelector('#blacklist-word-input').value.trim();
    const action = container.querySelector('#blacklist-mode-select').value;
    if (!word) return;
    try {
      await apiFetch(`/api/groups/${chatId}/blacklist`, {
        method: 'POST', body: JSON.stringify({ word, action }),
      });
      container.querySelector('#blacklist-word-input').value = '';
      showToast('✅ Word blacklisted', 'success');
      await loadBlacklist();
    } catch (e) { showToast(`❌ ${e.message}`, 'error'); }
  };

  let modeTimer = null;
  container.querySelector('#blacklist-mode-select').onchange = (e) => {
    clearTimeout(modeTimer);
    modeTimer = setTimeout(async () => {
      try {
        await apiFetch(`/api/groups/${chatId}/blacklist/mode`, {
          method: 'PUT', body: JSON.stringify({ mode: e.target.value }),
        });
        showToast(`✅ Blacklist mode: ${e.target.value}`, 'success');
      } catch (err) { showToast(`❌ ${err.message}`, 'error'); }
    }, 500);
  };

  await loadFilters();
  await loadBlacklist();
}

function addFilterRow(filterList, f, chatId) {
  const row = document.createElement('div');
  row.dataset.filterId = f.id || '';
  row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:10px 14px;';
  const preview = (f.response || '').length > 50 ? f.response.substring(0, 50) + '...' : (f.response || '');
  row.innerHTML = `
    <div style="min-width:0;flex:1;">
      <span style="font-weight:600;font-size:13px;">${escapeHtml(f.keyword)}</span>
      <span style="color:var(--text-muted);font-size:12px;margin-left:8px;">→ ${escapeHtml(preview)}</span>
    </div>
    <button style="background:none;border:none;cursor:pointer;color:var(--danger);font-size:18px;padding:0 0 0 8px;flex-shrink:0;" data-id="${f.id || f.keyword}">×</button>
  `;
  row.querySelector('button').onclick = async () => {
    try {
      if (f.id) {
        await apiFetch(`/api/groups/${chatId}/filters/${f.id}`, { method: 'DELETE' });
      } else {
        await apiFetch(`/api/groups/${chatId}/filters/${encodeURIComponent(f.keyword)}`, { method: 'DELETE' });
      }
      row.remove();
      showToast('✅ Filter removed', 'success');
    } catch (e) { showToast(`❌ ${e.message}`, 'error'); }
  };
  filterList.appendChild(row);
}

// ── Tab 5: Log ────────────────────────────────────────────────────────────────

async function renderLogTab(container, chatId) {
  container.innerHTML = `
    <div style="display:flex;gap:8px;margin-bottom:var(--sp-3);">
      <input id="log-search" class="input" placeholder="🔍 Filter by action, admin, or user..." style="flex:1;">
    </div>
    <div id="mod-log-feed" style="display:flex;flex-direction:column;gap:8px;"></div>
    <div id="log-load-more" style="text-align:center;margin-top:var(--sp-3);"></div>
  `;

  let page = 1;
  const feed = container.querySelector('#mod-log-feed');
  const loadMoreEl = container.querySelector('#log-load-more');

  async function loadLogs(append = false) {
    if (!append) {
      feed.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-muted);">Loading...</div>';
    }
    try {
      const res = await apiFetch(`/api/groups/${chatId}/mod-log?page=${page}&limit=20`);
      const logs = res.data || [];

      if (!append) feed.innerHTML = '';
      if (logs.length === 0 && !append) {
        feed.innerHTML = '<div style="text-align:center;padding:32px;color:var(--text-muted);">No mod actions yet.</div>';
        return;
      }
      logs.forEach(log => prependLogItem(feed, log, false));
      loadMoreEl.innerHTML = logs.length === 20
        ? `<button class="btn btn-secondary">Load more</button>`
        : '';
      if (logs.length === 20) {
        loadMoreEl.querySelector('button').onclick = () => {
          page++;
          loadLogs(true);
        };
      }
    } catch (e) {
      if (!append) feed.innerHTML = `<div style="color:var(--danger);text-align:center;">${e.message}</div>`;
    }
  }

  await loadLogs();
}

function prependLogItem(feed, data, prepend = true) {
  const item = createLogItem(data);
  if (prepend) {
    feed.prepend(item);
  } else {
    feed.appendChild(item);
  }
}

function createLogItem(data) {
  const actionColors = {
    ban: '#ef4444', unban: '#10b981', mute: '#818cf8', unmute: '#10b981',
    warn: '#f59e0b', kick: '#fb923c', promote: '#06b6d4', demote: '#ef4444',
    restrict: '#8b5cf6', resetwarns: '#10b981',
  };
  const actionEmojis = {
    ban: '🔨', unban: '✅', mute: '🔇', unmute: '✅', warn: '⚠️',
    kick: '👢', promote: '⭐', demote: '📉', restrict: '🔒', resetwarns: '🔄',
  };

  const action = data.action || 'unknown';
  const color = actionColors[action] || 'var(--text-muted)';
  const emoji = actionEmojis[action] || '⚡';

  const item = document.createElement('div');
  item.style.cssText = `
    background:var(--card); border:1px solid var(--border);
    border-radius:var(--r-lg); padding:var(--sp-3);
    border-left:3px solid ${color};
  `;

  const targetName = data.target_name || (data.target_id ? `User ${data.target_id}` : 'Unknown');
  const adminName = data.admin_name || (data.admin_id ? `User ${data.admin_id}` : 'System');
  const reason = data.reason || '';
  const duration = data.duration || '';
  const timeStr = data.done_at
    ? new Date(data.done_at).toLocaleString()
    : 'Just now';

  item.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px;">
      <span style="font-weight:600;font-size:13px;color:${color};">${emoji} ${action.toUpperCase()}</span>
      <span style="font-size:11px;color:var(--text-muted);">${timeStr}</span>
    </div>
    <div style="font-size:13px;margin-bottom:2px;">
      <span style="color:var(--text-muted);">By</span> <strong>${escapeHtml(adminName)}</strong>
      <span style="color:var(--text-muted);"> → </span> <strong>${escapeHtml(targetName)}</strong>
      ${duration ? `<span style="color:var(--text-muted);"> (${escapeHtml(duration)})</span>` : ''}
    </div>
    ${reason ? `<div style="font-size:12px;color:var(--text-muted);font-style:italic;">"${escapeHtml(reason)}"</div>` : ''}
  `;

  return item;
}

function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
