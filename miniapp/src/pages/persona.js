/**
 * miniapp/src/pages/persona.js
 * 
 * Bot persona / personality configuration page.
 */

import { t } from '../../lib/i18n.js?v=1.6.0';
import { showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

export async function renderPersonaPage(container) {
  const chatId = useStore.getState().activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.innerHTML = `
      <div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">
        <div style="font-size:3rem;margin-bottom:var(--sp-3)">🎭</div>
        <div>Select a group first</div>
      </div>
    `;
    return;
  }

  const header = document.createElement('div');
  header.innerHTML = `
    <div style="display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);">
      <div style="font-size:2rem">🎭</div>
      <div>
        <div style="font-size:1.2rem;font-weight:700">${t('nav_persona', 'Bot Persona')}</div>
        <div style="font-size:0.85rem;color:var(--text-muted)">Customize bot personality and tone</div>
      </div>
    </div>
  `;
  container.appendChild(header);

  const section = document.createElement('div');
  section.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);';
  section.innerHTML = `
    <div style="font-weight:600;margin-bottom:var(--sp-3)">${t('personality_settings', 'Personality Settings')}</div>
    
    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('bot_tone', 'Bot Tone')}
      </label>
      <select class="input" id="bot-tone">
        <option value="friendly">🙂 Friendly</option>
        <option value="professional">👔 Professional</option>
        <option value="casual">😎 Casual</option>
        <option value="strict">⚖️ Strict</option>
        <option value="funny">😄 Funny</option>
      </select>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('greeting_style', 'Greeting Style')}
      </label>
      <select class="input" id="greeting-style">
        <option value="enthusiastic">🎉 Enthusiastic</option>
        <option value="welcoming">🤗 Welcoming</option>
        <option value="formal">📋 Formal</option>
        <option value="short">💬 Short & Sweet</option>
      </select>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('custom_welcome', 'Custom Welcome Message')}
      </label>
      <textarea class="input" id="welcome-message" rows="3" placeholder="Custom welcome message (optional)..."></textarea>
      <div style="font-size:0.75rem;color:var(--text-muted);margin-top:var(--sp-1)">
        Use {name} for user's name, {group} for group name
      </div>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('emoji_style', 'Emoji Usage')}
      </label>
      <select class="input" id="emoji-style">
        <option value="plenty">🎊 Plenty</option>
        <option value="moderate">😊 Moderate</option>
        <option value="minimal">😐 Minimal</option>
        <option value="none">🚫 None</option>
      </select>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('preview', 'Preview')}
      </label>
      <div id="persona-preview" style="padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);border:1px solid var(--border);font-size:0.85rem;">
        Loading preview...
      </div>
    </div>

    <button class="btn btn-primary" style="margin-top:var(--sp-4);width:100%" id="save-persona">
      ${t('save_btn', 'Save')}
    </button>
  `;
  container.appendChild(section);

  // Update preview on change
  const updatePreview = () => {
    const tone = section.querySelector('#bot-tone').value;
    const greeting = section.querySelector('#greeting-style').value;
    const welcomeMsg = section.querySelector('#welcome-message').value;
    
    let preview = '';
    if (welcomeMsg.trim()) {
      preview = welcomeMsg.replace('{name}', 'New User').replace('{group}', 'This Group');
    } else {
      const greetings = {
        enthusiastic: ['🎉 Welcome to the group {name}!', '🌟 So happy to have you here, {name}!'],
        welcoming: ['🤗 Welcome aboard, {name}!', '👋 Great to see you, {name}!'],
        formal: ['📋 Welcome, {name}. We are pleased to have you.', '👋 Hello {name}, welcome to the group.'],
        short: ['Hi {name}!', 'Welcome!']
      };
      const msgList = greetings[greeting] || greetings.welcoming;
      preview = msgList[Math.floor(Math.random() * msgList.length)].replace('{name}', 'New User');
    }

    const emojis = {
      plenty: '🎉 🌟 ✨ 💫',
      moderate: '😊 👍 👋',
      minimal: '✓ ✓',
      none: ''
    };

    section.querySelector('#persona-preview').textContent = preview + ' ' + emojis[section.querySelector('#emoji-style').value];
  };

  // Attach event listeners
  section.querySelectorAll('select, textarea').forEach(el => {
    el.addEventListener('change', updatePreview);
    el.addEventListener('input', updatePreview);
  });

  // Initial preview
  updatePreview();

  // Save functionality
  section.querySelector('#save-persona').onclick = async () => {
    const tone = section.querySelector('#bot-tone').value;
    const greetingStyle = section.querySelector('#greeting-style').value;
    const welcomeMessage = section.querySelector('#welcome-message').value;
    const emojiStyle = section.querySelector('#emoji-style').value;

    try {
      showToast(t('loading', 'Saving...'));
      await apiFetch(`/api/groups/${chatId}/personality`, {
        method: 'POST',
        body: JSON.stringify({ tone, greetingStyle, welcomeMessage, emojiStyle })
      });
      showToast(t('toast_save_success', 'Saved successfully!'));
    } catch (err) {
      console.error('Failed to save persona:', err);
      showToast(t('error', 'Failed to save'));
    }
  };
}
