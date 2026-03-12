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

import { Card, Toggle, Badge, EmptyState, showToast } from '../lib/components.js';
import { RULE_TEMPLATES, applyTemplate } from '../lib/rule_templates.js';
import { useStore } from '../store/index.js';

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
export function renderAutomodPage(container) {
  const chatId = store.getState().activeChatId;
  const settings = store.getState().settings || {};
  
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  // Templates section
  const templatesCard = Card({
    title: 'Quick Templates',
    subtitle: 'Apply a preset configuration',
    children: _renderTemplatesSection(),
  });
  container.appendChild(templatesCard);

  // AutoMod sections
  AUTOMOD_SECTIONS.forEach(section => {
    const sectionCard = Card({
      title: `${section.icon} ${section.title}`,
      subtitle: section.description,
      children: _renderSection(section, settings),
    });
    container.appendChild(sectionCard);
  });
}

/**
 * Render templates section
 */
function _renderTemplatesSection() {
  const initData = window.Telegram?.WebApp?.initData || '';
  const chatId = store.getState().activeChatId;
  
  const templatesHtml = RULE_TEMPLATES.map(template => `
    <button 
      class="template-use-btn" 
      data-template="${template.id}"
      style="
        width: 100%;
        padding: var(--sp-3);
        background: var(--bg-input);
        border: 1px solid var(--border);
        border-radius: var(--r-lg);
        margin-bottom: var(--sp-2);
        cursor: pointer;
        text-align: left;
        transition: all var(--dur-fast);
      "
    >
      <div style="font-weight: var(--fw-semibold); font-size: var(--text-sm); color: var(--text-primary)">
        ${template.name}
      </div>
      <div style="font-size: var(--text-xs); color: var(--text-muted); margin-top: 4px">
        ${template.description}
      </div>
    </button>
  `).join('');

  return `
    <div style="display: flex; flex-direction: column; gap: var(--sp-2);">
      ${templatesHtml}
    </div>
    <script>
      document.querySelectorAll('[data-template]').forEach(btn => {
        btn.onclick = async () => {
          const templateId = btn.dataset.template;
          const chatId = '${chatId}';
          const initData = '${initData}';
          
          btn.disabled = true;
          btn.innerHTML = '<span style="color: var(--accent);">⏳ Applying...</span>';
          
          try {
            const res = await fetch('/api/groups/' + chatId + '/settings/bulk', {
              method: 'PUT',
              headers: {
                'Content-Type': 'application/json',
                'x-init-data': initData
              },
              body: JSON.stringify({ 
                settings: ${JSON.stringify(RULE_TEMPLATES.reduce((acc, t) => ({ ...acc, [t.id]: t.settings }), {}))}[templateId] 
              })
            });
            
            if (res.ok) {
              btn.innerHTML = '<span style="color: var(--success);">✅ Applied!</span>';
              setTimeout(() => btn.disabled = false, 2000);
            } else {
              throw new Error('Failed');
            }
          } catch (e) {
            btn.innerHTML = '<span style="color: var(--danger);">❌ Failed</span>';
            setTimeout(() => btn.disabled = false, 2000);
          }
        };
      });
    </script>
  `;
}

/**
 * Render a single automod section
 */
function _renderSection(section, settings) {
  const initData = window.Telegram?.WebApp?.initData || '';
  const chatId = store.getState().activeChatId;
  
  let html = '<div style="display: flex; flex-direction: column; gap: var(--sp-2);">';
  
  section.settings.forEach(setting => {
    const value = settings[setting.key] ?? setting.default ?? false;
    
    if (setting.type === 'toggle') {
      html += `
        <div class="toggle-row" style="display: flex; align-items: center; justify-content: space-between; padding: var(--sp-2) 0;">
          <span style="font-size: var(--text-sm); color: var(--text-primary);">${setting.label}</span>
          <label style="position: relative; display: inline-flex; width: 44px; height: 26px; cursor: pointer; flex-shrink: 0;">
            <input 
              type="checkbox" 
              data-setting="${setting.key}"
              ${value ? 'checked' : ''}
              style="position: absolute; opacity: 0; width: 0; height: 0;"
            >
            <span class="toggle-track" style="
              position: absolute; inset: 0;
              border-radius: var(--r-full);
              background: ${value ? 'var(--accent)' : 'var(--bg-overlay)'};
              transition: background var(--dur-normal) var(--ease-out);
            ">
              <span class="toggle-dot" style="
                position: absolute; top: 3px;
                left: ${value ? '21px' : '3px'};
                width: 20px; height: 20px;
                border-radius: 50%;
                background: white;
                box-shadow: var(--shadow-sm);
                transition: left var(--dur-normal) var(--ease-out);
              "></span>
            </span>
          </label>
        </div>
      `;
    } else if (setting.type === 'number') {
      html += `
        <div class="toggle-row" style="display: flex; align-items: center; justify-content: space-between; padding: var(--sp-2) 0;">
          <span style="font-size: var(--text-sm); color: var(--text-primary);">${setting.label}</span>
          <input 
            type="number" 
            data-setting="${setting.key}"
            value="${value || setting.default}"
            min="${setting.min}"
            max="${setting.max}"
            class="number-input"
            style="
              width: 5rem;
              background: var(--bg-input);
              border-radius: var(--r-lg);
              padding: var(--sp-2) var(--sp-3);
              font-size: var(--text-sm);
              color: var(--text-primary);
              text-align: right;
              border: 1px solid var(--border);
            "
          >
        </div>
      `;
    } else if (setting.type === 'select') {
      const options = setting.options.map(opt => 
        `<option value="${opt.value}" ${value === opt.value ? 'selected' : ''}>${opt.label}</option>`
      ).join('');
      
      html += `
        <div class="toggle-row" style="display: flex; align-items: center; justify-content: space-between; padding: var(--sp-2) 0;">
          <span style="font-size: var(--text-sm); color: var(--text-primary);">${setting.label}</span>
          <select 
            data-setting="${setting.key}"
            class="input"
            style="
              width: auto;
              min-width: 120px;
              padding: var(--sp-2) var(--sp-3);
              background: var(--bg-input);
              border: 1px solid var(--border);
              border-radius: var(--r-lg);
              color: var(--text-primary);
              font-size: var(--text-sm);
            "
          >
            ${options}
          </select>
        </div>
      `;
    } else if (setting.type === 'text') {
      html += `
        <div style="padding: var(--sp-2) 0;">
          <span style="font-size: var(--text-sm); color: var(--text-primary); display: block; margin-bottom: var(--sp-1);">${setting.label}</span>
          <input 
            type="text" 
            data-setting="${setting.key}"
            value="${value || ''}"
            placeholder="${setting.placeholder || ''}"
            class="input"
            style="
              width: 100%;
              padding: var(--sp-2) var(--sp-3);
              background: var(--bg-input);
              border: 1px solid var(--border);
              border-radius: var(--r-lg);
              color: var(--text-primary);
              font-size: var(--text-sm);
            "
          >
        </div>
      `;
    }
  });
  
  html += '</div>';
  
  // Add event listeners script
  html += `
    <script>
      (function() {
        const chatId = '${chatId}';
        const initData = '${initData}';
        
        // Handle toggles
        document.querySelectorAll('[data-setting][type="checkbox"]').forEach(input => {
          input.addEventListener('change', async function() {
            const key = this.dataset.setting;
            const value = this.checked;
            
            // Update toggle visual
            const track = this.nextElementSibling;
            const dot = track.querySelector('.toggle-dot');
            track.style.background = value ? 'var(--accent)' : 'var(--bg-overlay)';
            dot.style.left = value ? '21px' : '3px';
            
            // Save to server
            try {
              await fetch('/api/groups/' + chatId + '/settings/' + key, {
                method: 'PUT',
                headers: {
                  'Content-Type': 'application/json',
                  'x-init-data': initData
                },
                body: JSON.stringify({ value: value })
              });
              
              // Update store
              const store = window.__store;
              if (store) {
                store.setState(s => ({ 
                  settings: { ...s.settings, [key]: value } 
                }));
              }
            } catch (e) {
              console.error('Failed to save setting:', e);
            }
          });
        });
        
        // Handle number inputs
        document.querySelectorAll('[data-setting][type="number"]').forEach(input => {
          input.addEventListener('change', async function() {
            const key = this.dataset.setting;
            const value = parseInt(this.value, 10);
            
            try {
              await fetch('/api/groups/' + chatId + '/settings/' + key, {
                method: 'PUT',
                headers: {
                  'Content-Type': 'application/json',
                  'x-init-data': initData
                },
                body: JSON.stringify({ value: value })
              });
            } catch (e) {
              console.error('Failed to save setting:', e);
            }
          });
        });
        
        // Handle selects
        document.querySelectorAll('[data-setting]:not([type="checkbox"]):not([type="number"])').forEach(input => {
          if (input.tagName === 'SELECT') {
            input.addEventListener('change', async function() {
              const key = this.dataset.setting;
              const value = this.value;
              
              try {
                await fetch('/api/groups/' + chatId + '/settings/' + key, {
                  method: 'PUT',
                  headers: {
                    'Content-Type': 'application/json',
                    'x-init-data': initData
                  },
                  body: JSON.stringify({ value: value })
                });
              } catch (e) {
                console.error('Failed to save setting:', e);
              }
            });
          }
        });
      })();
    </script>
  `;
  
  return html;
}
