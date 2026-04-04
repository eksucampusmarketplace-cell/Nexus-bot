/**
 * miniapp/src/pages/booster.js
 * 
 * Member Booster management page.
 * Enhanced with manual tracking, invite progress, and leaderboard.
 */

import { Card, EmptyState, Toggle, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { t } from '../../lib/i18n.js?v=1.6.0';

export async function renderBoosterPage(container) {
  const chatId = useStore.getState().activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '🚀',
      title: t('select_group', 'Select a group'),
      description: t('booster_select_group', 'Choose a group to manage member booster.')
    }));
    return;
  }

  const header = document.createElement('div');
  header.style.cssText = 'margin-bottom: var(--sp-6);';
  header.innerHTML = `
    <h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">🚀 ${t('nav_booster', 'Member Booster')}</h2>
    <p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">${t('booster_subtitle', 'Manage invite-to-unlock and join requirements')}</p>
  `;
  container.appendChild(header);

  const loadingEl = document.createElement('div');
  loadingEl.style.cssText = 'text-align:center;padding:var(--sp-8);color:var(--text-muted);';
  loadingEl.textContent = t('loading', 'Loading...');
  container.appendChild(loadingEl);

  try {
    const config = await apiFetch(`/api/groups/${chatId}/boost/config`);
    loadingEl.remove();

    // --- Configuration Card ---
    const configCard = Card({
      title: '⚙️ ' + t('booster_config', 'Booster Configuration'),
      subtitle: t('booster_config_sub', 'Set requirements for new members')
    });

    const formEl = document.createElement('div');
    formEl.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-4);padding-top:var(--sp-2);';
    formEl.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <span>${t('booster_enable', 'Enable Member Booster')}</span>
        <div id="booster-enabled-toggle"></div>
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <span>${t('booster_required', 'Required Invites')}</span>
        <input type="number" id="boost-count-input" class="input" style="width:80px;" value="${config?.required_count || 0}" min="0">
      </div>
      <button id="save-booster-config" class="btn btn-primary">${t('save_btn', 'Save Configuration')}</button>
    `;
    configCard.appendChild(formEl);
    container.appendChild(configCard);
    
    const toggleContainer = configCard.querySelector('#booster-enabled-toggle');
    toggleContainer.appendChild(Toggle({
      checked: config?.enabled || false,
      onChange: async (v) => {
        try {
          await apiFetch(`/api/groups/${chatId}/boost/config`, {
            method: 'PUT',
            body: { enabled: v }
          });
          showToast(t('nav_booster', 'Booster') + ' ' + (v ? t('enabled', 'enabled') : t('disabled', 'disabled')), 'success');
        } catch (e) { showToast(t('error_update', 'Error updating booster'), 'error'); }
      }
    }));
    
    configCard.querySelector('#save-booster-config').onclick = async () => {
      const count = parseInt(configCard.querySelector('#boost-count-input').value);
      try {
        await apiFetch(`/api/groups/${chatId}/boost/config`, {
          method: 'PUT',
          body: { required_count: count }
        });
        showToast(t('toast_save_success', 'Configuration saved'), 'success');
      } catch (e) {
        showToast(t('error_save', 'Failed to save'), 'error');
      }
    };

    // --- Manual Grant Card ---
    const grantCard = Card({
      title: '👤 ' + t('booster_manual', 'Manual Member Grant'),
      subtitle: t('booster_manual_sub', 'Manually grant or revoke boost access for specific users')
    });
    const grantForm = document.createElement('div');
    grantForm.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-3);padding-top:var(--sp-2);';
    grantForm.innerHTML = `
      <div>
        <label style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:var(--sp-1);">${t('booster_user_id', 'User ID')}</label>
        <input type="number" id="grant-user-id" class="input" placeholder="${t('booster_user_id_placeholder', 'Enter Telegram user ID')}" style="width:100%;box-sizing:border-box;">
      </div>
      <div style="display:flex;gap:var(--sp-2);">
        <button id="grant-boost-btn" class="btn btn-primary" style="flex:1;">✅ ${t('booster_grant', 'Grant Access')}</button>
        <button id="revoke-boost-btn" class="btn btn-danger" style="flex:1;">❌ ${t('booster_revoke', 'Revoke Access')}</button>
      </div>
    `;
    grantCard.appendChild(grantForm);
    container.appendChild(grantCard);

    grantCard.querySelector('#grant-boost-btn').onclick = async () => {
      const uid = parseInt(grantCard.querySelector('#grant-user-id').value);
      if (!uid) { showToast(t('booster_enter_id', 'Enter a valid user ID'), 'error'); return; }
      try {
        await apiFetch(`/api/groups/${chatId}/boost/grant`, {
          method: 'POST',
          body: { user_id: uid }
        });
        showToast(t('booster_granted', 'Access granted to user ') + uid, 'success');
        grantCard.querySelector('#grant-user-id').value = '';
        _loadTracking(chatId, trackingContainer);
      } catch (e) {
        showToast(e.message || t('error', 'Failed to grant access'), 'error');
      }
    };

    grantCard.querySelector('#revoke-boost-btn').onclick = async () => {
      const uid = parseInt(grantCard.querySelector('#grant-user-id').value);
      if (!uid) { showToast(t('booster_enter_id', 'Enter a valid user ID'), 'error'); return; }
      try {
        await apiFetch(`/api/groups/${chatId}/boost/revoke`, {
          method: 'POST',
          body: { user_id: uid }
        });
        showToast(t('booster_revoked', 'Access revoked for user ') + uid, 'success');
        grantCard.querySelector('#grant-user-id').value = '';
        _loadTracking(chatId, trackingContainer);
      } catch (e) {
        showToast(e.message || t('error', 'Failed to revoke access'), 'error');
      }
    };

    // --- Invite Progress & Tracking Card ---
    const trackingCard = Card({
      title: '📊 ' + t('booster_tracking', 'Invite Tracking'),
      subtitle: t('booster_tracking_sub', 'Track member invite progress and manually added members')
    });
    const trackingContainer = document.createElement('div');
    trackingContainer.id = 'boost-tracking-container';
    trackingCard.appendChild(trackingContainer);
    container.appendChild(trackingCard);

    _loadTracking(chatId, trackingContainer);

  } catch (e) {
    loadingEl.remove();
    container.appendChild(EmptyState({
      icon: '⚠️',
      title: t('booster_unavailable', 'Feature not available'),
      description: t('booster_unavailable_desc', 'The Member Booster API is not responding. Make sure the booster module is enabled in Modules.')
    }));
  }
}

async function _loadTracking(chatId, container) {
  container.innerHTML = '<div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);">' + t('loading', 'Loading...') + '</div>';

  try {
    const data = await apiFetch(`/api/groups/${chatId}/boost/tracking`);
    container.innerHTML = '';

    const members = Array.isArray(data) ? data : (data?.members || data?.tracking || []);

    if (members.length === 0) {
      container.innerHTML = '<div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);">' +
        '<div style="font-size:2rem;margin-bottom:var(--sp-2);">📭</div>' +
        t('booster_no_tracking', 'No boost tracking data yet. Members will appear here once they start inviting or are manually granted.') +
        '</div>';
      return;
    }

    // Stats summary
    const totalGranted = members.filter(m => m.granted || m.unlocked).length;
    const totalPending = members.filter(m => !m.granted && !m.unlocked).length;
    const manualCount = members.filter(m => m.manual).length;

    const statsRow = document.createElement('div');
    statsRow.style.cssText = 'display:grid;grid-template-columns:repeat(3,1fr);gap:var(--sp-2);margin-bottom:var(--sp-3);';
    statsRow.innerHTML = `
      <div style="background:var(--bg-input);padding:var(--sp-2);border-radius:var(--r-lg);text-align:center;">
        <div style="font-size:var(--text-lg);font-weight:700;color:var(--success);">${totalGranted}</div>
        <div style="font-size:var(--text-xs);color:var(--text-muted);">${t('booster_unlocked', 'Unlocked')}</div>
      </div>
      <div style="background:var(--bg-input);padding:var(--sp-2);border-radius:var(--r-lg);text-align:center;">
        <div style="font-size:var(--text-lg);font-weight:700;color:var(--warning);">${totalPending}</div>
        <div style="font-size:var(--text-xs);color:var(--text-muted);">${t('booster_pending', 'Pending')}</div>
      </div>
      <div style="background:var(--bg-input);padding:var(--sp-2);border-radius:var(--r-lg);text-align:center;">
        <div style="font-size:var(--text-lg);font-weight:700;color:var(--accent);">${manualCount}</div>
        <div style="font-size:var(--text-xs);color:var(--text-muted);">${t('booster_manual_short', 'Manual')}</div>
      </div>
    `;
    container.appendChild(statsRow);

    // Member list sorted by invite count
    const list = document.createElement('div');
    list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';

    members.sort((a, b) => (b.invite_count || 0) - (a.invite_count || 0));

    members.forEach((m, idx) => {
      const isUnlocked = m.granted || m.unlocked;
      const progress = m.invite_count || 0;
      const required = m.required_count || 0;
      const pct = required > 0 ? Math.min((progress / required) * 100, 100) : (isUnlocked ? 100 : 0);
      const medal = idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : '';

      const item = document.createElement('div');
      item.style.cssText = 'display:flex;align-items:center;gap:var(--sp-3);padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);' + (isUnlocked ? 'border-left:3px solid var(--success);' : '');
      item.innerHTML = `
        <div style="flex:1;min-width:0;">
          <div style="display:flex;align-items:center;gap:var(--sp-1);">
            ${medal ? '<span>' + medal + '</span>' : ''}
            <span style="font-weight:var(--fw-semibold);font-size:var(--text-sm);">${_escapeHtml(m.first_name || m.username || 'User ' + (m.user_id || ''))}</span>
            ${m.manual ? '<span style="font-size:var(--text-xs);background:var(--accent-dim);color:var(--accent);padding:1px 6px;border-radius:var(--r-full);margin-left:var(--sp-1);">Manual</span>' : ''}
          </div>
          <div style="font-size:var(--text-xs);color:var(--text-muted);">
            ${isUnlocked ? '✅ ' + t('booster_access_granted', 'Access granted') : progress + '/' + required + ' ' + t('booster_invites', 'invites')}
          </div>
          ${!isUnlocked && required > 0 ? '<div style="height:4px;background:var(--bg-card);border-radius:2px;margin-top:4px;overflow:hidden;"><div style="height:100%;width:' + pct + '%;background:var(--accent);border-radius:2px;transition:width .3s;"></div></div>' : ''}
        </div>
        <div style="flex-shrink:0;">
          <span style="font-size:var(--text-xs);color:${isUnlocked ? 'var(--success)' : 'var(--warning)'};font-weight:var(--fw-semibold);">
            ${isUnlocked ? '✅' : '⏳'}
          </span>
        </div>
      `;
      list.appendChild(item);
    });

    container.appendChild(list);
  } catch (e) {
    container.innerHTML = '<div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);">' +
      '<div style="font-size:2rem;margin-bottom:var(--sp-2);">📊</div>' +
      t('booster_tracking_unavailable', 'Invite tracking data is not available yet. Grant access manually or wait for members to start inviting.') +
      '</div>';
  }
}

function _escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}
