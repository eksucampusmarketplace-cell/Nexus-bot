/**
 * miniapp/src/pages/captcha.js
 * 
 * Unified Captcha configuration page.
 * Merged from captcha.js + captcha_config.js (duplicate removed).
 */

import { t, showToast } from '../../lib/i18n.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { Toggle } from '../../lib/components.js?v=1.6.0';

export async function renderCaptchaPage(container) {
  const chatId = useStore.getState().activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.innerHTML = `
      <div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">
        <div style="font-size:3rem;margin-bottom:var(--sp-3)">🤖</div>
        <div>${t('select_group', 'Select a group first')}</div>
      </div>
    `;
    return;
  }

  // Load current settings from server
  let currentEnabled = false;
  let currentType = 'button';
  let currentTimeout = 300;
  let currentKickFailures = 3;
  let hasExternalUrl = false;

  try {
    const res = await apiFetch(`/api/groups/${chatId}/captcha`);
    currentEnabled = res.enabled ?? false;
    currentType = res.type ?? 'button';
    currentTimeout = res.timeout ?? 300;
    currentKickFailures = res.kick_failures ?? res.kickFailures ?? 3;
    hasExternalUrl = res.has_external_url ?? false;
  } catch (err) {
    console.error('Failed to load captcha settings:', err);
  }

  const header = document.createElement('div');
  header.innerHTML = `
    <div style="display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);">
      <div style="font-size:2rem">🤖</div>
      <div>
        <div style="font-size:1.2rem;font-weight:700">${t('nav_captcha', 'Captcha')}</div>
        <div style="font-size:0.85rem;color:var(--text-muted)">${t('captcha_subtitle', 'Protect your group from bots')}</div>
      </div>
    </div>
  `;
  container.appendChild(header);

  const section = document.createElement('div');
  section.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);';
  section.innerHTML = `
    <div style="font-weight:600;margin-bottom:var(--sp-3)">${t('section_captcha', 'Captcha Settings')}</div>
    
    <div class="toggle-row" style="display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) 0;">
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
      <div id="webapp-warning" style="display:none;margin-top:var(--sp-2);padding:var(--sp-2);background:var(--warning-dim);border-radius:var(--r-md);font-size:0.85rem;color:var(--warning);"></div>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('timeout_lbl', 'Timeout (seconds)')}
      </label>
      <input type="number" class="input" id="captcha-timeout" value="${currentTimeout}" min="60" max="3600">
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('kick_after_fail', 'Kick after failures')}
      </label>
      <input type="number" class="input" id="kick-failures" value="${currentKickFailures}" min="1" max="10">
      <div style="font-size:0.75rem;color:var(--text-muted);margin-top:var(--sp-1)">
        ${t('kick_failures_hint', 'Number of failed attempts before the user is kicked')}
      </div>
    </div>

    <button class="btn btn-primary" style="margin-top:var(--sp-4);width:100%" id="save-captcha">
      ${t('save_btn', 'Save')}
    </button>
  `;
  container.appendChild(section);

  // Toggle functionality using Toggle component
  let enabled = currentEnabled;
  const toggleWrapper = section.querySelector('#captcha-toggle-wrapper');
  toggleWrapper.appendChild(Toggle({
    checked: currentEnabled,
    onChange: (val) => { enabled = val; }
  }));

  // Set initial select value
  const typeSelect = section.querySelector('#captcha-type');
  typeSelect.value = currentType;

  // Show/hide WebApp warning based on selection and env status
  const webappWarning = section.querySelector('#webapp-warning');
  const webappModes = ['emoji', 'word_scramble', 'odd_one_out', 'number_sequence', 'webapp'];
  
  function updateWarning() {
    if (webappModes.includes(typeSelect.value)) {
      if (hasExternalUrl) {
        webappWarning.style.display = 'block';
        webappWarning.style.background = 'rgba(var(--accent-rgb), 0.08)';
        webappWarning.style.color = 'var(--success)';
        webappWarning.textContent = '\u2705 RENDER_EXTERNAL_URL is configured. WebApp captcha modes are available.';
      } else {
        webappWarning.style.display = 'block';
        webappWarning.style.background = 'var(--warning-dim)';
        webappWarning.style.color = 'var(--warning)';
        webappWarning.textContent = '\u26a0\ufe0f WebApp modes require RENDER_EXTERNAL_URL to be set in your environment.';
      }
    } else {
      webappWarning.style.display = 'none';
    }
  }
  updateWarning();
  typeSelect.addEventListener('change', updateWarning);

  // Save functionality
  section.querySelector('#save-captcha').onclick = async () => {
    const type = typeSelect.value;
    const timeout = parseInt(section.querySelector('#captcha-timeout').value);
    const kickFailures = parseInt(section.querySelector('#kick-failures').value);
    
    try {
      showToast(t('loading', 'Saving...'));
      await apiFetch(`/api/groups/${chatId}/captcha`, {
        method: 'POST',
        body: JSON.stringify({ enabled, type, timeout, kick_failures: kickFailures })
      });
      showToast(t('toast_save_success', 'Saved successfully!'));
    } catch (err) {
      console.error('Failed to save captcha:', err);
      showToast(t('error', 'Failed to save'));
    }
  };
}

// Re-export for backward compatibility with captcha_config imports
export { renderCaptchaPage as renderCaptchaConfigPage };
