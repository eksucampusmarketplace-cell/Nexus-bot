/**
 * miniapp/src/pages/engagement.js
 *
 * Engagement management page with tabs:
 * [⭐ XP & Levels] [👍 Reputation] [🏅 Badges] [📰 Newsletter] [🌐 Network]
 */

import { Card, EmptyState, showToast } from '../../lib/components.js?v=1.3.3';
import { apiFetch } from '../../lib/api.js?v=1.3.3';
import { useStore } from '../../store/index.js?v=1.3.3';

const store = useStore;

const TABS = [
  { id: 'xp', label: '⭐ XP & Levels' },
  { id: 'rep', label: '👍 Reputation' },
  { id: 'badges', label: '🏅 Badges' },
  { id: 'newsletter', label: '📰 Newsletter' },
  { id: 'network', label: '🌐 Network' },
];

let _activeTab = 'xp';

export async function renderEngagementPage(container) {
  const state = store.getState();
  const chatId = state.activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '⭐',
      title: 'Select a group',
      description: 'Choose a group to manage engagement settings.',
    }));
    return;
  }

  const header = document.createElement('div');
  header.style.cssText = 'margin-bottom: var(--sp-4);';
  header.innerHTML = `
    <h2 style="font-size:20px;font-weight:700;margin:0;">⭐ Engagement</h2>
    <p style="color:var(--text-muted);font-size:13px;margin:4px 0 0;">XP, reputation, badges, newsletters &amp; networks</p>
  `;
  container.appendChild(header);

  const tabBar = document.createElement('div');
  tabBar.style.cssText = `
    display:flex;gap:var(--sp-1);overflow-x:auto;margin-bottom:var(--sp-4);
    border-bottom:1px solid var(--border);padding-bottom:var(--sp-2);
  `;
  tabBar.innerHTML = TABS.map(t => `
    <button data-tab="${t.id}" style="
      padding:var(--sp-2) var(--sp-3);border:none;background:none;cursor:pointer;
      font-size:var(--text-sm);font-weight:var(--fw-medium);white-space:nowrap;
      color:${_activeTab === t.id ? 'var(--accent)' : 'var(--text-secondary)'};
      border-bottom:2px solid ${_activeTab === t.id ? 'var(--accent)' : 'transparent'};
    ">${t.label}</button>
  `).join('');
  container.appendChild(tabBar);

  const contentArea = document.createElement('div');
  container.appendChild(contentArea);

  tabBar.querySelectorAll('[data-tab]').forEach(btn => {
    btn.onclick = async () => {
      _activeTab = btn.dataset.tab;
      tabBar.querySelectorAll('[data-tab]').forEach(b => {
        const isActive = b.dataset.tab === _activeTab;
        b.style.color = isActive ? 'var(--accent)' : 'var(--text-secondary)';
        b.style.borderBottom = isActive ? '2px solid var(--accent)' : '2px solid transparent';
      });
      await renderTab(contentArea, chatId, _activeTab);
    };
  });

  await renderTab(contentArea, chatId, _activeTab);
}

async function renderTab(container, chatId, tab) {
  container.innerHTML = `
    <div style="text-align:center;padding:var(--sp-8);">
      <div style="font-size:48px;">⏳</div>
      <div style="color:var(--text-muted);margin-top:var(--sp-2);">Loading...</div>
    </div>
  `;
  try {
    switch (tab) {
      case 'xp': await renderXpTab(container, chatId); break;
      case 'rep': await renderRepTab(container, chatId); break;
      case 'badges': await renderBadgesTab(container, chatId); break;
      case 'newsletter': await renderNewsletterTab(container, chatId); break;
      case 'network': await renderNetworkTab(container, chatId); break;
    }
  } catch (err) {
    container.innerHTML = '';
    container.appendChild(EmptyState({ icon: '⚠️', title: 'Error', description: err.message }));
  }
}

function progressBar(pct, length = 12) {
  const filled = Math.round(length * pct / 100);
  return '█'.repeat(filled) + '░'.repeat(length - filled);
}

// ── XP & Levels Tab ───────────────────────────────────────────────────────────

async function renderXpTab(container, chatId) {
  container.innerHTML = '';

  let leaderboard = [], settings = {};
  try {
    [leaderboard, settings] = await Promise.all([
      apiFetch(`/api/groups/${chatId}/xp/leaderboard?limit=10`).then(r => r.leaderboard || []),
      apiFetch(`/api/groups/${chatId}/xp/settings`).catch(() => ({})),
    ]);
  } catch (e) {
    leaderboard = [];
  }

  if (settings.double_xp_active) {
    const banner = document.createElement('div');
    banner.style.cssText = `
      background:linear-gradient(135deg,#f59e0b,#d97706);color:#000;
      border-radius:var(--r-xl);padding:var(--sp-4);margin-bottom:var(--sp-4);
      font-weight:var(--fw-bold);font-size:var(--text-sm);text-align:center;
    `;
    banner.textContent = '⚡ DOUBLE XP ACTIVE — All XP earnings are multiplied by 2x!';
    container.appendChild(banner);
  }

  const lbCard = document.createElement('div');
  lbCard.style.cssText = 'margin-bottom:var(--sp-4);';
  lbCard.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-3);">
      <h3 style="margin:0;font-size:16px;font-weight:700;">🏆 XP Leaderboard</h3>
    </div>
  `;

  if (!leaderboard.length) {
    lbCard.appendChild(EmptyState({ icon: '⭐', title: 'No XP data yet', description: 'Members earn XP by chatting.' }));
  } else {
    const medals = ['👑', '⭐', '🌟', '🏅', '🔹'];
    const maxXp = leaderboard[0]?.xp || 1;
    leaderboard.forEach((entry, i) => {
      const pct = Math.round((entry.xp / maxXp) * 100);
      const bar = progressBar(pct);
      const row = document.createElement('div');
      row.style.cssText = `
        display:flex;align-items:center;gap:var(--sp-3);
        padding:var(--sp-3);background:var(--card);border:1px solid var(--border);
        border-radius:var(--r-lg);margin-bottom:var(--sp-2);
      `;
      row.innerHTML = `
        <div style="font-size:18px;width:28px;text-align:center;">${medals[i] || i + 1}</div>
        <div style="flex:1;min-width:0;">
          <div style="font-weight:600;font-size:14px;">User ${entry.user_id}</div>
          <div style="font-size:11px;color:var(--text-muted);">Lv.${entry.level} · ${(entry.xp || 0).toLocaleString()} XP</div>
          <div style="font-size:10px;color:var(--accent);font-family:monospace;margin-top:2px;">${bar}</div>
        </div>
      `;
      lbCard.appendChild(row);
    });
  }
  container.appendChild(lbCard);

  const settingsCard = Card({ title: '⚙️ XP Settings', children: '<div id="xp-settings-content"></div>' });
  container.appendChild(settingsCard);

  const sc = settingsCard.querySelector('#xp-settings-content');
  sc.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-3);">
      <label style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:var(--text-sm);">Enable XP System</span>
        <input type="checkbox" id="xp-enabled" ${settings.enabled !== false ? 'checked' : ''}>
      </label>
      <label style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:var(--text-sm);">XP per message</span>
        <input type="number" id="xp-per-msg" value="${settings.xp_per_message ?? 1}" style="width:60px;" class="input">
      </label>
      <label style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:var(--text-sm);">Message cooldown (seconds)</span>
        <input type="number" id="xp-cooldown" value="${settings.message_cooldown_s ?? 60}" style="width:70px;" class="input">
      </label>
      <label style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:var(--text-sm);">XP per daily check-in</span>
        <input type="number" id="xp-per-daily" value="${settings.xp_per_daily ?? 10}" style="width:60px;" class="input">
      </label>
      <label style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:var(--text-sm);">Level-up announcement</span>
        <input type="checkbox" id="xp-announce" ${settings.level_up_announce !== false ? 'checked' : ''}>
      </label>
      <div style="margin-top:var(--sp-2);">
        <div style="font-size:var(--text-sm);font-weight:var(--fw-medium);margin-bottom:var(--sp-2);">⚡ Double XP Event</div>
        <div style="display:flex;gap:var(--sp-2);align-items:center;">
          <input type="number" id="dxp-hours" value="2" min="1" max="24" style="width:60px;" class="input" placeholder="hrs">
          <button id="start-double-xp" class="btn btn-primary" style="font-size:var(--text-xs);">Start Double XP</button>
        </div>
      </div>
      <button id="save-xp-settings" class="btn btn-primary" style="margin-top:var(--sp-2);">💾 Save Settings</button>
    </div>
  `;

  sc.querySelector('#save-xp-settings').onclick = async () => {
    try {
      await apiFetch(`/api/groups/${chatId}/xp/settings`, {
        method: 'PUT',
        body: JSON.stringify({
          enabled: sc.querySelector('#xp-enabled').checked,
          xp_per_message: parseInt(sc.querySelector('#xp-per-msg').value) || 1,
          message_cooldown_s: parseInt(sc.querySelector('#xp-cooldown').value) || 60,
          xp_per_daily: parseInt(sc.querySelector('#xp-per-daily').value) || 10,
          level_up_announce: sc.querySelector('#xp-announce').checked,
        }),
      });
      showToast('XP settings saved!', 'success');
    } catch (e) { showToast(e.message || 'Failed to save', 'error'); }
  };

  sc.querySelector('#start-double-xp').onclick = async () => {
    const hours = parseInt(sc.querySelector('#dxp-hours').value) || 2;
    try {
      await apiFetch(`/api/groups/${chatId}/xp/double`, {
        method: 'POST',
        body: JSON.stringify({ hours }),
      });
      showToast(`⚡ Double XP active for ${hours} hours!`, 'success');
    } catch (e) { showToast(e.message || 'Failed', 'error'); }
  };
}

// ── Reputation Tab ────────────────────────────────────────────────────────────

async function renderRepTab(container, chatId) {
  container.innerHTML = '';

  let board = [];
  try {
    const data = await apiFetch(`/api/groups/${chatId}/rep/leaderboard?limit=10`);
    board = data.leaderboard || [];
  } catch (e) { board = []; }

  const lbCard = document.createElement('div');
  lbCard.style.cssText = 'margin-bottom:var(--sp-4);';
  lbCard.innerHTML = `<h3 style="margin:0 0 var(--sp-3);font-size:16px;font-weight:700;">👍 Reputation Board</h3>`;

  if (!board.length) {
    lbCard.appendChild(EmptyState({ icon: '👍', title: 'No rep data yet', description: 'Members earn rep from /rep command.' }));
  } else {
    const maxRep = board[0]?.rep_score || 1;
    board.forEach((entry, i) => {
      const pct = Math.round((entry.rep_score / maxRep) * 100);
      const bar = progressBar(pct);
      const row = document.createElement('div');
      row.style.cssText = `
        display:flex;align-items:center;gap:var(--sp-3);
        padding:var(--sp-3);background:var(--card);border:1px solid var(--border);
        border-radius:var(--r-lg);margin-bottom:var(--sp-2);
      `;
      row.innerHTML = `
        <div style="font-weight:700;width:24px;text-align:center;">${i + 1}.</div>
        <div style="flex:1;">
          <div style="font-size:14px;font-weight:600;">User ${entry.user_id}</div>
          <div style="font-size:11px;color:var(--text-muted);">${entry.rep_score} rep · ${bar}</div>
        </div>
      `;
      lbCard.appendChild(row);
    });
  }
  container.appendChild(lbCard);

  const adminCard = Card({
    title: '⚙️ Admin Rep Actions',
    children: `
      <div style="display:flex;flex-direction:column;gap:var(--sp-3);">
        <div>
          <label style="font-size:var(--text-xs);color:var(--text-muted);">User ID</label>
          <input id="rep-user" type="number" class="input" placeholder="User ID" style="margin-top:4px;">
        </div>
        <div>
          <label style="font-size:var(--text-xs);color:var(--text-muted);">Amount</label>
          <div style="display:flex;gap:var(--sp-2);margin-top:4px;">
            <button class="btn btn-secondary rep-amount" data-val="1">+1</button>
            <button class="btn btn-secondary rep-amount" data-val="-1">-1</button>
            <button class="btn btn-secondary rep-amount" data-val="5">+5</button>
            <input id="rep-custom" type="number" class="input" placeholder="custom" style="width:80px;">
          </div>
        </div>
        <div>
          <label style="font-size:var(--text-xs);color:var(--text-muted);">Reason (optional)</label>
          <input id="rep-reason" type="text" class="input" placeholder="reason..." style="margin-top:4px;">
        </div>
        <button id="give-rep-btn" class="btn btn-primary">Give Rep</button>
      </div>
    `,
  });
  container.appendChild(adminCard);

  let selectedAmount = 1;
  adminCard.querySelectorAll('.rep-amount').forEach(btn => {
    btn.onclick = () => {
      selectedAmount = parseInt(btn.dataset.val);
      adminCard.querySelectorAll('.rep-amount').forEach(b => b.style.background = '');
      btn.style.background = 'var(--accent-dim)';
    };
  });

  adminCard.querySelector('#give-rep-btn').onclick = async () => {
    const userId = parseInt(adminCard.querySelector('#rep-user').value);
    const custom = adminCard.querySelector('#rep-custom').value;
    const amount = custom ? parseInt(custom) : selectedAmount;
    const reason = adminCard.querySelector('#rep-reason').value;
    if (!userId) { showToast('Enter user ID', 'error'); return; }
    try {
      const result = await apiFetch(`/api/groups/${chatId}/rep/give`, {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, amount, reason: reason || null }),
      });
      showToast(result.message || 'Rep given!', 'success');
    } catch (e) { showToast(e.message || 'Failed', 'error'); }
  };
}

// ── Badges Tab ────────────────────────────────────────────────────────────────

async function renderBadgesTab(container, chatId) {
  container.innerHTML = '';

  let badges = [];
  try {
    const data = await apiFetch(`/api/groups/${chatId}/badges`);
    badges = data.badges || [];
  } catch (e) { badges = []; }

  const header = document.createElement('div');
  header.style.cssText = 'margin-bottom:var(--sp-4);';
  header.innerHTML = `<h3 style="margin:0;font-size:16px;font-weight:700;">🏅 Badges (${badges.length})</h3>`;
  container.appendChild(header);

  if (!badges.length) {
    container.appendChild(EmptyState({ icon: '🏅', title: 'No badges', description: 'Default badges are seeded automatically.' }));
    return;
  }

  const grid = document.createElement('div');
  grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:var(--sp-3);';

  badges.forEach(badge => {
    const card = document.createElement('div');
    card.style.cssText = `
      padding:var(--sp-3);background:var(--card);border:1px solid var(--border);
      border-radius:var(--r-xl);text-align:center;
      ${badge.is_rare ? 'border-color:var(--accent);' : ''}
    `;
    card.innerHTML = `
      <div style="font-size:28px;margin-bottom:var(--sp-1);">${badge.emoji}</div>
      <div style="font-weight:700;font-size:var(--text-sm);">${badge.name}</div>
      <div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:4px;">${badge.description || ''}</div>
      ${badge.is_rare ? '<div style="font-size:10px;color:var(--accent);margin-top:4px;">✨ Rare</div>' : ''}
    `;
    grid.appendChild(card);
  });
  container.appendChild(grid);

  const createCard = Card({
    title: '+ Create Custom Badge',
    children: `
      <div style="display:flex;flex-direction:column;gap:var(--sp-3);">
        <div style="display:flex;gap:var(--sp-2);">
          <input id="badge-emoji" type="text" class="input" placeholder="🎯" style="width:60px;text-align:center;">
          <input id="badge-name" type="text" class="input" placeholder="Badge name" style="flex:1;">
        </div>
        <input id="badge-desc" type="text" class="input" placeholder="Description">
        <div style="display:flex;gap:var(--sp-2);">
          <select id="badge-condition" class="input" style="flex:1;">
            <option value="level">Level</option>
            <option value="messages">Messages</option>
            <option value="streak">Streak days</option>
            <option value="rep_received">Rep received</option>
            <option value="game_wins">Game wins</option>
            <option value="manual">Manual grant</option>
          </select>
          <input id="badge-value" type="number" class="input" placeholder="Value" style="width:80px;">
        </div>
        <label style="display:flex;align-items:center;gap:var(--sp-2);font-size:var(--text-sm);">
          <input type="checkbox" id="badge-rare"> Rare badge
        </label>
        <button id="create-badge-btn" class="btn btn-primary">Create Badge</button>
      </div>
    `,
  });
  container.appendChild(createCard);

  createCard.querySelector('#create-badge-btn').onclick = async () => {
    const emoji = createCard.querySelector('#badge-emoji').value.trim();
    const name = createCard.querySelector('#badge-name').value.trim();
    const description = createCard.querySelector('#badge-desc').value.trim();
    const condition_type = createCard.querySelector('#badge-condition').value;
    const condition_value = parseInt(createCard.querySelector('#badge-value').value) || 0;
    const is_rare = createCard.querySelector('#badge-rare').checked;
    if (!emoji || !name) { showToast('Emoji and name required', 'error'); return; }
    try {
      await apiFetch(`/api/groups/${chatId}/badges/grant`, {
        method: 'POST',
        body: JSON.stringify({ emoji, name, description, condition_type, condition_value, is_rare }),
      });
      showToast('Badge created!', 'success');
      await renderBadgesTab(container, chatId);
    } catch (e) { showToast(e.message || 'Failed', 'error'); }
  };
}

// ── Newsletter Tab ────────────────────────────────────────────────────────────

async function renderNewsletterTab(container, chatId) {
  container.innerHTML = '';

  let config = {}, history = [];
  try {
    [config, history] = await Promise.all([
      apiFetch(`/api/groups/${chatId}/newsletter/settings`).catch(() => ({})),
      apiFetch(`/api/groups/${chatId}/newsletter/history`).then(r => r.history || []).catch(() => []),
    ]);
  } catch (e) { config = {}; history = []; }

  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

  const previewCard = Card({
    title: '📰 Newsletter Preview',
    children: `
      <div style="display:flex;gap:var(--sp-2);flex-wrap:wrap;">
        <button id="preview-nl" class="btn btn-secondary">👁️ Preview This Week</button>
        <button id="send-nl" class="btn btn-primary">📤 Send Now</button>
      </div>
      <div id="nl-preview-content" style="margin-top:var(--sp-3);"></div>
    `,
  });
  container.appendChild(previewCard);

  previewCard.querySelector('#preview-nl').onclick = async () => {
    const content = previewCard.querySelector('#nl-preview-content');
    content.innerHTML = '<div style="color:var(--text-muted);">Generating preview...</div>';
    try {
      const data = await apiFetch(`/api/groups/${chatId}/newsletter/preview`);
      content.innerHTML = `<pre style="white-space:pre-wrap;font-size:12px;background:var(--bg-input);padding:var(--sp-3);border-radius:var(--r-lg);">${data.preview || ''}</pre>`;
    } catch (e) { content.innerHTML = `<div style="color:var(--danger);">Error: ${e.message}</div>`; }
  };

  previewCard.querySelector('#send-nl').onclick = async () => {
    if (!confirm('Send newsletter to this group now?')) return;
    try {
      await apiFetch(`/api/groups/${chatId}/newsletter/send-now`, { method: 'POST' });
      showToast('Newsletter sent!', 'success');
    } catch (e) { showToast(e.message || 'Failed', 'error'); }
  };

  const settingsCard = Card({
    title: '⚙️ Newsletter Settings',
    children: `
      <div style="display:flex;flex-direction:column;gap:var(--sp-3);">
        <label style="display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:var(--text-sm);">Enable weekly newsletter</span>
          <input type="checkbox" id="nl-enabled" ${config.enabled !== false ? 'checked' : ''}>
        </label>
        <div style="display:flex;gap:var(--sp-2);align-items:center;">
          <label style="font-size:var(--text-sm);flex:1;">Send on:</label>
          <select id="nl-day" class="input" style="flex:1;">
            ${days.map((d, i) => `<option value="${i}" ${config.send_day === i ? 'selected' : ''}>${d}</option>`).join('')}
          </select>
        </div>
        <div style="display:flex;gap:var(--sp-2);align-items:center;">
          <label style="font-size:var(--text-sm);flex:1;">Hour (UTC):</label>
          <input id="nl-hour" type="number" min="0" max="23" value="${config.send_hour_utc ?? 9}" class="input" style="width:70px;">
        </div>
        <div style="font-size:var(--text-xs);font-weight:var(--fw-semibold);color:var(--text-muted);">Include sections:</div>
        ${[
          ['include_top_members', 'Most active members'],
          ['include_new_members', 'New members'],
          ['include_leaderboard', 'Leaderboard snapshot'],
          ['include_milestones', 'Milestones'],
        ].map(([key, label]) => `
          <label style="display:flex;align-items:center;gap:var(--sp-2);font-size:var(--text-sm);">
            <input type="checkbox" id="nl-${key}" ${config[key] !== false ? 'checked' : ''}> ${label}
          </label>
        `).join('')}
        <div>
          <label style="font-size:var(--text-xs);color:var(--text-muted);">Custom intro (optional)</label>
          <textarea id="nl-intro" class="input" rows="3" style="margin-top:4px;resize:vertical;"
            placeholder="Welcome to our weekly digest!">${config.custom_intro || ''}</textarea>
        </div>
        <button id="save-nl-settings" class="btn btn-primary">💾 Save Settings</button>
      </div>
    `,
  });
  container.appendChild(settingsCard);

  settingsCard.querySelector('#save-nl-settings').onclick = async () => {
    try {
      const body = {
        enabled: settingsCard.querySelector('#nl-enabled').checked,
        send_day: parseInt(settingsCard.querySelector('#nl-day').value),
        send_hour_utc: parseInt(settingsCard.querySelector('#nl-hour').value),
        include_top_members: settingsCard.querySelector('#nl-include_top_members').checked,
        include_new_members: settingsCard.querySelector('#nl-include_new_members').checked,
        include_leaderboard: settingsCard.querySelector('#nl-include_leaderboard').checked,
        include_milestones: settingsCard.querySelector('#nl-include_milestones').checked,
        custom_intro: settingsCard.querySelector('#nl-intro').value || null,
      };
      await apiFetch(`/api/groups/${chatId}/newsletter/settings`, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      showToast('Newsletter settings saved!', 'success');
    } catch (e) { showToast(e.message || 'Failed', 'error'); }
  };

  if (history.length) {
    const histCard = Card({
      title: '📜 Newsletter History',
      children: history.map(h => {
        const date = new Date(h.sent_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        return `<div style="padding:var(--sp-2) 0;border-bottom:1px solid var(--border);font-size:var(--text-sm);">
          ${date}
          <span style="float:right;color:var(--text-muted);">msg #${h.message_id || '?'}</span>
        </div>`;
      }).join(''),
    });
    container.appendChild(histCard);
  }
}

// ── Network Tab ───────────────────────────────────────────────────────────────

async function renderNetworkTab(container, chatId) {
  container.innerHTML = '';

  let networks = [];
  try {
    const data = await apiFetch(`/api/networks`);
    networks = data.networks || [];
  } catch (e) { networks = []; }

  const header = document.createElement('div');
  header.style.cssText = 'margin-bottom:var(--sp-4);';
  header.innerHTML = `<h3 style="margin:0;font-size:16px;font-weight:700;">🌐 Your Networks</h3>`;
  container.appendChild(header);

  if (!networks.length) {
    container.appendChild(EmptyState({
      icon: '🌐',
      title: 'No networks yet',
      description: 'Join or create a network to share leaderboards.',
    }));
  } else {
    networks.forEach(net => {
      const card = document.createElement('div');
      card.style.cssText = `
        padding:var(--sp-4);background:var(--card);border:1px solid var(--border);
        border-radius:var(--r-xl);margin-bottom:var(--sp-3);
      `;
      card.innerHTML = `
        <div style="font-weight:700;font-size:var(--text-sm);">${net.name}</div>
        <div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:4px;">
          Groups: ${net.member_count || '?'} | Code: <code>${net.invite_code}</code>
        </div>
        <div style="display:flex;gap:var(--sp-2);margin-top:var(--sp-3);">
          <button class="btn btn-secondary view-net" data-id="${net.id}" style="font-size:var(--text-xs);">View</button>
          <button class="btn btn-secondary cast-net" data-id="${net.id}" data-name="${net.name}" style="font-size:var(--text-xs);">Broadcast</button>
          <button class="btn btn-danger leave-net" data-id="${net.id}" style="font-size:var(--text-xs);background:none;color:var(--danger);border:1px solid var(--danger);">Leave</button>
        </div>
      `;
      card.querySelector('.view-net').onclick = () => showNetworkDetail(container, net.id, net.name, chatId);
      card.querySelector('.cast-net').onclick = () => showBroadcastModal(net.id, net.name, chatId, net.member_count || 0);
      card.querySelector('.leave-net').onclick = async () => {
        if (!confirm(`Leave network "${net.name}"?`)) return;
        try {
          await apiFetch(`/api/networks/${net.id}/members/${chatId}`, { method: 'DELETE' });
          showToast('Left network', 'success');
          await renderNetworkTab(container, chatId);
        } catch (e) { showToast(e.message || 'Failed', 'error'); }
      };
      container.appendChild(card);
    });
  }

  const joinCard = Card({
    title: '➕ Join a Network',
    children: `
      <div style="display:flex;gap:var(--sp-2);">
        <input id="join-code" type="text" class="input" placeholder="Invite code (e.g. GAME2024)" style="flex:1;text-transform:uppercase;">
        <button id="join-btn" class="btn btn-primary">Join</button>
      </div>
    `,
  });
  container.appendChild(joinCard);

  joinCard.querySelector('#join-btn').onclick = async () => {
    const code = joinCard.querySelector('#join-code').value.trim().toUpperCase();
    if (!code) { showToast('Enter invite code', 'error'); return; }
    try {
      const result = await apiFetch('/api/networks/join', {
        method: 'POST',
        body: JSON.stringify({ invite_code: code, chat_id: chatId }),
      });
      if (result.ok) {
        showToast('Joined network!', 'success');
        await renderNetworkTab(container, chatId);
      } else {
        showToast(result.message || 'Failed', 'error');
      }
    } catch (e) { showToast(e.message || 'Failed', 'error'); }
  };

  const createCard = Card({
    title: '🆕 Create New Network',
    children: `
      <div style="display:flex;flex-direction:column;gap:var(--sp-3);">
        <input id="net-name" type="text" class="input" placeholder="Network name">
        <input id="net-desc" type="text" class="input" placeholder="Description (optional)">
        <button id="create-net-btn" class="btn btn-primary">Create Network</button>
      </div>
    `,
  });
  container.appendChild(createCard);

  createCard.querySelector('#create-net-btn').onclick = async () => {
    const name = createCard.querySelector('#net-name').value.trim();
    const description = createCard.querySelector('#net-desc').value.trim();
    if (!name) { showToast('Enter network name', 'error'); return; }
    try {
      const result = await apiFetch('/api/networks', {
        method: 'POST',
        body: JSON.stringify({ name, description }),
      });
      if (result.ok) {
        showToast(`Network created! Code: ${result.invite_code}`, 'success');
        await renderNetworkTab(container, chatId);
      } else {
        showToast(result.reason || 'Failed', 'error');
      }
    } catch (e) { showToast(e.message || 'Failed', 'error'); }
  };
}

async function showNetworkDetail(container, networkId, networkName, chatId) {
  container.innerHTML = `
    <button id="back-to-networks" class="btn btn-secondary" style="margin-bottom:var(--sp-3);font-size:var(--text-xs);">← Back</button>
    <h3 style="margin:0 0 var(--sp-3);font-size:16px;font-weight:700;">🌐 ${networkName}</h3>
    <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);">Loading...</div>
  `;
  container.querySelector('#back-to-networks').onclick = () => renderNetworkTab(container, chatId);

  try {
    const data = await apiFetch(`/api/networks/${networkId}`);
    const lb = data.leaderboard || [];

    const lbDiv = document.createElement('div');
    lbDiv.innerHTML = '<h4 style="margin:0 0 var(--sp-2);">🏆 Network Leaderboard</h4>';
    if (!lb.length) {
      lbDiv.appendChild(EmptyState({ icon: '⭐', title: 'No XP data yet', description: '' }));
    } else {
      lb.forEach((entry, i) => {
        const row = document.createElement('div');
        row.style.cssText = `
          display:flex;align-items:center;gap:var(--sp-3);
          padding:var(--sp-2);border-bottom:1px solid var(--border);font-size:var(--text-sm);
        `;
        row.innerHTML = `
          <div style="width:24px;text-align:center;">${i + 1}.</div>
          <div style="flex:1;">User ${entry.user_id}</div>
          <div style="color:var(--text-muted);">${entry.total_xp.toLocaleString()} XP (${entry.contributing_groups} groups)</div>
        `;
        lbDiv.appendChild(row);
      });
    }
    container.querySelector('div:last-child').replaceWith(lbDiv);
  } catch (e) {
    showToast(e.message || 'Failed to load', 'error');
  }
}

function showBroadcastModal(networkId, networkName, chatId, groupCount) {
  const modal = document.createElement('div');
  modal.style.cssText = `
    position:fixed;top:0;left:0;right:0;bottom:0;
    background:rgba(0,0,0,0.7);z-index:9999;
    display:flex;align-items:center;justify-content:center;padding:var(--sp-4);
  `;
  modal.innerHTML = `
    <div style="background:var(--bg-base);border-radius:var(--r-2xl);padding:var(--sp-5);max-width:420px;width:100%;">
      <h3 style="margin:0 0 var(--sp-2);">📢 Broadcast to ${networkName}</h3>
      <p style="font-size:var(--text-sm);color:var(--text-muted);margin:0 0 var(--sp-3);">
        This will be sent to all ${groupCount} groups. Max 1 broadcast per hour.
      </p>
      <textarea id="cast-msg" class="input" rows="5" placeholder="Your message..."
        style="resize:vertical;margin-bottom:var(--sp-3);"></textarea>
      <div style="display:flex;gap:var(--sp-2);">
        <button id="cast-cancel" class="btn btn-secondary" style="flex:1;">Cancel</button>
        <button id="cast-send" class="btn btn-primary" style="flex:1;">Send to ${groupCount} Groups</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  modal.querySelector('#cast-cancel').onclick = () => modal.remove();
  modal.querySelector('#cast-send').onclick = async () => {
    const message = modal.querySelector('#cast-msg').value.trim();
    if (!message) { showToast('Enter a message', 'error'); return; }
    try {
      const result = await apiFetch(`/api/networks/${networkId}/broadcast`, {
        method: 'POST',
        body: JSON.stringify({ message, from_chat_id: chatId }),
      });
      showToast(`Broadcast sent to ${result.delivered} groups!`, 'success');
      modal.remove();
    } catch (e) {
      showToast(e.message || 'Failed', 'error');
    }
  };
}
