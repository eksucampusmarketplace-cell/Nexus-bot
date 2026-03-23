/**
 * miniapp/src/pages/community_vote.js
 * 
 * Community vote configuration page.
 */

import { t } from '../../lib/i18n.js?v=1.6.0';
import { showToast, Toggle } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

export async function renderCommunityVotePage(container) {
  const chatId = useStore.getState().activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.innerHTML = `
      <div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">
        <div style="font-size:3rem;margin-bottom:var(--sp-3)">⚖️</div>
        <div>Select a group first</div>
      </div>
    `;
    return;
  }

  const header = document.createElement('div');
  header.innerHTML = `
    <div style="display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);">
      <div style="font-size:2rem">⚖️</div>
      <div>
        <div style="font-size:1.2rem;font-weight:700">${t('nav_community_vote', 'Community Vote')}</div>
        <div style="font-size:0.85rem;color:var(--text-muted)">Let members vote on suspicious users</div>
      </div>
    </div>
  `;
  container.appendChild(header);

  // Load current settings from server
  let currentVoteEnabled = false;
  let currentScamEnabled = true;
  let currentThreshold = 5;
  let currentTimeout = 10;
  let currentAction = 'ban';

  try {
    showToast(t('loading', 'Loading...'));
    const res = await apiFetch(`/api/groups/${chatId}/community-vote`);
    currentVoteEnabled = res.enabled ?? false;
    currentScamEnabled = res.autoDetectScams ?? true;
    currentThreshold = res.threshold ?? 5;
    currentTimeout = res.timeout ?? 10;
    currentAction = res.action ?? 'ban';
  } catch (err) {
    console.error('Failed to load community vote settings:', err);
  }

  const section = document.createElement('div');
  section.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);';
  section.innerHTML = `
    <div style="font-weight:600;margin-bottom:var(--sp-3)">${t('vote_settings', 'Vote Settings')}</div>
    
    <div class="toggle-row">
      <span>${t('enable_label', 'Enable Community Vote')}</span>
      <div id="vote-toggle-wrapper"></div>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('vote_threshold', 'Vote Threshold')}
      </label>
      <input type="number" class="input" id="vote-threshold" value="${currentThreshold}" min="3" max="20">
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('timeout_lbl', 'Vote Timeout (minutes)')}
      </label>
      <input type="number" class="input" id="vote-timeout" value="${currentTimeout}" min="5" max="60">
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('vote_action', 'Action on Vote Pass')}
      </label>
      <select class="input" id="vote-action">
        <option value="ban">Ban</option>
        <option value="kick">Kick</option>
        <option value="mute">Mute</option>
      </select>
    </div>

    <div class="toggle-row" style="margin-top:var(--sp-4)">
      <span>${t('auto_detect_scams', 'Auto-Detect Scams')}</span>
      <div id="scam-toggle-wrapper"></div>
    </div>

    <button class="btn btn-primary" style="margin-top:var(--sp-4);width:100%" id="save-vote">
      ${t('save_btn', 'Save')}
    </button>
  `;
  container.appendChild(section);

  // Toggle functionality using Toggle component
  let voteEnabled = currentVoteEnabled;
  let scamEnabled = currentScamEnabled;

  const voteToggleWrapper = section.querySelector('#vote-toggle-wrapper');
  voteToggleWrapper.appendChild(Toggle({
    checked: currentVoteEnabled,
    onChange: (val) => { voteEnabled = val; }
  }));

  const scamToggleWrapper = section.querySelector('#scam-toggle-wrapper');
  scamToggleWrapper.appendChild(Toggle({
    checked: currentScamEnabled,
    onChange: (val) => { scamEnabled = val; }
  }));

  // Set initial select value
  section.querySelector('#vote-action').value = currentAction;

  // Save functionality
  section.querySelector('#save-vote').onclick = async () => {
    const threshold = parseInt(section.querySelector('#vote-threshold').value);
    const timeout = parseInt(section.querySelector('#vote-timeout').value);
    const action = section.querySelector('#vote-action').value;

    try {
      showToast(t('loading', 'Saving...'));
      await apiFetch(`/api/groups/${chatId}/community-vote`, {
        method: 'POST',
        body: JSON.stringify({ enabled: voteEnabled, threshold, timeout, action, autoDetectScams: scamEnabled })
      });
      showToast(t('toast_save_success', 'Saved successfully!'));
    } catch (err) {
      console.error('Failed to save vote settings:', err);
      showToast(t('error', 'Failed to save'));
    }
  };
}
