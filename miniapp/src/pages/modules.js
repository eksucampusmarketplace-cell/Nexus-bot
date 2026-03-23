/**
 * miniapp/src/pages/modules.js
 * Task 8 of 12 — Modules page
 * Extracted from index.html renderModules()
 */

import { Card, EmptyState, Toggle, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { t } from '../../lib/i18n.js?v=1.6.0';

const store = useStore;
const getState = store.getState;

export async function renderModules(container) {
  const state = getState();
  const chatId = state.activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({ icon: '👆', title: t('select_group', 'Select a group'), description: t('modules_select_group', 'Choose a group to manage modules') }));
    return;
  }

  container.innerHTML = `
    <div style="text-align: center; padding: var(--sp-8);">
      <div style="font-size: 48px; margin-bottom: var(--sp-4);">⏳</div>
      <div style="color: var(--text-muted);">Loading modules...</div>
    </div>
  `;

  try {
    const group = await apiFetch(`/api/groups/${chatId}`);
    const settings = group.settings || {};
    state.setSettings(settings);

    container.innerHTML = '';
    container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto; display: flex; flex-direction: column; gap: var(--sp-4);';

    const header = document.createElement('div');
    header.style.cssText = 'margin-bottom: var(--sp-2);';
    header.innerHTML = `
      <h2 style="font-size: 20px; font-weight: 700; margin: 0;">📦 ${t('nav_modules', 'Modules')}</h2>
      <p style="color: var(--text-muted); font-size: 13px; margin: 4px 0 0;">${t('modules_subtitle', 'Toggle features for this group')}</p>
    `;
    container.appendChild(header);

    const moduleList = [
      { id: 'welcome',    name: '👋 Welcome Messages',  desc: 'Greet new members',               settingKey: 'welcome_enabled',      page: 'greetings' },
      { id: 'goodbye',    name: '👋 Goodbye Messages',  desc: 'Farewell leaving members',         settingKey: 'goodbye_enabled',      page: 'greetings' },
      { id: 'rules',      name: '📋 Group Rules',        desc: '/rules command',                   settingKey: 'rules_enabled',        page: null },
      { id: 'captcha',    name: '🔐 Captcha',            desc: 'Verify new members',               settingKey: 'captcha_enabled',      page: 'automod' },
      { id: 'xp',         name: '⭐ XP & Levels',        desc: 'Member progression',               settingKey: 'xp_enabled',           page: 'engagement' },
      { id: 'games',      name: '🎮 Games',               desc: 'In-chat games',                    settingKey: 'games_enabled',        page: null },
      { id: 'channel',    name: '📢 Channel Posting',    desc: 'Post to linked channel',           settingKey: 'channel_enabled',      page: null },
      { id: 'logging',    name: '📋 Mod Logging',         desc: 'Log actions to channel',           settingKey: 'log_enabled',          page: 'logs' },
      { id: 'inline',     name: '⚡ Inline Mode',         desc: '@botname queries',                 settingKey: 'inline_mode_enabled',  page: null },
      { id: 'reports',    name: '🚨 Reports',             desc: '/report command',                  settingKey: 'reports_enabled',      page: 'reports' },
      { id: 'notes',      name: '📝 Notes',               desc: 'Save and retrieve notes',          settingKey: 'notes_enabled',        page: 'notes' },
      { id: 'broadcast',  name: '📡 Broadcast',           desc: 'Mass message system',              settingKey: 'broadcast_enabled',    page: 'broadcast' },
      { id: 'autodelete', name: '🗑️ Auto-Delete',          desc: 'Delete messages after N seconds', settingKey: 'autodelete_enabled',   page: 'settings' },
    ];

    moduleList.forEach(m => {
      const enabled = settings[m.settingKey] || false;
      const card = Card({
        title: m.name,
        subtitle: m.desc,
        actions: Toggle({
          checked: enabled,
          onChange: async (v) => {
            try {
              await apiFetch(`/api/groups/${chatId}/settings/bulk`, {
                method: 'PUT',
                validate: false,
                body: JSON.stringify({ settings: { [m.settingKey]: v } })
              });
              state.updateSetting(m.settingKey, v);
              showToast(`${m.name} ${v ? 'enabled' : 'disabled'}`, 'success');
            } catch (e) {
              showToast('Failed to update', 'error');
            }
          }
        })
      });
      if (m.page) {
        const link = document.createElement('div');
        link.style.cssText = 'margin-top:var(--sp-2);';
        link.innerHTML = `<button class="btn btn-secondary" style="font-size:var(--text-xs);padding:var(--sp-1) var(--sp-3);" data-page="${m.page}">Configure →</button>`;
        link.querySelector('button').onclick = () => window.navigateToPage(m.page);
        card.appendChild(link);
      }
      container.appendChild(card);
    });
  } catch (e) {
    container.innerHTML = '';
    container.appendChild(EmptyState({ icon: '⚠️', title: t('modules_load_failed', 'Failed to load modules'), description: t('modules_try_again', 'Please try again') }));
  }
}
