/**
 * miniapp/src/pages/federation.js
 * 
 * TrustNet Federation management page.
 * v22: Restored missing file.
 */

import { t } from '../../lib/i18n.js?v=1.6.0';
import { showToast, EmptyState } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

export async function renderFederationPage(container) {
  const chatId = useStore?.getState()?.activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '🔗',
      title: 'Select a group',
      description: 'Choose a group from the dropdown above to manage federation settings.'
    }));
    return;
  }

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
  bansSection.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);margin-bottom:var(--sp-4);';
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
  
  // Federation Name History section
  const historySection = document.createElement('div');
  historySection.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);';
  historySection.innerHTML = `
    <div style="font-weight:600;margin-bottom:var(--sp-3)">Federation Name History</div>
    
    <div class="toggle-row">
      <span>Enable cross-group name history</span>
      <div class="toggle" id="fed-history-toggle">
        <div class="toggle-dot"></div>
      </div>
    </div>

    <div style="margin-top:var(--sp-3);font-size:0.85rem;color:var(--text-muted)">
      Track and share name changes across all groups in your federation
    </div>
    
    <div id="fed-history-content" style="margin-top:var(--sp-3);">
      <!-- Will be populated if user has a federation -->
    </div>
  `;
  container.appendChild(historySection);

  // Load federation data
  loadFederationData(myFedSection, historySection);

  // Toggle functionality
  setupToggle(bansSection.querySelector('#ban-prop-toggle'));
  setupToggle(bansSection.querySelector('#share-rep-toggle'));
  setupToggle(historySection.querySelector('#fed-history-toggle'));

  // Join button
  joinSection.querySelector('#join-fed-btn').onclick = async () => {
    const code = joinSection.querySelector('#invite-code').value.trim();
    const currentChatId = useStore?.getState()?.activeChatId;
    
    if (!code) {
      showToast(t('enter_code', 'Please enter an invite code'));
      return;
    }
    
    if (!currentChatId) {
      showToast(t('select_group_first', 'Please select a group first'));
      return;
    }
    
    try {
      showToast(t('joining', 'Joining...'));
      await apiFetch('/api/federation/join', {
        method: 'POST',
        body: JSON.stringify({ invite_code: code, chat_id: currentChatId })
      });
      showToast(t('joined_success', 'Joined federation!'));
      loadFederationData(myFedSection);
    } catch (err) {
      console.error('Failed to join federation:', err);
      const errorMsg = err.message || t('join_failed', 'Failed to join');
      showToast(errorMsg);
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

async function loadFederationData(container, historySection = null) {
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
      
      // Load federation name history if section exists
      if (historySection) {
        loadFederationNameHistory(historySection, fed.id);
      }
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
        const chatId = useStore?.getState()?.activeChatId;
        if (!chatId) {
          showToast(t('select_group_first', 'Please select a group first'));
          return;
        }
        // Prompt for federation name
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
          loadFederationData(container, historySection);
        } catch (err) {
          console.error('Failed to create federation:', err);
          showToast(t('create_failed', 'Failed to create') + (err.message ? ': ' + err.message : ''));
        }
      };
      
      // Hide history section if no federation
      if (historySection) {
        historySection.querySelector('#fed-history-content').innerHTML = `
          <div style="text-align:center;padding:var(--sp-3);color:var(--text-muted);font-size:0.85rem">
            Join or create a federation to see cross-group name history
          </div>
        `;
      }
    }
  } catch (err) {
    container.querySelector('#my-fed-content').innerHTML = `
      <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted)">
        ${t('load_failed', 'Failed to load')}
      </div>
    `;
  }
}

async function loadFederationNameHistory(container, fedId) {
  const contentDiv = container.querySelector('#fed-history-content');
  if (!contentDiv) return;
  
  try {
    contentDiv.innerHTML = '<div style="text-align:center;padding:var(--sp-3);color:var(--text-muted)">Loading...</div>';
    
    const data = await apiFetch(`/api/federation/federations/${fedId}/name-history?limit=20`);
    
    if (!data.history || data.history.length === 0) {
      contentDiv.innerHTML = `
        <div style="text-align:center;padding:var(--sp-3);color:var(--text-muted);font-size:0.85rem">
          No name changes recorded across federation yet
        </div>
      `;
      return;
    }
    
    // Build history list
    let html = '<div style="max-height:300px;overflow-y:auto;">';
    data.history.forEach(entry => {
      const date = entry.changed_at ? new Date(entry.changed_at).toLocaleDateString() : '—';
      const oldName = entry.old_name || '(unknown)';
      const fedBadge = entry.is_federated ? '<span style="font-size:0.7rem;background:var(--accent);color:#000;padding:1px 4px;border-radius:4px;margin-left:4px">FED</span>' : '';
      
      html += `
        <div style="padding:var(--sp-2) 0;border-bottom:1px solid var(--border);font-size:0.85rem;">
          <div style="display:flex;align-items:center;gap:var(--sp-2);">
            <span style="color:var(--text-muted);text-decoration:line-through;">${escapeHtml(oldName)}</span>
            <span style="color:var(--accent)">→</span>
            <span style="font-weight:500;">${escapeHtml(entry.user_name)}</span>
            ${fedBadge}
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px;">
            ${date} • ${escapeHtml(entry.group_name)}
          </div>
        </div>
      `;
    });
    html += '</div>';
    
    // Add stats link
    html += `
      <div style="margin-top:var(--sp-3);text-align:center;">
        <button class="btn btn-secondary" id="view-fed-stats" style="font-size:0.85rem;">
          View Federation Stats
        </button>
      </div>
    `;
    
    contentDiv.innerHTML = html;
    
    contentDiv.querySelector('#view-fed-stats').onclick = () => {
      window.open(`/api/federation/federations/${fedId}/name-history/stats`, '_blank');
    };
    
  } catch (err) {
    console.error('Failed to load federation name history:', err);
    contentDiv.innerHTML = `
      <div style="text-align:center;padding:var(--sp-3);color:var(--text-muted);font-size:0.85rem">
        Failed to load history
      </div>
    `;
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}
