/**
 * miniapp/src/pages/channel_gate.js
 * 
 * Channel Gate configuration page with enable/disable toggle.
 */
import { Card, EmptyState, Toggle, showToast } from '../../lib/components.js?v=1.6.0';
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
  header.innerHTML = '<h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">📢 Channel Gate</h2><p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">Require users to join a channel before chatting</p>';
  container.appendChild(header);

  const loadingEl = document.createElement('div');
  loadingEl.style.cssText = 'text-align:center;padding:var(--sp-8);color:var(--text-muted);';
  loadingEl.textContent = 'Loading...';
  container.appendChild(loadingEl);

  try {
    const config = await apiFetch(`/api/groups/${chatId}/channel-gate/config`);
    loadingEl.remove();
    const card = Card({ title: 'Gate Settings', subtitle: 'Configure force-join requirements' });

    const formEl = document.createElement('div');
    formEl.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-4);padding-top:var(--sp-2);';
    const isEnabled = config?.force_channel_enabled || config?.enabled || false;
    const channelId = config?.force_channel_id || config?.force_channel_username || config?.channel_id || '';
    formEl.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <div style="font-size:var(--text-sm);font-weight:var(--fw-semibold);">Enable Channel Gate</div>
          <div style="font-size:var(--text-xs);color:var(--text-muted);">Users must join the channel before chatting</div>
        </div>
        <div id="gate-toggle-wrapper"></div>
      </div>
      <div id="gate-config-fields" style="display:${isEnabled ? 'flex' : 'none'};flex-direction:column;gap:var(--sp-3);">
        <div>
          <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:var(--sp-1);">Target Channel ID/Username</label>
          <input type="text" id="gate-channel" class="input" value="${channelId}" placeholder="-100... or @channel">
        </div>
        <div id="gate-status" style="display:${channelId ? 'block' : 'none'};padding:var(--sp-2);background:var(--bg-input);border-radius:var(--r-md);font-size:var(--text-xs);">
          ${channelId ? '✅ Channel gate is configured for: ' + channelId : ''}
        </div>
        <button id="save-gate-config" class="btn btn-primary">Save Gate</button>
      </div>
    `;
    card.appendChild(formEl);
    container.appendChild(card);

    // Toggle
    const toggleWrapper = card.querySelector('#gate-toggle-wrapper');
    toggleWrapper.appendChild(Toggle({
      checked: isEnabled,
      onChange: async (v) => {
        try {
          await apiFetch(`/api/groups/${chatId}/channel-gate/config`, {
            method: 'PUT',
            body: JSON.stringify({ force_channel_enabled: v })
          });
          card.querySelector('#gate-config-fields').style.display = v ? 'flex' : 'none';
          showToast(`Channel gate ${v ? 'enabled' : 'disabled'}`, 'success');
        } catch (e) { showToast('Error updating channel gate', 'error'); }
      }
    }));

    card.querySelector('#save-gate-config').onclick = async () => {
      const channelId = card.querySelector('#gate-channel').value.trim();
      if (!channelId) { showToast('Enter a channel ID or username', 'error'); return; }

      // Determine if it's an ID or username
      const isId = channelId.startsWith('-100') || /^\d+$/.test(channelId);
      const updateData = isId ? { force_channel_id: parseInt(channelId), force_channel_username: null }
                                   : { force_channel_id: null, force_channel_username: channelId.replace('@', '') };

      try {
        await apiFetch(`/api/groups/${chatId}/channel-gate/config`, {
          method: 'PUT',
          body: JSON.stringify(updateData)
        });
        const statusEl = card.querySelector('#gate-status');
        statusEl.style.display = 'block';
        statusEl.textContent = '\u2705 Channel gate is configured for: ' + channelId;
        showToast('Saved', 'success');
      } catch (e) { showToast('Error saving gate config', 'error'); }
    };
  } catch (e) {
    loadingEl.remove();
    container.appendChild(EmptyState({ icon: '⚠️', title: 'Channel Gate', description: 'API not responding. Please try again.' }));
  }
}
