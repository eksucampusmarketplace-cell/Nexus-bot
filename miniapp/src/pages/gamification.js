/**
 * miniapp/src/pages/gamification.js
 * Task 3 of 12 — Leaderboard / Gamification page
 * Extracted from index.html renderGamificationPage()
 */

import { EmptyState } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

const store = useStore;
const getState = store.getState;

export async function renderGamificationPage(container) {
  const state = getState();
  const chatId = state.activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId && state.groups && state.groups.length > 0) {
    const firstGroup = state.groups[0];
    state.setActiveChatId(firstGroup.chat_id);
  }

  const finalChatId = getState().activeChatId;

  if (!finalChatId) {
    container.appendChild(EmptyState({ icon: '🏆', title: 'Select a group', description: 'Choose a group to view the leaderboard.' }));
    return;
  }

  container.innerHTML = `
    <div style="text-align: center; padding: var(--sp-8);">
      <div style="font-size: 48px; margin-bottom: var(--sp-4);">⏳</div>
      <div style="color: var(--text-muted);">Loading leaderboard...</div>
    </div>
  `;

  try {
    let leaderboardData = [];

    try {
      const data = await apiFetch(`/api/groups/${finalChatId}/xp/leaderboard?limit=20`);
      const leaderboardItems = data?.leaderboard || [];
      if (leaderboardItems.length) {
        leaderboardData = leaderboardItems;
      }
    } catch (e) {
      console.error('[Leaderboard] Failed to fetch:', e);
    }

    container.innerHTML = '';
    container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

    const header = document.createElement('div');
    header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-4);';
    header.innerHTML = `
      <div>
        <h2 style="font-size:20px;font-weight:700;margin:0;">🏆 Leaderboard</h2>
        <p style="color:var(--text-muted);font-size:13px;margin:4px 0 0;">Top members by XP</p>
      </div>
      <a href="games.html?chat_id=${finalChatId}" class="btn btn-primary" style="text-decoration:none;">🎮 Play Games</a>
    `;
    container.appendChild(header);

    if (!leaderboardData || leaderboardData.length === 0) {
      container.appendChild(EmptyState({ icon: '🏆', title: 'No XP data yet', description: 'Members need to chat and play games to earn XP.' }));
      return;
    }

    const medals = ['🥇', '🥈', '🥉'];
    const list = document.createElement('div');
    list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';

    leaderboardData.forEach((user, i) => {
      const badges = Array.isArray(user.badges) ? user.badges : [];
      const badgeMap = {
        'first_100': '💯', 'first_1000': '🏆', 'streak_7': '🔥',
        'streak_30': '⚡', 'level_5': '📈', 'level_10': '👑', 'level_25': '🔱'
      };
      const badgesHtml = badges.map(b => `<span style="margin-left:2px;">${badgeMap[b] || '🏅'}</span>`).join('');

      const row = document.createElement('div');
      row.style.cssText = `
        display:flex;align-items:center;gap:var(--sp-3);
        padding:var(--sp-3);background:var(--card);
        border:1px solid var(--border);border-radius:var(--r-lg);
      `;
      row.innerHTML = `
        <div style="font-size:20px;width:32px;text-align:center;font-weight:700;">${medals[i] || i + 1}</div>
        <div style="width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#00d4ff);display:flex;align-items:center;justify-content:center;font-weight:700;">${(user.first_name || 'U').charAt(0).toUpperCase()}</div>
        <div style="flex:1;min-width:0;">
          <div style="font-weight:600;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${user.first_name || 'User'} ${badgesHtml}</div>
          <div style="font-size:12px;color:var(--text-muted);">Level ${user.level || 1} • ${user.xp || 0} XP</div>
        </div>
      `;
      list.appendChild(row);
    });

    container.appendChild(list);
  } catch (err) {
    container.innerHTML = '';
    container.appendChild(EmptyState({ icon: '⚠️', title: 'Failed to load', description: err.message }));
  }
}
