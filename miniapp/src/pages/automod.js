/**
 * miniapp/src/pages/automod.js
 *
 * AutoMod configuration page.
 * Allows users to configure anti-flood, anti-spam, anti-link,
 * captcha verification, and other automod settings.
 *
 * Dependencies:
 *   - lib/components.js (Card, Toggle, Badge, EmptyState, showToast)
 *   - lib/rule_templates.js (RULE_TEMPLATES, applyTemplate)
 *   - store/index.js (useStore)
 */

import { Card, Toggle, EmptyState, showToast } from '../../lib/components.js';
import { RULE_TEMPLATES, applyTemplate } from '../../lib/rule_templates.js';
import { useStore } from '../../store/index.js';

const store = useStore;

/**
 * Default automod sections configuration
 */
const AUTOMOD_SECTIONS = [
  {
    id: 'antiflood',
    title: 'Anti-Flood',
    description: 'Prevent rapid message flooding',
    icon: '🌊',
    settings: [
      { key: 'antiflood', label: 'Enable Anti-Flood', type: 'toggle' },
      { key: 'antiflood_limit', label: 'Max messages', type: 'number', min: 3, max: 20, default: 5 },
      { key: 'antiflood_window', label: 'Time window (seconds)', type: 'number', min: 5, max: 120, default: 10 },
      { key: 'antiflood_action', label: 'Action', type: 'select', options: [
        { value: 'delete', label: 'Delete only' },
        { value: 'mute', label: 'Mute' },
        { value: 'kick', label: 'Kick' },
        { value: 'ban', label: 'Ban' },
      ], default: 'mute' },
    ],
  },
  {
    id: 'antispam',
    title: 'Anti-Spam',
    description: 'Block known spam patterns and bots',
    icon: '🛡️',
    settings: [
      { key: 'antispam', label: 'Enable Anti-Spam', type: 'toggle' },
      { key: 'lock_username', label: 'Block spam usernames', type: 'toggle' },
      { key: 'lock_bot', label: 'Block bot invites', type: 'toggle' },
      { key: 'lock_bot_inviter', label: 'Block bots from adding users', type: 'toggle' },
    ],
  },
  {
    id: 'antilink',
    title: 'Anti-Link',
    description: 'Control external links and forwards',
    icon: '🔗',
    settings: [
      { key: 'lock_link', label: 'Block Telegram links', type: 'toggle' },
      { key: 'lock_website', label: 'Block external websites', type: 'toggle' },
      { key: 'lock_forward', label: 'Block message forwards', type: 'toggle' },
      { key: 'lock_channel', label: 'Block channel forwards', type: 'toggle' },
      { key: 'whitelist_links', label: 'Whitelist (comma URLs)', type: 'text', placeholder: 'example.com, mysite.org' },
    ],
  },
  {
    id: 'captcha',
    title: 'Captcha Verification',
    description: 'Require new members to verify',
    icon: '🔐',
    settings: [
      { key: 'captcha_enabled', label: 'Enable Captcha', type: 'toggle' },
      { key: 'captcha_timeout', label: 'Timeout (seconds)', type: 'number', min: 30, max: 300, default: 60 },
      { key: 'captcha_action', label: 'On failure', type: 'select', options: [
        { value: 'kick', label: 'Kick' },
        { value: 'ban', label: 'Ban' },
      ], default: 'kick' },
    ],
  },
  {
    id: 'media',
    title: 'Media Restrictions',
    description: 'Control media types in chat',
    icon: '📸',
    settings: [
      { key: 'lock_photo', label: 'Block photos', type: 'toggle' },
      { key: 'lock_video', label: 'Block videos', type: 'toggle' },
      { key: 'lock_sticker', label: 'Block stickers', type: 'toggle' },
      { key: 'lock_gif', label: 'Block GIFs', type: 'toggle' },
      { key: 'lock_voice', label: 'Block voice messages', type: 'toggle' },
      { key: 'lock_file', label: 'Block files', type: 'toggle' },
    ],
  },
  {
    id: 'content',
    title: 'Content Filter',
    description: 'Filter specific content types',
    icon: '🚫',
    settings: [
      { key: 'lock_porn', label: 'Block adult content', type: 'toggle' },
      { key: 'lock_hashtag', label: 'Block hashtags', type: 'toggle' },
      { key: 'lock_unofficial_tg', label: 'Block unofficial Telegram', type: 'toggle' },
      { key: 'lock_userbots', label: 'Block userbots', type: 'toggle' },
    ],
  },
  {
    id: 'warnings',
    title: 'Warnings System',
    description: 'Configure warning thresholds and actions',
    icon: '⚠️',
    settings: [
      { key: 'warn_enabled', label: 'Enable Warnings', type: 'toggle' },
      { key: 'warn_max', label: 'Max warns before action', type: 'number', min: 1, max: 10, default: 3 },
      { key: 'warn_action', label: 'Action after max warns', type: 'select', options: [
        { value: 'mute_1h', label: 'Mute for 1 hour' },
        { value: 'mute_12h', label: 'Mute for 12 hours' },
        { value: 'mute_24h', label: 'Mute for 24 hours' },
        { value: 'kick', label: 'Kick' },
        { value: 'ban', label: 'Ban' },
        { value: 'ban_permanent', label: 'Permanent ban' },
      ], default: 'mute_24h' },
    ],
  },
];

/**
 * Render the AutoMod configuration page
 * @param {HTMLElement} container - Container element to render into
 */
export async function renderAutomodPage(container) {
  const chatId = store.getState().activeChatId;
  const initData = window.Telegram?.WebApp?.initData || '';

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  // Show loading state
  container.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: center; padding: 40px;">
      <div style="text-align: center; color: var(--text-muted);">
        <div style="font-size: 24px; margin-bottom: 12px;">⏳</div>
        <div style="font-size: var(--text-sm);">Loading settings...</div>
      </div>
    </div>
  `;

  let settings = store.getState().settings || {};

  // Fetch settings from API if we have a chat ID
  if (chatId) {
    try {
      const res = await fetch(`/api/groups/${chatId}`, {
        headers: { 'x-init-data': initData }
      });

      if (res.ok) {
        const group = await res.json();
        settings = group.settings || {};
        store.setSettings(settings);
      }
    } catch (error) {
      console.error('[AutoMod] Failed to load settings:', error);
    }
  }

  // Clear loading state
  container.innerHTML = '';

  // Templates section
  const templatesCard = Card({
    title: 'Quick Templates',
    subtitle: 'Apply a preset configuration',
  });
  container.appendChild(templatesCard);

  // Render templates section DOM
  const templatesContainer = templatesCard;
  templatesContainer.appendChild(_renderTemplatesSection());

  // AutoMod sections
  AUTOMOD_SECTIONS.forEach(section => {
    const sectionCard = Card({
      title: `${section.icon} ${section.title}`,
      subtitle: section.description,
    });
    container.appendChild(sectionCard);

    // Render section DOM
    sectionCard.appendChild(_renderSection(section, settings));
  });
}

/**
 * Render templates section
 */
function _renderTemplatesSection() {
  const initData = window.Telegram?.WebApp?.initData || '';
  const chatId = store.getState().activeChatId;

  const container = document.createElement('div');
  container.style.cssText = 'display: flex; flex-direction: column; gap: var(--sp-2);';

  RULE_TEMPLATES.forEach(template => {
    const btn = document.createElement('button');
    btn.className = 'template-use-btn';
    btn.dataset.template = template.id;
    btn.style.cssText = `
      width: 100%;
      padding: var(--sp-3);
      background: var(--bg-input);
      border: 1px solid var(--border);
      border-radius: var(--r-lg);
      margin-bottom: var(--sp-2);
      cursor: pointer;
      text-align: left;
      transition: all var(--dur-fast);
    `;

    const templateSettings = RULE_TEMPLATES.reduce((acc, t) => ({ ...acc, [t.id]: t.settings }), {});

    btn.onclick = async () => {
      if (!chatId) {
        showToast('Please select a group first', 'warning');
        return;
      }
      btn.disabled = true;
      btn.innerHTML = '<span style="color: var(--accent);">⏳ Applying...</span>';

      try {
        const res = await fetch(`/api/groups/${chatId}/settings/bulk`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'x-init-data': initData
          },
          body: JSON.stringify({
            settings: templateSettings[template.id]
          })
        });

        if (res.ok) {
          btn.innerHTML = '<span style="color: var(--success);">✅ Applied!</span>';
          setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = `
              <div style="font-weight: var(--fw-semibold); font-size: var(--text-sm); color: var(--text-primary)">
                ${template.name}
              </div>
              <div style="font-size: var(--text-xs); color: var(--text-muted); margin-top: 4px">
                ${template.description}
              </div>
            `;
          }, 2000);
        } else {
          throw new Error('Failed');
        }
      } catch (e) {
        console.error('Failed to apply template:', e);
        btn.innerHTML = '<span style="color: var(--danger);">❌ Failed</span>';
        setTimeout(() => {
          btn.disabled = false;
          btn.innerHTML = `
            <div style="font-weight: var(--fw-semibold); font-size: var(--text-sm); color: var(--text-primary)">
              ${template.name}
            </div>
            <div style="font-size: var(--text-xs); color: var(--text-muted); margin-top: 4px">
              ${template.description}
            </div>
          `;
        }, 2000);
      }
    };

    btn.innerHTML = `
      <div style="font-weight: var(--fw-semibold); font-size: var(--text-sm); color: var(--text-primary)">
        ${template.name}
      </div>
      <div style="font-size: var(--text-xs); color: var(--text-muted); margin-top: 4px">
        ${template.description}
      </div>
    `;

    container.appendChild(btn);
  });

  return container;
}

/**
 * Render a single automod section
 */
function _renderSection(section, settings) {
  const initData = window.Telegram?.WebApp?.initData || '';
  const chatId = store.getState().activeChatId;

  const container = document.createElement('div');
  container.style.cssText = 'display: flex; flex-direction: column; gap: var(--sp-2);';

  section.settings.forEach(setting => {
    const value = settings[setting.key] ?? setting.default ?? false;

    if (setting.type === 'toggle') {
      const row = document.createElement('div');
      row.style.cssText = 'display: flex; align-items: center; justify-content: space-between; padding: var(--sp-2) 0;';

      const label = document.createElement('span');
      label.textContent = setting.label;
      label.style.cssText = 'font-size: var(--text-sm); color: var(--text-primary);';

      const toggle = Toggle({
        checked: value,
        onChange: async (isChecked) => {
          if (!chatId) { showToast('Please select a group first', 'warning'); return; }
          try {
            // Get current settings from store
            const currentSettings = store.getState().settings || {};

            // Update with new value
            const updatedSettings = {
              ...currentSettings,
              [setting.key]: isChecked
            };

            // Send full settings object to API
            await fetch(`/api/groups/${chatId}/settings`, {
              method: 'PUT',
              headers: {
                'Content-Type': 'application/json',
                'x-init-data': initData
              },
              body: JSON.stringify(updatedSettings)
            });

            // Update store
            store.updateSetting(setting.key, isChecked);
            showToast('Setting saved', 'success');
          } catch (e) {
            console.error('Failed to save setting:', e);
            showToast('Failed to save setting', 'error');
          }
        }
      });

      row.appendChild(label);
      row.appendChild(toggle);
      container.appendChild(row);
    } else if (setting.type === 'number') {
      const row = document.createElement('div');
      row.style.cssText = 'display: flex; align-items: center; justify-content: space-between; padding: var(--sp-2) 0;';

      const label = document.createElement('span');
      label.textContent = setting.label;
      label.style.cssText = 'font-size: var(--text-sm); color: var(--text-primary);';

      const input = document.createElement('input');
      input.type = 'number';
      input.value = value || setting.default;
      input.min = setting.min;
      input.max = setting.max;
      input.style.cssText = `
        width: 5rem;
        background: var(--bg-input);
        border-radius: var(--r-lg);
        padding: var(--sp-2) var(--sp-3);
        font-size: var(--text-sm);
        color: var(--text-primary);
        text-align: right;
        border: 1px solid var(--border);
      `;
      input.addEventListener('change', async () => {
        if (!chatId) { showToast('Please select a group first', 'warning'); return; }
        const numValue = parseInt(input.value, 10);
        try {
          // Get current settings from store
          const currentSettings = store.getState().settings || {};

          // Update with new value
          const updatedSettings = {
            ...currentSettings,
            [setting.key]: numValue
          };

          // Send full settings object to API
          await fetch(`/api/groups/${chatId}/settings`, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'x-init-data': initData
            },
            body: JSON.stringify(updatedSettings)
          });

          // Update store
          store.updateSetting(setting.key, numValue);
          showToast('Setting saved', 'success');
        } catch (e) {
          console.error('Failed to save setting:', e);
          showToast('Failed to save setting', 'error');
        }
      });

      row.appendChild(label);
      row.appendChild(input);
      container.appendChild(row);
    } else if (setting.type === 'select') {
      const row = document.createElement('div');
      row.style.cssText = 'display: flex; align-items: center; justify-content: space-between; padding: var(--sp-2) 0;';

      const label = document.createElement('span');
      label.textContent = setting.label;
      label.style.cssText = 'font-size: var(--text-sm); color: var(--text-primary);';

      const select = document.createElement('select');
      select.style.cssText = `
        width: auto;
        min-width: 120px;
        padding: var(--sp-2) var(--sp-3);
        background: var(--bg-input);
        border: 1px solid var(--border);
        border-radius: var(--r-lg);
        color: var(--text-primary);
        font-size: var(--text-sm);
      `;

      setting.options.forEach(opt => {
        const option = document.createElement('option');
        option.value = opt.value;
        option.textContent = opt.label;
        if (value === opt.value) option.selected = true;
        select.appendChild(option);
      });

      select.addEventListener('change', async () => {
        if (!chatId) { showToast('Please select a group first', 'warning'); return; }
        try {
          // Get current settings from store
          const currentSettings = store.getState().settings || {};

          // Update with new value
          const updatedSettings = {
            ...currentSettings,
            [setting.key]: select.value
          };

          // Send full settings object to API
          await fetch(`/api/groups/${chatId}/settings`, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'x-init-data': initData
            },
            body: JSON.stringify(updatedSettings)
          });

          // Update store
          store.updateSetting(setting.key, select.value);
          showToast('Setting saved', 'success');
        } catch (e) {
          console.error('Failed to save setting:', e);
          showToast('Failed to save setting', 'error');
        }
      });

      row.appendChild(label);
      row.appendChild(select);
      container.appendChild(row);
    } else if (setting.type === 'text') {
      const wrapper = document.createElement('div');
      wrapper.style.cssText = 'padding: var(--sp-2) 0;';

      const label = document.createElement('span');
      label.textContent = setting.label;
      label.style.cssText = 'font-size: var(--text-sm); color: var(--text-primary); display: block; margin-bottom: var(--sp-1);';

      const input = document.createElement('input');
      input.type = 'text';
      input.value = value || '';
      input.placeholder = setting.placeholder || '';
      input.style.cssText = `
        width: 100%;
        padding: var(--sp-2) var(--sp-3);
        background: var(--bg-input);
        border: 1px solid var(--border);
        border-radius: var(--r-lg);
        color: var(--text-primary);
        font-size: var(--text-sm);
      `;
      input.addEventListener('change', async () => {
        if (!chatId) { showToast('Please select a group first', 'warning'); return; }
        try {
          // Get current settings from store
          const currentSettings = store.getState().settings || {};

          // Update with new value
          const updatedSettings = {
            ...currentSettings,
            [setting.key]: input.value
          };

          // Send full settings object to API
          await fetch(`/api/groups/${chatId}/settings`, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'x-init-data': initData
            },
            body: JSON.stringify(updatedSettings)
          });

          // Update store
          store.updateSetting(setting.key, input.value);
          showToast('Setting saved', 'success');
        } catch (e) {
          console.error('Failed to save setting:', e);
          showToast('Failed to save setting', 'error');
        }
      });

      wrapper.appendChild(label);
      wrapper.appendChild(input);
      container.appendChild(wrapper);
    }
  });

  return container;
}
