/**
 * miniapp/src/pages/booster.js
 * 
 * Member Booster management page.
 */

import { Card, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

const store = useStore;

export async function renderBoosterPage(container) {
  const chatId = store.getState().activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '🚀',
      title: 'Select a group',
      description: 'Choose a group to manage member booster.'
    }));
    return;
  }

  const header = document.createElement('div');
  header.style.cssText = 'margin-bottom: var(--sp-6);';
  header.innerHTML = `
    <h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">🚀 Member Booster</h2>
    <p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">Manage invite-to-unlock and join requirements</p>
  `;
  container.appendChild(header);

  container.innerHTML += '<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading booster settings...</div>';

  try {
    const config = await apiFetch(`/api/groups/${chatId}/boost/config`);
    container.innerHTML = '';
    container.appendChild(header);

    const configCard = Card({
      title: '⚙️ Booster Configuration',
      subtitle: 'Set requirements for new members'
    });

    configCard.innerHTML += `
      <div style="display:flex;flex-direction:column;gap:var(--sp-4);padding-top:var(--sp-2);">
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <span>Enable Member Booster</span>
          <div id="booster-enabled-toggle"></div>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <span>Required Invites</span>
          <input type="number" id="boost-count-input" class="input" style="width:80px;" value="${config?.required_count || 0}">
        </div>
        <button id="save-booster-config" class="btn btn-primary">Save Configuration</button>
      </div>
    `;
    container.appendChild(configCard);
    
    // Initialize toggle
    const toggleContainer = configCard.querySelector('#booster-enabled-toggle');
    if (toggleContainer) {
      import('../../lib/components.js').then(({ Toggle }) => {
        toggleContainer.appendChild(Toggle({
          checked: config?.enabled || false,
          onChange: async (v) => {
            try {
              await apiFetch(`/api/groups/${chatId}/boost/config`, {
                method: 'PUT',
                body: JSON.stringify({ enabled: v })
              });
              showToast(`Booster ${v ? 'enabled' : 'disabled'}`, 'success');
            } catch (e) { showToast('Error', 'error'); }
          }
        }));
      });
    }
    
    configCard.querySelector('#save-booster-config').onclick = async () => {
      const count = parseInt(configCard.querySelector('#boost-count-input').value);
      try {
        await apiFetch(`/api/groups/${chatId}/boost/config`, {
          method: 'PUT',
          body: JSON.stringify({ required_count: count })
        });
        showToast('Configuration saved', 'success');
      } catch (e) {
        showToast('Failed to save', 'error');
      }
    };

  } catch (e) {
    container.innerHTML = '';
    container.appendChild(header);
    container.appendChild(EmptyState({ icon: '⚠️', title: 'Feature coming soon', description: 'The Member Booster API returned an error or is not yet fully linked.' }));
  }
}
