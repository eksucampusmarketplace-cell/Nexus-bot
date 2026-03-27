/**
 * miniapp/src/pages/tickets.js
 *
 * Ticket / Support System dashboard for the Mini App.
 * Features: ticket list with filters, assignment view, response templates,
 * SLA indicators, satisfaction survey results, and staff workload.
 */

import { Card, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';

const store = useStore;

export async function renderTicketsPage(container) {
  const state = store.getState();
  const chatId = state.activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '🎫',
      title: 'Select a group',
      description: 'Choose a group to manage support tickets.'
    }));
    return;
  }

  // ── Header ──────────────────────────────────────────────────────────────
  const header = document.createElement('div');
  header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-3);';
  header.innerHTML = `
    <div>
      <h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">🎫 Support Tickets</h2>
      <p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;" id="tickets-count">Loading...</p>
    </div>
    <div style="display:flex;gap:var(--sp-2);">
      <button id="btn-analytics" class="btn btn-secondary" style="font-size:var(--text-xs);padding:var(--sp-2) var(--sp-3);">📊 Analytics</button>
      <button id="btn-sla" class="btn btn-secondary" style="font-size:var(--text-xs);padding:var(--sp-2) var(--sp-3);">⏱️ SLA</button>
      <button id="btn-templates" class="btn btn-secondary" style="font-size:var(--text-xs);padding:var(--sp-2) var(--sp-3);">📝 Templates</button>
    </div>
  `;
  container.appendChild(header);

  // ── Tab Navigation ──────────────────────────────────────────────────────
  const tabBar = document.createElement('div');
  tabBar.style.cssText = 'display:flex;gap:var(--sp-2);margin-bottom:var(--sp-4);border-bottom:1px solid var(--border);padding-bottom:var(--sp-2);';

  const tabs = [
    { id: 'list', label: '📋 Tickets', active: true },
    { id: 'workload', label: '👷 Staff' },
  ];

  let activeTab = 'list';

  tabs.forEach(tab => {
    const btn = document.createElement('button');
    btn.textContent = tab.label;
    btn.dataset.tab = tab.id;
    btn.style.cssText = `padding:var(--sp-2) var(--sp-3);border:none;background:none;font-size:var(--text-sm);cursor:pointer;border-bottom:2px solid ${tab.active ? 'var(--accent)' : 'transparent'};color:${tab.active ? 'var(--text-primary)' : 'var(--text-muted)'};font-weight:${tab.active ? 'var(--fw-semibold)' : 'normal'};`;
    btn.onclick = () => {
      activeTab = tab.id;
      tabBar.querySelectorAll('[data-tab]').forEach(b => {
        const isActive = b.dataset.tab === tab.id;
        b.style.borderBottom = isActive ? '2px solid var(--accent)' : '2px solid transparent';
        b.style.color = isActive ? 'var(--text-primary)' : 'var(--text-muted)';
        b.style.fontWeight = isActive ? 'var(--fw-semibold)' : 'normal';
      });
      if (tab.id === 'list') loadTickets(currentStatus);
      else if (tab.id === 'workload') loadWorkload();
    };
    tabBar.appendChild(btn);
  });
  container.appendChild(tabBar);

  // ── Filter Chips ────────────────────────────────────────────────────────
  const filterBar = document.createElement('div');
  filterBar.id = 'ticket-filters';
  filterBar.style.cssText = 'display:flex;gap:var(--sp-2);margin-bottom:var(--sp-4);flex-wrap:wrap;';

  const filterOptions = ['open', 'in_progress', 'escalated', 'closed', 'all'];
  const filterLabels = { open: 'Open', in_progress: 'In Progress', escalated: 'Escalated', closed: 'Closed', all: 'All' };
  let currentStatus = 'open';

  filterOptions.forEach((status, i) => {
    const btn = document.createElement('button');
    btn.textContent = filterLabels[status];
    btn.dataset.status = status;
    btn.style.cssText = `padding:4px 16px;border-radius:var(--r-full);border:1px solid var(--border);font-size:var(--text-sm);cursor:pointer;background:${i === 0 ? 'var(--accent)' : 'var(--bg-input)'};color:${i === 0 ? 'white' : 'var(--text-muted)'};`;
    btn.onclick = () => {
      currentStatus = status;
      filterBar.querySelectorAll('[data-status]').forEach(b => {
        b.style.background = b === btn ? 'var(--accent)' : 'var(--bg-input)';
        b.style.color = b === btn ? 'white' : 'var(--text-muted)';
      });
      loadTickets(status);
    };
    filterBar.appendChild(btn);
  });
  container.appendChild(filterBar);

  // ── Content Area ────────────────────────────────────────────────────────
  const content = document.createElement('div');
  content.id = 'tickets-content';
  container.appendChild(content);

  // ── Load Tickets ────────────────────────────────────────────────────────
  async function loadTickets(status) {
    document.getElementById('ticket-filters').style.display = 'flex';
    content.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading tickets...</div>`;

    try {
      const params = status && status !== 'all' ? `?status=${status}` : '';
      const res = await apiFetch(`/api/groups/${chatId}/tickets${params}`);
      const tickets = res?.tickets || [];
      const total = res?.total || tickets.length;

      const countEl = document.getElementById('tickets-count');
      if (countEl) countEl.textContent = `${total} ticket(s)`;

      content.innerHTML = '';

      if (tickets.length === 0) {
        content.appendChild(EmptyState({
          icon: '✅',
          title: `No ${filterLabels[status] || ''} tickets`,
          description: status === 'open' ? 'No open support tickets!' : 'Nothing here.'
        }));
        return;
      }

      tickets.forEach(t => {
        const card = document.createElement('div');
        card.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);margin-bottom:var(--sp-3);cursor:pointer;';
        card.onclick = () => showTicketDetail(t.id);

        const priorityEmoji = { low: '🟢', normal: '🔵', high: '🟠', urgent: '🔴' }[t.priority] || '🔵';
        const statusEmoji = { open: '📋', in_progress: '🔧', escalated: '⬆️', closed: '✅' }[t.status] || '📋';
        const slaWarning = _getSLAWarning(t);

        card.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:var(--sp-2);">
            <div style="flex:1;min-width:0;">
              <div style="display:flex;align-items:center;gap:var(--sp-2);margin-bottom:4px;">
                <span style="font-size:var(--text-xs);color:var(--text-muted);">#${t.id}</span>
                <span style="font-size:var(--text-xs);">${priorityEmoji} ${t.priority}</span>
                <span style="padding:2px 8px;border-radius:var(--r-full);font-size:var(--text-xs);background:${_statusColor(t.status)};color:white;">${statusEmoji} ${(t.status || '').replace('_', ' ')}</span>
                ${t.escalation_level > 0 ? `<span style="font-size:var(--text-xs);color:var(--warning);">⬆️ L${t.escalation_level}</span>` : ''}
                ${slaWarning}
              </div>
              <div style="font-size:var(--text-sm);font-weight:var(--fw-semibold);margin-bottom:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${_escapeHtml(t.subject)}</div>
              <div style="font-size:var(--text-xs);color:var(--text-muted);">
                By ${_escapeHtml(t.creator_name || 'Unknown')}${t.assigned_name ? ` · Assigned: ${_escapeHtml(t.assigned_name)}` : ''}
              </div>
            </div>
            <span style="font-size:var(--text-xs);color:var(--text-muted);white-space:nowrap;margin-left:var(--sp-2);">${_timeAgo(t.created_at)}</span>
          </div>
          ${t.status !== 'closed' ? `
          <div style="display:flex;gap:var(--sp-2);margin-top:var(--sp-2);">
            <button class="btn btn-secondary" style="font-size:var(--text-xs);padding:var(--sp-1) var(--sp-3);" data-action="close" data-id="${t.id}">✅ Close</button>
            <button class="btn btn-secondary" style="font-size:var(--text-xs);padding:var(--sp-1) var(--sp-3);" data-action="escalate" data-id="${t.id}">⬆️ Escalate</button>
          </div>` : `${t.satisfaction_rating ? `<div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:var(--sp-1);">⭐ ${t.satisfaction_rating}/5</div>` : ''}`}
        `;

        card.querySelectorAll('[data-action]').forEach(btn => {
          btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const action = btn.dataset.action;
            const tid = btn.dataset.id;
            try {
              await apiFetch(`/api/groups/${chatId}/tickets/${tid}/${action}`, {
                method: 'POST',
                body: JSON.stringify({})
              });
              showToast(`Ticket ${action === 'close' ? 'closed' : 'escalated'}`, 'success');
              loadTickets(currentStatus);
            } catch (err) {
              showToast('Failed: ' + err.message, 'error');
            }
          });
        });

        content.appendChild(card);
      });
    } catch (e) {
      content.innerHTML = '';
      content.appendChild(EmptyState({
        icon: '⚠️',
        title: 'Failed to load tickets',
        description: e.message
      }));
    }
  }

  // ── Ticket Detail View ──────────────────────────────────────────────────
  async function showTicketDetail(ticketId) {
    content.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading ticket...</div>`;
    document.getElementById('ticket-filters').style.display = 'none';

    try {
      const [ticket, messagesRes] = await Promise.all([
        apiFetch(`/api/groups/${chatId}/tickets/${ticketId}`),
        apiFetch(`/api/groups/${chatId}/tickets/${ticketId}/messages`),
      ]);
      const messages = messagesRes?.messages || [];

      const priorityEmoji = { low: '🟢', normal: '🔵', high: '🟠', urgent: '🔴' }[ticket.priority] || '🔵';
      const statusEmoji = { open: '📋', in_progress: '🔧', escalated: '⬆️', closed: '✅' }[ticket.status] || '📋';

      content.innerHTML = '';

      // Back button
      const backBtn = document.createElement('button');
      backBtn.textContent = '← Back to list';
      backBtn.style.cssText = 'background:none;border:none;color:var(--accent);cursor:pointer;font-size:var(--text-sm);margin-bottom:var(--sp-3);padding:0;';
      backBtn.onclick = () => {
        document.getElementById('ticket-filters').style.display = 'flex';
        loadTickets(currentStatus);
      };
      content.appendChild(backBtn);

      // Ticket header card
      const headerCard = document.createElement('div');
      headerCard.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);margin-bottom:var(--sp-3);';
      headerCard.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:var(--sp-3);">
          <h3 style="margin:0;font-size:var(--text-lg);">🎫 Ticket #${ticket.id}</h3>
          <span style="padding:4px 12px;border-radius:var(--r-full);font-size:var(--text-sm);background:${_statusColor(ticket.status)};color:white;">${statusEmoji} ${(ticket.status || '').replace('_', ' ')}</span>
        </div>
        <p style="margin:0 0 var(--sp-2);font-size:var(--text-sm);">${_escapeHtml(ticket.subject)}</p>
        <div style="display:flex;flex-wrap:wrap;gap:var(--sp-3);font-size:var(--text-xs);color:var(--text-muted);">
          <span>👤 ${_escapeHtml(ticket.creator_name || 'Unknown')}</span>
          <span>${priorityEmoji} ${ticket.priority}</span>
          ${ticket.assigned_name ? `<span>📥 ${_escapeHtml(ticket.assigned_name)}</span>` : ''}
          ${ticket.escalation_level > 0 ? `<span>⬆️ Level ${ticket.escalation_level}</span>` : ''}
          <span>📅 ${new Date(ticket.created_at).toLocaleString()}</span>
        </div>
      `;
      content.appendChild(headerCard);

      // Messages thread
      const threadCard = document.createElement('div');
      threadCard.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);margin-bottom:var(--sp-3);';
      threadCard.innerHTML = `<h4 style="margin:0 0 var(--sp-3);font-size:var(--text-sm);font-weight:var(--fw-semibold);">💬 Messages (${messages.length})</h4>`;

      if (messages.length === 0) {
        threadCard.innerHTML += `<p style="color:var(--text-muted);font-size:var(--text-sm);">No messages yet.</p>`;
      } else {
        messages.forEach(m => {
          const msgEl = document.createElement('div');
          const bgColor = m.is_system ? 'var(--bg-overlay)' : (m.is_staff ? 'var(--accent-light, rgba(59,130,246,0.1))' : 'var(--bg-input)');
          msgEl.style.cssText = `padding:var(--sp-2) var(--sp-3);margin-bottom:var(--sp-2);border-radius:var(--r-lg);background:${bgColor};font-size:var(--text-sm);`;
          msgEl.innerHTML = `
            <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
              <span style="font-weight:var(--fw-semibold);font-size:var(--text-xs);">${m.is_system ? '🤖 System' : (m.is_staff ? '👷 ' : '👤 ') + _escapeHtml(m.sender_name || 'Unknown')}</span>
              <span style="font-size:var(--text-xs);color:var(--text-muted);">${_timeAgo(m.created_at)}</span>
            </div>
            <div>${_escapeHtml(m.message_text)}</div>
          `;
          threadCard.appendChild(msgEl);
        });
      }

      // Reply input (if not closed)
      if (ticket.status !== 'closed') {
        const replyArea = document.createElement('div');
        replyArea.style.cssText = 'display:flex;gap:var(--sp-2);margin-top:var(--sp-3);';
        replyArea.innerHTML = `
          <input type="text" id="ticket-reply-input" placeholder="Type a reply..." style="flex:1;padding:var(--sp-2) var(--sp-3);border:1px solid var(--border);border-radius:var(--r-lg);background:var(--bg-input);color:var(--text-primary);font-size:var(--text-sm);" />
          <button id="ticket-reply-send" class="btn btn-primary" style="font-size:var(--text-sm);padding:var(--sp-2) var(--sp-3);">Send</button>
        `;
        threadCard.appendChild(replyArea);

        setTimeout(() => {
          const sendBtn = document.getElementById('ticket-reply-send');
          const replyInput = document.getElementById('ticket-reply-input');
          if (sendBtn && replyInput) {
            const sendReply = async () => {
              const text = replyInput.value.trim();
              if (!text) return;
              try {
                await apiFetch(`/api/groups/${chatId}/tickets/${ticketId}/message`, {
                  method: 'POST',
                  body: JSON.stringify({ message_text: text, is_staff: true })
                });
                showToast('Reply sent', 'success');
                showTicketDetail(ticketId);
              } catch (err) {
                showToast('Failed: ' + err.message, 'error');
              }
            };
            sendBtn.onclick = sendReply;
            replyInput.addEventListener('keydown', (e) => {
              if (e.key === 'Enter') sendReply();
            });
          }
        }, 0);
      }

      content.appendChild(threadCard);

      // Action buttons
      if (ticket.status !== 'closed') {
        const actions = document.createElement('div');
        actions.style.cssText = 'display:flex;gap:var(--sp-2);flex-wrap:wrap;';
        actions.innerHTML = `
          <button class="btn btn-primary" style="font-size:var(--text-sm);" data-action="close">✅ Close Ticket</button>
          <button class="btn btn-secondary" style="font-size:var(--text-sm);" data-action="escalate">⬆️ Escalate</button>
          <select id="priority-select" style="padding:var(--sp-2) var(--sp-3);border:1px solid var(--border);border-radius:var(--r-lg);background:var(--bg-input);color:var(--text-primary);font-size:var(--text-sm);">
            <option value="" disabled selected>🔄 Priority</option>
            <option value="low">🟢 Low</option>
            <option value="normal">🔵 Normal</option>
            <option value="high">🟠 High</option>
            <option value="urgent">🔴 Urgent</option>
          </select>
        `;
        actions.querySelectorAll('[data-action]').forEach(btn => {
          btn.onclick = async () => {
            try {
              await apiFetch(`/api/groups/${chatId}/tickets/${ticketId}/${btn.dataset.action}`, {
                method: 'POST',
                body: JSON.stringify({})
              });
              showToast(`Ticket ${btn.dataset.action === 'close' ? 'closed' : 'escalated'}`, 'success');
              showTicketDetail(ticketId);
            } catch (err) {
              showToast('Failed: ' + err.message, 'error');
            }
          };
        });

        setTimeout(() => {
          const prioritySelect = document.getElementById('priority-select');
          if (prioritySelect) {
            prioritySelect.onchange = async () => {
              const newPriority = prioritySelect.value;
              if (!newPriority) return;
              try {
                await apiFetch(`/api/groups/${chatId}/tickets/${ticketId}/priority`, {
                  method: 'POST',
                  body: JSON.stringify({ priority: newPriority })
                });
                showToast(`Priority changed to ${newPriority}`, 'success');
                showTicketDetail(ticketId);
              } catch (err) {
                showToast('Failed: ' + err.message, 'error');
              }
            };
          }
        }, 0);

        content.appendChild(actions);
      }
    } catch (e) {
      content.innerHTML = '';
      content.appendChild(EmptyState({
        icon: '⚠️',
        title: 'Failed to load ticket',
        description: e.message
      }));
    }
  }

  // ── Staff Workload View ─────────────────────────────────────────────────
  async function loadWorkload() {
    document.getElementById('ticket-filters').style.display = 'none';
    content.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading staff workload...</div>`;

    try {
      const res = await apiFetch(`/api/groups/${chatId}/tickets/workload`);
      const workload = res?.workload || [];

      content.innerHTML = '';

      if (workload.length === 0) {
        content.appendChild(EmptyState({
          icon: '👷',
          title: 'No staff assignments yet',
          description: 'Tickets will be assigned as staff members claim or get assigned tickets.'
        }));
        return;
      }

      const table = document.createElement('div');
      table.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);overflow:hidden;';

      // Header row
      table.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr repeat(2,80px);padding:var(--sp-3) var(--sp-4);background:var(--bg-overlay);font-size:var(--text-xs);font-weight:var(--fw-semibold);color:var(--text-muted);">
          <span>Staff Member</span>
          <span style="text-align:center;">Active</span>
          <span style="text-align:center;">Closed</span>
        </div>
      `;

      workload.forEach(w => {
        const row = document.createElement('div');
        row.style.cssText = 'display:grid;grid-template-columns:1fr repeat(2,80px);padding:var(--sp-3) var(--sp-4);border-top:1px solid var(--border);font-size:var(--text-sm);align-items:center;';
        row.innerHTML = `
          <span>👷 ${_escapeHtml(w.staff_name || 'ID: ' + w.staff_id)}</span>
          <span style="text-align:center;font-weight:var(--fw-semibold);color:${w.active_tickets > 3 ? 'var(--danger)' : 'var(--text-primary)'};">${w.active_tickets}</span>
          <span style="text-align:center;color:var(--text-muted);">${w.closed_tickets}</span>
        `;
        table.appendChild(row);
      });

      content.appendChild(table);
    } catch (e) {
      content.innerHTML = '';
      content.appendChild(EmptyState({
        icon: '⚠️',
        title: 'Failed to load workload',
        description: e.message
      }));
    }
  }

  // ── Analytics Modal ─────────────────────────────────────────────────────
  document.getElementById('btn-analytics').onclick = async () => {
    try {
      const res = await apiFetch(`/api/groups/${chatId}/tickets/analytics`);
      const a = res?.analytics || {};

      const overlay = _createModal('📊 Ticket Analytics', `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-3);">
          <div style="background:var(--bg-input);padding:var(--sp-3);border-radius:var(--r-lg);text-align:center;">
            <div style="font-size:var(--text-2xl);font-weight:var(--fw-bold);">${a.total || 0}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">Total Tickets</div>
          </div>
          <div style="background:var(--bg-input);padding:var(--sp-3);border-radius:var(--r-lg);text-align:center;">
            <div style="font-size:var(--text-2xl);font-weight:var(--fw-bold);color:var(--warning);">${a.open_count || 0}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">Open</div>
          </div>
          <div style="background:var(--bg-input);padding:var(--sp-3);border-radius:var(--r-lg);text-align:center;">
            <div style="font-size:var(--text-2xl);font-weight:var(--fw-bold);color:var(--danger);">${a.escalated_count || 0}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">Escalated</div>
          </div>
          <div style="background:var(--bg-input);padding:var(--sp-3);border-radius:var(--r-lg);text-align:center;">
            <div style="font-size:var(--text-2xl);font-weight:var(--fw-bold);color:var(--success);">${a.closed_count || 0}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">Closed</div>
          </div>
        </div>
        <div style="margin-top:var(--sp-3);display:flex;flex-direction:column;gap:var(--sp-2);">
          <div style="display:flex;justify-content:space-between;font-size:var(--text-sm);padding:var(--sp-2) 0;border-bottom:1px solid var(--border);">
            <span>Avg Response Time</span>
            <span style="font-weight:var(--fw-semibold);">${a.avg_first_response_mins != null ? a.avg_first_response_mins + ' min' : 'N/A'}</span>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:var(--text-sm);padding:var(--sp-2) 0;border-bottom:1px solid var(--border);">
            <span>Avg Resolution Time</span>
            <span style="font-weight:var(--fw-semibold);">${a.avg_resolution_hours != null ? a.avg_resolution_hours + ' hrs' : 'N/A'}</span>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:var(--text-sm);padding:var(--sp-2) 0;border-bottom:1px solid var(--border);">
            <span>Avg Satisfaction</span>
            <span style="font-weight:var(--fw-semibold);">${a.avg_satisfaction != null ? '⭐ ' + a.avg_satisfaction + '/5' : 'N/A'}</span>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:var(--text-sm);padding:var(--sp-2) 0;border-bottom:1px solid var(--border);">
            <span>SLA Response Breached</span>
            <span style="font-weight:var(--fw-semibold);color:${(a.sla_response_breached || 0) > 0 ? 'var(--danger)' : 'var(--success)'};">${a.sla_response_breached || 0}</span>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:var(--text-sm);padding:var(--sp-2) 0;">
            <span>SLA Resolution Breached</span>
            <span style="font-weight:var(--fw-semibold);color:${(a.sla_resolution_breached || 0) > 0 ? 'var(--danger)' : 'var(--success)'};">${a.sla_resolution_breached || 0}</span>
          </div>
        </div>
      `);
      document.body.appendChild(overlay);
    } catch (e) {
      showToast('Failed to load analytics: ' + e.message, 'error');
    }
  };

  // ── SLA Config Modal ────────────────────────────────────────────────────
  document.getElementById('btn-sla').onclick = async () => {
    try {
      const res = await apiFetch(`/api/groups/${chatId}/tickets/sla`);
      const configs = res?.sla_configs || [];

      let rows = '';
      const priorities = ['low', 'normal', 'high', 'urgent'];
      const priorityEmojis = { low: '🟢', normal: '🔵', high: '🟠', urgent: '🔴' };

      priorities.forEach(p => {
        const cfg = configs.find(c => c.priority === p) || {};
        rows += `
          <div style="display:grid;grid-template-columns:80px 1fr 1fr 80px;gap:var(--sp-2);align-items:center;padding:var(--sp-2) 0;border-bottom:1px solid var(--border);" data-priority="${p}">
            <span style="font-size:var(--text-sm);">${priorityEmojis[p]} ${p}</span>
            <input type="number" class="sla-response" value="${cfg.response_time_mins || (p === 'urgent' ? 15 : p === 'high' ? 30 : 60)}" min="1" style="padding:var(--sp-1) var(--sp-2);border:1px solid var(--border);border-radius:var(--r-md);background:var(--bg-input);color:var(--text-primary);font-size:var(--text-sm);width:100%;" />
            <input type="number" class="sla-resolve" value="${cfg.resolution_time_mins || (p === 'urgent' ? 240 : p === 'high' ? 480 : 1440)}" min="1" style="padding:var(--sp-1) var(--sp-2);border:1px solid var(--border);border-radius:var(--r-md);background:var(--bg-input);color:var(--text-primary);font-size:var(--text-sm);width:100%;" />
            <input type="number" class="sla-autoclose" value="${cfg.auto_close_hours || 48}" min="1" style="padding:var(--sp-1) var(--sp-2);border:1px solid var(--border);border-radius:var(--r-md);background:var(--bg-input);color:var(--text-primary);font-size:var(--text-sm);width:100%;" />
          </div>
        `;
      });

      const overlay = _createModal('⏱️ SLA Configuration', `
        <div style="display:grid;grid-template-columns:80px 1fr 1fr 80px;gap:var(--sp-2);padding:var(--sp-2) 0;font-size:var(--text-xs);color:var(--text-muted);font-weight:var(--fw-semibold);">
          <span>Priority</span>
          <span>Response (min)</span>
          <span>Resolution (min)</span>
          <span>Auto-close (hrs)</span>
        </div>
        ${rows}
        <button id="save-sla" class="btn btn-primary" style="margin-top:var(--sp-4);width:100%;">Save SLA Config</button>
      `);
      document.body.appendChild(overlay);

      setTimeout(() => {
        const saveBtn = document.getElementById('save-sla');
        if (saveBtn) {
          saveBtn.onclick = async () => {
            const modalContent = overlay.querySelector('[data-priority]').parentElement;
            for (const p of priorities) {
              const row = modalContent.querySelector(`[data-priority="${p}"]`);
              if (!row) continue;
              const responseTime = parseInt(row.querySelector('.sla-response').value) || 60;
              const resolveTime = parseInt(row.querySelector('.sla-resolve').value) || 1440;
              const autoClose = parseInt(row.querySelector('.sla-autoclose').value) || 48;
              try {
                await apiFetch(`/api/groups/${chatId}/tickets/sla`, {
                  method: 'PUT',
                  body: JSON.stringify({
                    priority: p,
                    response_time_mins: responseTime,
                    resolution_time_mins: resolveTime,
                    auto_close_hours: autoClose,
                    escalation_chain: [],
                  })
                });
              } catch (err) {
                showToast(`Failed to save ${p}: ${err.message}`, 'error');
                return;
              }
            }
            showToast('SLA config saved!', 'success');
            overlay.remove();
          };
        }
      }, 0);
    } catch (e) {
      showToast('Failed to load SLA config: ' + e.message, 'error');
    }
  };

  // ── Templates Modal ─────────────────────────────────────────────────────
  document.getElementById('btn-templates').onclick = async () => {
    try {
      const res = await apiFetch(`/api/groups/${chatId}/tickets/templates`);
      const templates = res?.templates || [];

      let templateRows = '';
      templates.forEach(t => {
        templateRows += `
          <div style="display:flex;justify-content:space-between;align-items:center;padding:var(--sp-2) var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);margin-bottom:var(--sp-2);">
            <div style="flex:1;min-width:0;">
              <div style="font-size:var(--text-sm);font-weight:var(--fw-semibold);">${_escapeHtml(t.name)}</div>
              <div style="font-size:var(--text-xs);color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${_escapeHtml(t.content)}</div>
            </div>
            <button class="btn btn-danger" style="font-size:var(--text-xs);padding:var(--sp-1) var(--sp-2);margin-left:var(--sp-2);" data-delete="${t.name}">✗</button>
          </div>
        `;
      });

      const overlay = _createModal('📝 Response Templates', `
        ${templateRows || '<p style="color:var(--text-muted);font-size:var(--text-sm);">No templates yet.</p>'}
        <div style="margin-top:var(--sp-3);border-top:1px solid var(--border);padding-top:var(--sp-3);">
          <h4 style="font-size:var(--text-sm);margin:0 0 var(--sp-2);">Add Template</h4>
          <input type="text" id="tpl-name" placeholder="Template name" style="width:100%;padding:var(--sp-2);border:1px solid var(--border);border-radius:var(--r-md);background:var(--bg-input);color:var(--text-primary);font-size:var(--text-sm);margin-bottom:var(--sp-2);box-sizing:border-box;" />
          <textarea id="tpl-content" placeholder="Template content..." rows="3" style="width:100%;padding:var(--sp-2);border:1px solid var(--border);border-radius:var(--r-md);background:var(--bg-input);color:var(--text-primary);font-size:var(--text-sm);resize:vertical;box-sizing:border-box;"></textarea>
          <button id="save-template" class="btn btn-primary" style="margin-top:var(--sp-2);width:100%;">Save Template</button>
        </div>
      `);
      document.body.appendChild(overlay);

      setTimeout(() => {
        // Delete buttons
        overlay.querySelectorAll('[data-delete]').forEach(btn => {
          btn.onclick = async () => {
            try {
              await apiFetch(`/api/groups/${chatId}/tickets/templates/${encodeURIComponent(btn.dataset.delete)}`, { method: 'DELETE' });
              showToast('Template deleted', 'success');
              overlay.remove();
              document.getElementById('btn-templates').click();
            } catch (err) {
              showToast('Failed: ' + err.message, 'error');
            }
          };
        });

        // Save button
        const saveBtn = document.getElementById('save-template');
        if (saveBtn) {
          saveBtn.onclick = async () => {
            const name = document.getElementById('tpl-name').value.trim();
            const tplContent = document.getElementById('tpl-content').value.trim();
            if (!name || !tplContent) { showToast('Name and content required', 'error'); return; }
            try {
              await apiFetch(`/api/groups/${chatId}/tickets/templates`, {
                method: 'POST',
                body: JSON.stringify({ name, content: tplContent })
              });
              showToast('Template saved!', 'success');
              overlay.remove();
              document.getElementById('btn-templates').click();
            } catch (err) {
              showToast('Failed: ' + err.message, 'error');
            }
          };
        }
      }, 0);
    } catch (e) {
      showToast('Failed to load templates: ' + e.message, 'error');
    }
  };

  // Load initial data
  await loadTickets('open');
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function _timeAgo(ts) {
  if (!ts) return '';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
  return `${Math.floor(mins / 1440)}d ago`;
}

function _statusColor(status) {
  return {
    open: '#3b82f6',
    in_progress: '#f59e0b',
    escalated: '#ef4444',
    closed: '#22c55e',
  }[status] || '#6b7280';
}

function _getSLAWarning(ticket) {
  if (ticket.status === 'closed') return '';
  const now = Date.now();

  if (ticket.sla_response_deadline && !ticket.first_response_at) {
    const deadline = new Date(ticket.sla_response_deadline).getTime();
    if (now > deadline) {
      return '<span style="padding:2px 6px;border-radius:var(--r-full);font-size:10px;background:var(--danger);color:white;">SLA BREACHED</span>';
    }
    const remaining = Math.floor((deadline - now) / 60000);
    if (remaining < 30) {
      return `<span style="padding:2px 6px;border-radius:var(--r-full);font-size:10px;background:var(--warning);color:white;">⏱️ ${remaining}m left</span>`;
    }
  }

  if (ticket.sla_resolution_deadline) {
    const deadline = new Date(ticket.sla_resolution_deadline).getTime();
    if (now > deadline) {
      return '<span style="padding:2px 6px;border-radius:var(--r-full);font-size:10px;background:var(--danger);color:white;">OVERDUE</span>';
    }
  }

  return '';
}

function _escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function _createModal(title, bodyHtml) {
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;padding:var(--sp-4);';
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

  const modal = document.createElement('div');
  modal.style.cssText = 'background:var(--bg-card);border-radius:var(--r-xl);padding:var(--sp-4);max-width:480px;width:100%;max-height:80vh;overflow-y:auto;';
  modal.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-3);">
      <h3 style="margin:0;font-size:var(--text-lg);">${title}</h3>
      <button style="background:none;border:none;font-size:var(--text-xl);cursor:pointer;color:var(--text-muted);padding:0;" id="modal-close">✕</button>
    </div>
    ${bodyHtml}
  `;
  overlay.appendChild(modal);

  setTimeout(() => {
    const closeBtn = document.getElementById('modal-close');
    if (closeBtn) closeBtn.onclick = () => overlay.remove();
  }, 0);

  return overlay;
}
