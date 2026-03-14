/**
 * miniapp/src/pages/engagement.js
 *
 * Engagement management page with tabs:
 * [⭐ XP & Levels] [👍 Reputation] [🏅 Badges] [📰 Newsletter] [🌐 Network]
 */

import { Card, Toggle, Badge, EmptyState, showToast } from '../../lib/components.js?v=1.5.0';
import { useStore } from '../../store/index.js?v=1.5.0';
import { apiFetch } from '../../lib/api.js?v=1.5.0';

const store = useStore;
const getState = store.getState;

export async function renderEngagementPage(container) {
  const state = getState();
  const chatId = state.activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '⭐',
      title: 'Select a group',
      description: 'Choose a group to manage engagement settings.'
    }));
    return;
  }

  // Show loading
  container.innerHTML = `
    <div style="text-align: center; padding: var(--sp-8);">
      <div style="font-size: 48px; margin-bottom: var(--sp-4);">⏳</div>
      <div style="color: var(--text-muted);">Loading engagement data...</div>
    </div>
  `;

  try {
    // Load data
    const [leaderboardData, xpSettings] = await Promise.all([
      apiFetch(`/api/groups/${chatId}/xp/leaderboard?limit=20`).catch(() => ({ leaderboard: [] })),
      apiFetch(`/api/groups/${chatId}/xp/settings`).catch(() => ({ enabled: true }))
    ]);

    container.innerHTML = '';

    // Header
    const header = document.createElement('div');
    header.style.cssText = 'margin-bottom: var(--sp-6);';
    header.innerHTML = `
      <h2 style="font-size: 24px; font-weight: 700; margin: 0;">⭐ Engagement</h2>
      <p style="color: var(--text-muted); margin: var(--sp-2) 0 0;">
        XP, reputation, badges, and cross-group networks
      </p>
    `;
    container.appendChild(header);

    // Tab navigation
    const tabs = [
      { id: 'xp', label: 'XP & Levels', icon: '⭐' },
      { id: 'rep', label: 'Reputation', icon: '👍' },
      { id: 'badges', label: 'Badges', icon: '🏅' },
      { id: 'newsletter', label: 'Newsletter', icon: '📰' },
      { id: 'network', label: 'Network', icon: '🌐' },
    ];

    let activeTab = 'xp';

    const tabContainer = document.createElement('div');
    tabContainer.style.cssText = `
      display: flex;
      gap: var(--sp-2);
      margin-bottom: var(--sp-6);
      overflow-x: auto;
      padding-bottom: var(--sp-2);
    `;

    function renderTabs() {
      tabContainer.innerHTML = tabs.map(t => `
        <button
          data-tab="${t.id}"
          style="
            padding: var(--sp-3) var(--sp-4);
            border-radius: var(--r-lg);
            border: none;
            background: ${activeTab === t.id ? 'var(--accent)' : 'var(--bg-input)'};
            color: ${activeTab === t.id ? '#000' : 'var(--text-primary)'};
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s;
          "
        >
          ${t.icon} ${t.label}
        </button>
      `).join('');

      tabContainer.querySelectorAll('button').forEach(btn => {
        btn.onclick = () => {
          activeTab = btn.dataset.tab;
          renderTabs();
          renderTabContent();
        };
      });
    }

    container.appendChild(tabContainer);

    // Content container
    const contentContainer = document.createElement('div');
    container.appendChild(contentContainer);

    function renderTabContent() {
      contentContainer.innerHTML = '';

      switch (activeTab) {
        case 'xp':
          renderXPContent(contentContainer, chatId, leaderboardData, xpSettings);
          break;
        case 'rep':
          renderRepContent(contentContainer, chatId);
          break;
        case 'badges':
          renderBadgesContent(contentContainer, chatId);
          break;
        case 'newsletter':
          renderNewsletterContent(contentContainer, chatId);
          break;
        case 'network':
          renderNetworkContent(contentContainer, chatId);
          break;
      }
    }

    renderTabs();
    renderTabContent();

  } catch (err) {
    container.innerHTML = '';
    container.appendChild(EmptyState({
      icon: '⚠️',
      title: 'Failed to load',
      description: err.message
    }));
  }
}

function renderXPContent(container, chatId, data, settings) {
  // Double XP banner (if active)
  const banner = document.createElement('div');
  banner.style.cssText = `
    background: linear-gradient(135deg, #f59e0b, #d97706);
    border-radius: var(--r-xl);
    padding: var(--sp-4);
    margin-bottom: var(--sp-4);
    color: white;
    display: none;
  `;
  banner.innerHTML = `
    <div style="font-weight: 700; font-size: 16px;">⚡ DOUBLE XP ACTIVE</div>
    <div style="font-size: 14px; opacity: 0.9;">All XP earnings are multiplied by 2x!</div>
  `;
  container.appendChild(banner);

  // Check double XP status
  apiFetch(`/api/groups/${chatId}/xp/settings`).then(s => {
    if (s.double_xp_active) {
      banner.style.display = 'block';
    }
  });

  // Leaderboard
  const leaderboard = data.leaderboard || [];
  const lbCard = Card({
    title: '🏆 XP Leaderboard',
    subtitle: 'Top members by XP',
    children: leaderboard.length ? `
      <div style="display: flex; flex-direction: column; gap: var(--sp-2);">
        ${leaderboard.map((m, i) => {
          const medals = ['🥇', '🥈', '🥉'];
          const rank = medals[i] || `${i + 1}.`;
          const progress = Math.min(100, (m.xp / (m.xp + 1000)) * 100);
          return `
            <div style="
              display: flex;
              align-items: center;
              gap: var(--sp-3);
              padding: var(--sp-3);
              background: var(--bg-input);
              border-radius: var(--r-lg);
            ">
              <div style="font-size: 20px; width: 32px; text-align: center;">${rank}</div>
              <div style="flex: 1;">
                <div style="font-weight: 600;">User ${m.user_id}</div>
                <div style="font-size: 12px; color: var(--text-muted);">
                  Lv.${m.level} • ${m.xp.toLocaleString()} XP
                </div>
                <div style="
                  height: 4px;
                  background: var(--bg-hover);
                  border-radius: 2px;
                  margin-top: var(--sp-1);
                  overflow: hidden;
                ">
                  <div style="
                    width: ${progress}%;
                    height: 100%;
                    background: var(--accent);
                    border-radius: 2px;
                  "></div>
                </div>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    ` : '<div style="text-align: center; padding: var(--sp-8); color: var(--text-muted);">No XP earned yet!</div>'
  });
  container.appendChild(lbCard);

  // XP Settings
  const settingsCard = Card({
    title: '⚙️ XP Settings',
    subtitle: 'Configure XP earning rates',
    children: `
      <div style="display: flex; flex-direction: column; gap: var(--sp-4);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>Enable XP System</span>
          <div class="toggle-wrapper" data-setting="enabled" data-value="${settings.enabled !== false}"></div>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>XP per message</span>
          <input type="number" class="xp-input" data-setting="xp_per_message" value="${settings.xp_per_message || 1}" style="width: 60px; text-align: center;" />
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>Message cooldown (seconds)</span>
          <input type="number" class="xp-input" data-setting="message_cooldown_s" value="${settings.message_cooldown_s || 60}" style="width: 60px; text-align: center;" />
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>XP per daily check-in</span>
          <input type="number" class="xp-input" data-setting="xp_per_daily" value="${settings.xp_per_daily || 10}" style="width: 60px; text-align: center;" />
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>XP per game win</span>
          <input type="number" class="xp-input" data-setting="xp_per_game_win" value="${settings.xp_per_game_win || 5}" style="width: 60px; text-align: center;" />
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>Level-up announcements</span>
          <div class="toggle-wrapper" data-setting="level_up_announce" data-value="${settings.level_up_announce !== false}"></div>
        </div>
        <button class="btn btn-primary save-xp-settings" style="margin-top: var(--sp-2);">
          💾 Save Settings
        </button>
      </div>
    `
  });
  container.appendChild(settingsCard);

  // Double XP button
  const doubleXpCard = Card({
    title: '⚡ Double XP Event',
    subtitle: 'Start a limited-time double XP event',
    children: `
      <div style="display: flex; gap: var(--sp-2); align-items: center;">
        <span>Duration:</span>
        <select id="double-xp-hours" style="flex: 1; padding: var(--sp-2); border-radius: var(--r-lg);">
          <option value="1">1 hour</option>
          <option value="2" selected>2 hours</option>
          <option value="4">4 hours</option>
          <option value="8">8 hours</option>
          <option value="24">24 hours</option>
        </select>
        <button class="btn btn-primary start-double-xp">
          Start Event
        </button>
      </div>
    `
  });
  container.appendChild(doubleXpCard);

  // Initialize toggles
  container.querySelectorAll('.toggle-wrapper').forEach(el => {
    const setting = el.dataset.setting;
    const value = el.dataset.value === 'true';

    const toggle = document.createElement('div');
    toggle.style.cssText = `
      width: 44px;
      height: 24px;
      background: ${value ? 'var(--accent)' : 'var(--bg-hover)'};
      border-radius: 12px;
      position: relative;
      cursor: pointer;
      transition: background 0.2s;
    `;

    const dot = document.createElement('div');
    dot.style.cssText = `
      width: 20px;
      height: 20px;
      background: white;
      border-radius: 50%;
      position: absolute;
      top: 2px;
      left: ${value ? '22px' : '2px'};
      transition: left 0.2s;
    `;
    toggle.appendChild(dot);
    el.appendChild(toggle);

    toggle.onclick = () => {
      const newValue = dot.style.left === '2px';
      dot.style.left = newValue ? '22px' : '2px';
      toggle.style.background = newValue ? 'var(--accent)' : 'var(--bg-hover)';
      el.dataset.value = newValue;
    };
  });

  // Save settings
  container.querySelector('.save-xp-settings').onclick = async () => {
    const newSettings = {};
    container.querySelectorAll('.toggle-wrapper').forEach(el => {
      newSettings[el.dataset.setting] = el.dataset.value === 'true';
    });
    container.querySelectorAll('.xp-input').forEach(el => {
      newSettings[el.dataset.setting] = parseInt(el.value) || 0;
    });

    try {
      await apiFetch(`/api/groups/${chatId}/xp/settings`, {
        method: 'PUT',
        body: JSON.stringify(newSettings)
      });
      showToast('Settings saved!', 'success');
    } catch (e) {
      showToast('Failed to save settings', 'error');
    }
  };

  // Start double XP
  container.querySelector('.start-double-xp').onclick = async () => {
    const hours = parseInt(container.querySelector('#double-xp-hours').value);
    try {
      await apiFetch(`/api/groups/${chatId}/xp/double`, {
        method: 'POST',
        body: JSON.stringify({ hours })
      });
      showToast(`Double XP started for ${hours} hours!`, 'success');
      banner.style.display = 'block';
    } catch (e) {
      showToast('Failed to start double XP', 'error');
    }
  };
}

async function renderRepContent(container, chatId) {
  try {
    const repData = await apiFetch(`/api/groups/${chatId}/rep/leaderboard?limit=10`);

    const repCard = Card({
      title: '👍 Reputation Board',
      subtitle: 'Top members by reputation',
      children: repData.leaderboard?.length ? `
        <div style="display: flex; flex-direction: column; gap: var(--sp-2);">
          ${repData.leaderboard.map((m, i) => `
            <div style="
              display: flex;
              align-items: center;
              gap: var(--sp-3);
              padding: var(--sp-3);
              background: var(--bg-input);
              border-radius: var(--r-lg);
            ">
              <div style="font-size: 20px; width: 32px; text-align: center;">${i + 1}.</div>
              <div style="flex: 1;">
                <div style="font-weight: 600;">User ${m.user_id}</div>
                <div style="font-size: 12px; color: var(--text-muted);">${m.rep_score} rep</div>
              </div>
              <div style="
                height: 8px;
                width: 60px;
                background: var(--bg-hover);
                border-radius: 4px;
                overflow: hidden;
              ">
                <div style="
                  width: ${Math.min(100, (m.rep_score / 50) * 100)}%;
                  height: 100%;
                  background: linear-gradient(90deg, #10b981, #34d399);
                  border-radius: 4px;
                "></div>
              </div>
            </div>
          `).join('')}
        </div>
      ` : '<div style="text-align: center; padding: var(--sp-8); color: var(--text-muted);">No reputation yet!</div>'
    });
    container.appendChild(repCard);

    // Rep settings
    const settingsCard = Card({
      title: '⚙️ Reputation Settings',
      subtitle: 'Configure reputation system',
      children: `
        <div style="display: flex; flex-direction: column; gap: var(--sp-4);">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>Daily rep limit per user</span>
            <input type="number" value="3" style="width: 60px; text-align: center;" />
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>Allow negative rep</span>
            <div style="width: 44px; height: 24px; background: var(--bg-hover); border-radius: 12px; position: relative;">
              <div style="width: 20px; height: 20px; background: white; border-radius: 50%; position: absolute; top: 2px; left: 2px;"></div>
            </div>
          </div>
          <button class="btn btn-primary" style="margin-top: var(--sp-2);">
            💾 Save Settings
          </button>
        </div>
      `
    });
    container.appendChild(settingsCard);

  } catch (e) {
    container.appendChild(EmptyState({
      icon: '⚠️',
      title: 'Failed to load reputation data',
      description: e.message
    }));
  }
}

async function renderBadgesContent(container, chatId) {
  try {
    const badgesData = await apiFetch(`/api/groups/${chatId}/badges`);
    const badges = badgesData.badges || [];

    const badgesCard = Card({
      title: '🏅 Badges',
      subtitle: `${badges.length} badges available`,
      children: badges.length ? `
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: var(--sp-3);">
          ${badges.map(b => `
            <div style="
              background: var(--bg-input);
              border-radius: var(--r-lg);
              padding: var(--sp-4);
              text-align: center;
              border: 1px solid ${b.earned_count > 0 ? 'var(--accent)' : 'var(--border)'};
            ">
              <div style="font-size: 32px; margin-bottom: var(--sp-2);">${b.emoji}</div>
              <div style="font-weight: 600; font-size: 14px;">${b.name}</div>
              <div style="font-size: 12px; color: var(--text-muted); margin-top: var(--sp-1);">
                ${b.earned_count} earned
              </div>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: var(--sp-1);">
                ${b.description}
              </div>
            </div>
          `).join('')}
        </div>
        <button class="btn btn-primary" style="margin-top: var(--sp-4); width: 100%;">
          + Create Custom Badge
        </button>
      ` : '<div style="text-align: center; padding: var(--sp-8); color: var(--text-muted);">No badges yet!</div>'
    });
    container.appendChild(badgesCard);

  } catch (e) {
    container.appendChild(EmptyState({
      icon: '⚠️',
      title: 'Failed to load badges',
      description: e.message
    }));
  }
}

async function renderNewsletterContent(container, chatId) {
  try {
    const [config, history] = await Promise.all([
      apiFetch(`/api/groups/${chatId}/newsletter/settings`),
      apiFetch(`/api/groups/${chatId}/newsletter/history`)
    ]);

    // Preview card
    const previewCard = Card({
      title: '📰 Newsletter Preview',
      subtitle: 'Next send: Sunday at 9:00 AM UTC',
      children: `
        <div style="display: flex; gap: var(--sp-2); flex-wrap: wrap;">
          <button class="btn btn-secondary preview-newsletter">
            👁️ Preview
          </button>
          <button class="btn btn-primary send-newsletter-now">
            📤 Send Now
          </button>
        </div>
        <div class="preview-content" style="
          margin-top: var(--sp-4);
          padding: var(--sp-4);
          background: var(--bg-input);
          border-radius: var(--r-lg);
          white-space: pre-wrap;
          display: none;
        "></div>
      `
    });
    container.appendChild(previewCard);

    // Settings
    const settingsCard = Card({
      title: '⚙️ Newsletter Settings',
      subtitle: 'Configure weekly newsletter',
      children: `
        <div style="display: flex; flex-direction: column; gap: var(--sp-3);">
          <label style="display: flex; align-items: center; gap: var(--sp-2);">
            <input type="checkbox" ${config.enabled !== false ? 'checked' : ''} />
            <span>Enable weekly newsletter</span>
          </label>
          <label style="display: flex; align-items: center; gap: var(--sp-2);">
            <input type="checkbox" ${config.include_top_members !== false ? 'checked' : ''} />
            <span>Include most active members</span>
          </label>
          <label style="display: flex; align-items: center; gap: var(--sp-2);">
            <input type="checkbox" ${config.include_leaderboard !== false ? 'checked' : ''} />
            <span>Include leaderboard snapshot</span>
          </label>
          <label style="display: flex; align-items: center; gap: var(--sp-2);">
            <input type="checkbox" ${config.include_milestones !== false ? 'checked' : ''} />
            <span>Include milestones</span>
          </label>
          <button class="btn btn-primary" style="margin-top: var(--sp-2);">
            💾 Save Settings
          </button>
        </div>
      `
    });
    container.appendChild(settingsCard);

    // History
    if (history.history?.length) {
      const historyCard = Card({
        title: '📜 Newsletter History',
        subtitle: 'Previously sent newsletters',
        children: `
          <div style="display: flex; flex-direction: column; gap: var(--sp-2);">
            ${history.history.map(h => `
              <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: var(--sp-3);
                background: var(--bg-input);
                border-radius: var(--r-lg);
              ">
                <span>${new Date(h.sent_at).toLocaleDateString()}</span>
                <button class="btn btn-secondary" style="padding: var(--sp-1) var(--sp-2); font-size: 12px;">
                  View
                </button>
              </div>
            `).join('')}
          </div>
        `
      });
      container.appendChild(historyCard);
    }

    // Preview handler
    container.querySelector('.preview-newsletter').onclick = async () => {
      const previewEl = container.querySelector('.preview-content');
      previewEl.style.display = 'block';
      previewEl.textContent = 'Loading...';

      try {
        const data = await apiFetch(`/api/groups/${chatId}/newsletter/preview`);
        previewEl.textContent = data.preview;
      } catch (e) {
        previewEl.textContent = 'Failed to load preview';
      }
    };

  } catch (e) {
    container.appendChild(EmptyState({
      icon: '⚠️',
      title: 'Failed to load newsletter data',
      description: e.message
    }));
  }
}

async function renderNetworkContent(container, chatId) {
  try {
    // For now, show a placeholder for network features
    const networkCard = Card({
      title: '🌐 Network',
      subtitle: 'Cross-group networks',
      children: `
        <div style="text-align: center; padding: var(--sp-8);">
          <div style="font-size: 48px; margin-bottom: var(--sp-4);">🌐</div>
          <h3 style="margin: 0 0 var(--sp-2);">Cross-Group Networks</h3>
          <p style="color: var(--text-muted); margin: 0 0 var(--sp-4);">
            Join networks to share leaderboards and announcements across groups.
          </p>
          <div style="display: flex; gap: var(--sp-2); justify-content: center;">
            <button class="btn btn-primary">Join Network</button>
            <button class="btn btn-secondary">Create Network</button>
          </div>
        </div>
        <div style="margin-top: var(--sp-6);">
          <h4 style="margin: 0 0 var(--sp-3);">Available Networks</h4>
          <div style="
            display: flex;
            flex-direction: column;
            gap: var(--sp-2);
            color: var(--text-muted);
            text-align: center;
            padding: var(--sp-4);
          ">
            No networks joined yet.
          </div>
        </div>
      `
    });
    container.appendChild(networkCard);

  } catch (e) {
    container.appendChild(EmptyState({
      icon: '⚠️',
      title: 'Failed to load network data',
      description: e.message
    }));
  }
}
