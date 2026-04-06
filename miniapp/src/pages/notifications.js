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
import { t } from '../../lib/i18n.js?v=1.6.0';

const store = useStore;

// Error type display names and descriptions
const ERROR_TYPE_INFO = {
  // Clone owner notifications
  PRIVACY_MODE_ON: {
    label: t('notif_privacy_mode', 'Privacy Mode Warnings'),
    description: t('notif_privacy_mode_desc', 'When clone bots have privacy mode enabled'),
    icon: '🔒'
  },
  BOT_NOT_ADMIN: {
    label: t('notif_not_admin', 'Bot Not Admin'),
    description: t('notif_not_admin_desc', 'When bot is added without admin rights'),
    icon: '⚠️'
  },
  BOT_CANT_DELETE: {
    label: t('notif_cant_delete', 'Cannot Delete Messages'),
    description: t('notif_cant_delete_desc', 'Missing delete permission in a group'),
    icon: '🗑️'
  },
  BOT_CANT_RESTRICT: {
    label: t('notif_cant_restrict', 'Cannot Restrict Members'),
    description: t('notif_cant_restrict_desc', 'Missing restrict/ban permission'),
    icon: '🔇'
  },
  BOT_KICKED: {
    label: t('notif_kicked', 'Bot Removed'),
    description: t('notif_kicked_desc', 'When bot is kicked from a group'),
    icon: '👢'
  },
  FED_BAN_PROPAGATION_FAILED: {
    label: t('notif_trustnet_fail', 'TrustNet Ban Failures'),
    description: t('notif_trustnet_fail_desc', 'When federation bans cannot be enforced'),
    icon: '🌐'
  },
  CAPTCHA_WEBAPP_URL_MISSING: {
    label: t('notif_captcha_url', 'Captcha URL Missing'),
    description: t('notif_captcha_url_desc', 'WebApp captcha mode without RENDER_EXTERNAL_URL'),
    icon: '🤖'
  },
  WEBHOOK_FAILED: {
    label: t('notif_webhook_fail', 'Webhook Setup Failed'),
    description: t('notif_webhook_fail_desc', 'When webhook registration fails'),
    icon: '🔌'
  },
  WEBHOOK_MISSING_UPDATES: {
    label: t('notif_missing_updates', 'Missing Updates'),
    description: t('notif_missing_updates_desc', 'Webhook set but no updates arriving'),
    icon: '📡'
  },
  GROUPS_NOT_APPEARING: {
    label: t('notif_groups_missing', 'Groups Missing'),
    description: t('notif_groups_missing_desc', 'When groups are missing from dashboard'),
    icon: '👥'
  },
  INVALID_TOKEN: {
    label: t('notif_invalid_token', 'Invalid Token'),
    description: t('notif_invalid_token_desc', 'When Telegram rejects a bot token'),
    icon: '🔑'
  },
  // System notifications (main owner only)
  MISSING_ENV_VAR: {
    label: t('notif_missing_env', 'Missing Environment Variables'),
    description: t('notif_missing_env_desc', 'Required env vars not set at startup'),
    icon: '⚙️'
  },
  SUPABASE_CONNECTION_FAILED: {
    label: t('notif_db_fail', 'Database Connection Failed'),
    description: t('notif_db_fail_desc', 'Cannot connect to Supabase'),
    icon: '💾'
  },
  ANALYTICS_ERROR: {
    label: t('notif_analytics_error', 'Analytics Errors'),
    description: t('notif_analytics_error_desc', 'Persistent analytics job failures'),
    icon: '📊'
  },
  // ML notifications
  ML_TRAINING_COMPLETE: {
    label: t('notif_ml_complete', 'ML Training Complete'),
    description: t('notif_ml_complete_desc', 'When spam classifier training finishes'),
    icon: '✅'
  },
  ML_TRAINING_FAILED: {
    label: t('notif_ml_fail', 'ML Training Failed'),
    description: t('notif_ml_fail_desc', 'When training fails or has insufficient data'),
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
      <div style="font-size:1.2rem;font-weight:700">${t('notif_settings_title', 'Notification Settings')}</div>
      <div style="font-size:0.875rem;color:var(--text-muted)">${t('notif_settings_subtitle', 'Manage DM alerts from your bots')}</div>
    </div>
  `;
  container.appendChild(header);

  // Loading state
  container.appendChild(Card({
    title: t('loading', 'Loading...'),
    children: `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted)">${t('loading_notif_prefs', 'Loading notification preferences...')}</div>`
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
      title: '📋 ' + t('recent_notifications', 'Recent Notifications'),
      subtitle: t('last_10_alerts', 'Last 10 DM alerts sent to you')
    });

    if (notifications.length === 0) {
      recentCard.innerHTML += EmptyState({
        icon: '📭',
        title: t('no_notifications_yet', 'No notifications yet'),
        description: t('no_notifications_desc', 'You haven\'t received any DM alerts. They\'ll appear here when sent.')
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
      title: '⚙️ ' + t('notif_prefs_title', 'Notification Preferences'),
      subtitle: t('notif_prefs_subtitle', 'Toggle off to silence specific alert types')
    });

    // Group by category
    const categories = {
      clone: { label: t('notif_cat_clone', 'Clone Bot Alerts'), items: [] },
      system: { label: t('notif_cat_system', 'System Alerts'), items: [] },
      ml: { label: t('notif_cat_ml', 'ML Training Alerts'), items: [] },
      other: { label: t('notif_cat_other', 'Other'), items: [] }
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
              showToast(`${info.label} ${enabled ? t('enabled', 'enabled') : t('muted', 'muted')}`, 'success');
              } catch (e) {
              showToast(t('failed_to_update_preference', 'Failed to update preference'), 'error');
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
              title: 'ℹ️ ' + t('about_notifications', 'About Notifications'),
              children: `
              <div style="font-size:0.875rem;color:var(--text-secondary);line-height:1.5;">
              <p style="margin:0 0 var(--sp-3);">
              <b>${t('deduplication', 'Deduplication')}:</b> ${t('deduplication_desc', 'Same error type + same bot = one DM per 24 hours.')}
              </p>
              <p style="margin:0 0 var(--sp-3);">
              <b>${t('clone_owners', 'Clone owners')}</b> ${t('clone_owners_notif_desc', 'receive alerts about their specific clones.')}
              <b>${t('main_owner', 'Main owner')}</b> ${t('main_owner_notif_desc', 'receives system-wide alerts.')}
              </p>
              <p style="margin:0;">
              ${t('muting_notif_hint', 'Muting a notification type prevents future DMs but does not affect bot functionality.')}
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
              title: t('failed_to_load', 'Failed to load'),
              description: e.message || t('could_not_load_notif_settings', 'Could not load notification settings.')
              }));
              }
              }

              function _formatTimeAgo(isoString) {
              if (!isoString) return t('unknown', 'Unknown');
              const date = new Date(isoString);
              const now = new Date();
              const diff = Math.floor((now - date) / 1000);

              if (diff < 60) return t('just_now', 'Just now');
              if (diff < 3600) return `${Math.floor(diff / 60)}${t('m_ago', 'm ago')}`;
              if (diff < 86400) return `${Math.floor(diff / 3600)}${t('h_ago', 'h ago')}`;
              if (diff < 604800) return `${Math.floor(diff / 86400)}${t('d_ago', 'd ago')}`;
              return date.toLocaleDateString();
              }
