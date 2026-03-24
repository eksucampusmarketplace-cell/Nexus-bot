/**
 * miniapp/src/pages/history.js
 * 
 * Name history (Sangmata) page.
 */

import { t } from '../../lib/i18n.js?v=1.6.0';
import { showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { Toggle } from '../../lib/components.js?v=1.6.0';

export async function renderHistoryPage(container) {
  const chatId = useStore.getState().activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.innerHTML = `
      <div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">
        <div style="font-size:3rem;margin-bottom:var(--sp-3)">📜</div>
        <div>${t('select_group', 'Select a group first')}</div>
      </div>
    `;
    return;
  }

  // Load current settings
  let currentEnabled = false;
  let currentLimit = 10;

  try {
    const res = await apiFetch(`/api/groups/${chatId}/name-history`);
    currentEnabled = res.enabled ?? false;
    currentLimit = res.limit ?? 10;
  } catch (err) {
    console.debug('Failed to load history settings:', err);
  }

  const header = document.createElement('div');
  header.innerHTML = `
    <div style="display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);">
      <div style="font-size:2rem">📜</div>
      <div>
        <div style="font-size:1.2rem;font-weight:700">${t('nav_history', 'Name History')}</div>
        <div style="font-size:0.85rem;color:var(--text-muted)">${t('history_subtitle', 'Track user name changes')}</div>
      </div>
    </div>
  `;
  container.appendChild(header);

  const section = document.createElement('div');
  section.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);';
  section.innerHTML = `
    <div style="font-weight:600;margin-bottom:var(--sp-3)">${t('settings', 'Settings')}</div>
    
    <div class="toggle-row" style="display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) 0;">
      <span>${t('enable_label', 'Track Name Changes')}</span>
      <div id="history-toggle-wrapper"></div>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('history_limit', 'History Limit (per user)')}
      </label>
      <input type="number" class="input" id="history-limit" value="${currentLimit}" min="1" max="50">
    </div>

    <button class="btn btn-primary" style="margin-top:var(--sp-4);width:100%" id="save-history">
      ${t('save_btn', 'Save')}
    </button>

    <div style="margin-top:var(--sp-6);padding-top:var(--sp-4);border-top:1px solid var(--border)">
      <div style="font-weight:600;margin-bottom:var(--sp-3)">${t('recent_changes', 'Recent Name Changes')}</div>
      <div id="history-list" style="display:flex;flex-direction:column;gap:var(--sp-2)">
        <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);font-size:0.85rem">
          ${t('no_history', 'No recent name changes')}
        </div>
      </div>
    </div>
  `;
  container.appendChild(section);

  // Toggle functionality using Toggle component (was using raw div before)
  let enabled = currentEnabled;
  const toggleWrapper = section.querySelector('#history-toggle-wrapper');
  toggleWrapper.appendChild(Toggle({
    checked: currentEnabled,
    onChange: (val) => { enabled = val; }
  }));

  // Save functionality
  section.querySelector('#save-history').onclick = async () => {
    const limit = parseInt(section.querySelector('#history-limit').value);

    try {
      showToast(t('loading', 'Saving...'));
      await apiFetch(`/api/groups/${chatId}/name-history`, {
        method: 'POST',
        body: JSON.stringify({ enabled, limit })
      });
      showToast(t('toast_save_success', 'Saved successfully!'));
    } catch (err) {
      console.error('Failed to save history settings:', err);
      showToast(t('error', 'Failed to save'));
    }
  };

  // Load recent history (chatId passed as parameter, not relying on closure of undefined var)
  loadRecentHistory(chatId);
}

async function loadRecentHistory(chatId) {
  const list = document.getElementById('history-list');
  if (!list) return;

  try {
    const history = await apiFetch(`/api/groups/${chatId}/name-history/recent`).catch(() => []);
    
    if (!history || history.length === 0) {
      return;
    }

    list.innerHTML = '';
    history.forEach(entry => {
      const item = document.createElement('div');
      item.style.cssText = 'display:flex;align-items:center;gap:var(--sp-2);padding:var(--sp-2);background:var(--bg-input);border-radius:var(--r-lg);font-size:0.85rem;';
      item.innerHTML = `
        <span style="font-weight:600">${escapeText(entry.user_name || 'Unknown')}</span>
        <span style="color:var(--text-muted)">\u2192</span>
        <span>${escapeText(entry.old_name || '')}</span>
        <span style="color:var(--text-muted);margin-left:auto">${new Date(entry.changed_at).toLocaleDateString()}</span>
      `;
      list.appendChild(item);
    });
  } catch (err) {
    console.error('Failed to load history:', err);
  }
}

function escapeText(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
