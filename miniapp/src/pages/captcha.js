/**
 * miniapp/src/pages/captcha.js
 * 
 * Captcha configuration page.
 */

import { t, showToast } from '../../lib/i18n.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { Toggle } from '../../lib/components.js';

export async function renderCaptchaPage(container) {
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

  // Load current settings from server
  let currentEnabled = false;
  let currentType = 'button';
  let currentTimeout = 300;

  try {
    showToast(t('loading', 'Loading...'));
    const res = await apiFetch(`/api/groups/${chatId}/captcha`);
    currentEnabled = res.enabled ?? false;
    currentType = res.type ?? 'button';
    currentTimeout = res.timeout ?? 300;
  } catch (err) {
    console.error('Failed to load captcha settings:', err);
    showToast(t('error', 'Failed to load settings'));
  }

  const header = document.createElement('div');
  header.innerHTML = `
    <div style="display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);">
      <div style="font-size:2rem">🤖</div>
      <div>
        <div style="font-size:1.2rem;font-weight:700">${t('nav_captcha', 'Captcha')}</div>
        <div style="font-size:0.85rem;color:var(--text-muted)">Protect your group from bots</div>
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
      <div id="captcha-toggle-wrapper"></div>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('captcha_type', 'Captcha Type')}
      </label>
      <select class="input" id="captcha-type">
        <optgroup label="Classic (works immediately)">
          <option value="button">🔘 Button Click</option>
          <option value="math">🔢 Math Problem</option>
          <option value="text">🔤 Word Scramble</option>
        </optgroup>
        <optgroup label="WebApp (requires RENDER_EXTERNAL_URL)">
          <option value="emoji">😀 Emoji Match</option>
          <option value="word_scramble">🔤 Word Unscramble</option>
          <option value="odd_one_out">🔍 Odd One Out</option>
          <option value="number_sequence">🔢 Number Sequence</option>
          <option value="webapp">🌐 Generic WebApp</option>
        </optgroup>
      </select>
      <div id="webapp-warning" style="display:none;margin-top:var(--sp-2);padding:var(--sp-2);background:var(--warning-dim);border-radius:var(--r-md);font-size:0.85rem;color:var(--warning);">
        ⚠️ WebApp modes require RENDER_EXTERNAL_URL to be set in your environment.
      </div>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('timeout_lbl', 'Timeout (seconds)')}
      </label>
      <input type="number" class="input" id="captcha-timeout" value="${currentTimeout}" min="60" max="3600">
    </div>

    <button class="btn btn-primary" style="margin-top:var(--sp-4);width:100%" id="save-captcha">
      ${t('save_btn', 'Save')}
    </button>
  `;
  container.appendChild(section);

  // Toggle functionality using Toggle component
  let enabled = currentEnabled;
  const toggleWrapper = section.querySelector('#captcha-toggle-wrapper');
  const toggleEl = Toggle({
    checked: currentEnabled,
    onChange: (val) => { enabled = val; }
  });
  toggleWrapper.appendChild(toggleEl);

  // Set initial select value
  const typeSelect = section.querySelector('#captcha-type');
  typeSelect.value = currentType;

  // Show/hide WebApp warning based on selection
  const webappWarning = section.querySelector('#webapp-warning');
  const webappModes = ['emoji', 'word_scramble', 'odd_one_out', 'number_sequence', 'webapp'];
  
  function updateWarning() {
    webappWarning.style.display = webappModes.includes(typeSelect.value) ? 'block' : 'none';
  }
  updateWarning();
  typeSelect.addEventListener('change', updateWarning);

  // Save functionality
  section.querySelector('#save-captcha').onclick = async () => {
    const type = section.querySelector('#captcha-type').value;
    const timeout = parseInt(section.querySelector('#captcha-timeout').value);
    
    try {
      showToast(t('loading', 'Saving...'));
      await apiFetch(`/api/groups/${chatId}/captcha`, {
        method: 'POST',
        body: { enabled, type, timeout }
      });
      showToast(t('toast_save_success', 'Saved successfully!'));
    } catch (err) {
      console.error('Failed to save captcha:', err);
      showToast(t('error', 'Failed to save'));
    }
  };
}
