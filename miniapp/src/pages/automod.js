/**
 * miniapp/src/pages/automod.js
 *
 * AutoMod configuration page.
 * Allows users to configure anti-flood, anti-spam, anti-link,
 * and other automod settings.
 *
 * Dependencies:
 *   - lib/components.js (Card, Toggle, Badge, EmptyState, showToast)
 *   - lib/rule_templates.js (RULE_TEMPLATES, applyTemplate)
 *   - store/index.js (useStore)
 */

import { Card, Toggle, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { RULE_TEMPLATES, applyTemplate } from '../../lib/rule_templates.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';

const store = useStore;

// Render guard token
let _automodRenderToken = 0;

/**
 * AutoMod sections configuration
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
      { key: 'duplicate_limit', label: 'Max duplicate messages', type: 'number', min: 1, max: 10, default: 2 },
      { key: 'duplicate_window_mins', label: 'Duplicate window (mins)', type: 'number', min: 1, max: 60, default: 5 },
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
    id: 'advanced_content',
    title: 'Advanced Content',
    description: 'Strict message length and content rules',
    icon: '📏',
    settings: [
      { key: 'min_words', label: 'Min words', type: 'number', min: 0, max: 50, default: 0 },
      { key: 'max_words', label: 'Max words', type: 'number', min: 0, max: 1000, default: 0 },
      { key: 'min_chars', label: 'Min characters', type: 'number', min: 0, max: 500, default: 0 },
      { key: 'max_chars', label: 'Max characters', type: 'number', min: 0, max: 4000, default: 0 },
      { key: 'min_lines', label: 'Min lines', type: 'number', min: 0, max: 20, default: 0 },
      { key: 'max_lines', label: 'Max lines', type: 'number', min: 0, max: 100, default: 0 },
      { key: 'regex_active', label: 'Enable Regex Filters', type: 'toggle' },
      { key: 'necessary_words_active', label: 'Enable Required Words', type: 'toggle' },
      { key: 'self_destruct_enabled', label: 'Enable Self-Destruct', type: 'toggle' },
      { key: 'self_destruct_minutes', label: 'Self-Destruct (minutes)', type: 'number', min: 1, max: 1440, default: 60 },
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
      { key: 'lock_document', label: 'Block files', type: 'toggle' },
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
];

/**
 * Render the AutoMod configuration page
 */
export async function renderAutomodPage(container) {
  // Increment render guard token
  const myToken = ++_automodRenderToken;
  const isCurrent = () => myToken === _automodRenderToken;

  const state = store.getState();
  const chatId = state.activeChatId;

  // Always clear and reset container
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  // If no chatId, try to get first available group
  if (!chatId && state.groups && state.groups.length > 0) {
    const firstGroup = state.groups[0];
    state.setActiveChatId(firstGroup.chat_id);
  }

  // Check again after auto-selecting
  const finalChatId = store.getState().activeChatId;

  if (!finalChatId) {
    container.appendChild(EmptyState({
      icon: '👆',
      title: 'Select a group',
      description: 'Choose a group from the top to configure AutoMod'
    }));
    return;
  }

  // Show loading state
  container.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: center; padding: 40px;">
      <div style="text-align: center; color: var(--text-muted);">
        <div style="font-size: 24px; margin-bottom: 12px;">⏳</div>
        <div style="font-size: var(--text-sm);">Loading settings...</div>
      </div>
    </div>
  `;

  let settings = {};

  try {
    console.debug('[AutoMod] Loading settings from /api/groups/' + finalChatId + '/settings');
    const res = await apiFetch(`/api/groups/${finalChatId}/settings`);
    console.debug('[AutoMod] Settings loaded:', res);
    settings = res.settings || res || {};
    store.getState().setSettings(settings);

    if (!isCurrent()) return;
  } catch (error) {
    console.error('[AutoMod] Failed to load settings:', error);
    showToast('Failed to load settings: ' + (error.message || 'unknown error'), 'error');
    if (!isCurrent()) return;
  }

  // Clear loading state
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  // Templates section
  const templatesCard = Card({
    title: 'Quick Templates',
    subtitle: 'Apply a preset configuration',
  });
  container.appendChild(templatesCard);

  // Render templates section DOM
  const templatesContainer = templatesCard;
  templatesContainer.appendChild(_renderTemplatesSection(finalChatId, settings));

  if (!isCurrent()) return;

  // AutoMod sections
  AUTOMOD_SECTIONS.forEach(section => {
    const sectionCard = Card({
      title: `${section.icon} ${section.title}`,
      subtitle: section.description,
    });
    container.appendChild(sectionCard);

    // Render section DOM
    sectionCard.appendChild(_renderSection(section, settings, finalChatId));
  });
}

/**
 * Render templates section
 */
function _renderTemplatesSection(chatId, currentSettings) {
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

    btn.onclick = async () => {
      btn.disabled = true;
      btn.innerHTML = '<span style="color: var(--accent);">⏳ Applying...</span>';

      try {
        console.debug('[AutoMod] Applying template:', template.id);

        // Use the bulk endpoint and send only the template settings
        await apiFetch(`/api/groups/${chatId}/settings/bulk`, {
          method: 'PUT',
          validate: false,
          body: { settings: template.settings || {} },
        });
        console.debug('[AutoMod] Template applied successfully');

        btn.innerHTML = '<span style="color: var(--success);">✅ Applied! Refreshing...</span>';

        // Re-fetch settings and re-render all sections
        try {
          const res = await apiFetch(`/api/groups/${chatId}/settings`);
          const newSettings = res.settings || res || {};
          store.getState().setSettings(newSettings);

          // Re-render the entire page
          const automodContainer = document.querySelector('#automod-page') || document.querySelector('[data-page="automod"]');
          if (automodContainer) {
            await renderAutomodPage(automodContainer);
          }
        } catch (refreshErr) {
          console.warn('[AutoMod] Could not refresh after template:', refreshErr);
          showToast('Template applied but refresh failed', 'warning');
        }
      } catch (e) {
        console.error('[AutoMod] Failed to apply template:', e);
        showToast('Failed to apply template: ' + (e.message || 'unknown error'), 'error');
        btn.innerHTML = '<span style="color: var(--danger);">❌ Failed</span>';
      }

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
      }, 2500);
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
function _renderSection(section, settings, chatId) {
  const container = document.createElement('div');
  container.style.cssText = 'display: flex; flex-direction: column; gap: var(--sp-2);';

  const _saveSetting = async (key, val) => {
    try {
      console.debug(`[AutoMod] Saving ${key} =`, val);
      // Send ONLY the changed key via the bulk endpoint
      await apiFetch(`/api/groups/${chatId}/settings/bulk`, {
        method: 'PUT',
        validate: false,
        body: { settings: { [key]: val } },
      });
      console.debug(`[AutoMod] Saved ${key} successfully`);
      store.getState().updateSetting(key, val);
      showToast('Saved', 'success');
    } catch (e) {
      console.error(`[AutoMod] Failed to save ${key}:`, e);
      showToast('Failed to save: ' + (e.message || 'unknown error'), 'error');
    }
  };

  section.settings.forEach(setting => {
    const value = settings[setting.key] ?? setting.default ?? false;

    if (setting.type === 'toggle') {
      const row = document.createElement('div');
      row.style.cssText = 'display: flex; align-items: center; justify-content: space-between; padding: var(--sp-2) 0;';

      const label = document.createElement('span');
      label.textContent = setting.label;
      label.style.cssText = 'font-size: var(--text-sm); color: var(--text-primary);';

      // For lock toggles, add status label
      const isLockSetting = setting.key.startsWith('lock_');
      let statusLabel = null;

      const toggle = Toggle({
        checked: value,
        onChange: async (isChecked) => {
          await _saveSetting(setting.key, isChecked);
          if (statusLabel) {
            statusLabel.textContent = isChecked ? '🔴 LOCKED' : '🟢 OPEN';
            statusLabel.style.color = isChecked ? 'var(--danger)' : 'var(--success)';
          }
        }
      });

      row.appendChild(label);

      if (isLockSetting) {
        const statusWrapper = document.createElement('div');
        statusWrapper.style.cssText = 'display: flex; align-items: center; gap: var(--sp-2);';

        statusLabel = document.createElement('span');
        statusLabel.textContent = value ? '🔴 LOCKED' : '🟢 OPEN';
        statusLabel.style.cssText = 'font-size: 10px; font-weight: 600; color: ' + (value ? 'var(--danger)' : 'var(--success)');

        statusWrapper.appendChild(toggle);
        statusWrapper.appendChild(statusLabel);
        row.appendChild(statusWrapper);
      } else {
        row.appendChild(toggle);
      }

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
        const numVal = parseInt(input.value, 10);
        if (isNaN(numVal)) return;
        // Clamp to min/max
        const clampedVal = Math.max(setting.min, Math.min(setting.max, numVal));
        await _saveSetting(setting.key, clampedVal);
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
        await _saveSetting(setting.key, select.value);
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
        await _saveSetting(setting.key, input.value);
      });

      wrapper.appendChild(label);
      wrapper.appendChild(input);
      container.appendChild(wrapper);
    }
  });

  return container;
}
