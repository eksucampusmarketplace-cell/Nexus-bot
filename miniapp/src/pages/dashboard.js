/**
 * miniapp/src/pages/dashboard.js
 * Task 6 of 12 — Dashboard page
 * Extracted from index.html renderDashboard(), getActionEmoji(), formatAction(), formatTime()
 */

import { Card, StatCard, EmptyState } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { getActionEmoji, formatAction, formatTime } from '../../lib/helpers.js?v=1.6.0';
import { t } from '../../lib/i18n.js?v=1.6.0';

const store = useStore;
const getState = store.getState;

export async function renderDashboard(container) {
  const state = getState();
  const chatId = state.activeChatId;
  const initData = window.Telegram?.WebApp?.initData || '';

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  const groups = state.groups || [];

  if (!chatId && groups.length > 0) {
    const firstGroup = groups[0];
    state.setActiveChatId(firstGroup.chat_id);
  }

  const finalChatId = getState().activeChatId;

  if (!finalChatId && groups.length === 0) {
    container.appendChild(EmptyState({
      icon: '🤖',
      title: t('dashboard_no_groups', 'No Groups Found'),
      description: t('dashboard_no_groups_desc', 'Add the bot to a group and make it an admin to get started.')
    }));
    return;
  }

  const quickActions = document.createElement('div');
  quickActions.style.cssText = 'margin-bottom: var(--sp-6);';

  const gamesUrl = finalChatId ? `games.html?chat_id=${finalChatId}` : 'games.html';

  quickActions.innerHTML = `
    <div style="
      background: linear-gradient(135deg, rgba(var(--accent-rgb), 0.1), rgba(var(--accent-rgb), 0.05));
      border: 1px solid rgba(var(--accent-rgb), 0.2);
      border-radius: var(--r-xl);
      padding: var(--sp-5);
    ">
      <div style="font-size: 18px; font-weight: var(--fw-semibold); margin-bottom: var(--sp-3);">
        🚀 <b>${t('dashboard_quick_actions', 'Quick Actions')}</b>
      </div>
      <div style="display: flex; gap: var(--sp-2); flex-wrap: wrap;">
        <button onclick="window.navigateToPage('commands')" class="btn btn-primary">
          📚 ${t('dashboard_view_commands', 'View Commands')}
        </button>
        <button onclick="window.navigateToPage('automod')" class="btn btn-secondary">
          🛡️ ${t('dashboard_configure_automod', 'Configure AutoMod')}
        </button>
        <button onclick="window.navigateToPage('modules')" class="btn btn-secondary">
          📦 ${t('dashboard_manage_modules', 'Manage Modules')}
        </button>
        <button onclick="window.navigateToPage('analytics')" class="btn btn-secondary">
          📊 ${t('nav_analytics', 'Analytics')}
        </button>
        <a href="${gamesUrl}" class="btn btn-secondary" style="text-decoration:none;display:inline-flex;">
          🎮 ${t('dashboard_play_games', 'Play Games')}
        </a>
      </div>
    </div>
  `;
  container.appendChild(quickActions);

  const statsGrid = document.createElement('div');
  statsGrid.className = 'stats-grid';
  const loadingStats = [
    { label: t('dashboard_total_members', 'Total Members'), value: '...', icon: '👥', color: 'accent' },
    { label: t('dashboard_messages_today', 'Messages Today'), value: '...', icon: '💬', color: 'success' },
    { label: t('dashboard_actions_today', 'Actions Today'), value: '...', icon: '⚡', color: 'warning' },
  ];
  loadingStats.forEach(s => statsGrid.appendChild(StatCard(s)));
  container.appendChild(statsGrid);

  if (finalChatId) {
    try {
      const [group, logsRaw, analyticsData] = await Promise.all([
        apiFetch(`/api/groups/${finalChatId}`),
        apiFetch(`/api/groups/${finalChatId}/logs`),
        apiFetch(`/api/groups/${finalChatId}/analytics`).catch(() => ({ activity: [] }))
      ]);

      const logs = Array.isArray(logsRaw)
        ? logsRaw
        : Array.isArray(logsRaw?.logs)
          ? logsRaw.logs
          : [];

      const memberCount = group?.member_count || 0;
      const activity = analyticsData?.activity || [];
      const todayMessages = activity.length > 0 ? (activity[activity.length - 1]?.messages || 0) : 0;
      const stats = [
        { label: t('dashboard_total_members', 'Total Members'), value: memberCount.toLocaleString(), icon: '👥', color: 'accent' },
        { label: t('dashboard_messages_today', 'Messages Today'), value: todayMessages.toLocaleString(), icon: '💬', color: 'success' },
        { label: t('dashboard_actions_today', 'Actions Today'), value: (() => {
          const today = new Date().toDateString();
          const actionsToday = (Array.isArray(logs) ? logs : []).filter(log => {
            const logDate = new Date(log.timestamp || log.created_at);
            return logDate.toDateString() === today;
          }).length;
          return actionsToday.toLocaleString();
        })(), icon: '⚡', color: 'warning' },
      ];

      statsGrid.innerHTML = '';
      stats.forEach(s => statsGrid.appendChild(StatCard(s)));

      const logList = Array.isArray(logs) ? logs : [];
      state.setLogs(logList);

      const recentLogs = logList.slice(0, 10);
      container.appendChild(Card({
        title: t('dashboard_recent_activity', 'Recent Activity'),
        children: recentLogs.length > 0 ? recentLogs.map(log => `
          <div style="padding: 8px 0; border-bottom: 1px solid var(--border);">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 14px;">${getActionEmoji(log.action)}</span>
              <div style="flex: 1;">
                <div style="font-size: 13px; font-weight: 500;">${formatAction(log.action)}</div>
                <div style="font-size: 11px; color: var(--text-muted);">
                  ${log.by_username ? `by ${log.by_username}` : 'System'}
                </div>
              </div>
              <span style="font-size: 11px; color: var(--text-muted);">${formatTime(log.timestamp)}</span>
            </div>
          </div>
        `).join('') : EmptyState({ icon: '📭', title: t('dashboard_no_activity', 'No recent activity') })
      }));
    } catch (error) {
      console.error('[Dashboard] Error:', error);
    }
  } else {
    container.appendChild(Card({
      title: t('dashboard_welcome', 'Welcome to Nexus'),
      children: EmptyState({
        icon: '👆',
        title: t('dashboard_select_group', 'Select a group'),
        description: t('dashboard_select_group_desc', 'Choose one of your managed groups from the dropdown in the top bar to get started.')
      })
    }));
  }
}
