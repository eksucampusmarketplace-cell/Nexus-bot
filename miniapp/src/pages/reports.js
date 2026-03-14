/**
 * miniapp/src/pages/reports.js
 *
 * Reports inbox page for the Mini App.
 */

import { Card, EmptyState, showToast } from '../../lib/components.js?v=1.5.0';
import { useStore } from '../../store/index.js?v=1.5.0';
import { apiFetch } from '../../lib/api.js?v=1.5.0';

const store = useStore;

export async function renderReportsPage(container) {
  const state = store.getState();
  const chatId = state.activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '🚨',
      title: 'Select a group',
      description: 'Choose a group to view reports.'
    }));
    return;
  }

  container.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading reports...</div>`;

  try {
    const res = await apiFetch(`/api/groups/${chatId}/reports`);
    const reports = Array.isArray(res) ? res : (res?.reports || []);

    container.innerHTML = '';

    const header = document.createElement('div');
    header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-4);';
    header.innerHTML = `
      <div>
        <h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">🚨 Reports</h2>
        <p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">${reports.length} open report(s)</p>
      </div>
    `;
    container.appendChild(header);

    if (reports.length === 0) {
      container.appendChild(EmptyState({
        icon: '✅',
        title: 'No open reports',
        description: 'Your group is clean! 🎉'
      }));
      return;
    }

    reports.forEach(r => {
      const card = document.createElement('div');
      card.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);margin-bottom:var(--sp-3);';
      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:var(--sp-2);">
          <div style="flex:1;min-width:0;">
            <span style="font-size:var(--text-sm);font-weight:var(--fw-semibold);">@${r.reporter_username || r.reporter_id || 'Unknown'}</span>
            <span style="color:var(--text-muted);font-size:var(--text-sm);"> reported </span>
            <span style="font-size:var(--text-sm);font-weight:var(--fw-semibold);">@${r.target_username || r.reported_user_id || 'Unknown'}</span>
          </div>
          <span style="font-size:var(--text-xs);color:var(--text-muted);white-space:nowrap;margin-left:var(--sp-2);">${_timeAgo(r.created_at)}</span>
        </div>
        <p style="font-size:var(--text-sm);color:var(--text-secondary);margin:0 0 var(--sp-3);max-height:60px;overflow:hidden;">${r.message_text || r.reason || 'No message preview'}</p>
        <div style="display:flex;gap:var(--sp-2);">
          <button class="btn btn-secondary" style="font-size:var(--text-xs);padding:var(--sp-2) var(--sp-3);" data-action="resolve" data-id="${r.id}">✓ Resolve</button>
          <button class="btn btn-danger" style="font-size:var(--text-xs);padding:var(--sp-2) var(--sp-3);" data-action="ban" data-id="${r.id}">🔨 Ban</button>
          <button class="btn btn-secondary" style="font-size:var(--text-xs);padding:var(--sp-2) var(--sp-3);" data-action="dismissed" data-id="${r.id}">✗ Dismiss</button>
        </div>
      `;

      card.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', async () => {
          const action = btn.dataset.action;
          const rid = btn.dataset.id;
          try {
            await apiFetch(`/api/groups/${chatId}/reports/${rid}`, {
              method: 'PUT',
              body: JSON.stringify({ status: action === 'ban' ? 'resolved' : action, action })
            });
            showToast(`Report ${action === 'dismissed' ? 'dismissed' : action + 'd'}`, 'success');
            renderReportsPage(container);
          } catch (e) {
            showToast('Failed: ' + e.message, 'error');
          }
        });
      });

      container.appendChild(card);
    });
  } catch (e) {
    container.innerHTML = '';
    container.appendChild(EmptyState({
      icon: '⚠️',
      title: 'Failed to load reports',
      description: e.message
    }));
  }
}

function _timeAgo(ts) {
  if (!ts) return '';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
  return new Date(ts).toLocaleDateString();
}
