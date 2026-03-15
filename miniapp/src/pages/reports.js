/**
 * miniapp/src/pages/reports.js
 *
 * Reports inbox page for the Mini App.
 * Includes filter chips: Open / Resolved / Dismissed / All
 */

import { Card, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';

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

  const header = document.createElement('div');
  header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-3);';
  header.innerHTML = `
    <div>
      <h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">🚨 Reports</h2>
      <p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;" id="reports-count">Loading...</p>
    </div>
  `;
  container.appendChild(header);

  const filterBar = document.createElement('div');
  filterBar.style.cssText = 'display:flex;gap:var(--sp-2);margin-bottom:var(--sp-4);flex-wrap:wrap;';
  const filterOptions = ['open', 'resolved', 'dismissed', 'all'];
  let currentStatus = 'open';

  filterOptions.forEach((status, i) => {
    const btn = document.createElement('button');
    btn.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    btn.dataset.status = status;
    btn.style.cssText = `padding:4px 16px;border-radius:var(--r-full);border:1px solid var(--border);font-size:var(--text-sm);cursor:pointer;background:${i===0?'var(--accent)':'var(--bg-input)'};color:${i===0?'white':'var(--text-muted)'};`;
    btn.onclick = () => {
      currentStatus = status;
      filterBar.querySelectorAll('[data-status]').forEach(b => {
        b.style.background = b === btn ? 'var(--accent)' : 'var(--bg-input)';
        b.style.color = b === btn ? 'white' : 'var(--text-muted)';
      });
      loadReports(currentStatus);
    };
    filterBar.appendChild(btn);
  });
  container.appendChild(filterBar);

  const feed = document.createElement('div');
  feed.id = 'reports-feed';
  container.appendChild(feed);

  async function loadReports(status) {
    feed.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading reports...</div>`;
    try {
      const url = status === 'all'
        ? `/api/groups/${chatId}/reports`
        : `/api/groups/${chatId}/reports?status=${status}`;
      const res = await apiFetch(url);
      const reports = Array.isArray(res) ? res : (res?.reports || []);

      const countEl = document.getElementById('reports-count');
      if (countEl) countEl.textContent = `${reports.length} ${status} report(s)`;

      feed.innerHTML = '';

      if (reports.length === 0) {
        feed.appendChild(EmptyState({
          icon: '✅',
          title: `No ${status} reports`,
          description: status === 'open' ? 'Your group is clean! 🎉' : 'Nothing here.'
        }));
        return;
      }

      reports.forEach(r => {
        const card = document.createElement('div');
        card.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);margin-bottom:var(--sp-3);';
        const statusBadge = r.status !== 'open' ? `<span style="padding:2px 8px;border-radius:var(--r-full);font-size:var(--text-xs);background:${r.status==='resolved'?'var(--success)':'var(--bg-overlay)'};color:white;">${r.status}</span>` : '';
        card.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:var(--sp-2);">
            <div style="flex:1;min-width:0;">
              <span style="font-size:var(--text-sm);font-weight:var(--fw-semibold);">@${r.reporter_username || r.reporter_id || 'Unknown'}</span>
              <span style="color:var(--text-muted);font-size:var(--text-sm);"> reported </span>
              <span style="font-size:var(--text-sm);font-weight:var(--fw-semibold);">@${r.target_username || r.reported_user_id || 'Unknown'}</span>
              ${statusBadge}
            </div>
            <span style="font-size:var(--text-xs);color:var(--text-muted);white-space:nowrap;margin-left:var(--sp-2);">${_timeAgo(r.created_at)}</span>
          </div>
          <p style="font-size:var(--text-sm);color:var(--text-secondary);margin:0 0 var(--sp-3);max-height:60px;overflow:hidden;">${r.message_text || r.reason || 'No message preview'}</p>
          ${status === 'open' ? `
          <div style="display:flex;gap:var(--sp-2);">
            <button class="btn btn-secondary" style="font-size:var(--text-xs);padding:var(--sp-2) var(--sp-3);" data-action="resolve" data-id="${r.id}">✓ Resolve</button>
            <button class="btn btn-danger" style="font-size:var(--text-xs);padding:var(--sp-2) var(--sp-3);" data-action="ban" data-id="${r.id}">🔨 Ban</button>
            <button class="btn btn-secondary" style="font-size:var(--text-xs);padding:var(--sp-2) var(--sp-3);" data-action="dismissed" data-id="${r.id}">✗ Dismiss</button>
          </div>` : ''}
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
              loadReports(currentStatus);
            } catch (e) {
              showToast('Failed: ' + e.message, 'error');
            }
          });
        });

        feed.appendChild(card);
      });
    } catch (e) {
      feed.innerHTML = '';
      feed.appendChild(EmptyState({
        icon: '⚠️',
        title: 'Failed to load reports',
        description: e.message
      }));
    }
  }

  await loadReports('open');
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
