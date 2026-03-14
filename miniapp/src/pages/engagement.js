/**
 * miniapp/src/pages/engagement.js
 *
 * Engagement management page: XP/Levels, Reputation, Badges, Newsletter, Network.
 */

import { apiFetch } from '../../lib/api.js?v=1.5.0';
import { useStore } from '../../store/index.js?v=1.5.0';
import { showToast, Toggle, Card } from '../../lib/components.js?v=1.5.0';

const getState = useStore.getState;

function progressBar(pct, width = 12) {
  const filled = Math.round(width * pct / 100);
  return '█'.repeat(filled) + '░'.repeat(width - filled);
}

function xpBar(xp, maxXp) {
  const pct = maxXp > 0 ? Math.min(100, Math.round(xp / maxXp * 100)) : 0;
  const barWidth = Math.round(pct / 100 * 180);
  return `<div style="background:var(--bg-input);border-radius:4px;height:6px;width:180px;overflow:hidden;">
    <div style="background:var(--accent);height:100%;width:${barWidth}px;border-radius:4px;transition:width 0.3s;"></div>
  </div>`;
}

export async function renderEngagementPage(container) {
  const state = getState();
  const chatId = state.selectedGroup;
  const botId = state.selectedBot;

  if (!chatId || !botId) {
    container.innerHTML = `<div class="empty-state"><div style="font-size:32px">⭐</div><p>Select a group to view engagement settings.</p></div>`;
    return;
  }

  container.innerHTML = `
    <div style="padding:var(--sp-4)">
      <h2 style="margin:0 0 var(--sp-4);font-size:var(--text-lg);font-weight:var(--fw-bold);">
        ⭐ Engagement
      </h2>

      <!-- Tab bar -->
      <div id="engagement-tabs" style="display:flex;gap:var(--sp-2);margin-bottom:var(--sp-4);overflow-x:auto;padding-bottom:var(--sp-1);">
        ${['xp', 'rep', 'badges', 'newsletter', 'network'].map((t, i) => `
          <button class="eng-tab btn ${i === 0 ? 'btn-primary' : 'btn-secondary'}" data-tab="${t}"
            style="white-space:nowrap;font-size:var(--text-xs);">
            ${{xp:'⭐ XP & Levels', rep:'👍 Reputation', badges:'🏅 Badges', newsletter:'📰 Newsletter', network:'🌐 Network'}[t]}
          </button>
        `).join('')}
      </div>

      <div id="engagement-content"></div>
    </div>
  `;

  const tabs = container.querySelectorAll('.eng-tab');
  const content = container.querySelector('#engagement-content');

  async function switchTab(tab) {
    tabs.forEach(t => {
      t.classList.toggle('btn-primary', t.dataset.tab === tab);
      t.classList.toggle('btn-secondary', t.dataset.tab !== tab);
    });
    content.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">Loading...</div>';
    try {
      switch (tab) {
        case 'xp': await renderXpTab(content, chatId, botId); break;
        case 'rep': await renderRepTab(content, chatId, botId); break;
        case 'badges': await renderBadgesTab(content, chatId, botId); break;
        case 'newsletter': await renderNewsletterTab(content, chatId, botId); break;
        case 'network': await renderNetworkTab(content, chatId, botId); break;
      }
    } catch (e) {
      content.innerHTML = `<div class="empty-state">Failed to load: ${e.message}</div>`;
    }
  }

  tabs.forEach(t => t.addEventListener('click', () => switchTab(t.dataset.tab)));
  await switchTab('xp');
}

// ── XP & Levels Tab ──────────────────────────────────────────────────────────

async function renderXpTab(container, chatId, botId) {
  const [lbData, settingsData] = await Promise.all([
    apiFetch(`/api/groups/${chatId}/xp/leaderboard?bot_id=${botId}&limit=10`).catch(() => ({ leaderboard: [] })),
    apiFetch(`/api/groups/${chatId}/xp/settings?bot_id=${botId}`).catch(() => ({})),
  ]);

  const lb = lbData.leaderboard || [];
  const s = settingsData || {};
  const doubleActive = s.double_xp_active;

  container.innerHTML = `
    ${doubleActive ? `
      <div id="double-xp-banner" style="background:linear-gradient(135deg,#f59e0b,#d97706);color:#000;border-radius:var(--r-lg);padding:var(--sp-3) var(--sp-4);margin-bottom:var(--sp-4);font-weight:var(--fw-bold);font-size:var(--text-sm);">
        ⚡ DOUBLE XP ACTIVE — all earnings multiplied by 2x
      </div>
    ` : ''}

    <div class="section" style="margin-bottom:var(--sp-4);">
      <div class="section-header" style="cursor:default;">
        <span class="section-title">🏆 XP Leaderboard</span>
      </div>
      <div style="padding:var(--sp-3)">
        ${lb.length === 0 ? '<p style="color:var(--text-muted);font-size:var(--text-sm);">No XP data yet.</p>' :
          lb.map(e => `
            <div style="display:flex;align-items:center;gap:var(--sp-3);padding:var(--sp-2) 0;border-bottom:1px solid var(--border);">
              <span style="font-weight:var(--fw-bold);color:var(--accent);min-width:24px;">${e.rank}.</span>
              <div style="flex:1;">
                <div style="font-size:var(--text-sm);font-weight:var(--fw-medium);">User ${e.user_id}</div>
                <div style="font-size:var(--text-xs);color:var(--text-muted);">Lv.${e.level} — ${e.xp?.toLocaleString()} XP</div>
              </div>
            </div>
          `).join('')}
      </div>
    </div>

    <div class="section" style="margin-bottom:var(--sp-4);">
      <div class="section-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
        <span class="section-title">⚙️ XP Settings</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-content" style="display:none;padding:var(--sp-3);">
        <div class="toggle-row">
          <span style="font-size:var(--text-sm);">Enable XP system</span>
          <div class="toggle-btn ${s.enabled ? 'bg-accent' : 'bg-muted'}" style="background:${s.enabled ? 'var(--accent)' : 'var(--text-disabled)'};" id="xp-enabled-toggle">
            <div class="toggle-dot" style="transform:translateX(${s.enabled ? '22px' : '4px'})"></div>
          </div>
        </div>
        <div style="display:grid;gap:var(--sp-2);margin-top:var(--sp-2);">
          ${[
            ['xp-per-message', 'XP per message', s.xp_per_message ?? 1],
            ['xp-cooldown', 'Message cooldown (s)', s.message_cooldown_s ?? 60],
            ['xp-per-daily', 'XP per daily check-in', s.xp_per_daily ?? 10],
            ['xp-per-gamewin', 'XP per game win', s.xp_per_game_win ?? 5],
            ['xp-admin-grant', 'Admin grant max', s.xp_admin_grant ?? 20],
          ].map(([id, label, val]) => `
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <label style="font-size:var(--text-sm);color:var(--text-secondary);">${label}</label>
              <input class="number-input" id="${id}" type="number" value="${val}" min="0" max="9999" style="width:80px;">
            </div>
          `).join('')}
        </div>
        <div class="toggle-row" style="margin-top:var(--sp-2);">
          <span style="font-size:var(--text-sm);">Level-up announcement</span>
          <div class="toggle-btn" style="background:${s.level_up_announce ? 'var(--accent)' : 'var(--text-disabled)'};" id="xp-announce-toggle">
            <div class="toggle-dot" style="transform:translateX(${s.level_up_announce ? '22px' : '4px'})"></div>
          </div>
        </div>
        <button class="btn btn-primary" id="save-xp-settings" style="margin-top:var(--sp-3);width:100%;">💾 Save Settings</button>

        <hr style="border:none;border-top:1px solid var(--border);margin:var(--sp-4) 0;">
        <p style="font-size:var(--text-sm);font-weight:var(--fw-semibold);">⚡ Start Double XP Event</p>
        <div style="display:flex;gap:var(--sp-2);align-items:center;margin-top:var(--sp-2);">
          <input class="number-input" id="double-xp-hours" type="number" value="2" min="1" max="72" style="width:80px;">
          <span style="font-size:var(--text-sm);color:var(--text-muted);">hours</span>
          <button class="btn btn-primary" id="start-double-xp">Start</button>
        </div>
      </div>
    </div>
  `;

  container.querySelector('#save-xp-settings')?.addEventListener('click', async () => {
    const body = {
      bot_id: Number(botId),
      xp_per_message: Number(container.querySelector('#xp-per-message').value),
      message_cooldown_s: Number(container.querySelector('#xp-cooldown').value),
      xp_per_daily: Number(container.querySelector('#xp-per-daily').value),
      xp_per_game_win: Number(container.querySelector('#xp-per-gamewin').value),
      xp_admin_grant: Number(container.querySelector('#xp-admin-grant').value),
    };
    try {
      await apiFetch(`/api/groups/${chatId}/xp/settings?bot_id=${botId}`, { method: 'PUT', body: JSON.stringify(body) });
      showToast('✅ XP settings saved!', 'success');
    } catch (e) {
      showToast('❌ Failed to save: ' + e.message, 'error');
    }
  });

  container.querySelector('#start-double-xp')?.addEventListener('click', async () => {
    const hours = Number(container.querySelector('#double-xp-hours').value);
    try {
      await apiFetch(`/api/groups/${chatId}/xp/double`, { method: 'POST', body: JSON.stringify({ hours, bot_id: Number(botId) }) });
      showToast(`⚡ Double XP active for ${hours} hours!`, 'success');
    } catch (e) {
      showToast('❌ Failed: ' + e.message, 'error');
    }
  });
}

// ── Reputation Tab ───────────────────────────────────────────────────────────

async function renderRepTab(container, chatId, botId) {
  const data = await apiFetch(`/api/groups/${chatId}/rep/leaderboard?bot_id=${botId}&limit=10`).catch(() => ({ leaderboard: [] }));
  const lb = data.leaderboard || [];

  container.innerHTML = `
    <div class="section" style="margin-bottom:var(--sp-4);">
      <div class="section-header" style="cursor:default;">
        <span class="section-title">👍 Reputation Board</span>
      </div>
      <div style="padding:var(--sp-3);">
        ${lb.length === 0 ? '<p style="color:var(--text-muted);font-size:var(--text-sm);">No reputation data yet.</p>' :
          lb.map(e => `
            <div style="display:flex;align-items:center;gap:var(--sp-3);padding:var(--sp-2) 0;border-bottom:1px solid var(--border);">
              <span style="font-weight:var(--fw-bold);color:var(--accent);min-width:24px;">${e.rank}.</span>
              <div style="flex:1;">
                <div style="font-size:var(--text-sm);font-weight:var(--fw-medium);">User ${e.user_id}</div>
                <div style="font-size:var(--text-xs);color:var(--text-muted);">${e.rep_score} rep</div>
              </div>
            </div>
          `).join('')}
      </div>
    </div>

    <div class="section">
      <div class="section-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
        <span class="section-title">⚙️ Admin Rep Actions</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-content" style="display:none;padding:var(--sp-3);">
        <div style="display:grid;gap:var(--sp-2);">
          <input class="input" id="rep-user-id" type="number" placeholder="User ID">
          <input class="input" id="rep-amount" type="number" value="1" placeholder="Amount (+1 or -1)">
          <input class="input" id="rep-reason" type="text" placeholder="Reason (optional)">
          <button class="btn btn-primary" id="give-rep-btn" style="width:100%;">👍 Give Rep</button>
        </div>
      </div>
    </div>
  `;

  container.querySelector('#give-rep-btn')?.addEventListener('click', async () => {
    const userId = Number(container.querySelector('#rep-user-id').value);
    const amount = Number(container.querySelector('#rep-amount').value);
    const reason = container.querySelector('#rep-reason').value;
    if (!userId) { showToast('Enter a user ID', 'error'); return; }
    try {
      const state = getState();
      await apiFetch(`/api/groups/${chatId}/rep/give`, {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, amount, reason, bot_id: Number(botId), admin_id: state.userId || 0 }),
      });
      showToast('✅ Rep given!', 'success');
    } catch (e) {
      showToast('❌ ' + e.message, 'error');
    }
  });
}

// ── Badges Tab ───────────────────────────────────────────────────────────────

async function renderBadgesTab(container, chatId, botId) {
  const data = await apiFetch(`/api/groups/${chatId}/badges?bot_id=${botId}`).catch(() => ({ badges: [] }));
  const badges = data.badges || [];

  container.innerHTML = `
    <div class="section">
      <div class="section-header" style="cursor:default;">
        <span class="section-title">🏅 Badges (${badges.length})</span>
      </div>
      <div style="padding:var(--sp-3);display:grid;gap:var(--sp-2);">
        ${badges.length === 0
          ? '<p style="color:var(--text-muted);font-size:var(--text-sm);">No badges found. Default badges are seeded at bot startup.</p>'
          : badges.map(b => `
            <div style="display:flex;align-items:center;gap:var(--sp-3);padding:var(--sp-2);background:var(--bg-input);border-radius:var(--r-lg);">
              <span style="font-size:20px;">${b.emoji}</span>
              <div style="flex:1;">
                <div style="font-size:var(--text-sm);font-weight:var(--fw-medium);">${b.name}</div>
                <div style="font-size:var(--text-xs);color:var(--text-muted);">${b.description || ''}</div>
              </div>
              ${b.is_rare ? '<span style="font-size:var(--text-xs);color:gold;">★ Rare</span>' : ''}
            </div>
          `).join('')}
      </div>
    </div>
  `;
}

// ── Newsletter Tab ───────────────────────────────────────────────────────────

async function renderNewsletterTab(container, chatId, botId) {
  const [settingsData, historyData] = await Promise.all([
    apiFetch(`/api/groups/${chatId}/newsletter/settings?bot_id=${botId}`).catch(() => ({})),
    apiFetch(`/api/groups/${chatId}/newsletter/history?bot_id=${botId}`).catch(() => ({ history: [] })),
  ]);
  const s = settingsData || {};
  const history = historyData.history || [];

  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

  container.innerHTML = `
    <div class="section" style="margin-bottom:var(--sp-4);">
      <div class="section-header" style="cursor:default;">
        <span class="section-title">📰 Newsletter Preview</span>
      </div>
      <div style="padding:var(--sp-3);display:flex;gap:var(--sp-2);">
        <button class="btn btn-secondary" id="preview-btn" style="flex:1;">👁️ Preview This Week</button>
        <button class="btn btn-primary" id="send-now-btn" style="flex:1;">📤 Send Now</button>
      </div>
      <div id="preview-content" style="display:none;padding:var(--sp-3);"></div>
    </div>

    <div class="section" style="margin-bottom:var(--sp-4);">
      <div class="section-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
        <span class="section-title">⚙️ Newsletter Settings</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-content" style="display:none;padding:var(--sp-3);">
        <div class="toggle-row">
          <span style="font-size:var(--text-sm);">Enable weekly newsletter</span>
          <div class="toggle-btn" style="background:${s.enabled ? 'var(--accent)' : 'var(--text-disabled)'};" id="nl-enabled-toggle">
            <div class="toggle-dot" style="transform:translateX(${s.enabled ? '22px' : '4px'})"></div>
          </div>
        </div>
        <div style="display:grid;gap:var(--sp-2);margin-top:var(--sp-3);">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <label style="font-size:var(--text-sm);">Send on</label>
            <select class="input" id="nl-send-day" style="width:140px;">
              ${days.map((d, i) => `<option value="${i}" ${s.send_day === i ? 'selected' : ''}>${d}</option>`).join('')}
            </select>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <label style="font-size:var(--text-sm);">Send at (UTC hour)</label>
            <input class="number-input" id="nl-send-hour" type="number" value="${s.send_hour_utc ?? 9}" min="0" max="23" style="width:80px;">
          </div>
        </div>
        <div style="margin-top:var(--sp-3);">
          <p style="font-size:var(--text-sm);font-weight:var(--fw-semibold);margin-bottom:var(--sp-2);">Include sections:</p>
          ${[
            ['nl-top-members', 'Most active members', s.include_top_members],
            ['nl-leaderboard', 'Leaderboard snapshot', s.include_leaderboard],
            ['nl-new-members', 'New members', s.include_new_members],
            ['nl-milestones', 'Milestones', s.include_milestones],
          ].map(([id, label, checked]) => `
            <div class="toggle-row">
              <span style="font-size:var(--text-sm);color:var(--text-secondary);">${label}</span>
              <div class="toggle-btn" style="background:${checked ? 'var(--accent)' : 'var(--text-disabled)'};" id="${id}">
                <div class="toggle-dot" style="transform:translateX(${checked ? '22px' : '4px'})"></div>
              </div>
            </div>
          `).join('')}
        </div>
        <div style="margin-top:var(--sp-2);">
          <label style="font-size:var(--text-sm);color:var(--text-secondary);">Custom intro (optional)</label>
          <textarea class="input" id="nl-custom-intro" rows="2" style="margin-top:var(--sp-1);">${s.custom_intro || ''}</textarea>
        </div>
        <button class="btn btn-primary" id="save-nl-settings" style="margin-top:var(--sp-3);width:100%;">💾 Save Settings</button>
      </div>
    </div>

    ${history.length > 0 ? `
      <div class="section">
        <div class="section-header" style="cursor:default;">
          <span class="section-title">📜 Newsletter History</span>
        </div>
        <div style="padding:var(--sp-3);">
          ${history.map(h => `
            <div style="display:flex;justify-content:space-between;padding:var(--sp-2) 0;border-bottom:1px solid var(--border);">
              <span style="font-size:var(--text-sm);">${new Date(h.sent_at).toLocaleDateString()}</span>
              <span style="font-size:var(--text-xs);color:var(--text-muted);">ID: ${h.message_id || '—'}</span>
            </div>
          `).join('')}
        </div>
      </div>
    ` : ''}
  `;

  container.querySelector('#preview-btn')?.addEventListener('click', async () => {
    const previewDiv = container.querySelector('#preview-content');
    previewDiv.style.display = 'block';
    previewDiv.innerHTML = '<p style="color:var(--text-muted)">Loading preview...</p>';
    try {
      const data = await apiFetch(`/api/groups/${chatId}/newsletter/preview?bot_id=${botId}`);
      previewDiv.innerHTML = `<pre style="white-space:pre-wrap;font-size:var(--text-xs);color:var(--text-secondary);font-family:monospace;">${data.preview}</pre>`;
    } catch (e) {
      previewDiv.innerHTML = `<p style="color:var(--danger)">Failed: ${e.message}</p>`;
    }
  });

  container.querySelector('#send-now-btn')?.addEventListener('click', async () => {
    if (!confirm('Send newsletter to this group now?')) return;
    try {
      await apiFetch(`/api/groups/${chatId}/newsletter/send-now`, {
        method: 'POST',
        body: JSON.stringify({ bot_id: Number(botId) }),
      });
      showToast('✅ Newsletter sent!', 'success');
    } catch (e) {
      showToast('❌ ' + e.message, 'error');
    }
  });

  container.querySelector('#save-nl-settings')?.addEventListener('click', async () => {
    const body = {
      bot_id: Number(botId),
      send_day: Number(container.querySelector('#nl-send-day').value),
      send_hour_utc: Number(container.querySelector('#nl-send-hour').value),
      custom_intro: container.querySelector('#nl-custom-intro').value || null,
    };
    try {
      await apiFetch(`/api/groups/${chatId}/newsletter/settings?bot_id=${botId}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      showToast('✅ Newsletter settings saved!', 'success');
    } catch (e) {
      showToast('❌ ' + e.message, 'error');
    }
  });
}

// ── Network Tab ──────────────────────────────────────────────────────────────

async function renderNetworkTab(container, chatId, botId) {
  const data = await apiFetch(`/api/networks?chat_id=${chatId}`).catch(() => ({ networks: [] }));
  const networks = data.networks || [];

  container.innerHTML = `
    <div class="section" style="margin-bottom:var(--sp-4);">
      <div class="section-header" style="cursor:default;">
        <span class="section-title">🌐 Your Networks</span>
      </div>
      <div style="padding:var(--sp-3);">
        ${networks.length === 0
          ? '<p style="color:var(--text-muted);font-size:var(--text-sm);">Not in any network yet.</p>'
          : networks.map(n => `
            <div style="background:var(--bg-input);border-radius:var(--r-lg);padding:var(--sp-3);margin-bottom:var(--sp-2);">
              <div style="font-size:var(--text-sm);font-weight:var(--fw-semibold);">${n.name}</div>
              <div style="font-size:var(--text-xs);color:var(--text-muted);">${n.member_count || 0} groups</div>
              <div style="font-size:var(--text-xs);color:var(--text-muted);">Code: <code>${n.invite_code}</code></div>
              <div style="display:flex;gap:var(--sp-2);margin-top:var(--sp-2);">
                <button class="btn btn-secondary broadcast-btn" data-network-id="${n.id}" style="font-size:var(--text-xs);">📢 Broadcast</button>
                <button class="btn btn-secondary leave-btn" data-network-id="${n.id}" style="font-size:var(--text-xs);">Leave</button>
              </div>
            </div>
          `).join('')}
      </div>
    </div>

    <div class="section" style="margin-bottom:var(--sp-4);">
      <div class="section-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
        <span class="section-title">➕ Join a Network</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-content" style="display:none;padding:var(--sp-3);">
        <input class="input" id="join-code" type="text" placeholder="Enter invite code (e.g. GAME2024)" style="margin-bottom:var(--sp-2);text-transform:uppercase;">
        <button class="btn btn-primary" id="join-network-btn" style="width:100%;">Join Network</button>
      </div>
    </div>

    <div class="section">
      <div class="section-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
        <span class="section-title">🆕 Create New Network</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-content" style="display:none;padding:var(--sp-3);">
        <input class="input" id="network-name" type="text" placeholder="Network name" style="margin-bottom:var(--sp-2);">
        <input class="input" id="network-desc" type="text" placeholder="Description (optional)" style="margin-bottom:var(--sp-2);">
        <button class="btn btn-primary" id="create-network-btn" style="width:100%;">Create Network</button>
        <div id="create-result" style="margin-top:var(--sp-2);"></div>
      </div>
    </div>
  `;

  container.querySelector('#join-network-btn')?.addEventListener('click', async () => {
    const code = container.querySelector('#join-code').value.trim().toUpperCase();
    if (!code) { showToast('Enter an invite code', 'error'); return; }
    try {
      const result = await apiFetch('/api/networks/join', {
        method: 'POST',
        body: JSON.stringify({ invite_code: code, chat_id: Number(chatId), bot_id: Number(botId) }),
      });
      showToast(result.message || '✅ Joined!', result.ok ? 'success' : 'error');
      if (result.ok) await renderNetworkTab(container, chatId, botId);
    } catch (e) {
      showToast('❌ ' + e.message, 'error');
    }
  });

  container.querySelector('#create-network-btn')?.addEventListener('click', async () => {
    const name = container.querySelector('#network-name').value.trim();
    const desc = container.querySelector('#network-desc').value.trim();
    if (!name) { showToast('Enter a network name', 'error'); return; }
    const state = getState();
    try {
      const result = await apiFetch('/api/networks', {
        method: 'POST',
        body: JSON.stringify({ name, description: desc || null, owner_user_id: state.userId || 0, owner_bot_id: Number(botId) }),
      });
      if (result.ok) {
        container.querySelector('#create-result').innerHTML =
          `<div style="background:var(--bg-input);border-radius:var(--r-lg);padding:var(--sp-2);font-size:var(--text-sm);">
            ✅ Created! Invite code: <code>${result.invite_code}</code>
          </div>`;
        showToast('✅ Network created!', 'success');
      }
    } catch (e) {
      showToast('❌ ' + e.message, 'error');
    }
  });

  container.querySelectorAll('.leave-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const networkId = Number(btn.dataset.networkId);
      if (!confirm('Leave this network?')) return;
      try {
        await apiFetch(`/api/networks/${networkId}/members/${chatId}`, { method: 'DELETE' });
        showToast('✅ Left network', 'success');
        await renderNetworkTab(container, chatId, botId);
      } catch (e) {
        showToast('❌ ' + e.message, 'error');
      }
    });
  });

  container.querySelectorAll('.broadcast-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const networkId = Number(btn.dataset.networkId);
      const msg = prompt('Enter broadcast message (max 1 per hour):');
      if (!msg) return;
      const state = getState();
      try {
        const result = await apiFetch(`/api/networks/${networkId}/broadcast`, {
          method: 'POST',
          body: JSON.stringify({ message: msg, from_chat_id: Number(chatId), sent_by: state.userId || 0, bot_id: Number(botId) }),
        });
        showToast(`✅ Sent to ${result.delivered} groups!`, 'success');
      } catch (e) {
        showToast('❌ ' + (e.message || 'Rate limited'), 'error');
      }
    });
  });
}
