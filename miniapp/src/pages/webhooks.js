/**
 * miniapp/src/pages/webhooks.js
 *
 * Webhook Integrations page for the Mini App.
 * Allows admins to configure external webhook endpoints
 * for events like member joins, bans, warnings, etc.
 */

import { Card, EmptyState, showToast, Spinner } from '../../lib/components.js?v=1.5.0';
import { apiFetch } from '../../lib/api.js?v=1.5.0';
import { useStore } from '../../store/index.js?v=1.5.0';

const store = useStore;

const EVENT_TYPES = [
  { type: 'member_join', label: 'Member Join', icon: '👋', desc: 'New member joins' },
  { type: 'member_leave', label: 'Member Leave', icon: '👋', desc: 'Member leaves' },
  { type: 'ban', label: 'Ban', icon: '🚫', desc: 'Member banned' },
  { type: 'unban', label: 'Unban', icon: '✅', desc: 'Member unbanned' },
  { type: 'mute', label: 'Mute', icon: '🔇', desc: 'Member muted' },
  { type: 'unmute', label: 'Unmute', icon: '🔊', desc: 'Member unmuted' },
  { type: 'warn', label: 'Warning', icon: '⚠️', desc: 'Warning issued' },
  { type: 'kick', label: 'Kick', icon: '👢', desc: 'Member kicked' },
  { type: 'automod_trigger', label: 'AutoMod', icon: '🤖', desc: 'AutoMod action' },
  { type: 'report_created', label: 'Report', icon: '🚨', desc: 'New report' },
  { type: 'settings_change', label: 'Settings', icon: '⚙️', desc: 'Settings changed' },
  { type: 'all', label: 'All Events', icon: '📡', desc: 'Subscribe to everything' },
];

export async function renderWebhooksPage(container) {
  const state = store.getState();
  const chatId = state.activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '🔗',
      title: 'Select a group',
      description: 'Choose a group to manage webhook integrations.',
    }));
    return;
  }

  // Header
  const header = document.createElement('div');
  header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-4);';
  header.innerHTML = `
    <div>
      <h2 style="margin:0;font-size:var(--text-xl);color:var(--text-primary);">🔗 Webhook Integrations</h2>
      <p style="margin:4px 0 0;color:var(--text-muted);font-size:var(--text-sm);">Connect your group to external services</p>
    </div>
    <button id="add-webhook-btn" class="btn btn-primary">
      <span>+</span> Add Webhook
    </button>
  `;
  container.appendChild(header);

  // Loading state
  const loadingEl = document.createElement('div');
  loadingEl.style.cssText = 'text-align:center;padding:var(--sp-8);color:var(--text-muted);';
  loadingEl.innerHTML = Spinner({ size: 32 }) + '<p>Loading webhooks...</p>';
  container.appendChild(loadingEl);

  try {
    const data = await apiFetch(`/api/groups/${chatId}/webhooks`);
    loadingEl.remove();

    // Stats card
    if (data.stats) {
      const statsCard = Card({ title: '📊 Integration Stats', subtitle: 'Webhook activity overview' });
      statsCard.innerHTML += `
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:var(--sp-3);margin-top:var(--sp-3);">
          <div style="text-align:center;padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);">
            <div style="font-size:var(--text-2xl);font-weight:var(--fw-bold);color:var(--accent);">${data.stats.active}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">Active</div>
          </div>
          <div style="text-align:center;padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);">
            <div style="font-size:var(--text-2xl);font-weight:var(--fw-bold);color:var(--text-muted);">${data.stats.total}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">Total</div>
          </div>
          <div style="text-align:center;padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);">
            <div style="font-size:var(--text-2xl);font-weight:var(--fw-bold);color:#4ade80;">${data.stats.deliveries_24h || 0}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">24h Deliveries</div>
          </div>
        </div>
      `;
      container.appendChild(statsCard);
    }

    // Webhooks list
    if (!data.webhooks || data.webhooks.length === 0) {
      const emptyCard = Card({
        title: '',
        children: EmptyState({
          icon: '🔗',
          title: 'No webhooks yet',
          description: 'Add your first webhook to integrate with Discord, Zapier, Make.com, or custom endpoints.',
        }).outerHTML
      });
      container.appendChild(emptyCard);
    } else {
      data.webhooks.forEach(webhook => {
        container.appendChild(_buildWebhookCard(webhook, chatId));
      });
    }

    // Bind add button
    document.getElementById('add-webhook-btn').onclick = () => _showWebhookModal(chatId);

  } catch (err) {
    loadingEl.remove();
    container.appendChild(Card({
      title: '❌ Error',
      children: `<p style="color:var(--danger);">Failed to load webhooks: ${err.message}</p>`
    }));
  }
}

function _buildWebhookCard(webhook, chatId) {
  const isActive = webhook.is_active;
  const events = webhook.events || [];
  
  const card = Card({
    title: `${isActive ? '🟢' : '⚪'} ${webhook.name}`,
    subtitle: `${events.length} event${events.length !== 1 ? 's' : ''} subscribed`,
    actions: `
      <button class="btn btn-secondary" style="padding:4px 8px;font-size:12px;" data-action="test" data-id="${webhook.id}">
        🧪 Test
      </button>
      <button class="btn btn-secondary" style="padding:4px 8px;font-size:12px;" data-action="edit" data-id="${webhook.id}">
        ✏️ Edit
      </button>
      <button class="btn btn-secondary" style="padding:4px 8px;font-size:12px;color:var(--danger);" data-action="delete" data-id="${webhook.id}">
        🗑️
      </button>
    `
  });

  // Event badges
  const eventBadges = events.slice(0, 6).map(e => {
    const evt = EVENT_TYPES.find(et => et.type === e) || { label: e, icon: '📡' };
    return `<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;background:var(--accent-dim);color:var(--accent);border-radius:999px;font-size:11px;margin:2px;">${evt.icon} ${evt.label}</span>`;
  }).join('');
  
  if (events.length > 6) {
    eventBadges += `<span style="padding:2px 8px;background:var(--bg-hover);color:var(--text-muted);border-radius:999px;font-size:11px;margin:2px;">+${events.length - 6} more</span>`;
  }

  card.innerHTML += `
    <div style="margin-top:var(--sp-3);">
      <div style="font-size:var(--text-xs);color:var(--text-muted);margin-bottom:var(--sp-1);">URL</div>
      <code style="font-size:var(--text-xs);background:var(--bg-input);padding:4px 8px;border-radius:var(--r-md);display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
        ${webhook.url}
      </code>
    </div>
    <div style="margin-top:var(--sp-3);">
      <div style="font-size:var(--text-xs);color:var(--text-muted);margin-bottom:var(--sp-1);">Events</div>
      <div style="display:flex;flex-wrap:wrap;gap:4px;">${eventBadges}</div>
    </div>
    ${webhook.last_error ? `
    <div style="margin-top:var(--sp-3);padding:var(--sp-2);background:rgba(239,68,68,0.1);border-radius:var(--r-md);">
      <div style="font-size:var(--text-xs);color:var(--danger);">⚠️ ${webhook.last_error}</div>
    </div>
    ` : ''}
  `;

  // Bind actions
  card.querySelectorAll('[data-action]').forEach(btn => {
    btn.onclick = () => _handleWebhookAction(btn.dataset.action, webhook, chatId);
  });

  return card;
}

async function _handleWebhookAction(action, webhook, chatId) {
  if (action === 'delete') {
    if (!confirm(`Delete webhook "${webhook.name}"?`)) return;
    try {
      await apiFetch(`/api/groups/${chatId}/webhooks/${webhook.id}`, { method: 'DELETE' });
      showToast('Webhook deleted', 'success');
      renderWebhooksPage(document.getElementById('page-webhooks'));
    } catch (e) {
      showToast('Failed to delete webhook', 'error');
    }
  } else if (action === 'test') {
    _testWebhook(webhook, chatId);
  } else if (action === 'edit') {
    _showWebhookModal(chatId, webhook);
  }
}

async function _testWebhook(webhook, chatId) {
  showToast('Sending test event...', 'info');
  try {
    const result = await apiFetch(`/api/groups/${chatId}/webhooks/${webhook.id}/test`, {
      method: 'POST',
      body: JSON.stringify({ event_type: 'member_join' })
    });
    
    if (result.success) {
      showToast(`Test delivered in ${result.duration_ms}ms`, 'success');
    } else {
      showToast(`Test failed: ${result.error || 'HTTP ' + result.status_code}`, 'error');
    }
  } catch (e) {
    showToast('Test request failed', 'error');
  }
}

function _showWebhookModal(chatId, webhook = null) {
  const modal = document.createElement('div');
  modal.id = 'webhook-modal';
  modal.style.cssText = `
    position:fixed;top:0;left:0;right:0;bottom:0;
    background:rgba(0,0,0,0.7);z-index:1000;
    display:flex;align-items:center;justify-content:center;
    padding:var(--sp-4);
  `;
  
  const isEdit = !!webhook;
  const events = webhook?.events || ['member_join', 'ban', 'warn'];
  
  modal.innerHTML = `
    <div style="background:var(--surface);border-radius:var(--r-xl);width:100%;max-width:500px;max-height:90vh;overflow-y:auto;">
      <div style="padding:var(--sp-4);border-bottom:1px solid var(--border);">
        <h3 style="margin:0;font-size:var(--text-lg);">${isEdit ? 'Edit' : 'Add'} Webhook</h3>
      </div>
      <div style="padding:var(--sp-4);">
        <div style="margin-bottom:var(--sp-3);">
          <label style="display:block;font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--sp-1);">Name</label>
          <input type="text" id="wh-name" class="input" value="${webhook?.name || ''}" placeholder="Discord Notifications">
        </div>
        <div style="margin-bottom:var(--sp-3);">
          <label style="display:block;font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--sp-1);">Webhook URL</label>
          <input type="url" id="wh-url" class="input" value="${webhook?.url || ''}" placeholder="https://discord.com/api/webhooks/...">
        </div>
        <div style="margin-bottom:var(--sp-3);">
          <label style="display:block;font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--sp-1);">Secret (optional, for HMAC)</label>
          <input type="text" id="wh-secret" class="input" value="${webhook?.secret || ''}" placeholder="your-secret-key">
        </div>
        <div style="margin-bottom:var(--sp-3);">
          <label style="display:block;font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--sp-2);">Events</label>
          <div id="wh-events" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:var(--sp-2);">
            ${EVENT_TYPES.map(evt => `
              <label style="display:flex;align-items:center;gap:var(--sp-2);padding:var(--sp-2);background:var(--bg-input);border-radius:var(--r-md);cursor:pointer;">
                <input type="checkbox" value="${evt.type}" ${events.includes(evt.type) ? 'checked' : ''}>
                <span style="font-size:var(--text-sm);">${evt.icon} ${evt.label}</span>
              </label>
            `).join('')}
          </div>
        </div>
        ${isEdit ? `
        <div style="margin-bottom:var(--sp-3);">
          <label style="display:flex;align-items:center;gap:var(--sp-2);cursor:pointer;">
            <input type="checkbox" id="wh-active" ${webhook?.is_active ? 'checked' : ''}>
            <span style="font-size:var(--text-sm);">Active</span>
          </label>
        </div>
        ` : ''}
      </div>
      <div style="padding:var(--sp-4);border-top:1px solid var(--border);display:flex;gap:var(--sp-2);justify-content:flex-end;">
        <button id="wh-cancel" class="btn btn-secondary">Cancel</button>
        <button id="wh-save" class="btn btn-primary">${isEdit ? 'Save' : 'Add'} Webhook</button>
      </div>
    </div>
  `;
  
  document.body.appendChild(modal);
  
  // Close on backdrop click
  modal.onclick = (e) => {
    if (e.target === modal) modal.remove();
  };
  
  document.getElementById('wh-cancel').onclick = () => modal.remove();
  
  document.getElementById('wh-save').onclick = async () => {
    const name = document.getElementById('wh-name').value.trim();
    const url = document.getElementById('wh-url').value.trim();
    const secret = document.getElementById('wh-secret').value.trim();
    const selectedEvents = Array.from(modal.querySelectorAll('#wh-events input:checked')).map(cb => cb.value);
    const isActive = isEdit ? document.getElementById('wh-active').checked : true;
    
    if (!name || !url) {
      showToast('Name and URL are required', 'error');
      return;
    }
    if (selectedEvents.length === 0) {
      showToast('Select at least one event', 'error');
      return;
    }
    
    const payload = {
      name,
      url,
      events: selectedEvents,
      ...(secret && { secret }),
      ...(isEdit && { is_active: isActive })
    };
    
    try {
      if (isEdit) {
        await apiFetch(`/api/groups/${chatId}/webhooks/${webhook.id}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        });
      } else {
        await apiFetch(`/api/groups/${chatId}/webhooks`, {
          method: 'POST',
          body: JSON.stringify(payload)
        });
      }
      showToast(`Webhook ${isEdit ? 'updated' : 'created'}`, 'success');
      modal.remove();
      renderWebhooksPage(document.getElementById('page-webhooks'));
    } catch (e) {
      showToast(e.message || 'Failed to save webhook', 'error');
    }
  };
}
