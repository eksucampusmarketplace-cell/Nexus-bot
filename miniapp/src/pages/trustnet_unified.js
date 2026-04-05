/**
 * miniapp/src/pages/trustnet_unified.js
 *
 * Unified TrustNet, Federation, and Community Vote management page.
 * Combines functionality from separate pages into a tabbed interface.
 */

import { t } from '../../lib/i18n.js?v=1.6.0';
import { showToast, EmptyState, Toggle, Card } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

const store = useStore;

export async function renderTrustnetUnifiedPage(container) {
  const chatId = store.getState().activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '🌐',
      title: 'Select a group',
      description: 'Choose a group to manage TrustNet, Federation, and Community Vote settings.'
    }));
    return;
  }

  const header = document.createElement('div');
  header.innerHTML = `
    <div style="display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);">
      <div style="font-size:2rem">🌐</div>
      <div>
        <div style="font-size:1.2rem;font-weight:700">${t('nav_trustnet', 'TrustNet & Federation')}</div>
        <div style="font-size:0.85rem;color:var(--text-muted)">Cross-group ban sharing and community moderation</div>
      </div>
    </div>
  `;
  container.appendChild(header);

  // Tab navigation
  const tabs = [
    { id: 'federation', label: '🔗 Federation', active: true },
    { id: 'community', label: '⚖️ Community Vote', active: false },
  ];

  const tabBar = document.createElement('div');
  tabBar.style.cssText = 'display:flex;gap:var(--sp-1);margin-bottom:var(--sp-4);background:var(--bg-input);padding:4px;border-radius:var(--r-xl);overflow-x:auto;';
  
  let activeTab = 'federation';

  tabs.forEach((tab, i) => {
    const btn = document.createElement('button');
    btn.textContent = tab.label;
    btn.dataset.tab = tab.id;
    btn.style.cssText = `flex:1;padding:var(--sp-2) var(--sp-3);border:none;border-radius:var(--r-lg);font-size:var(--text-sm);font-weight:var(--fw-medium);cursor:pointer;white-space:nowrap;transition:all var(--dur-fast);background:${i===0?'var(--bg-card)':'transparent'};color:${i===0?'var(--text-primary)':'var(--text-muted)'};`;
    btn.onclick = () => {
      activeTab = tab.id;
      tabBar.querySelectorAll('[data-tab]').forEach(b => {
        const isActive = b.dataset.tab === tab.id;
        b.style.background = isActive ? 'var(--bg-card)' : 'transparent';
        b.style.color = isActive ? 'var(--text-primary)' : 'var(--text-muted)';
      });
      renderActiveTab();
    };
    tabBar.appendChild(btn);
  });
  container.appendChild(tabBar);

  const content = document.createElement('div');
  container.appendChild(content);

  async function renderActiveTab() {
    content.innerHTML = '';
    if (activeTab === 'federation') {
      await renderFederationTab(content, chatId);
    } else if (activeTab === 'community') {
      await renderCommunityTab(content, chatId);
    }
  }

  await renderActiveTab();
}

async function renderFederationTab(container, chatId) {
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
  loadFederationData(myFedSection, chatId);

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
        body: JSON.stringify({ invite_code: code, chat_id: chatId })
      });
      showToast(t('joined_success', 'Joined federation!'));
      loadFederationData(myFedSection, chatId);
    } catch (err) {
      console.error('Failed to join federation:', err);
      const errorMsg = err.message || t('join_failed', 'Failed to join');
      showToast(errorMsg);
    }
  };
}

async function renderCommunityTab(container, chatId) {
  // Load current settings
  let currentVoteEnabled = false;
  let currentScamEnabled = true;
  let currentThreshold = 5;
  let currentTimeout = 10;
  let currentAction = 'ban';

  try {
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

function setupToggle(toggle) {
  let enabled = false;
  toggle.onclick = () => {
    enabled = !enabled;
    toggle.style.background = enabled ? 'var(--accent)' : 'var(--bg-input)';
    toggle.querySelector('.toggle-dot').style.transform = enabled ? 'translateX(1.25rem)' : 'translateX(0)';
  };
  return () => enabled;
}

async function loadFederationData(container, chatId) {
  try {
    const fed = await apiFetch('/api/federation/my');
    const content = container.querySelector('#my-fed-content');
    
    if (fed && fed.length > 0 && fed[0].id) {
      const f = fed[0];
      content.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-3)">
          <div>
            <div style="font-weight:600">${f.name || 'Unnamed Federation'}</div>
            <div style="font-size:0.85rem;color:var(--text-muted)">${f.member_count || 0} members · ${f.ban_count || 0} shared bans</div>
          </div>
          <button class="btn" id="copy-invite">📋 Copy Invite</button>
        </div>
        <div style="font-size:0.85rem;color:var(--text-muted)">
          <code>${f.invite_code || 'N/A'}</code>
        </div>
      `;
      
      content.querySelector('#copy-invite').onclick = () => {
        navigator.clipboard.writeText(`/jointrust ${f.invite_code}`);
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
        if (!chatId) {
          showToast(t('select_group_first', 'Please select a group first'));
          return;
        }
        const name = prompt(t('enter_fed_name', 'Enter federation name:'));
        if (!name || !name.trim()) {
          return;
        }
        try {
          showToast(t('creating', 'Creating...'));
          await apiFetch('/api/federation/create', { 
            method: 'POST',
            body: JSON.stringify({ name: name.trim(), chat_id: chatId })
          });
          showToast(t('created', 'Federation created!'));
          loadFederationData(container, chatId);
        } catch (err) {
          console.error('Failed to create federation:', err);
          showToast(t('create_failed', 'Failed to create') + (err.message ? ': ' + err.message : ''));
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
