/**
 * miniapp/src/pages/settings.js
 * Task 9+10 of 12 — Settings page + custom messages helper
 * Extracted from index.html renderSettings(), renderCustomMessagesSection(), _showCopySettingsModal(), _updateGroupSetting()
 * NOTE: _settingsRenderToken moved here from index.html global scope
 */

import { Card, Toggle, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

const store = useStore;
const getState = store.getState;

// Render guard — prevents stale renders when user switches tabs fast
let _settingsRenderToken = 0;

async function _updateGroupSetting(key, val) {
  const state = getState();
  const chatId = state.activeChatId;
  if (!chatId) { showToast('No group selected', 'error'); return; }
  try {
    await apiFetch(`/api/groups/${chatId}/settings/bulk`, {
      method: 'PUT',
      validate: false,
      body: JSON.stringify({ settings: { [key]: val } }),
    });
    state.updateSetting(key, val);
    showToast('Saved', 'success');
  } catch (e) {
    console.error(`[Settings] Failed to save ${key}:`, e);
    showToast('Failed to save: ' + (e.message || 'unknown'), 'error');
  }
}

function _showCopySettingsModal(chatId, otherGroups) {
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;z-index:1000;background:#00000088;backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;padding:var(--sp-4);';
  const box = document.createElement('div');
  box.style.cssText = 'background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--r-2xl);padding:var(--sp-5);width:100%;max-width:420px;box-shadow:var(--shadow-xl);max-height:80vh;overflow-y:auto;';
  const moduleOpts = ['AutoMod','Welcome & Messages','Modules','Roles','Webhooks'];
  box.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--sp-4);">
      <div style="font-weight:var(--fw-semibold);font-size:var(--text-base);">📋 Copy Settings</div>
      <button id="copy-modal-close" style="background:none;border:none;color:var(--text-muted);font-size:20px;cursor:pointer;">✕</button>
    </div>
    <div style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);">What to copy</div>
    <div id="module-opts" style="display:flex;flex-wrap:wrap;gap:var(--sp-2);margin-bottom:var(--sp-4);">
      ${moduleOpts.map(m => `<label style="display:flex;align-items:center;gap:var(--sp-1);font-size:var(--text-sm);cursor:pointer;"><input type="checkbox" data-mod="${m.toLowerCase().replace(/ .*/,'')}" checked> ${m}</label>`).join('')}
    </div>
    <div style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);">Target groups</div>
    <div id="group-checklist" style="display:flex;flex-direction:column;gap:var(--sp-1);margin-bottom:var(--sp-4);">
      ${otherGroups.map(g => `<label style="display:flex;align-items:center;gap:var(--sp-2);font-size:var(--text-sm);cursor:pointer;padding:var(--sp-2);background:var(--bg-input);border-radius:var(--r-lg);"><input type="checkbox" data-gid="${g.chat_id}"> ${g.title || g.chat_id}</label>`).join('')}
    </div>
    <div id="copy-result" style="font-size:var(--text-sm);margin-bottom:var(--sp-3);"></div>
    <button id="copy-confirm-btn" class="btn btn-primary" style="width:100%;">Copy Settings</button>
  `;
  const close = () => overlay.remove();
  box.querySelector('#copy-modal-close').onclick = close;
  overlay.onclick = e => { if (e.target === overlay) close(); };
  box.querySelector('#copy-confirm-btn').onclick = async () => {
    const targetIds = [...box.querySelectorAll('#group-checklist input:checked')].map(el => parseInt(el.dataset.gid));
    const modules = [...box.querySelectorAll('#module-opts input:checked')].map(el => el.dataset.mod);
    if (!targetIds.length) { showToast('Select at least one group', 'error'); return; }
    try {
      const res = await apiFetch(`/api/groups/${chatId}/copy-settings`, {
        method: 'POST',
        body: JSON.stringify({ target_chat_ids: targetIds, modules })
      });
      const ok = (res.results || []).filter(r => r.ok).length;
      const fail = (res.results || []).filter(r => !r.ok).length;
      box.querySelector('#copy-result').textContent = `✓ ${ok} groups updated${fail ? `, ✗ ${fail} failed` : ''}`;
      showToast(`Settings copied to ${ok} group(s)`, 'success');
    } catch (err) { showToast('Failed to copy settings', 'error'); }
  };
  overlay.appendChild(box);
  document.body.appendChild(overlay);
}

export async function renderCustomMessagesSection(container, apiUrl) {
  container.innerHTML = '<div style="text-align:center;color:var(--text-muted)">Loading...</div>';
  try {
    const messages = await apiFetch(apiUrl);
    container.innerHTML = '';
    const list = document.createElement('div');
    list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2)';
    Object.entries(messages).forEach(([key, data]) => {
      const canEdit = data.canEdit !== false;
      const item = document.createElement('div');
      item.dataset.msgKey = key;
      item.style.cssText = `padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);border:1px solid ${data.isCustom ? 'var(--accent)' : 'var(--border)'}`;
      const renderView = () => {
        item.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <span style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-secondary)">${key.toUpperCase()}</span>
            ${data.isCustom ? '<span style="font-size:10px;color:var(--accent)">Customized</span>' : ''}
          </div>
          <div class="msg-body" style="font-size:var(--text-sm);margin-bottom:12px;white-space:pre-wrap;max-height:80px;overflow-y:auto">${data.body}</div>
          <div style="display:flex;gap:8px">
            ${canEdit ? '<button class="btn btn-secondary edit-btn" style="padding:4px 8px;font-size:12px">Edit</button>' : '<span style="font-size:11px;color:var(--text-muted)">Bot owner only</span>'}
            ${data.isCustom && canEdit ? '<button class="btn reset-btn" style="padding:4px 8px;font-size:12px;background:none;color:var(--danger);border:1px solid var(--danger)">Reset</button>' : ''}
          </div>
        `;
        if (canEdit) {
          item.querySelector('.edit-btn')?.addEventListener('click', () => renderEdit());
        }
        if (data.isCustom && canEdit) {
          item.querySelector('.reset-btn')?.addEventListener('click', async () => {
            if (!confirm('Reset to default?')) return;
            try {
              await apiFetch(`${apiUrl}/${key}`, { method: 'DELETE' });
              showToast('Reset', 'success');
              data.isCustom = false;
              data.body = '';
              renderView();
            } catch (e) { showToast('Error', 'error'); }
          });
        }
      };
      const renderEdit = () => {
        item.innerHTML = `
          <div style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-secondary);margin-bottom:8px">${key.toUpperCase()}</div>
          <textarea class="input edit-textarea" style="width:100%;min-height:80px;resize:vertical;font-size:var(--text-sm);margin-bottom:8px;box-sizing:border-box;">${data.body}</textarea>
          <div style="display:flex;gap:8px">
            <button class="btn btn-primary save-edit-btn" style="padding:4px 12px;font-size:12px">Save</button>
            <button class="btn btn-secondary cancel-edit-btn" style="padding:4px 12px;font-size:12px">Cancel</button>
          </div>
        `;
        item.querySelector('.save-edit-btn').addEventListener('click', async () => {
          const newVal = item.querySelector('.edit-textarea').value;
          try {
            await apiFetch(`${apiUrl}/${key}`, { method: 'PUT', body: JSON.stringify({ body: newVal }) });
            data.body = newVal;
            data.isCustom = true;
            showToast('Saved', 'success');
            renderView();
          } catch (e) { showToast('Error saving', 'error'); }
        });
        item.querySelector('.cancel-edit-btn').addEventListener('click', () => renderView());
      };
      renderView();
      list.appendChild(item);
    });
    container.appendChild(list);
  } catch (e) { container.innerHTML = 'Error loading messages'; }
}

export async function renderSettings(container) {
  const myToken = ++_settingsRenderToken;
  const isCurrent = () => myToken === _settingsRenderToken;

  const state = getState();
  const chatId = state.activeChatId;
  const userContext = state.userContext;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto; display: flex; flex-direction: column; gap: var(--sp-4);';

  if (chatId) {
    let groupSettings = {};
    try {
      const res = await apiFetch(`/api/groups/${chatId}/settings`);
      groupSettings = res?.settings || res || {};
      state.setSettings(groupSettings);
    } catch (e) {
      console.error('[Settings] Failed to load:', e);
      groupSettings = state.settings || {};
    }

    // 1. GROUP IDENTITY
    const LANGS = [
      { code: 'en', label: '🇬🇧 English' },
      { code: 'ar', label: '🇸🇦 Arabic' },
      { code: 'de', label: '🇩🇪 Deutsch' },
      { code: 'es', label: '🇪🇸 Español' },
      { code: 'fr', label: '🇫🇷 Français' },
      { code: 'hi', label: '🇮🇳 हिन्दी' },
      { code: 'id', label: '🇮🇩 Indonesia' },
      { code: 'pt', label: '🇧🇷 Português' },
      { code: 'ru', label: '🇷🇺 Russian' },
      { code: 'tr', label: '🇹🇷 Türkçe' },
    ];
    const allTimezones = (typeof Intl !== 'undefined' && Intl.supportedValuesOf) ? Intl.supportedValuesOf('timeZone') : [];
    const currentLang = groupSettings.language || 'en';
    const currentTz = groupSettings.timezone || 'UTC';
    const tzPreview = (tz) => {
      try { return new Intl.DateTimeFormat('en-US', { timeZone: tz, hour: 'numeric', minute: '2-digit' }).format(new Date()); } catch (e) { return ''; }
    };
    const identityCard = Card({
      title: '🌍 Group Identity',
      subtitle: 'Bot message language and timezone for this group',
      children: `
        <div style="display:flex;flex-direction:column;gap:var(--sp-3);">
          <div>
            <label style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:var(--sp-1);">Bot Message Language</label>
            <select id="lang-select" class="input">
              ${LANGS.map(l => `<option value="${l.code}" ${currentLang === l.code ? 'selected' : ''}>${l.label}</option>`).join('')}
            </select>
            <div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:var(--sp-1);line-height:1.5;">Language the bot uses in group messages. To change the mini app display language for yourself, use the Language page in the sidebar.</div>
          </div>
          <div>
            <label style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:var(--sp-1);">Timezone</label>
            <input id="tz-input" class="input" list="tz-list" value="${currentTz}" placeholder="e.g. America/New_York">
            <datalist id="tz-list">${allTimezones.map(z => `<option value="${z}">`).join('')}</datalist>
            <div id="tz-preview" style="font-size:var(--text-xs);color:var(--text-muted);margin-top:var(--sp-1);">Right now: ${tzPreview(currentTz)}</div>
          </div>
        </div>
      `
    });
    container.appendChild(identityCard);
    identityCard.querySelector('#lang-select').onchange = async (e) => {
      try {
        await apiFetch(`/api/groups/${chatId}/settings/bulk`, { method: 'PUT', validate: false, body: { settings: { language: e.target.value } } });
        state.updateSetting('language', e.target.value);
        showToast('Language saved', 'success');
      } catch (err) { showToast('Failed to save', 'error'); }
    };
    const tzInput = identityCard.querySelector('#tz-input');
    const tzPreviewEl = identityCard.querySelector('#tz-preview');
    tzInput.oninput = () => {
      const preview = tzPreview(tzInput.value);
      tzPreviewEl.textContent = preview ? 'Right now: ' + preview : 'Invalid timezone';
    };
    tzInput.onblur = async () => {
      try {
        await apiFetch(`/api/groups/${chatId}/settings/bulk`, { method: 'PUT', validate: false, body: { settings: { timezone: tzInput.value } } });
        state.updateSetting('timezone', tzInput.value);
        showToast('Timezone saved', 'success');
      } catch (err) { showToast('Failed to save', 'error'); }
    };

    // 2. WELCOME & GOODBYE
    const greetCard = Card({
      title: '👋 Welcome & Goodbye',
      subtitle: 'Control greeting messages',
      children: `
        <div style="display:flex;flex-direction:column;gap:var(--sp-2);">
          <div style="display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) 0;">
            <span style="font-size:var(--text-sm);">Welcome messages enabled</span>
            <div id="toggle-welcome"></div>
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) 0;">
            <span style="font-size:var(--text-sm);">Goodbye messages enabled</span>
            <div id="toggle-goodbye"></div>
          </div>
          <button class="btn btn-secondary" style="margin-top:var(--sp-2);font-size:var(--text-xs);" id="btn-edit-messages">Edit messages →</button>
        </div>
      `
    });
    container.appendChild(greetCard);
    greetCard.querySelector('#toggle-welcome').appendChild(Toggle({ checked: groupSettings.welcome_enabled || false, onChange: (v) => _updateGroupSetting('welcome_enabled', v) }));
    greetCard.querySelector('#toggle-goodbye').appendChild(Toggle({ checked: groupSettings.goodbye_enabled || false, onChange: (v) => _updateGroupSetting('goodbye_enabled', v) }));
    greetCard.querySelector('#btn-edit-messages').onclick = () => navigateToPage('greetings');

    // 3. SECURITY & ENTRY
    const slowModeOptions = [
      { v: 0, l: 'Off' }, { v: 10, l: '10s' }, { v: 30, l: '30s' },
      { v: 60, l: '1min' }, { v: 300, l: '5min' }, { v: 900, l: '15min' }, { v: 3600, l: '1hr' }
    ];
    const currentSlowMode = groupSettings.slow_mode_delay || 0;
    const secCard = Card({
      title: '🔒 Security & Entry',
      subtitle: 'Control who can join and how fast',
      children: `
        <div style="display:flex;flex-direction:column;gap:var(--sp-3);">
          <div style="display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) 0;">
            <div>
              <div style="font-size:var(--text-sm);">Password gate</div>
              <div style="font-size:var(--text-xs);color:var(--text-muted);">Require password to send messages</div>
            </div>
            <div id="toggle-password-gate"></div>
          </div>
          <div id="password-input-row" style="display:${groupSettings.password_gate_enabled ? 'flex' : 'none'};gap:var(--sp-2);">
            <input id="group-password-input" class="input" placeholder="Set password..." style="min-width:0;flex:1;" value="${groupSettings.group_password || ''}">
            <button class="btn btn-secondary" style="white-space:nowrap;flex-shrink:0;" id="save-password-btn">Save</button>
          </div>
          <div>
            <div style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);">Slow Mode</div>
            <div style="display:flex;flex-wrap:wrap;gap:var(--sp-1);" id="slowmode-pills">
              ${slowModeOptions.map(o => `<button data-val="${o.v}" class="btn ${currentSlowMode === o.v ? 'btn-primary' : 'btn-secondary'}" style="padding:var(--sp-1) var(--sp-3);font-size:var(--text-xs);min-width:48px;flex:0 0 auto;">${o.l}</button>`).join('')}
            </div>
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) 0;">
            <div>
              <div style="font-size:var(--text-sm);">Join request approval</div>
              <div style="font-size:var(--text-xs);color:var(--text-muted);">Admins must approve new join requests</div>
            </div>
            <div id="toggle-join-approval"></div>
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) 0;">
            <div>
              <div style="font-size:var(--text-sm);">Channel gate</div>
              <div style="font-size:var(--text-xs);color:var(--text-muted);">Must subscribe to a channel first</div>
            </div>
            <div id="toggle-channel-gate"></div>
          </div>
          <div id="channel-gate-input-row" style="display:${groupSettings.channel_gate_enabled ? 'flex' : 'none'};gap:var(--sp-2);">
            <input id="channel-username-input" class="input" placeholder="@channelname" style="min-width:0;flex:1;" value="${groupSettings.channel_username || ''}">
            <button class="btn btn-secondary" style="white-space:nowrap;flex-shrink:0;" id="save-channel-btn">Save</button>
          </div>
        </div>
      `
    });
    container.appendChild(secCard);
    secCard.querySelector('#toggle-password-gate').appendChild(Toggle({
      checked: groupSettings.password_gate_enabled || false,
      onChange: async (v) => {
        await _updateGroupSetting('password_gate_enabled', v);
        secCard.querySelector('#password-input-row').style.display = v ? 'flex' : 'none';
      }
    }));
    secCard.querySelector('#save-password-btn').onclick = async () => {
      const pw = secCard.querySelector('#group-password-input').value.trim();
      await _updateGroupSetting('group_password', pw);
    };
    secCard.querySelector('#toggle-join-approval').appendChild(Toggle({ checked: groupSettings.require_approval || false, onChange: (v) => _updateGroupSetting('require_approval', v) }));
    secCard.querySelector('#toggle-channel-gate').appendChild(Toggle({
      checked: groupSettings.channel_gate_enabled || false,
      onChange: async (v) => {
        await _updateGroupSetting('channel_gate_enabled', v);
        secCard.querySelector('#channel-gate-input-row').style.display = v ? 'flex' : 'none';
      }
    }));
    secCard.querySelector('#save-channel-btn').onclick = async () => {
      const un = secCard.querySelector('#channel-username-input').value.trim();
      await _updateGroupSetting('channel_username', un);
    };
    secCard.querySelectorAll('#slowmode-pills button').forEach(btn => {
      btn.onclick = async () => {
        const seconds = parseInt(btn.dataset.val);
        try {
          await apiFetch(`/api/groups/${chatId}/actions/slowmode`, { method: 'POST', body: JSON.stringify({ seconds }) });
          if (!isCurrent()) return;
          await _updateGroupSetting('slow_mode_delay', seconds);
          secCard.querySelectorAll('#slowmode-pills button').forEach(b => {
            b.className = `btn ${parseInt(b.dataset.val) === seconds ? 'btn-primary' : 'btn-secondary'}`;
            b.style.cssText = 'padding:var(--sp-1) var(--sp-3);font-size:var(--text-xs);';
          });
          showToast('Slow mode updated', 'success');
        } catch (err) { showToast('Failed to set slow mode', 'error'); }
      };
    });

    // 4. COPY SETTINGS
    const otherGroups = (store.getState().groups || []).filter(g => String(g.chat_id) !== String(chatId));
    if (otherGroups.length > 0) {
      const copyCard = Card({
        title: '📋 Copy Settings',
        subtitle: 'Copy these settings to other groups',
        children: `<button class="btn btn-secondary" id="open-copy-modal" style="width:100%;">Copy settings to other groups →</button>`
      });
      container.appendChild(copyCard);
      copyCard.querySelector('#open-copy-modal').onclick = () => _showCopySettingsModal(chatId, otherGroups);
    }

    // 5. LOG CHANNEL
    const LOG_EVENTS = ['ban','mute','warn','kick','promote','settings','joins','leaves'];
    const currentLogEvents = groupSettings.log_events || ['ban','mute','warn','kick','promote','settings'];
    const logCard = Card({
      title: '📋 Log Channel',
      subtitle: 'Where to send moderation logs',
      children: `
        <div style="display:flex;flex-direction:column;gap:var(--sp-3);">
          <div>
            <label style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:var(--sp-1);">Channel ID</label>
            <div style="display:flex;gap:var(--sp-2);">
              <input type="text" id="input-log-channel" class="input" style="min-width:0;flex:1;" placeholder="-100..." value="${groupSettings.log_channel_id || ''}">
              <button class="btn btn-secondary" style="white-space:nowrap;flex-shrink:0;" id="save-log-channel-btn">Save</button>
              <button class="btn btn-secondary" style="white-space:nowrap;" id="test-log-channel-btn">Test</button>
            </div>
          </div>
          <div>
            <div style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);">What to log</div>
            <div style="display:flex;flex-wrap:wrap;gap:var(--sp-3);row-gap:var(--sp-3);" id="log-events-list">
              ${LOG_EVENTS.map(ev => `
                <label style="display:flex;align-items:center;gap:var(--sp-1);font-size:var(--text-sm);cursor:pointer;">
                  <input type="checkbox" data-ev="${ev}" ${currentLogEvents.includes(ev) ? 'checked' : ''}> ${ev.charAt(0).toUpperCase() + ev.slice(1)}
                </label>
              `).join('')}
            </div>
            <button class="btn btn-secondary" style="margin-top:var(--sp-2);font-size:var(--text-xs);" id="save-log-events-btn">Save log events</button>
          </div>
        </div>
      `
    });
    container.appendChild(logCard);
    logCard.querySelector('#save-log-channel-btn').onclick = () => _updateGroupSetting('log_channel_id', logCard.querySelector('#input-log-channel').value);
    logCard.querySelector('#test-log-channel-btn').onclick = async () => {
      try {
        await apiFetch(`/api/groups/${chatId}/log-channel/test`, { method: 'POST' });
        showToast('Test message sent', 'success');
      } catch (err) { showToast('Test failed', 'error'); }
    };
    logCard.querySelector('#save-log-events-btn').onclick = async () => {
      const checked = [...logCard.querySelectorAll('#log-events-list input[type=checkbox]:checked')].map(el => el.dataset.ev);
      await _updateGroupSetting('log_events', checked);
    };
    window.saveLogChannel = () => _updateGroupSetting('log_channel_id', logCard.querySelector('#input-log-channel').value);

    // 6. ADVANCED
    const advancedCard = Card({
      title: '⚙️ Advanced Group Settings',
      children: `
        <div style="display: flex; flex-direction: column; gap: var(--sp-2);">
          <div style="display: flex; align-items: center; justify-content: space-between; padding: var(--sp-2) 0;">
            <span style="font-size: var(--text-sm);">Silent Commands</span>
            <div id="toggle-silent-commands"></div>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between; padding: var(--sp-2) 0;">
            <span style="font-size: var(--text-sm);">Delete Join/Leave Messages</span>
            <div id="toggle-delete-joinleave"></div>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between; padding: var(--sp-2) 0;">
            <span style="font-size: var(--text-sm);">Inline Mode</span>
            <div id="toggle-inline-mode"></div>
          </div>
        </div>
      `
    });
    container.appendChild(advancedCard);
    advancedCard.querySelector('#toggle-silent-commands').appendChild(Toggle({ checked: groupSettings.silent_commands || false, onChange: (v) => _updateGroupSetting('silent_commands', v) }));
    advancedCard.querySelector('#toggle-delete-joinleave').appendChild(Toggle({ checked: groupSettings.delete_join_leave || false, onChange: (v) => _updateGroupSetting('delete_join_leave', v) }));
    advancedCard.querySelector('#toggle-inline-mode').appendChild(Toggle({ checked: groupSettings.inline_mode_enabled || false, onChange: (v) => _updateGroupSetting('inline_mode_enabled', v) }));

    // Auto-Delete row
    const autoDelSep = document.createElement('hr');
    autoDelSep.style.cssText = 'border:none;border-top:1px solid var(--border);margin:var(--sp-2) 0;';
    advancedCard.appendChild(autoDelSep);
    const autoDelRow = document.createElement('div');
    autoDelRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) 0;gap:var(--sp-3);';
    autoDelRow.innerHTML = `
      <div style="flex:1;">
        <div style="font-size:var(--text-sm);">🗑️ Auto-Delete Messages</div>
        <div style="font-size:var(--text-xs);color:var(--text-muted);">Auto-delete bot messages after N seconds (0 = off)</div>
      </div>
      <input type="number" id="autodelete-seconds" min="0" max="3600"
        value="${groupSettings.autodelete_seconds || groupSettings.auto_delete_seconds || 0}"
        style="width:5rem;padding:4px;border:1px solid var(--border);border-radius:4px;background:var(--bg-input);color:var(--text-primary);text-align:center;">
    `;
    advancedCard.appendChild(autoDelRow);
    autoDelRow.querySelector('#autodelete-seconds').addEventListener('change', async (e) => {
      const secs = parseInt(e.target.value) || 0;
      await _updateGroupSetting('autodelete_seconds', secs);
      await _updateGroupSetting('autodelete_enabled', secs > 0);
    });

    // Join Password row
    const pwSep = document.createElement('hr');
    pwSep.style.cssText = 'border:none;border-top:1px solid var(--border);margin:var(--sp-2) 0;';
    advancedCard.appendChild(pwSep);
    const joinPwRow = document.createElement('div');
    joinPwRow.style.cssText = 'display:flex;flex-direction:column;gap:4px;padding:var(--sp-2) 0;';
    joinPwRow.innerHTML = `
      <div style="font-size:var(--text-sm);font-weight:600;">🔑 Join Password</div>
      <div style="font-size:var(--text-xs);color:var(--text-muted);">
        New members must DM the bot with this word before they can chat. Leave empty to disable.
      </div>
      <div style="display:flex;gap:8px;">
        <input type="text" id="join-password-input" placeholder="e.g. nexusrules"
          value="${groupSettings.join_password || ''}"
          style="flex:1;padding:var(--sp-2);border:1px solid var(--border);border-radius:4px;background:var(--bg-input);color:var(--text-primary);">
        <button id="save-join-password-btn" style="padding:var(--sp-2) var(--sp-3);background:var(--accent);color:#fff;border:none;border-radius:4px;cursor:pointer;">
          Save
        </button>
      </div>
    `;
    advancedCard.appendChild(joinPwRow);
    joinPwRow.querySelector('#save-join-password-btn').addEventListener('click', async () => {
      const val = joinPwRow.querySelector('#join-password-input').value.trim();
      await _updateGroupSetting('join_password', val || null);
      await _updateGroupSetting('password_enabled', !!val);
      showToast(val ? 'Password set' : 'Password cleared', 'success');
    });

    // 7. CUSTOM MESSAGES
    const groupMsgsCard = Card({ title: '📝 Group Custom Messages', subtitle: 'Customize responses for this group', children: '<div id="group-messages-container"></div>' });
    container.appendChild(groupMsgsCard);
    await renderCustomMessagesSection(groupMsgsCard.querySelector('#group-messages-container'), `/api/groups/${chatId}/messages`);

    // 8. DANGER ZONE
    const dangerCard = Card({ title: '⚠️ Danger Zone', subtitle: 'Irreversible actions' });
    dangerCard.style.cssText += '; border-color: var(--danger);';
    const dangerBody = document.createElement('div');
    dangerBody.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-3);';
    const resetBtn = document.createElement('button');
    resetBtn.className = 'btn btn-danger';
    resetBtn.style.cssText = 'align-self:flex-start;';
    resetBtn.textContent = '🔄 Reset all settings';
    resetBtn.onclick = async () => {
      if (!confirm('Reset ALL settings for this group? This cannot be undone.')) return;
      if (!confirm('Are you absolutely sure?')) return;
      try {
        await apiFetch(`/api/groups/${chatId}/settings/reset`, { method: 'DELETE' });
        showToast('Settings reset', 'success');
        await renderSettings(container);
      } catch (err) { showToast('Failed to reset', 'error'); }
    };
    const leaveBtn = document.createElement('button');
    leaveBtn.className = 'btn btn-danger';
    leaveBtn.style.cssText = 'align-self:flex-start;';
    leaveBtn.textContent = '🚪 Remove bot from group';
    leaveBtn.onclick = async () => {
      if (!confirm('Remove the bot from this group?')) return;
      try {
        await apiFetch(`/api/groups/${chatId}/actions/leave`, { method: 'POST' });
        showToast('Bot left the group', 'success');
      } catch (err) { showToast('Failed to leave group', 'error'); }
    };
    dangerBody.appendChild(resetBtn);
    dangerBody.appendChild(leaveBtn);
    dangerCard.appendChild(dangerBody);
    container.appendChild(dangerCard);
  }

  // THEME
  const themeCard = Card({ title: '🎨 Theme & Appearance', children: '<div id="theme-picker-container"></div>' });
  container.appendChild(themeCard);
  ThemeEngine.renderPicker(themeCard.querySelector('#theme-picker-container'));

  if (userContext?.role === 'owner' && userContext.bot_info?.id) {
    const botMsgsCard = Card({ title: '🤖 Bot Global Messages', subtitle: 'Default responses for all your groups', children: '<div id="bot-messages-container"></div>' });
    container.appendChild(botMsgsCard);
    await renderCustomMessagesSection(botMsgsCard.querySelector('#bot-messages-container'), `/api/bots/${userContext.bot_info.id}/messages`);
  }
}
