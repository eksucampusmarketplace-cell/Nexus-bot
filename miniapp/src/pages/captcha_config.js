/**
 * miniapp/src/pages/captcha_config.js
 * 
 * Extended Captcha configuration page with 10 modes.
 * v22: Restored missing file.
 */

import { t, showToast } from '../../lib/i18n.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

export async function renderCaptchaConfigPage(container) {
  const chatId = useStore.getState().activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.innerHTML = `
      <div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">
        <div style="font-size:3rem;margin-bottom:var(--sp-3)">🤖</div>
        <div>Select a group first</div>
      </div>
    `;
    return;
  }

  const header = document.createElement('div');
  header.innerHTML = `
    <div style="display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);">
      <div style="font-size:2rem">🤖</div>
      <div>
        <div style="font-size:1.2rem;font-weight:700">${t('nav_captcha', 'Captcha')}</div>
        <div style="font-size:0.85rem;color:var(--text-muted)">10 modes to stop bots</div>
      </div>
    </div>
  `;
  container.appendChild(header);

  const section = document.createElement('div');
  section.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);';
  section.innerHTML = `
    <div style="font-weight:600;margin-bottom:var(--sp-3)">${t('section_captcha', 'Captcha Settings')}</div>
    
    <div class="toggle-row">
      <span>${t('enable_label', 'Enable Captcha')}</span>
      <div class="toggle" id="captcha-toggle">
        <div class="toggle-dot"></div>
      </div>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('captcha_mode', 'Captcha Mode')}
      </label>
      <select class="input" id="captcha-mode">
        <optgroup label="Classic (3)">
          <option value="button">🔘 Button Click</option>
          <option value="math">🔢 Math Problem</option>
          <option value="word">🔤 Word Scramble</option>
        </optgroup>
        <optgroup label="WebApp (7)">
          <option value="emoji">😀 Emoji Match</option>
          <option value="color">🎨 Color Tap</option>
          <option value="puzzle">🧩 Slide Puzzle</option>
          <option value="catch">🎣 Catch the Object</option>
          <option value="sequence">🔢 Number Sequence</option>
          <option value="swipe">👆 Swipe Pattern</option>
          <option value="captcha">🛡️ Image CAPTCHA</option>
        </optgroup>
      </select>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('timeout_lbl', 'Timeout (seconds)')}
      </label>
      <input type="number" class="input" id="captcha-timeout" value="300" min="60" max="3600">
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('kick_after_fail', 'Kick after failures')}
      </label>
      <input type="number" class="input" id="kick-failures" value="3" min="1" max="10">
    </div>

    <button class="btn btn-primary" style="margin-top:var(--sp-4);width:100%" id="save-captcha">
      ${t('save_btn', 'Save')}
    </button>
  `;
  container.appendChild(section);

  // Load current settings
  loadCaptchaSettings(section, chatId);

  // Toggle functionality
  const toggle = section.querySelector('#captcha-toggle');
  let enabled = false;
  
  toggle.onclick = () => {
    enabled = !enabled;
    toggle.style.background = enabled ? 'var(--accent)' : 'var(--bg-input)';
    toggle.querySelector('.toggle-dot').style.transform = enabled ? 'translateX(1.25rem)' : 'translateX(0)';
  };

  // Save functionality
  section.querySelector('#save-captcha').onclick = async () => {
    const mode = section.querySelector('#captcha-mode').value;
    const timeout = parseInt(section.querySelector('#captcha-timeout').value);
    const kickFailures = parseInt(section.querySelector('#kick-failures').value);
    
    try {
      showToast(t('loading', 'Saving...'));
      await apiFetch(`/api/groups/${chatId}/captcha`, {
        method: 'POST',
        body: JSON.stringify({ enabled, mode, timeout, kickFailures })
      });
      showToast(t('toast_save_success', 'Saved successfully!'));
    } catch (err) {
      console.error('Failed to save captcha:', err);
      showToast(t('error', 'Failed to save'));
    }
  };
}

async function loadCaptchaSettings(section, chatId) {
  try {
    const settings = await apiFetch(`/api/groups/${chatId}/captcha`);
    if (settings) {
      const toggle = section.querySelector('#captcha-toggle');
      if (settings.enabled) {
        toggle.style.background = 'var(--accent)';
        toggle.querySelector('.toggle-dot').style.transform = 'translateX(1.25rem)';
      }
      if (settings.mode) {
        section.querySelector('#captcha-mode').value = settings.mode;
      }
      if (settings.timeout) {
        section.querySelector('#captcha-timeout').value = settings.timeout;
      }
      if (settings.kick_failures) {
        section.querySelector('#kick-failures').value = settings.kick_failures;
      }
    }
  } catch (err) {
    console.debug('Failed to load captcha settings:', err);
  }
}
