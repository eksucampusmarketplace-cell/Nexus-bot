/**
 * miniapp/src/pages/federation.js
 * 
 * TrustNet Federation management page.
 * v22: Restored missing file.
 */

import { t, showToast } from '../../lib/i18n.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';

export async function renderFederationPage(container) {
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  const header = document.createElement('div');
  header.innerHTML = `
    <div style="display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);">
      <div style="font-size:2rem">🌐</div>
      <div>
        <div style="font-size:1.2rem;font-weight:700">${t('nav_trustnet', 'TrustNet')}</div>
        <div style="font-size:0.85rem;color:var(--text-muted)">Federation & cross-group bans</div>
      </div>
    </div>
  `;
  container.appendChild(header);

  // My Federation section
  const myFedSection = document.createElement('div');
  myFedSection.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);margin-bottom:var(--sp-4);';
  myFedSection.innerHTML = `
    <div style="font-weight:600;margin-bottom:var(--sp-3)">${t('my_federation', 'My Federation')}</div>
    
    <div id="my-fed-content">
      <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted)">
        ${t('loading', 'Loading...')}
      </div>
    </div>
  `;
  container.appendChild(myFedSection);

  // Join Federation section
  const joinSection = document.createElement('div');
  joinSection.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);margin-bottom:var(--sp-4);';
  joinSection.innerHTML = `
    <div style="font-weight:600;margin-bottom:var(--sp-3)">${t('join_federation', 'Join Federation')}</div>
    
    <div style="display:flex;gap:var(--sp-2)">
      <input type="text" class="input" id="invite-code" placeholder="${t('invite_code_lbl', 'Enter invite code')}" style="flex:1">
      <button class="btn btn-primary" id="join-fed-btn">${t('join', 'Join')}</button>
    </div>
  `;
  container.appendChild(joinSection);

  // Federation Bans section
  const bansSection = document.createElement('div');
  bansSection.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);';
  bansSection.innerHTML = `
    <div style="font-weight:600;margin-bottom:var(--sp-3)">${t('federation_bans', 'Federation Bans')}</div>
    
    <div class="toggle-row">
      <span>${t('ban_propagation', 'Auto-enforce federation bans')}</span>
      <div class="toggle" id="ban-prop-toggle">
        <div class="toggle-dot"></div>
      </div>
    </div>

    <div class="toggle-row" style="margin-top:var(--sp-3)">
      <span>${t('share_reputation', 'Share reputation scores')}</span>
      <div class="toggle" id="share-rep-toggle">
        <div class="toggle-dot"></div>
      </div>
    </div>
  `;
  container.appendChild(bansSection);

  // Load federation data
  loadFederationData(myFedSection);

  // Toggle functionality
  setupToggle(bansSection.querySelector('#ban-prop-toggle'));
  setupToggle(bansSection.querySelector('#share-rep-toggle'));

  // Join button
  joinSection.querySelector('#join-fed-btn').onclick = async () => {
    const code = joinSection.querySelector('#invite-code').value.trim();
    if (!code) {
      showToast(t('enter_code', 'Please enter an invite code'));
      return;
    }
    
    try {
      showToast(t('joining', 'Joining...'));
      await apiFetch('/api/federation/join', {
        method: 'POST',
        body: JSON.stringify({ invite_code: code })
      });
      showToast(t('joined_success', 'Joined federation!'));
      loadFederationData(myFedSection);
    } catch (err) {
      console.error('Failed to join federation:', err);
      showToast(t('join_failed', 'Failed to join'));
    }
  };
}

function setupToggle(toggle) {
  let enabled = false;
  toggle.onclick = () => {
    enabled = !enabled;
    toggle.style.background = enabled ? 'var(--accent)' : 'var(--bg-input)';
    toggle.querySelector('.toggle-dot').style.transform = enabled ? 'translateX(1.25rem)' : 'translateX(0)';
  };
  return () => enabled;
}

async function loadFederationData(container) {
  try {
    const fed = await apiFetch('/api/federation/my');
    const content = container.querySelector('#my-fed-content');
    
    if (fed && fed.id) {
      content.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-3)">
          <div>
            <div style="font-weight:600">${fed.name || 'Unnamed Federation'}</div>
            <div style="font-size:0.85rem;color:var(--text-muted)">${fed.member_count || 0} members</div>
          </div>
          <button class="btn" id="copy-invite">${t('copy_invite', 'Copy Invite')}</button>
        </div>
        <div style="font-size:0.85rem;color:var(--text-muted)">
          <code>${fed.invite_code || 'N/A'}</code>
        </div>
      `;
      
      content.querySelector('#copy-invite').onclick = () => {
        navigator.clipboard.writeText(fed.invite_code);
        showToast(t('copied', 'Copied!'));
      };
    } else {
      content.innerHTML = `
        <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted)">
          ${t('no_federation', 'Not part of any federation')}
        </div>
        <button class="btn btn-primary" style="width:100%;margin-top:var(--sp-3)" id="create-fed">
          ${t('create_federation', 'Create Federation')}
        </button>
      `;
      
      content.querySelector('#create-fed').onclick = async () => {
        try {
          showToast(t('creating', 'Creating...'));
          await apiFetch('/api/federation/create', { method: 'POST' });
          showToast(t('created', 'Federation created!'));
          loadFederationData(container);
        } catch (err) {
          showToast(t('create_failed', 'Failed to create'));
        }
      };
    }
  } catch (err) {
    container.querySelector('#my-fed-content').innerHTML = `
      <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted)">
        ${t('load_failed', 'Failed to load')}
      </div>
    `;
  }
}
