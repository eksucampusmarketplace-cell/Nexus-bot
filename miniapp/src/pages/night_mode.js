/**
 * miniapp/src/pages/night_mode.js
 * 
 * Night mode configuration page.
 */

import { t, showToast } from '../lib/i18n.js?v=1.6.0';
import { apiFetch } from '../lib/api.js?v=1.6.0';

export async function renderNightModePage(container) {
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  const header = document.createElement('div');
  header.innerHTML = `
    <div style="display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);">
      <div style="font-size:2rem">🌙</div>
      <div>
        <div style="font-size:1.2rem;font-weight:700">${t('nav_night_mode', 'Night Mode')}</div>
        <div style="font-size:0.85rem;color:var(--text-muted)">Schedule restricted hours</div>
      </div>
    </div>
  `;
  container.appendChild(header);

  const section = document.createElement('div');
  section.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);';
  section.innerHTML = `
    <div style="font-weight:600;margin-bottom:var(--sp-3)">${t('night_schedule', 'Night Schedule')}</div>
    
    <div class="toggle-row">
      <span>${t('enable_label', 'Enable Night Mode')}</span>
      <div class="toggle" id="night-toggle">
        <div class="toggle-dot"></div>
      </div>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('night_start_lbl', 'Start Time')}
      </label>
      <input type="time" class="input" id="night-start" value="23:00">
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('night_end_lbl', 'End Time')}
      </label>
      <input type="time" class="input" id="night-end" value="07:00">
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('timezone_lbl', 'Timezone')}
      </label>
      <select class="input" id="timezone">
        <option value="UTC">UTC</option>
        <option value="America/New_York">America/New_York</option>
        <option value="Europe/London">Europe/London</option>
        <option value="Europe/Paris">Europe/Paris</option>
        <option value="Asia/Dubai">Asia/Dubai</option>
        <option value="Asia/Kolkata">Asia/Kolkata</option>
        <option value="Asia/Tokyo">Asia/Tokyo</option>
        <option value="Australia/Sydney">Australia/Sydney</option>
      </select>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('night_message_lbl', 'Night Message')}
      </label>
      <textarea class="input" id="night-message" rows="3" placeholder="Message shown when night mode activates...">🌙 Night mode is now active. Group permissions are restricted.</textarea>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('morning_msg_lbl', 'Morning Message')}
      </label>
      <textarea class="input" id="morning-message" rows="3" placeholder="Message shown when night mode ends...">☀️ Good morning! Group permissions have been restored.</textarea>
    </div>

    <button class="btn btn-primary" style="margin-top:var(--sp-4);width:100%" id="save-night">
      ${t('save_btn', 'Save')}
    </button>
  `;
  container.appendChild(section);

  // Toggle functionality
  const toggle = section.querySelector('#night-toggle');
  let enabled = false;
  
  toggle.onclick = () => {
    enabled = !enabled;
    toggle.style.background = enabled ? 'var(--accent)' : 'var(--bg-input)';
    toggle.querySelector('.toggle-dot').style.transform = enabled ? 'translateX(1.25rem)' : 'translateX(0)';
  };

  // Save functionality
  section.querySelector('#save-night').onclick = async () => {
    const startTime = section.querySelector('#night-start').value;
    const endTime = section.querySelector('#night-end').value;
    const timezone = section.querySelector('#timezone').value;
    const nightMessage = section.querySelector('#night-message').value;
    const morningMessage = section.querySelector('#morning-message').value;

    try {
      showToast(t('loading', 'Saving...'));
      await apiFetch('/api/groups/{chat_id}/night-mode', {
        method: 'POST',
        body: JSON.stringify({ enabled, startTime, endTime, timezone, nightMessage, morningMessage })
      });
      showToast(t('toast_save_success', 'Saved successfully!'));
    } catch (err) {
      console.error('Failed to save night mode:', err);
      showToast(t('error', 'Failed to save'));
    }
  };
}
