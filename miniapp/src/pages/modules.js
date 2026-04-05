/**
 * miniapp/src/pages/modules.js
 *
 * Feature modules toggle page.
 * Allows admins to enable/disable bot features for the active group.
 */

import { Card, Toggle, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { t } from '../../lib/i18n.js?v=1.6.0';

const store = useStore;

const MODULE_LIST = [
  { id: 'welcome',    name: '👋 Welcome Messages',  desc: 'Greet new members',               settingKey: 'welcome_enabled',      page: 'greetings' },
  { id: 'goodbye',    name: '👋 Goodbye Messages',  desc: 'Farewell leaving members',         settingKey: 'goodbye_enabled',      page: 'greetings' },
  { id: 'rules',      name: '📋 Group Rules',        desc: '/rules command',                   settingKey: 'rules_enabled',        page: null },
  { id: 'captcha',    name: '🔐 Captcha',            desc: 'Verify new members',               settingKey: 'captcha_enabled',      page: 'captcha' },
  { id: 'xp',         name: '⭐ XP & Levels',        desc: 'Member progression',               settingKey: 'xp_enabled',           page: 'engagement' },
  { id: 'games',      name: '🎮 Games',               desc: 'In-chat games',                    settingKey: 'games_enabled',        page: null },
  { id: 'channel',    name: '📢 Channel Posting',    desc: 'Post to linked channel',           settingKey: 'channel_enabled',      page: null },
  { id: 'logging',    name: '📋 Mod Logging',         desc: 'Log actions to channel',           settingKey: 'log_enabled',          page: 'logs' },
  { id: 'inline',     name: '⚡ Inline Mode',         desc: '@botname queries',                 settingKey: 'inline_mode_enabled',  page: null },
  { id: 'reports',    name: '🚨 Reports',             desc: '/report command',                  settingKey: 'reports_enabled',      page: 'reports' },
  { id: 'notes',      name: '📝 Notes',               desc: 'Save and retrieve notes',          settingKey: 'notes_enabled',        page: 'notes' },
  { id: 'broadcast',  name: '📡 Broadcast',           desc: 'Mass message system',              settingKey: 'broadcast_enabled',    page: 'broadcast' },
  { id: 'autodelete', name: '🗑️ Auto-Delete',          desc: 'Delete messages after N seconds', settingKey: 'autodelete_enabled',   page: null },
];

export async function renderModulesPage(container) {
  const state = store.getState();
  const chatId = state.activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '📦',
      title: t('modules_select_group', 'Select a group'),
      description: t('modules_select_group_desc', 'Choose a group to manage its modules.')
    }));
    return;
  }

  const header = document.createElement('div');
  header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-4);';
  header.innerHTML = `
    <div>
      <h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">📦 ${t('nav_modules', 'Modules')}</h2>
      <p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">${t('modules_subtitle', 'Enable or disable bot features for this group')}</p>
    </div>
  `;
  container.appendChild(header);

  let groupSettings = {};
  const loadingEl = document.createElement('div');
  loadingEl.style.cssText = 'text-align:center;padding:var(--sp-8);color:var(--text-muted);';
  loadingEl.textContent = t('loading', 'Loading...');
  container.appendChild(loadingEl);

  try {
    const res = await apiFetch(`/api/groups/${chatId}/settings`);
    groupSettings = res?.settings || res || {};
    state.setSettings(groupSettings);
  } catch (e) {
    console.error('[Modules] Failed to load settings:', e);
    groupSettings = state.settings || {};
  }

  loadingEl.remove();

  async function updateSetting(key, val) {
    try {
      await apiFetch(`/api/groups/${chatId}/settings/bulk`, {
        method: 'PUT',
        validate: false,
        body: { settings: { [key]: val } },
      });
      state.updateSetting(key, val);
      showToast(t('saved', 'Saved'), 'success');
    } catch (e) {
      showToast(t('save_failed', 'Failed to save'), 'error');
    }
  }

  const modulesCard = Card({
    title: `📦 ${t('nav_modules', 'Modules')}`,
    subtitle: t('modules_subtitle', 'Enable or disable bot features for this group'),
  });

  const list = document.createElement('div');
  list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';

  MODULE_LIST.forEach(m => {
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) 0;border-bottom:1px solid var(--border);';

    const info = document.createElement('div');
    info.innerHTML = `
      <div style="font-size:var(--text-sm);font-weight:var(--fw-medium);">${m.name}</div>
      <div style="font-size:var(--text-xs);color:var(--text-muted);">${m.desc}</div>
    `;

    const ctrl = document.createElement('div');
    ctrl.style.cssText = 'display:flex;align-items:center;gap:var(--sp-3);';

    if (m.page) {
      const cfgBtn = document.createElement('button');
      cfgBtn.className = 'btn btn-secondary';
      cfgBtn.style.cssText = 'padding:var(--sp-1) var(--sp-2);font-size:10px;height:24px;';
      cfgBtn.textContent = t('configure', 'Configure') + ' →';
      cfgBtn.onclick = () => window.navigateToPage(m.page);
      ctrl.appendChild(cfgBtn);
    }

    ctrl.appendChild(Toggle({
      checked: groupSettings[m.settingKey] || false,
      onChange: (v) => updateSetting(m.settingKey, v)
    }));

    row.appendChild(info);
    row.appendChild(ctrl);
    list.appendChild(row);
  });

  modulesCard.appendChild(list);
  container.appendChild(modulesCard);
}
