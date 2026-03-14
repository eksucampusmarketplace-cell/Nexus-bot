/**
 * miniapp/src/pages/analytics.js
 *
 * Analytics dashboard page for the Mini App.
 * Displays:
 *   - Message activity chart (last 30 days)
 *   - Member growth chart
 *   - Top active members leaderboard
 *   - Moderation actions breakdown
 *   - Open reports inbox with resolve/dismiss actions
 *
 * Dependencies:
 *   - lib/components.js (Card, StatCard, EmptyState, showToast)
 *   - lib/api.js (apiFetch)
 *   - store/index.js (useStore)
 */

import { Card, StatCard, EmptyState, showToast, Spinner } from '../../lib/components.js?v=1.3.3';
import { apiFetch } from '../../lib/api.js?v=1.3.3';
import { useStore } from '../../store/index.js?v=1.3.3';

const store = useStore;

const DAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export async function renderAnalyticsPage(container) {
  const state = store.getState();
  const chatId = state.activeChatId;

  // Always clear and reset container first
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '📊',
      title: 'Select a group',
      description: 'Choose a group to view analytics.',
    }));
    return;
  }

  // Show loading state
  container.innerHTML = `
    <div style="text-align: center; padding: var(--sp-8);">
      <div style="font-size: 48px; margin-bottom: var(--sp-4);">⏳</div>
      <div style="color: var(--text-muted);">Loading analytics...</div>
    </div>
  `;

  let analytics, memberStats, reports;

  try {
    [analytics, memberStats, reports] = await Promise.all([
      apiFetch(`/api/groups/${chatId}/analytics`),
      apiFetch(`/api/groups/${chatId}/member-stats`).catch(() => null),
      apiFetch(`/api/groups/${chatId}/reports`).catch(() => ({ reports: [], count: 0 })),
    ]);
  } catch (err) {
    container.innerHTML = '';
    container.appendChild(EmptyState({
      icon: '⚠️',
      title: 'Failed to load analytics',
      description: err.message || 'Please try again.',
    }));
    return;
  }

  container.innerHTML = '';

  const { activity = [], growth = [], modules: modActions = [] } = analytics || {};

  const totalMessages = activity.reduce((s, d) => s + (d.messages || 0), 0);
  const todayMessages = activity.length > 0 ? (activity[activity.length - 1]?.messages || 0) : 0;
  const totalJoins    = growth.reduce((s, d) => s + (d.joins || 0), 0);
  const totalLeaves   = growth.reduce((s, d) => s + (d.leaves || 0), 0);
  const openReports   = reports?.count || 0;

  const summaryGrid = document.createElement('div');
  summaryGrid.className = 'stats-grid';
  summaryGrid.style.marginBottom = 'var(--sp-5)';
  const cards = [
    { label: 'Messages (30d)', value: totalMessages.toLocaleString(), icon: '💬', color: 'accent' },
    { label: 'Today',          value: todayMessages.toLocaleString(),  icon: '📅', color: 'success' },
    { label: 'Joins (30d)',    value: totalJoins.toLocaleString(),     icon: '👋', color: 'warning' },
    { label: 'Open Reports',   value: openReports.toLocaleString(),    icon: '🚨', color: openReports > 0 ? 'danger' : 'success' },
  ];
  cards.forEach(c => summaryGrid.appendChild(StatCard(c)));
  container.appendChild(summaryGrid);

  container.appendChild(_buildActivityChart(activity));
  if (analytics.peak_hours) {
    container.appendChild(_buildPeakHoursChart(analytics.peak_hours));
  }
  container.appendChild(_buildGrowthChart(growth));
  container.appendChild(_buildModActionsCard(modActions));

  if (memberStats && Array.isArray(memberStats.top_members)) {
    container.appendChild(_buildLeaderboard(memberStats.top_members));
  }

  container.appendChild(await _buildReportsInbox(chatId, reports?.reports || []));
}


function _buildActivityChart(activity) {
  const maxVal = Math.max(...activity.map(d => d.messages || 0), 1);
  const last14 = activity.slice(-14);

  const wrap = document.createElement('div');
  wrap.style.marginBottom = 'var(--sp-4)';

  const card = Card({ title: '💬 Message Activity', subtitle: 'Last 14 days' });

  const canvas = document.createElement('canvas');
  canvas.id = 'activity-chart';
  canvas.style.cssText = 'max-height: 220px; width: 100%;';
  card.appendChild(canvas);
  
  // Load Chart.js from CDN if not already loaded
  if (!window.Chart) {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4';
    script.onload = () => renderActivityChart(canvas, last14);
    document.head.appendChild(script);
  } else {
    renderActivityChart(canvas, last14);
  }

  wrap.appendChild(card);
  return wrap;
}

function renderActivityChart(canvas, data) {
  const labels = data.map(d => d.date.slice(5)); // MM-DD
  const values = data.map(d => d.messages || 0);
  
  new Chart(canvas, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Messages',
        data: values,
        borderColor: getComputedStyle(document.documentElement).getPropertyValue('--accent') || '#00d4ff',
        backgroundColor: 'rgba(0, 212, 255, 0.1)',
        tension: 0.4,
        fill: true,
        pointRadius: 3,
        pointBackgroundColor: '#00d4ff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { 
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a2840',
          titleColor: '#e8edf7',
          bodyColor: '#e8edf7',
          borderColor: '#2a3850',
          borderWidth: 1
        }
      },
      scales: { 
        x: { 
          grid: { display: false },
          ticks: { color: '#6b7c99', font: { size: 10 } }
        },
        y: {
          grid: { color: '#1a2840' },
          ticks: { color: '#6b7c99', font: { size: 10 } }
        }
      }
    }
  });
}


function _buildPeakHoursChart(peakHours) {
  const wrap = document.createElement('div');
  wrap.style.marginBottom = 'var(--sp-4)';

  const card = Card({ title: '🔥 Peak Hours', subtitle: 'Activity by hour (24h)' });

  const maxVal = Math.max(...peakHours, 1);
  
  const chartWrap = document.createElement('div');
  chartWrap.style.cssText = 'overflow-x:auto;padding:var(--sp-2) 0;';

  const grid = document.createElement('div');
  grid.style.cssText = `
    display: grid;
    grid-template-columns: repeat(24, 1fr);
    gap: 2px;
    height: 60px;
    min-width: 400px;
  `;

  peakHours.forEach((count, hour) => {
    const opacity = Math.max(0.1, count / maxVal);
    const col = document.createElement('div');
    col.style.cssText = `
      background: linear-gradient(to top, rgba(0, 212, 255, ${opacity}), rgba(0, 212, 255, ${opacity * 0.3}));
      border-radius: 2px;
      height: 100%;
      position: relative;
    `;
    col.title = `${hour}:00 - ${count} events`;
    
    if (hour % 6 === 0) {
      const label = document.createElement('div');
      label.textContent = `${hour}`;
      label.style.cssText = 'position:absolute;bottom:-16px;left:50%;transform:translateX(-50%);font-size:9px;color:var(--text-muted);';
      col.appendChild(label);
    }
    
    grid.appendChild(col);
  });

  chartWrap.appendChild(grid);
  card.appendChild(chartWrap);
  wrap.appendChild(card);
  return wrap;
}


function _buildGrowthChart(growth) {
  const last14 = growth.slice(-14);

  const wrap = document.createElement('div');
  wrap.style.marginBottom = 'var(--sp-4)';

  const card = Card({ title: '👥 Member Growth', subtitle: 'Joins vs. leaves — last 14 days' });

  if (!last14.length || (last14.every(d => !d.joins && !d.leaves))) {
    card.appendChild(EmptyState({ icon: '📭', title: 'No join/leave data yet' }));
    wrap.appendChild(card);
    return wrap;
  }

  const tableWrap = document.createElement('div');
  tableWrap.style.cssText = 'overflow-x:auto;';

  const table = document.createElement('table');
  table.style.cssText = `
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-xs);
    color: var(--text-secondary);
  `;
  table.innerHTML = `
    <thead>
      <tr style="border-bottom:1px solid var(--border);">
        <th style="text-align:left;padding:6px 4px;color:var(--text-muted);">Date</th>
        <th style="text-align:right;padding:6px 4px;color:#4ade80;">Joins</th>
        <th style="text-align:right;padding:6px 4px;color:#f87171;">Leaves</th>
        <th style="text-align:right;padding:6px 4px;color:var(--text-muted);">Net</th>
      </tr>
    </thead>
  `;
  const tbody = document.createElement('tbody');
  last14.forEach(day => {
    const net = (day.joins || 0) - (day.leaves || 0);
    const netColor = net > 0 ? '#4ade80' : net < 0 ? '#f87171' : 'var(--text-muted)';
    const tr = document.createElement('tr');
    tr.style.borderBottom = '1px solid var(--border)';
    tr.innerHTML = `
      <td style="padding:5px 4px;">${day.date?.slice(5) || '?'}</td>
      <td style="text-align:right;padding:5px 4px;color:#4ade80;">${day.joins || 0}</td>
      <td style="text-align:right;padding:5px 4px;color:#f87171;">${day.leaves || 0}</td>
      <td style="text-align:right;padding:5px 4px;color:${netColor};font-weight:600;">${net > 0 ? '+' : ''}${net}</td>
    `;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  card.appendChild(tableWrap);
  wrap.appendChild(card);
  return wrap;
}


function _buildModActionsCard(modActions) {
  const wrap = document.createElement('div');
  wrap.style.marginBottom = 'var(--sp-4)';

  const card = Card({ title: '⚡ Moderation Actions', subtitle: 'Last 30 days' });

  if (!modActions.length || modActions[0]?.name === 'no_activity') {
    card.appendChild(EmptyState({ icon: '✅', title: 'No moderation activity' }));
    wrap.appendChild(card);
    return wrap;
  }

  const ACTION_ICONS = {
    moderation: '🛡️', warn_system: '⚠️', automod: '🤖',
    ban: '🚫', mute: '🔇', kick: '👢', warn: '⚠️', delete: '🗑️',
  };

  const maxCount = Math.max(...modActions.map(a => a.actions || 0), 1);
  const list = document.createElement('div');
  list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);margin-top:var(--sp-2);';

  modActions.forEach(mod => {
    const pct = Math.round(((mod.actions || 0) / maxCount) * 100);
    const row = document.createElement('div');
    row.innerHTML = `
      <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
        <span style="font-size:var(--text-sm);color:var(--text-secondary);">
          ${ACTION_ICONS[mod.name] || '📋'} ${mod.name.replace(/_/g, ' ')}
        </span>
        <span style="font-size:var(--text-sm);font-weight:600;color:var(--text-primary);">
          ${(mod.actions || 0).toLocaleString()}
        </span>
      </div>
      <div style="height:6px;background:var(--bg-input);border-radius:3px;overflow:hidden;">
        <div style="height:100%;width:${pct}%;background:var(--accent);border-radius:3px;transition:width 0.4s ease;"></div>
      </div>
    `;
    list.appendChild(row);
  });

  card.appendChild(list);
  wrap.appendChild(card);
  return wrap;
}


function _buildLeaderboard(topMembers) {
  const wrap = document.createElement('div');
  wrap.style.marginBottom = 'var(--sp-4)';

  const card = Card({ title: '🏆 Top Members', subtitle: 'Most active this month' });

  if (!topMembers.length) {
    card.appendChild(EmptyState({ icon: '📭', title: 'No member data yet' }));
    wrap.appendChild(card);
    return wrap;
  }

  const MEDALS = ['🥇', '🥈', '🥉'];
  const list = document.createElement('div');
  list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);margin-top:var(--sp-2);';

  topMembers.slice(0, 10).forEach((m, i) => {
    const name = m.first_name || m.username || `User ${m.user_id}`;
    const messages = m.message_count || 0;
    const trust = m.trust_score || 50;
    const trustColor = trust >= 86 ? '#4ade80' : trust >= 31 ? 'var(--text-muted)' : '#f87171';

    const row = document.createElement('div');
    row.style.cssText = `
      display: flex;
      align-items: center;
      gap: var(--sp-3);
      padding: var(--sp-2) 0;
      border-bottom: 1px solid var(--border);
    `;
    row.innerHTML = `
      <span style="font-size:18px;width:24px;text-align:center;">${MEDALS[i] || `${i + 1}.`}</span>
      <div style="flex:1;min-width:0;">
        <div style="font-size:var(--text-sm);font-weight:500;color:var(--text-primary);
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
          ${name}${m.username ? ` <span style="color:var(--text-muted);font-weight:400;">@${m.username}</span>` : ''}
        </div>
        <div style="font-size:var(--text-xs);color:var(--text-muted);">${messages.toLocaleString()} messages</div>
      </div>
      <div style="text-align:right;flex-shrink:0;">
        <div style="font-size:var(--text-xs);color:${trustColor};font-weight:600;">
          Trust ${trust}
        </div>
      </div>
    `;
    list.appendChild(row);
  });

  card.appendChild(list);
  wrap.appendChild(card);
  return wrap;
}


async function _buildReportsInbox(chatId, reports) {
  const wrap = document.createElement('div');
  wrap.style.marginBottom = 'var(--sp-6)';

  const headerActions = document.createElement('button');
  headerActions.className = 'btn btn-secondary';
  headerActions.style.cssText = 'padding: 4px 10px; font-size: var(--text-xs);';
  headerActions.textContent = '🔄 Refresh';
  headerActions.onclick = async () => {
    try {
      const fresh = await apiFetch(`/api/groups/${chatId}/reports`);
      _refreshReportsList(list, chatId, fresh?.reports || []);
    } catch (e) {
      showToast('Failed to refresh reports', 'error');
    }
  };

  const card = Card({
    title: `🚨 Report Inbox${reports.length > 0 ? ` (${reports.length} open)` : ''}`,
    subtitle: 'User-reported messages awaiting admin review',
    actions: headerActions,
  });

  const list = document.createElement('div');
  list.id = `reports-list-${chatId}`;
  _refreshReportsList(list, chatId, reports);

  card.appendChild(list);
  wrap.appendChild(card);
  return wrap;
}


function _refreshReportsList(listEl, chatId, reports) {
  listEl.innerHTML = '';

  if (!reports.length) {
    listEl.appendChild(EmptyState({ icon: '✅', title: 'No open reports', description: 'Your group is all clear!' }));
    return;
  }

  reports.forEach(r => {
    const row = document.createElement('div');
    row.id = `report-row-${r.id}`;
    row.style.cssText = `
      padding: var(--sp-3) 0;
      border-bottom: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      gap: var(--sp-2);
    `;

    const ts = r.created_at ? new Date(r.created_at).toLocaleString() : '?';
    const reason = (r.reason || 'No reason').slice(0, 120);

    row.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:var(--sp-2);">
        <div style="flex:1;min-width:0;">
          <div style="font-size:var(--text-sm);font-weight:600;color:var(--text-primary);">
            Report #${r.id}
          </div>
          <div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:2px;">${ts}</div>
        </div>
        <span style="font-size:var(--text-xs);background:rgba(239,68,68,0.15);color:#f87171;
                     padding:2px 8px;border-radius:999px;flex-shrink:0;font-weight:600;">
          OPEN
        </span>
      </div>
      <div style="font-size:var(--text-sm);color:var(--text-secondary);">${reason}</div>
      <div style="font-size:var(--text-xs);color:var(--text-muted);">
        Reporter: <code>${r.reporter_id}</code>
        ${r.reported_id ? ` &nbsp;·&nbsp; Reported: <code>${r.reported_id}</code>` : ''}
      </div>
      <div style="display:flex;gap:var(--sp-2);margin-top:var(--sp-1);">
        <button class="btn btn-primary" style="padding:4px 12px;font-size:var(--text-xs);"
          data-action="resolve" data-id="${r.id}" data-chat="${chatId}">
          ✅ Resolve
        </button>
        <button class="btn btn-secondary" style="padding:4px 12px;font-size:var(--text-xs);"
          data-action="dismiss" data-id="${r.id}" data-chat="${chatId}">
          ❌ Dismiss
        </button>
      </div>
    `;

    row.querySelectorAll('button[data-action]').forEach(btn => {
      btn.onclick = () => _handleReportAction(btn, listEl, chatId);
    });

    listEl.appendChild(row);
  });
}


async function _handleReportAction(btn, listEl, chatId) {
  const action   = btn.dataset.action;
  const reportId = btn.dataset.id;

  btn.disabled = true;
  btn.textContent = '…';

  try {
    await apiFetch(`/api/groups/${chatId}/reports/${reportId}/${action}`, {
      method: 'POST',
      body: { note: '' },
    });

    const row = document.getElementById(`report-row-${reportId}`);
    if (row) {
      row.style.opacity = '0';
      row.style.transition = 'opacity 0.3s';
      setTimeout(() => {
        row.remove();
        if (!listEl.querySelector('[id^="report-row-"]')) {
          listEl.appendChild(EmptyState({ icon: '✅', title: 'No open reports', description: 'All reports have been actioned.' }));
        }
      }, 350);
    }

    showToast(`Report #${reportId} ${action === 'resolve' ? 'resolved' : 'dismissed'}`, 'success');
  } catch (err) {
    btn.disabled = false;
    btn.textContent = action === 'resolve' ? '✅ Resolve' : '❌ Dismiss';
    showToast(err.message || 'Action failed', 'error');
  }
}
