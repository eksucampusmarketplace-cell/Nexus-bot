/**
 * miniapp/src/pages/moderation.js
 *
 * Moderation management page — COMPLETE REWRITE.
 * Fixes: wrong store API, Tailwind classes, SSE URL, broken endpoints, empty stubs.
 */

import { Card, Toggle, EmptyState, showToast } from '../../lib/components.js?v=1.5.0';
import { useStore } from '../../store/index.js?v=1.5.0';
import { apiFetch } from '../../lib/api.js?v=1.5.0';

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

  const tabs = ['Actions', 'Warns', 'Locks', 'Filters'];
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

  await switchTab('actions', container, chatId);
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
    case 'actions': return _renderActionsTab(content, chatId);
    case 'warns':   return _renderWarnsTab(content, chatId);
    case 'locks':   return _renderLocksTab(content, chatId);
    case 'filters': return _renderFiltersTab(content, chatId);
  }
}

async function _renderActionsTab(container, chatId) {
  container.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading actions...</div>`;

  try {
    const logs = await apiFetch(`/api/groups/${chatId}/logs?limit=50`);
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
        <span style="font-size:var(--text-sm);font-weight:var(--fw-medium);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${log.target_username || log.user_id || 'Unknown'}</span>
      </div>
      <div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:2px;">
        by ${log.by_username || 'System'}${log.reason ? ` · "${log.reason}"` : ''}
      </div>
    </div>
    <span style="font-size:var(--text-xs);color:var(--text-muted);white-space:nowrap;">${_timeAgo(log.timestamp || log.created_at)}</span>
  `;
  return row;
}

function _exportLogsCSV(logs) {
  const rows = [['Action', 'Target', 'Admin', 'Reason', 'Time']];
  logs.forEach(l => rows.push([l.action, l.target_username || l.user_id, l.by_username || 'System', l.reason || '', l.timestamp || l.created_at || '']));
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
    const group = await apiFetch(`/api/groups/${chatId}`);
    const s = group?.settings || {};
    warnSettings = {
      warn_max: s.warn_max || 3,
      warn_action: s.warn_action || 'mute_24h',
      warn_expiry: s.warn_expiry || 'never',
    };
  } catch (_) {}

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
      const group = await apiFetch(`/api/groups/${chatId}`);
      const newSettings = { ...(group?.settings || {}), warn_max: max, warn_action: action, warn_expiry: expiry };
      await apiFetch(`/api/groups/${chatId}/settings`, { method: 'PUT', body: JSON.stringify(newSettings) });
      showToast('Warn settings saved', 'success');
    } catch (e) {
      showToast('Failed to save: ' + e.message, 'error');
    }
  });
}

async function _renderLocksTab(container, chatId) {
  container.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading locks...</div>`;

  let locks = {};
  try {
    const res = await apiFetch(`/api/groups/${chatId}/locks`);
    locks = res?.data || res || {};
  } catch (_) {}

  container.innerHTML = '';

  const lockTypes = [
    { id: 'photo',    label: '📸 Photos',    group: 'media' },
    { id: 'video',    label: '🎬 Videos',    group: 'media' },
    { id: 'sticker',  label: '🎭 Stickers',  group: 'media' },
    { id: 'gif',      label: '🎞️ GIFs',      group: 'media' },
    { id: 'voice',    label: '🎙️ Voice',     group: 'media' },
    { id: 'audio',    label: '🎵 Audio',     group: 'media' },
    { id: 'document', label: '📄 Documents', group: 'media' },
    { id: 'link',     label: '🔗 Links',     group: 'comm' },
    { id: 'forward',  label: '↩️ Forwards',  group: 'comm' },
    { id: 'poll',     label: '📊 Polls',     group: 'comm' },
    { id: 'contact',  label: '📞 Contacts',  group: 'comm' },
  ];

  let debounceTimer = null;
  const pendingLocks = { ...locks };

  const saveLocks = async () => {
    try {
      await apiFetch(`/api/groups/${chatId}/locks`, { method: 'PUT', body: JSON.stringify(pendingLocks) });
    } catch (e) {
      showToast('Failed to save lock: ' + e.message, 'error');
    }
  };

  const buildGroup = (groupId, title, types) => {
    const section = document.createElement('div');
    section.style.marginBottom = 'var(--sp-4)';
    section.innerHTML = `<div style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:var(--sp-2);">${title}</div>`;

    const grid = document.createElement('div');
    grid.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-2);';

    types.filter(t => t.group === groupId).forEach(lock => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:var(--sp-3);background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-lg);';
      row.innerHTML = `<span style="font-size:var(--text-sm);">${lock.label}</span>`;

      const toggle = Toggle({
        checked: !!locks[lock.id],
        onChange: (checked) => {
          pendingLocks[lock.id] = checked;
          clearTimeout(debounceTimer);
          debounceTimer = setTimeout(saveLocks, 300);
        }
      });
      row.appendChild(toggle);
      grid.appendChild(row);
    });

    section.appendChild(grid);
    return section;
  };

  container.appendChild(buildGroup('media', '📸 Media', lockTypes));
  container.appendChild(buildGroup('comm', '💬 Communication', lockTypes));
}

async function _renderFiltersTab(container, chatId) {
  container.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading filters...</div>`;

  let blacklist = [];
  try {
    const res = await apiFetch(`/api/groups/${chatId}/blacklist`);
    blacklist = res?.words || res || [];
  } catch (_) {}

  container.innerHTML = '';

  const blacklistCard = Card({ title: '🚫 Word Blacklist', subtitle: 'Automatically act on these words' });

  const chipsContainer = document.createElement('div');
  chipsContainer.id = 'blacklist-chips';
  chipsContainer.style.cssText = 'display:flex;flex-wrap:wrap;gap:var(--sp-2);margin-bottom:var(--sp-3);min-height:32px;';

  const renderChips = (words) => {
    chipsContainer.innerHTML = '';
    words.forEach(word => {
      const chip = document.createElement('span');
      chip.style.cssText = 'display:inline-flex;align-items:center;gap:4px;padding:4px 10px;background:var(--bg-overlay);border:1px solid var(--border);border-radius:var(--r-full);font-size:var(--text-xs);';
      chip.innerHTML = `${word} <button onclick="this.parentElement.remove();removeBlacklistWord('${chatId}','${word}')" style="background:none;border:none;cursor:pointer;color:var(--text-muted);padding:0;font-size:14px;line-height:1;">&times;</button>`;
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
      await apiFetch(`/api/groups/${chatId}/blacklist`, { method: 'POST', body: JSON.stringify({ word }) });
      blacklist.push(word);
      renderChips(blacklist);
      input.value = '';
      showToast('Word added', 'success');
    } catch (e) {
      showToast('Failed: ' + e.message, 'error');
    }
  };

  blacklistCard.querySelector ? null : null;
  blacklistCard.appendChild(chipsContainer);
  blacklistCard.appendChild(addRow);
  blacklistCard.insertAdjacentHTML('beforeend', '');

  container.appendChild(blacklistCard);

  setTimeout(() => {
    blacklistCard.querySelector('#add-blacklist-btn')?.addEventListener('click', addWord);
    blacklistCard.querySelector('#blacklist-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') addWord(); });
  }, 0);

  window.removeBlacklistWord = async (cid, word) => {
    try {
      await apiFetch(`/api/groups/${cid}/blacklist/${encodeURIComponent(word)}`, { method: 'DELETE' });
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
    const initData = window.Telegram?.WebApp?.initData || '';
    _sseSource = new EventSource(`/api/events/${chatId}`);

    _sseSource.onopen = () => {
      if (dot) { dot.style.background = 'var(--success)'; dot.style.animation = 'pulse 1.5s infinite'; }
      if (label) label.textContent = 'Live';
    };

    _sseSource.onerror = () => {
      if (dot) { dot.style.background = 'var(--danger)'; dot.style.animation = ''; }
      if (label) label.textContent = 'Offline';
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
