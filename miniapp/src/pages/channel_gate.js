/**
 * miniapp/src/pages/channel_gate.js
 */
import { Card, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

export async function renderChannelGatePage(container) {
  const chatId = useStore.getState().activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({ icon: '📢', title: 'Select a group', description: 'Choose a group to manage channel gate.' }));
    return;
  }

  const header = document.createElement('div');
  header.style.cssText = 'margin-bottom: var(--sp-6);';
  header.innerHTML = `<h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">📢 Channel Gate</h2><p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">Require users to join a channel before chatting</p>`;
  container.appendChild(header);

  try {
    const config = await apiFetch(`/api/groups/${chatId}/channel-gate/config`);
    const card = Card({ title: 'Gate Settings', subtitle: 'Configure force-join requirements' });
    card.innerHTML += `
      <div style="display:flex;flex-direction:column;gap:var(--sp-4);padding-top:var(--sp-2);">
        <div>
          <label style="font-size:12px;color:var(--text-muted);">Target Channel ID/Username</label>
          <input type="text" id="gate-channel" class="input" value="${config?.channel_id || ''}" placeholder="-100... or @channel">
        </div>
        <button id="save-gate-config" class="btn btn-primary">Save Gate</button>
      </div>
    `;
    container.appendChild(card);
    card.querySelector('#save-gate-config').onclick = async () => {
      const channelId = card.querySelector('#gate-channel').value;
      try {
        await apiFetch(`/api/groups/${chatId}/channel-gate/config`, { method: 'PUT', body: JSON.stringify({ channel_id: channelId }) });
        showToast('Saved', 'success');
      } catch (e) { showToast('Error', 'error'); }
    };
  } catch (e) {
    container.appendChild(EmptyState({ icon: '⚠️', title: 'Channel Gate', description: 'API not responding.' }));
  }
}
