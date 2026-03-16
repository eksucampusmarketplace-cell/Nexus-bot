/**
 * miniapp/src/pages/notifications.js
 *
 * Owner notification settings page.
 * Allows owners to manage which error types they receive DM notifications for,
 * and view notification history.
 */

import { Card, EmptyState, showToast, Toggle } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

const store = useStore;

// Error type display names and descriptions
const ERROR_TYPE_INFO = {
  // Clone owner notifications
  PRIVACY_MODE_ON: {
    label: 'Privacy Mode Warnings',
    description: 'When clone bots have privacy mode enabled',
    icon: '🔒'
  },
  BOT_NOT_ADMIN: {
    label: 'Bot Not Admin',
    description: 'When bot is added without admin rights',
    icon: '⚠️'
  },
  BOT_CANT_DELETE: {
    label: 'Cannot Delete Messages',
    description: 'Missing delete permission in a group',
    icon: '🗑️'
  },
  BOT_CANT_RESTRICT: {
    label: 'Cannot Restrict Members',
    description: 'Missing restrict/ban permission',
    icon: '🔇'
  },
  BOT_KICKED: {
    label: 'Bot Removed',
    description: 'When bot is kicked from a group',
    icon: '👢'
  },
  FED_BAN_PROPAGATION_FAILED: {
    label: 'TrustNet Ban Failures',
    description: 'When federation bans cannot be enforced',
    icon: '🌐'
  },
  CAPTCHA_WEBAPP_URL_MISSING: {
    label: 'Captcha URL Missing',
    description: 'WebApp captcha mode without RENDER_EXTERNAL_URL',
    icon: '🤖'
  },
  WEBHOOK_FAILED: {
    label: 'Webhook Setup Failed',
    description: 'When webhook registration fails',
    icon: '🔌'
  },
  WEBHOOK_MISSING_UPDATES: {
    label: 'Missing Updates',
    description: 'Webhook set but no updates arriving',
    icon: '📡'
  },
  GROUPS_NOT_APPEARING: {
    label: 'Groups Missing',
    description: 'When groups are missing from dashboard',
    icon: '👥'
  },
  INVALID_TOKEN: {
    label: 'Invalid Token',
    description: 'When Telegram rejects a bot token',
    icon: '🔑'
  },
  // System notifications (main owner only)
  MISSING_ENV_VAR: {
    label: 'Missing Environment Variables',
    description: 'Required env vars not set at startup',
    icon: '⚙️'
  },
  SUPABASE_CONNECTION_FAILED: {
    label: 'Database Connection Failed',
    description: 'Cannot connect to Supabase',
    icon: '💾'
  },
  ANALYTICS_ERROR: {
    label: 'Analytics Errors',
    description: 'Persistent analytics job failures',
    icon: '📊'
  },
  // ML notifications
  ML_TRAINING_COMPLETE: {
    label: 'ML Training Complete',
    description: 'When spam classifier training finishes',
    icon: '✅'
  },
  ML_TRAINING_FAILED: {
    label: 'ML Training Failed',
    description: 'When training fails or has insufficient data',
    icon: '❌'
  }
};

export async function renderNotificationsPage(container) {
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  const header = document.createElement('div');
  header.style.cssText = 'display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);';
  header.innerHTML = `
    <div style="font-size:2rem">🔔</div>
    <div>
      <div style="font-size:1.2rem;font-weight:700">Notification Settings</div>
      <div style="font-size:0.875rem;color:var(--text-muted)">Manage DM alerts from your bots</div>
    </div>
  `;
  container.appendChild(header);

  // Loading state
  container.appendChild(Card({
    title: 'Loading...',
    children: '<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted)">Loading notification preferences...</div>'
  }));

  try {
    // Fetch preferences and history in parallel
    const [prefsRes, historyRes] = await Promise.all([
      apiFetch('/api/owner/notifications').catch(() => ({ preferences: [] })),
      apiFetch('/api/owner/notifications/history?limit=10').catch(() => ({ notifications: [] }))
    ]);

    const preferences = prefsRes.preferences || [];
    const notifications = historyRes.notifications || [];

    // Clear loading state
    container.innerHTML = '';
    container.appendChild(header);

    // ── Recent Notifications Section ──────────────────────────────────────
    const recentCard = Card({
      title: '📋 Recent Notifications',
      subtitle: 'Last 10 DM alerts sent to you'
    });

    if (notifications.length === 0) {
      recentCard.innerHTML += EmptyState({
        icon: '📭',
        title: 'No notifications yet',
        description: 'You haven\'t received any DM alerts. They\'ll appear here when sent.'
      });
    } else {
      const list = document.createElement('div');
      list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';

      notifications.forEach(n => {
        const info = ERROR_TYPE_INFO[n.error_type] || { label: n.error_type, icon: '🔔' };
        const timeAgo = _formatTimeAgo(n.sent_at);

        const row = document.createElement('div');
        row.style.cssText = `
          display:flex;align-items:center;gap:var(--sp-3);
          padding:var(--sp-3);background:var(--bg-card);
          border:1px solid var(--border);border-radius:var(--r-lg);
        `;
        row.innerHTML = `
          <div style="font-size:1.5rem">${info.icon}</div>
          <div style="flex:1;min-width:0;">
            <div style="font-weight:600;font-size:0.875rem;">${info.label}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">
              ${n.bot_name ? `@${n.bot_name}` : 'System'} • ${timeAgo}
            </div>
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;">
            ${n.error_type}
          </div>
        `;
        list.appendChild(row);
      });

      recentCard.appendChild(list);
    }
    container.appendChild(recentCard);

    // ── Notification Preferences Section ─────────────────────────────────
    const prefsCard = Card({
      title: '⚙️ Notification Preferences',
      subtitle: 'Toggle off to silence specific alert types'
    });

    // Group by category
    const categories = {
      clone: { label: 'Clone Bot Alerts', items: [] },
      system: { label: 'System Alerts', items: [] },
      ml: { label: 'ML Training Alerts', items: [] },
      other: { label: 'Other', items: [] }
    };

    preferences.forEach(pref => {
      const cat = categories[pref.category] || categories.other;
      cat.items.push(pref);
    });

    Object.entries(categories).forEach(([key, cat]) => {
      if (cat.items.length === 0) return;

      const catSection = document.createElement('div');
      catSection.style.cssText = 'margin-bottom:var(--sp-4);';
      catSection.innerHTML = `
        <div style="font-size:var(--text-xs);font-weight:700;color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);">
          ${cat.label}
        </div>
      `;

      cat.items.forEach(pref => {
        const info = ERROR_TYPE_INFO[pref.error_type] || {
          label: pref.error_type,
          description: '',
          icon: '🔔'
        };

        const row = document.createElement('div');
        row.style.cssText = `
          display:flex;align-items:center;gap:var(--sp-3);
          padding:var(--sp-3);background:var(--bg-card);
          border:1px solid var(--border);border-radius:var(--r-lg);
          margin-bottom:var(--sp-2);
        `;

        row.innerHTML = `
          <div style="font-size:1.25rem;">${info.icon}</div>
          <div style="flex:1;min-width:0;">
            <div style="font-weight:500;font-size:0.875rem;">${info.label}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">${info.description}</div>
          </div>
          <div class="toggle-container"></div>
        `;

        // Add toggle
        const toggleContainer = row.querySelector('.toggle-container');
        const toggle = Toggle({
          checked: !pref.muted,
          onChange: async (enabled) => {
            try {
              await apiFetch(`/api/owner/notifications/${pref.error_type}`, {
                method: 'PUT',
                body: JSON.stringify({ muted: !enabled })
              });
              showToast(`${info.label} ${enabled ? 'enabled' : 'muted'}`, 'success');
            } catch (e) {
              showToast('Failed to update preference', 'error');
              // Revert toggle visually
              toggle.querySelector('input').checked = !enabled;
            }
          }
        });
        toggleContainer.appendChild(toggle);

        catSection.appendChild(row);
      });

      prefsCard.appendChild(catSection);
    });

    container.appendChild(prefsCard);

    // ── Info Card ─────────────────────────────────────────────────────────
    const infoCard = Card({
      title: 'ℹ️ About Notifications',
      children: `
        <div style="font-size:0.875rem;color:var(--text-secondary);line-height:1.5;">
          <p style="margin:0 0 var(--sp-3);">
            <b>Deduplication:</b> Same error type + same bot = one DM per 24 hours.
          </p>
          <p style="margin:0 0 var(--sp-3);">
            <b>Clone owners</b> receive alerts about their specific clones.
            <b>Main owner</b> receives system-wide alerts.
          </p>
          <p style="margin:0;">
            Muting a notification type prevents future DMs but does not affect bot functionality.
          </p>
        </div>
      `
    });
    container.appendChild(infoCard);

  } catch (e) {
    container.innerHTML = '';
    container.appendChild(header);
    container.appendChild(EmptyState({
      icon: '⚠️',
      title: 'Failed to load',
      description: e.message || 'Could not load notification settings.'
    }));
  }
}

function _formatTimeAgo(isoString) {
  if (!isoString) return 'Unknown';
  const date = new Date(isoString);
  const now = new Date();
  const diff = Math.floor((now - date) / 1000);

  if (diff < 60) return 'Just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return date.toLocaleDateString();
}
