/**
 * miniapp/src/pages/antiraid.js
 *
 * Anti-raid management page — 5-tab dashboard.
 * Tabs: Status | Settings | Incidents | Raiders | Global List
 */

import { Card, Toggle, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { t } from '../../lib/i18n.js?v=1.6.0';

const store = useStore;
const getState = store.getState;

export async function renderAntiraidPage(container) {
  const chatId = getState().activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '🛡️',
      title: t('select_group', 'Select a group'),
      description: t('antiraid_select_group_desc', 'Choose a group to manage anti-raid settings.')
    }));
    return;
  }

  const header = document.createElement('div');
  header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-4);';
  header.innerHTML = `
    <div>
      <h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">🛡️ ${t('nav_antiraid', 'Anti-Raid')}</h2>
      <p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">${t('antiraid_subtitle', 'Protect your group from coordinated raids')}</p>
    </div>
  `;
  container.appendChild(header);

  const tabs = [
    { id: 'status', label: t('tab_status', 'Status') },
    { id: 'settings', label: t('tab_settings', 'Settings') },
    { id: 'incidents', label: t('tab_incidents', 'Incidents') },
    { id: 'raiders', label: t('tab_raiders', 'Raiders') },
    { id: 'global list', label: t('tab_global_list', 'Global List') }
  ];
  const tabBar = document.createElement('div');
  tabBar.style.cssText = 'display:flex;gap:var(--sp-1);margin-bottom:var(--sp-4);background:var(--bg-input);padding:4px;border-radius:var(--r-xl);overflow-x:auto;';
  tabs.forEach((tab, i) => {
    const btn = document.createElement('button');
    btn.textContent = tab.label;
    btn.dataset.tab = tab.id;
    btn.style.cssText = `flex:1;padding:var(--sp-2) var(--sp-3);border:none;border-radius:var(--r-lg);font-size:var(--text-sm);font-weight:var(--fw-medium);cursor:pointer;white-space:nowrap;transition:all var(--dur-fast);background:${i===0?'var(--bg-card)':'transparent'};color:${i===0?'var(--text-primary)':'var(--text-muted)'};`;
    btn.onclick = () => switchTab(tab.id, content, chatId, tabBar);
    tabBar.appendChild(btn);
  });
  container.appendChild(tabBar);

  const content = document.createElement('div');
  container.appendChild(content);

  await switchTab('status', content, chatId, tabBar);
}

function switchTab(tab, container, chatId, tabBar) {
  tabBar.querySelectorAll('[data-tab]').forEach(btn => {
    const active = btn.dataset.tab === tab;
    btn.style.background = active ? 'var(--bg-card)' : 'transparent';
    btn.style.color = active ? 'var(--text-primary)' : 'var(--text-muted)';
  });
  container.innerHTML = '';
  switch (tab) {
    case 'status':      return _renderStatusTab(container, chatId);
    case 'settings':    return _renderSettingsTab(container, chatId);
    case 'incidents':   return _renderIncidentsTab(container, chatId);
    case 'raiders':     return _renderRaidersTab(container, chatId);
    case 'global list': return _renderGlobalListTab(container, chatId);
  }
}

async function _renderStatusTab(container, chatId) {
  container.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">${t('loading_status', 'Loading status...')}</div>`;

  let data = {};
  try {
    data = await apiFetch(`/api/groups/${chatId}/antiraid`);
  } catch (_) {}

  container.innerHTML = '';

  const threatLevel = typeof data.threat_level === 'number' ? data.threat_level : 0;
  const threatLabels = [t('threat_safe', 'Safe'), t('threat_low', 'Low'), t('threat_medium', 'Medium'), t('threat_high', 'High'), t('threat_critical', 'Critical')];
  const threatColors = ['var(--success)', '#10b981', 'var(--warning)', '#f97316', 'var(--danger)'];
  const levelIdx = Math.min(Math.max(Math.floor(threatLevel / 20), 0), 4);

  const threatCard = document.createElement('div');
  threatCard.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);margin-bottom:var(--sp-4);';
  threatCard.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-3);">
      <span style="font-size:var(--text-sm);font-weight:var(--fw-semibold);">${t('antiraid_threat', 'Threat Level')}</span>
      <span style="font-size:var(--text-xs);font-weight:var(--fw-bold);padding:4px 12px;border-radius:var(--r-full);background:${threatColors[levelIdx]};color:white;">${threatLabels[levelIdx]}</span>
    </div>
    <div style="height:12px;background:var(--bg-input);border-radius:var(--r-full);overflow:hidden;margin-bottom:var(--sp-2);">
      <div style="width:${threatLevel}%;height:100%;background:${threatColors[levelIdx]};border-radius:var(--r-full);transition:width .5s;"></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-3);margin-top:var(--sp-3);">
      <div style="background:var(--bg-input);padding:var(--sp-3);border-radius:var(--r-lg);">
        <div style="font-size:var(--text-xs);color:var(--text-muted);">${t('antiraid_joins_min', 'Joins/min')}</div>
        <div style="font-size:18px;font-weight:700;">${data.joins_per_min || 0}</div>
      </div>
      <div style="background:var(--bg-input);padding:var(--sp-3);border-radius:var(--r-lg);">
        <div style="font-size:var(--text-xs);color:var(--text-muted);">${t('antiraid_status', 'Status')}</div>
        <div style="font-size:var(--text-sm);font-weight:700;">${data.lockdown_active ? '🔒 ' + t('lockdown', 'Lockdown') : '✅ ' + t('normal', 'Normal')}</div>
      </div>
    </div>
  `;
  container.appendChild(threatCard);

  if (data.lockdown_active) {
    const lockdownCard = document.createElement('div');
    lockdownCard.style.cssText = 'background:rgba(239,68,68,0.1);border:1px solid var(--danger);border-radius:var(--r-xl);padding:var(--sp-4);margin-bottom:var(--sp-4);';
    lockdownCard.innerHTML = `
      <div style="font-weight:var(--fw-semibold);color:var(--danger);margin-bottom:var(--sp-2);">🚨 ${t('lockdown_active', 'Lockdown Active')}</div>
      <div style="font-size:var(--text-xs);color:var(--text-muted);margin-bottom:var(--sp-3);">${t('raiders_detected_count', '{count} raiders detected').replace('{count}', data.raiders_count || 0)}</div>
      <button id="end-lockdown-btn" class="btn btn-secondary" style="margin-right:var(--sp-2);font-size:var(--text-xs);">${t('end_lockdown', 'End Lockdown')}</button>
    `;
    lockdownCard.querySelector('#end-lockdown-btn').addEventListener('click', async () => {
      try {
        await apiFetch(`/api/groups/${chatId}/antiraid/lockdown`, { method: 'DELETE' });
        showToast(t('lockdown_ended', 'Lockdown ended'), 'success');
        _renderStatusTab(container, chatId);
      } catch (e) { showToast(t('failed_prefix', 'Failed') + ': ' + e.message, 'error'); }
    });
    container.appendChild(lockdownCard);
  }

  const recentCard = Card({ title: '📋 ' + t('recent_activity', 'Recent Activity'), subtitle: t('last_raid_events', 'Last raid events') });
  const events = data.recent_events || [];
  if (events.length === 0) {
    recentCard.appendChild(EmptyState({ icon: '✅', title: t('no_recent_raid_events', 'No recent raid events'), description: t('group_is_safe', 'Your group is safe.') }));
  } else {
    events.forEach(ev => {
      const row = document.createElement('div');
      row.style.cssText = 'padding:var(--sp-2) 0;border-bottom:1px solid var(--border);font-size:var(--text-xs);display:flex;justify-content:space-between;';
      row.innerHTML = `<span>${ev.message || ev.type}</span><span style="color:var(--text-muted);">${_timeAgo(ev.timestamp)}</span>`;
      recentCard.appendChild(row);
    });
  }
  container.appendChild(recentCard);
}

async function _renderSettingsTab(container, chatId) {
  container.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">${t('loading_settings', 'Loading settings...')}</div>`;

  let settings = {};
  try {
    const data = await apiFetch(`/api/groups/${chatId}/antiraid`);
    settings = data.settings || data || {};
  } catch (_) {}

  container.innerHTML = '';

  const settingsCard = Card({ title: '⚙️ ' + t('settings_antiraid_title', 'Anti-Raid Settings'), subtitle: t('settings_antiraid_subtitle', 'Configure raid detection thresholds') });

  const rows = [
    { key: 'antiraid_enabled', label: t('antiraid_enabled_lbl', 'Enable Anti-Raid'), type: 'toggle' },
    { key: 'auto_antiraid_enabled', label: t('auto_antiraid_enabled_lbl', 'Auto-activate on raid detection'), type: 'toggle' },
    { key: 'antiraid_threshold', label: t('antiraid_threshold_lbl', 'Join threshold (per minute)'), type: 'number', min: 3, max: 100 },
    { key: 'ban_suspicious', label: t('ban_suspicious_lbl', 'Ban suspicious accounts'), type: 'toggle' },
    { key: 'block_no_photo', label: t('block_no_photo_lbl', 'Block accounts without profile photo'), type: 'toggle' },
    { key: 'block_no_username', label: t('block_no_username_lbl', 'Block accounts without username'), type: 'toggle' },
    { key: 'min_account_age_days', label: t('min_account_age_days_lbl', 'Min account age (days)'), type: 'number', min: 0, max: 365 },
  ];

  const form = document.createElement('div');
  form.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-3);';

  rows.forEach(row => {
    const rowEl = document.createElement('div');
    rowEl.style.cssText = 'display:flex;align-items:center;justify-content:space-between;';
    const label = document.createElement('span');
    label.textContent = row.label;
    label.style.cssText = 'font-size:var(--text-sm);';
    rowEl.appendChild(label);

    if (row.type === 'toggle') {
      const tog = Toggle({
        checked: !!settings[row.key],
        onChange: async (v) => {
          try {
            await apiFetch(`/api/groups/${chatId}/antiraid/settings`, { method: 'PUT', body: JSON.stringify({ ...settings, [row.key]: v }) });
            settings[row.key] = v;
            showToast(t('saved', 'Saved'), 'success');
            } catch (e) { showToast(t('failed_prefix', 'Failed'), 'error'); }
            }
            });
            rowEl.appendChild(tog);
            } else {
            const input = document.createElement('input');
            input.type = 'number';
            input.value = settings[row.key] || 0;
            input.min = row.min;
            input.max = row.max;
            input.style.cssText = 'width:5rem;background:var(--bg-input);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-2) var(--sp-3);font-size:var(--text-sm);color:var(--text-primary);text-align:right;';
            input.addEventListener('change', async () => {
            try {
            await apiFetch(`/api/groups/${chatId}/antiraid/settings`, { method: 'PUT', body: JSON.stringify({ ...settings, [row.key]: parseInt(input.value) }) });
            settings[row.key] = parseInt(input.value);
            showToast(t('saved', 'Saved'), 'success');
            } catch (e) { showToast(t('failed_prefix', 'Failed'), 'error'); }
            });
            rowEl.appendChild(input);
            }
            form.appendChild(rowEl);
            });

            settingsCard.appendChild(form);
            container.appendChild(settingsCard);
            }

            async function _renderIncidentsTab(container, chatId) {
            container.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">${t('loading_incidents', 'Loading incidents...')}</div>`;

            let incidents = [];
            try {
            const data = await apiFetch(`/api/groups/${chatId}/antiraid/incidents`);
            incidents = Array.isArray(data) ? data : (data.incidents || []);
            } catch (_) {}

            container.innerHTML = '';

            const header = document.createElement('div');
            header.style.cssText = 'margin-bottom:var(--sp-4);';
            header.innerHTML = `<h3 style="font-size:var(--text-sm);font-weight:var(--fw-semibold);margin:0;">📋 ${t('incident_history', 'Incident History')}</h3>`;
            container.appendChild(header);

            if (incidents.length === 0) {
            container.appendChild(EmptyState({ icon: '✅', title: t('no_incidents_recorded', 'No incidents recorded'), description: t('group_no_raids_desc', 'Your group has not experienced any raids.') }));
            return;
            }

            const list = document.createElement('div');
            list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-3);';

            incidents.forEach(inc => {
            const card = document.createElement('div');
            card.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-3);';
            const severityColor = inc.severity === 'critical' ? 'var(--danger)' : inc.severity === 'high' ? '#f97316' : 'var(--warning)';
            card.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-2);">
            <span style="font-size:var(--text-xs);font-weight:var(--fw-bold);padding:2px 8px;border-radius:var(--r-full);background:${severityColor};color:white;">${(t('severity_' + (inc.severity || 'medium'), (inc.severity || 'medium'))).toUpperCase()}</span>
            <span style="font-size:var(--text-xs);color:var(--text-muted);">${_timeAgo(inc.created_at)}</span>
            </div>
            <div style="font-size:var(--text-sm);">${t('raiders_detected_count', '{count} raiders detected').replace('{count}', inc.raiders_count || 0)}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">${t('action_taken', 'Action')}: ${t('action_' + (inc.action_taken || 'restrict'), inc.action_taken || 'restrict')}</div>
            `;
            list.appendChild(card);
            });

            container.appendChild(list);
            }

            async function _renderRaidersTab(container, chatId) {
            container.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">${t('loading_raiders', 'Loading raiders...')}</div>`;

            let raiders = [];
            try {
            const data = await apiFetch(`/api/groups/${chatId}/antiraid/raiders`);
            raiders = Array.isArray(data) ? data : (data.raiders || []);
            } catch (_) {}

            container.innerHTML = '';

            const header = document.createElement('div');
            header.style.cssText = 'margin-bottom:var(--sp-4);';
            header.innerHTML = `<h3 style="font-size:var(--text-sm);font-weight:var(--fw-semibold);margin:0;">🎯 ${t('tab_raiders', 'Raiders')} (${raiders.length})</h3>`;
            container.appendChild(header);

            if (raiders.length === 0) {
            container.appendChild(EmptyState({ icon: '✅', title: t('no_raiders_found', 'No raiders found'), description: t('no_suspicious_accounts_flagged', 'No suspicious accounts have been flagged.') }));
            return;
            }

            const list = document.createElement('div');
            list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';

            raiders.forEach(raider => {
            const card = document.createElement('div');
            card.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-3);display:flex;justify-content:space-between;align-items:center;';
            card.innerHTML = `
            <div>
            <div style="font-size:var(--text-sm);font-weight:var(--fw-medium);">${raider.first_name || t('user', 'User')} ${raider.username ? '(@' + raider.username + ')' : ''}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">ID: ${raider.user_id || raider.id} · ${t('score', 'Score')}: ${raider.suspicion_score || 0}</div>
            </div>
            <div style="display:flex;gap:var(--sp-2);">
            <button class="btn btn-danger" data-action="ban" data-uid="${raider.user_id || raider.id}" style="font-size:var(--text-xs);padding:var(--sp-1) var(--sp-2);">🔨 ${t('action_ban', 'Ban')}</button>
            </div>
            `;
            card.querySelector('[data-action="ban"]').addEventListener('click', async (e) => {
            const uid = parseInt(e.target.dataset.uid);
            try {
            await apiFetch(`/api/groups/${chatId}/bans`, { method: 'POST', body: JSON.stringify({ user_id: uid, reason: 'Anti-raid', duration: null }) });
            showToast(t('user_banned_toast', 'User banned'), 'success');
            card.remove();
            } catch (err) { showToast(t('failed_prefix', 'Failed') + ': ' + err.message, 'error'); }
            });
            list.appendChild(card);
            });

            container.appendChild(list);
            }

            async function _renderGlobalListTab(container, chatId) {
            container.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">${t('loading_global_ban_list', 'Loading global ban list...')}</div>`;

            let banList = [];
            let canManage = false;
            try {
            const res = await apiFetch('/api/antiraid/banlist');
            banList = res?.ban_list || [];
            canManage = res?.can_manage === true;
            } catch (_) {}

            container.innerHTML = '';

            // Info banner with clear explanation of permissions
            const infoBanner = document.createElement('div');
            infoBanner.style.cssText = 'background:rgba(var(--accent-rgb),0.08);border:1px solid rgba(var(--accent-rgb),0.2);border-radius:var(--r-lg);padding:var(--sp-3);margin-bottom:var(--sp-3);font-size:var(--text-xs);color:var(--text-secondary);';
            if (canManage) {
            infoBanner.innerHTML = `
            <strong>🔒 ${t('bot_owner_access', 'Bot Owner Access')}</strong><br>
            ${t('bot_owner_access_desc', 'You are the bot owner. You can add/remove users from the global ban list. Users on this list are automatically banned from ALL groups using this bot.')}
            `;
            } else {
            infoBanner.innerHTML = `
            <strong>🔒 ${t('bot_owner_only', 'Bot Owner Only')}</strong><br>
            ${t('bot_owner_only_desc', 'The global ban list is managed by the bot owner only. Contact the bot owner to request additions or removals. Regular group admins cannot modify this list.')}
            `;
            }
            container.appendChild(infoBanner);

            // Only show add form if user has manage permission
            if (canManage) {
            const addCard = Card({ title: '➕ ' + t('add_to_global_list', 'Add to Global List'), subtitle: t('add_to_global_list_desc', 'Flag a user across all groups (Owner only)') });
            addCard.style.cssText += 'margin-bottom:var(--sp-3);';
            const addForm = document.createElement('div');
            addForm.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';
            addForm.innerHTML = `
            <input type="number" id="gbl-user-id" class="input" placeholder="${t('user_id_placeholder', 'User ID (e.g. 123456789)')}">
            <input type="text" id="gbl-reason" class="input" placeholder="${t('reason_placeholder', 'Reason (optional)')}">
            <button id="gbl-add-btn" class="btn btn-danger" style="width:100%;justify-content:center;">🚫 ${t('add_to_global_ban_list_btn', 'Add to Global Ban List')}</button>
            `;
            addCard.appendChild(addForm);
            container.appendChild(addCard);
            }

            const listCard = Card({ title: `🌍 ${t('tab_global_list', 'Global Ban List')} (${banList.length})`, subtitle: t('global_ban_list_subtitle', 'Users banned across all groups') });
            const listEl = document.createElement('div');
            listEl.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';

            const renderList = (items) => {
            listEl.innerHTML = '';
            if (items.length === 0) {
            listEl.innerHTML = `<div style="color:var(--text-muted);font-size:var(--text-sm);text-align:center;padding:var(--sp-3);">${t('no_users_on_global_ban_list', 'No users on the global ban list')}</div>`;
            return;
            }
            items.forEach(entry => {
            const row = document.createElement('div');
            row.style.cssText = 'display:flex;align-items:center;gap:var(--sp-2);padding:var(--sp-2) var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);';
            // Only show remove button if user has manage permission
            const removeBtn = canManage
            ? `<button data-uid="${entry.user_id}" style="background:none;border:none;cursor:pointer;color:var(--danger);font-size:18px;line-height:1;padding:0 var(--sp-1);">×</button>`
            : '';
            row.innerHTML = `
            <span style="font-size:var(--text-xs);font-weight:var(--fw-bold);padding:2px 8px;background:var(--danger);color:white;border-radius:var(--r-full);flex-shrink:0;">${entry.user_id}</span>
            <span style="flex:1;font-size:var(--text-sm);color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${entry.reason || t('no_reason', 'No reason')}</span>
            <span style="font-size:var(--text-xs);color:var(--text-muted);flex-shrink:0;">${entry.flagged_at ? new Date(entry.flagged_at).toLocaleDateString() : ''}</span>
            ${removeBtn}
            `;
            if (canManage) {
            const removeButton = row.querySelector('[data-uid]');
            if (removeButton) {
            removeButton.onclick = async () => {
            try {
              await apiFetch(`/api/antiraid/banlist/${entry.user_id}`, { method: 'DELETE' });
              banList = banList.filter(x => x.user_id !== entry.user_id);
              renderList(banList);
              showToast(t('user_removed_from_global_list_toast', 'User removed from global list'), 'success');
            } catch (e) { showToast(t('failed_prefix', 'Failed') + ': ' + e.message, 'error'); }
            };
            }
            }
            listEl.appendChild(row);
            });
            };

            renderList(banList);
            listCard.appendChild(listEl);
            container.appendChild(listCard);

            // Only attach add listener if user has manage permission
            if (canManage) {
            setTimeout(() => {
            container.querySelector('#gbl-add-btn')?.addEventListener('click', async () => {
            const uid = parseInt(container.querySelector('#gbl-user-id').value.trim());
            const reason = container.querySelector('#gbl-reason').value.trim();
            if (!uid) { showToast(t('enter_valid_user_id', 'Enter a valid user ID'), 'error'); return; }
            try {
            await apiFetch('/api/antiraid/banlist', { method: 'POST', body: JSON.stringify({ user_id: uid, chat_id: chatId, reason }) });
            banList.push({ user_id: uid, reason, flagged_at: new Date().toISOString(), is_active: true });
            renderList(banList);
            container.querySelector('#gbl-user-id').value = '';
            container.querySelector('#gbl-reason').value = '';
            showToast(t('user_added_to_global_ban_list_toast', 'User added to global ban list'), 'success');
            } catch (e) { showToast(t('failed_prefix', 'Failed') + ': ' + e.message, 'error'); }
            });
            }, 0);
            }
            }

            function _timeAgo(ts) {
            if (!ts) return '';
            const diff = Date.now() - new Date(ts).getTime();
            const mins = Math.floor(diff / 60000);
            if (mins < 1) return t('just_now', 'Just now');
            if (mins < 60) return `${mins}${t('m_ago', 'm ago')}`;
            if (mins < 1440) return `${Math.floor(mins / 60)}${t('h_ago', 'h ago')}`;
            return new Date(ts).toLocaleDateString();
            }
