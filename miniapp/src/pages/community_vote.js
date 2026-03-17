/**
 * miniapp/src/pages/community_vote.js
 * 
 * Community vote configuration page.
 */

import { t, showToast } from '../../lib/i18n.js?v=1.6.0';
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

  const section = document.createElement('div');
  section.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);';
  section.innerHTML = `
    <div style="font-weight:600;margin-bottom:var(--sp-3)">${t('vote_settings', 'Vote Settings')}</div>
    
    <div class="toggle-row">
      <span>${t('enable_label', 'Enable Community Vote')}</span>
      <div class="toggle" id="vote-toggle">
        <div class="toggle-dot"></div>
      </div>
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('vote_threshold', 'Vote Threshold')}
      </label>
      <input type="number" class="input" id="vote-threshold" value="5" min="3" max="20">
    </div>

    <div style="margin-top:var(--sp-4)">
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
        ${t('timeout_lbl', 'Vote Timeout (minutes)')}
      </label>
      <input type="number" class="input" id="vote-timeout" value="10" min="5" max="60">
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
      <div class="toggle" id="scam-toggle">
        <div class="toggle-dot"></div>
      </div>
    </div>

    <button class="btn btn-primary" style="margin-top:var(--sp-4);width:100%" id="save-vote">
      ${t('save_btn', 'Save')}
    </button>
  `;
  container.appendChild(section);

  // Toggle functionality
  const voteToggle = section.querySelector('#vote-toggle');
  const scamToggle = section.querySelector('#scam-toggle');
  let voteEnabled = false;
  let scamEnabled = true;

  voteToggle.onclick = () => {
    voteEnabled = !voteEnabled;
    voteToggle.style.background = voteEnabled ? 'var(--accent)' : 'var(--bg-input)';
    voteToggle.querySelector('.toggle-dot').style.transform = voteEnabled ? 'translateX(1.25rem)' : 'translateX(0)';
  };

  scamToggle.onclick = () => {
    scamEnabled = !scamEnabled;
    scamToggle.style.background = scamEnabled ? 'var(--accent)' : 'var(--bg-input)';
    scamToggle.querySelector('.toggle-dot').style.transform = scamEnabled ? 'translateX(1.25rem)' : 'translateX(0)';
  };

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
