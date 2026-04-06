/**
 * miniapp/src/pages/owner.js
 * 
 * Owner Panel page - supports both main owner and clone owners
 */

import { Card, StatCard, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { t } from '../../lib/i18n.js?v=1.6.0';

const store = useStore;
const getState = store.getState;

export async function renderOwnerPage(container) {
  container.innerHTML = '';
  container.style.cssText = 'padding:var(--sp-4);max-width:var(--content-max);margin:0 auto;';

  // Check if user is main owner or clone owner
  let isMainOwner = false;
  let isCloneOwner = false;
  
  try {
    const statsRes = await apiFetch('/api/admin/stats');
    isMainOwner = statsRes.is_main_owner === true;
  } catch (e) {
    // Try clone owner endpoint
    try {
      const cloneStats = await apiFetch('/api/clone-owner/stats');
      isCloneOwner = cloneStats && cloneStats.bots !== undefined;
    } catch (e2) {
      // Not an owner at all
    }
  }

  const header = document.createElement('div');
  header.style.cssText = 'display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);';
  const title = isMainOwner ? t('nav_owner', 'Owner Panel') : t('nav_clone_owner', 'Clone Owner Panel');
  const icon = isMainOwner ? '👑' : '🤖';
  header.innerHTML = `<div style="font-size:2rem">${icon}</div><div style="font-size:1.2rem;font-weight:700">${title}</div>`;
  container.appendChild(header);

  if (isMainOwner) {
    await renderMainOwnerPanel(container);
  } else if (isCloneOwner) {
    await renderCloneOwnerPanel(container);
  } else {
    const msg = document.createElement('div');
    msg.style.cssText = 'text-align:center;padding:var(--sp-8);color:var(--text-muted);';
    msg.textContent = t('owner_access_only', 'Owner access only.');
    container.appendChild(msg);
  }
}

async function renderMainOwnerPanel(container) {
  // Fetch stats
  let statsRes = null;
  try {
    statsRes = await apiFetch('/api/admin/stats');
  } catch (e) {
    console.error('Failed to fetch stats:', e);
  }

  if (statsRes) {
    const row = document.createElement('div');
    row.style.cssText = 'display:grid;grid-template-columns:repeat(3,1fr);gap:var(--sp-3);margin-bottom:var(--sp-5);';
    [{label:t('owner_clones', 'Clones'),val:statsRes.bots,icon:'🤖'},{label:t('owner_groups', 'Groups'),val:statsRes.groups,icon:'👥'},{label:t('owner_users', 'Users'),val:statsRes.users,icon:'👤'}]
      .forEach(s => {
        const c = document.createElement('div');
        c.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-3);text-align:center;';
        c.innerHTML = '<div style="font-size:1.5rem">'+s.icon+'</div><div style="font-size:1.5rem;font-weight:700">'+(s.val||0)+'</div><div style="font-size:0.75rem;color:var(--text-muted)">'+s.label+'</div>';
        row.appendChild(c);
      });
    container.appendChild(row);
  }

  // Quick Actions
  const actRow = document.createElement('div');
  actRow.style.cssText = 'display:grid;grid-template-columns:repeat(2,1fr);gap:var(--sp-3);margin-bottom:var(--sp-4);';
  const actions = [
    {label:'📋 ' + t('owner_view_clones', 'Manage Clones'), page:'bots'},
    {label:'📢 ' + t('owner_broadcast', 'Broadcast'), page:'broadcast'},
    {label:'📊 ' + t('nav_analytics', 'Analytics'), page:'analytics'},
    {label:'🎮 ' + t('nav_games', 'Games Leaderboard'), page:'games'}
  ];
  actions.forEach(a => {
    const btn = document.createElement('button');
    btn.textContent = a.label;
    btn.style.cssText = 'padding:var(--sp-3);background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);cursor:pointer;text-align:center;font-size:0.9rem;color:var(--text-primary);transition:all 0.2s;';
    btn.onmouseover = () => { btn.style.borderColor = 'var(--accent)'; btn.style.background = 'var(--bg-elevated)'; };
    btn.onmouseout = () => { btn.style.borderColor = 'var(--border)'; btn.style.background = 'var(--bg-card)'; };
    btn.onclick = () => window.navigateToPage(a.page);
    actRow.appendChild(btn);
  });
  container.appendChild(actRow);

  // Clone Status Section
  await renderCloneStatusSection(container);

  // Group Detection Section
  await renderGroupsSection(container);

  // System Health Section
  await renderSystemHealthSection(container);

  // Economy Controls (Owner Only)
  await renderEconomyControls(container);

  // Notification Settings
  await renderNotificationSettings(container);
}

async function renderCloneOwnerPanel(container) {
  // Fetch clone owner stats
  let statsRes = null;
  try {
    statsRes = await apiFetch('/api/clone-owner/stats');
  } catch (e) {
    console.error('Failed to fetch clone owner stats:', e);
  }

  if (statsRes) {
    const row = document.createElement('div');
    row.style.cssText = 'display:grid;grid-template-columns:repeat(3,1fr);gap:var(--sp-3);margin-bottom:var(--sp-5);';
    const stats = [
      {label:t('owner_my_clones', 'My Clones'),val:statsRes.bots?.length || 0,icon:'🤖'},
      {label:t('owner_groups', 'Groups'),val:statsRes.total_groups,icon:'👥'},
      {label:t('owner_users', 'Users'),val:statsRes.total_users,icon:'👤'}
    ];
    stats.forEach(s => {
      const c = document.createElement('div');
      c.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-3);text-align:center;';
      c.innerHTML = '<div style="font-size:1.5rem">'+s.icon+'</div><div style="font-size:1.5rem;font-weight:700">'+(s.val||0)+'</div><div style="font-size:0.75rem;color:var(--text-muted)">'+s.label+'</div>';
      row.appendChild(c);
    });
    container.appendChild(row);
  }

  // Quick Actions for clone owners
  const actRow = document.createElement('div');
  actRow.style.cssText = 'display:grid;grid-template-columns:repeat(2,1fr);gap:var(--sp-3);margin-bottom:var(--sp-4);';
  const actions = [
    {label:'📋 ' + t('owner_view_clones', 'Manage Clones'), page:'bots'},
    {label:'📢 ' + t('owner_broadcast', 'Broadcast'), page:'broadcast'},
    {label:'📊 ' + t('nav_analytics', 'Analytics'), page:'analytics'},
    {label:'📝 ' + t('nav_commands', 'Custom Commands'), page:'custom_commands'}
  ];
  actions.forEach(a => {
    const btn = document.createElement('button');
    btn.textContent = a.label;
    btn.style.cssText = 'padding:var(--sp-3);background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);cursor:pointer;text-align:center;font-size:0.9rem;color:var(--text-primary);transition:all 0.2s;';
    btn.onmouseover = () => { btn.style.borderColor = 'var(--accent)'; btn.style.background = 'var(--bg-elevated)'; };
    btn.onmouseout = () => { btn.style.borderColor = 'var(--border)'; btn.style.background = 'var(--bg-card)'; };
    btn.onclick = () => window.navigateToPage(a.page);
    actRow.appendChild(btn);
  });
  container.appendChild(actRow);

  // Clone Bots Status
  if (statsRes?.bots?.length) {
    const cloneCard = Card({ title: '🤖 ' + t('owner_my_clones', 'My Clone Bots'), subtitle: t('owner_clone_status_sub', 'Status of your bot clones') });
    const cloneList = document.createElement('div');
    cloneList.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);padding-top:var(--sp-2);';

    const statusCounts = { online: 0, offline: 0, error: 0 };

    statsRes.bots.forEach(bot => {
      const isOnline = bot.status === 'active';
      const isDead = bot.status === 'dead';
      
      if (isOnline) statusCounts.online++;
      else if (isDead) statusCounts.error++;
      else statusCounts.offline++;

      const statusColor = isOnline ? 'var(--success)' : isDead ? 'var(--danger)' : 'var(--warning)';
      const statusIcon = isOnline ? '🟢' : isDead ? '🔴' : '🟡';
      const statusText = isOnline ? t('status_online', 'Online') : isDead ? t('status_error', 'Error') : t('status_offline', 'Offline');

      const item = document.createElement('div');
      item.style.cssText = 'display:flex;align-items:center;gap:var(--sp-3);padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);border-left:3px solid ' + statusColor + ';';
      item.innerHTML = `
        <div style="flex:1;">
          <div style="font-weight:var(--fw-semibold);font-size:var(--text-sm);">@${escapeHtml(bot.username || 'Unknown')}</div>
          <div style="font-size:var(--text-xs);color:var(--text-muted);">${bot.groups_count || 0} groups</div>
        </div>
        <div style="display:flex;align-items:center;gap:var(--sp-1);">
          <span style="font-size:0.7rem;">${statusIcon}</span>
          <span style="font-size:var(--text-xs);color:${statusColor};font-weight:var(--fw-semibold);">${statusText}</span>
        </div>
      `;
      
      if (isDead && bot.death_reason) {
        const errorInfo = document.createElement('div');
        errorInfo.style.cssText = 'font-size:var(--text-xs);color:var(--danger);margin-top:var(--sp-1);padding-left:var(--sp-1);';
        errorInfo.textContent = bot.death_reason;
        item.querySelector('div').appendChild(errorInfo);
      }

      cloneList.appendChild(item);
    });

    // Status summary
    const summaryBar = document.createElement('div');
    summaryBar.style.cssText = 'display:flex;gap:var(--sp-3);padding:var(--sp-2) 0;margin-bottom:var(--sp-2);';
    summaryBar.innerHTML = `
      <span style="font-size:var(--text-xs);color:var(--success);font-weight:600;">🟢 ${statusCounts.online} Online</span>
      <span style="font-size:var(--text-xs);color:var(--danger);font-weight:600;">🔴 ${statusCounts.error} Error</span>
    `;
    cloneCard.appendChild(summaryBar);
    cloneCard.appendChild(cloneList);
    container.appendChild(cloneCard);
  }

  // Groups for clone owners
  try {
    const groupsRes = await apiFetch('/api/clone-owner/groups');
    if (groupsRes?.length) {
      const groupCard = Card({ title: '👥 ' + t('owner_detected_groups', 'My Groups'), subtitle: t('owner_detected_groups_sub', 'Groups where your bots are active') });
      const groupList = document.createElement('div');
      groupList.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);padding-top:var(--sp-2);';

      groupsRes.slice(0, 10).forEach(group => {
        const item = document.createElement('div');
        item.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);cursor:pointer;transition:all 0.2s;';
        item.innerHTML = `
          <div style="flex:1;min-width:0;">
            <div style="font-weight:var(--fw-semibold);font-size:var(--text-sm);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(group.title || 'Unnamed Group')}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">${group.member_count || 0} members • @${escapeHtml(group.bot_username || '')}</div>
          </div>
          <span style="font-size:var(--text-xs);color:var(--accent);">Open →</span>
        `;
        item.onclick = () => {
          getState().setActiveChatId(group.chat_id);
          window.navigateToPage('dashboard');
        };
        groupList.appendChild(item);
      });

      if (groupsRes.length > 10) {
        const more = document.createElement('div');
        more.style.cssText = 'text-align:center;padding:var(--sp-2);color:var(--text-muted);font-size:var(--text-xs);';
        more.textContent = `+ ${groupsRes.length - 10} more groups`;
        groupList.appendChild(more);
      }

      groupCard.appendChild(groupList);
      container.appendChild(groupCard);
    }
  } catch (e) {
    console.debug('Failed to load groups:', e);
  }
}

async function renderCloneStatusSection(container) {
  try {
    const botsRes = await apiFetch('/api/bots');
    const botsArray = Array.isArray(botsRes) ? botsRes : (botsRes?.bots || []);
    
    if (botsArray.length > 0) {
      const cloneCard = Card({ title: '🤖 ' + t('owner_clone_status_title', 'Clone Status'), subtitle: t('owner_clone_status_sub', 'Real-time status of all bot clones') });
      const cloneList = document.createElement('div');
      cloneList.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);padding-top:var(--sp-2);';

      const statusCounts = { online: 0, offline: 0, error: 0 };

      botsArray.forEach(bot => {
        const status = bot.status || 'unknown';
        const isOnline = status === 'running' || status === 'online' || status === 'active';
        const isDead = status === 'dead' || status === 'error' || status === 'stopped';
        
        if (isOnline) statusCounts.online++;
        else if (isDead) statusCounts.error++;
        else statusCounts.offline++;

        const statusColor = isOnline ? 'var(--success)' : isDead ? 'var(--danger)' : 'var(--warning)';
        const statusIcon = isOnline ? '🟢' : isDead ? '🔴' : '🟡';
        const statusText = isOnline ? t('status_online', 'Online') : isDead ? t('status_error', 'Error') : t('status_offline', 'Offline');

        const item = document.createElement('div');
        item.style.cssText = 'display:flex;align-items:center;gap:var(--sp-3);padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);border-left:3px solid ' + statusColor + ';';
        item.innerHTML = `
          <div style="flex:1;">
            <div style="font-weight:var(--fw-semibold);font-size:var(--text-sm);">@${escapeHtml(bot.username || bot.bot_id || 'Unknown')}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">${bot.groups_count ? bot.groups_count + ' groups' : 'No groups'}</div>
          </div>
          <div style="display:flex;align-items:center;gap:var(--sp-1);">
            <span style="font-size:0.7rem;">${statusIcon}</span>
            <span style="font-size:var(--text-xs);color:${statusColor};font-weight:var(--fw-semibold);">${statusText}</span>
          </div>
        `;
        
        if (isDead && (bot.death_reason || bot.error)) {
          const errorInfo = document.createElement('div');
          errorInfo.style.cssText = 'font-size:var(--text-xs);color:var(--danger);margin-top:var(--sp-1);padding-left:var(--sp-1);';
          errorInfo.textContent = bot.death_reason || bot.error || 'Invalid token';
          item.querySelector('div').appendChild(errorInfo);
        }

        cloneList.appendChild(item);
      });

      // Status summary bar
      const summaryBar = document.createElement('div');
      summaryBar.style.cssText = 'display:flex;gap:var(--sp-3);padding:var(--sp-2) 0;margin-bottom:var(--sp-2);';
      summaryBar.innerHTML = `
        <span style="font-size:var(--text-xs);color:var(--success);font-weight:600;">🟢 ${statusCounts.online} Online</span>
        <span style="font-size:var(--text-xs);color:var(--warning);font-weight:600;">🟡 ${statusCounts.offline} Offline</span>
        <span style="font-size:var(--text-xs);color:var(--danger);font-weight:600;">🔴 ${statusCounts.error} Error</span>
      `;
      cloneCard.appendChild(summaryBar);
      cloneCard.appendChild(cloneList);
      container.appendChild(cloneCard);
    }
  } catch(e) {
    console.debug('Failed to load clone status:', e);
  }
}

async function renderGroupsSection(container) {
  try {
    const groupsRes = await apiFetch('/api/groups');
    const groups = Array.isArray(groupsRes) ? groupsRes : [];
    
    if (groups.length > 0) {
      const groupCard = Card({ title: '👥 ' + t('owner_detected_groups', 'Detected Groups'), subtitle: t('owner_detected_groups_sub', 'Groups where your bots are active') });
      const groupList = document.createElement('div');
      groupList.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);padding-top:var(--sp-2);';

      groups.slice(0, 15).forEach(group => {
        const item = document.createElement('div');
        item.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);cursor:pointer;transition:all 0.2s;';
        item.onmouseover = () => { item.style.background = 'var(--bg-elevated)'; };
        item.onmouseout = () => { item.style.background = 'var(--bg-input)'; };
        item.innerHTML = `
          <div style="flex:1;min-width:0;">
            <div style="font-weight:var(--fw-semibold);font-size:var(--text-sm);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(group.title || 'Unnamed Group')}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">${group.member_count ? group.member_count + ' members' : 'ID: ' + group.chat_id}</div>
          </div>
          <span style="font-size:var(--text-xs);color:var(--accent);">Open →</span>
        `;
        item.onclick = () => {
          getState().setActiveChatId(group.chat_id);
          window.navigateToPage('dashboard');
        };
        groupList.appendChild(item);
      });

      if (groups.length > 15) {
        const more = document.createElement('div');
        more.style.cssText = 'text-align:center;padding:var(--sp-2);color:var(--text-muted);font-size:var(--text-xs);';
        more.textContent = `+ ${groups.length - 15} more groups`;
        groupList.appendChild(more);
      }

      groupCard.appendChild(groupList);
      container.appendChild(groupCard);
    }
  } catch(e) {
    console.debug('Failed to load groups:', e);
  }
}

async function renderSystemHealthSection(container) {
  const healthCard = Card({ title: '🩺 ' + t('owner_system_health', 'System Health'), subtitle: t('owner_system_health_sub', 'Check system status') });

  const healthInfo = document.createElement('div');
  healthInfo.style.cssText = 'display:grid;grid-template-columns:repeat(2,1fr);gap:var(--sp-3);padding:var(--sp-3) 0;';

  // Check database
  const dbStatus = document.createElement('div');
  dbStatus.style.cssText = 'padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);text-align:center;cursor:help;';
  dbStatus.title = 'Database connection status';
  dbStatus.innerHTML = '<div style="font-size:1.5rem;">💾</div><div style="font-size:var(--text-sm);font-weight:var(--fw-semibold);">Database</div><div id="db-status" style="font-size:var(--text-xs);color:var(--success);">Checking...</div>';
  healthInfo.appendChild(dbStatus);

  // Check webhooks
  const webhookStatus = document.createElement('div');
  webhookStatus.style.cssText = 'padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);text-align:center;cursor:help;';
  webhookStatus.title = 'Telegram webhook health status (real-time)';
  webhookStatus.innerHTML = '<div style="font-size:1.5rem;">🌐</div><div style="font-size:var(--text-sm);font-weight:var(--fw-semibold);">Webhooks</div><div id="webhook-status" style="font-size:var(--text-xs);color:var(--success);">Checking...</div>';
  healthInfo.appendChild(webhookStatus);

  healthCard.appendChild(healthInfo);
  container.appendChild(healthCard);

  // Add webhook details container (hidden by default, shown on click)
  const webhookDetails = document.createElement('div');
  webhookDetails.id = 'webhook-details';
  webhookDetails.style.cssText = 'display:none;margin-top:var(--sp-3);padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);';
  healthCard.appendChild(webhookDetails);

  // Update status based on real-time checks
  try {
    // Check database
    try {
      await apiFetch('/api/groups');
      document.getElementById('db-status').textContent = t('connected', 'Connected');
      document.getElementById('db-status').style.color = 'var(--success)';
    } catch (e) {
      document.getElementById('db-status').textContent = t('error', 'Error');
      document.getElementById('db-status').style.color = 'var(--danger)';
    }

    // Check webhooks in real-time
    try {
      const webhookHealth = await apiFetch('/api/bots/webhook-health');
      const { healthy, total, unhealthy, bots: webhookDetailsList } = webhookHealth;

      // Update webhook status display
      document.getElementById('webhook-status').textContent = `${healthy}/${total} healthy`;
      document.getElementById('webhook-status').style.color = unhealthy > 0 ? 'var(--warning)' : 'var(--success)';

      // Click to show details
      webhookStatus.style.cursor = 'pointer';
      webhookStatus.onclick = function() {
        const details = document.getElementById('webhook-details');
        details.style.display = details.style.display === 'none' ? 'block' : 'none';

        if (details.style.display === 'block' && details.children.length === 0) {
          // Show webhook details
          details.innerHTML = webhookDetailsList.map(bot => {
            const statusColor = bot.webhook_healthy ? 'var(--success)' : 'var(--danger)';
            const statusIcon = bot.webhook_healthy ? '🟢' : '🔴';
            const statusText = bot.webhook_healthy ? 'Healthy' : 'Error';

            return `
              <div style="display:flex;align-items:center;gap:var(--sp-2);padding:var(--sp-2);border-bottom:1px solid var(--border);">
                <span style="font-size:0.7rem;">${statusIcon}</span>
                <div style="flex:1;">
                  <div style="font-size:var(--text-sm);font-weight:var(--fw-medium);">@${bot.username}</div>
                  ${bot.last_error ? `<div style="font-size:var(--text-xs);color:var(--danger);">${bot.last_error}</div>` : ''}
                  ${bot.pending_updates > 0 ? `<div style="font-size:var(--text-xs);color:var(--warning);">Pending updates: ${bot.pending_updates}</div>` : ''}
                </div>
                <span style="font-size:var(--text-xs);color:${statusColor};font-weight:var(--fw-semibold);">${statusText}</span>
              </div>
            `;
          }).join('');
        }
      };
    } catch (e) {
      console.error('[SystemHealth] Webhook check failed:', e);
      document.getElementById('webhook-status').textContent = t('error', 'Error');
      document.getElementById('webhook-status').style.color = 'var(--danger)';
    }
  } catch (e) {
    console.error('[SystemHealth] System check failed:', e);
    document.getElementById('db-status').textContent = t('error', 'Error');
    document.getElementById('db-status').style.color = 'var(--danger)';
    document.getElementById('webhook-status').textContent = t('error', 'Error');
    document.getElementById('webhook-status').style.color = 'var(--danger)';
  }
}

async function renderEconomyControls(container) {
  const econCard = Card({ title: '💰 ' + t('owner_economy', 'Economy Controls'), subtitle: t('owner_economy_sub', 'Manage Stars and promotions') });
  
  const content = document.createElement('div');
  content.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-4);padding:var(--sp-2) 0;';
  
  // Grant Stars Section
  const grantSection = document.createElement('div');
  grantSection.innerHTML = `
    <div style="font-size:var(--text-xs);font-weight:700;color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);">${t('owner_grant_stars', 'Grant Bonus Stars')}</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <input id="grant-uid" placeholder="{t('user_id', 'User ID')}" type="number" style="flex:1;min-width:100px;padding:var(--sp-2);border:1px solid var(--border);border-radius:4px;background:var(--bg-input);color:var(--text-primary);">
      <input id="grant-amt" placeholder="{t('stars', 'Stars')}" type="number" style="width:5rem;padding:var(--sp-2);border:1px solid var(--border);border-radius:4px;background:var(--bg-input);color:var(--text-primary);text-align:center;">
      <button id="grant-btn" style="padding:var(--sp-2) var(--sp-3);background:var(--accent);color:#fff;border:none;border-radius:4px;cursor:pointer;white-space:nowrap;">Grant ⭐</button>
    </div>
  `;
  content.appendChild(grantSection);
  
  // Promo Code Section
  const promoSection = document.createElement('div');
  promoSection.innerHTML = `
    <div style="font-size:var(--text-xs);font-weight:700;color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);">${t('owner_create_promo', 'Create Promo Code')}</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <input id="promo-code" placeholder="Code (e.g. WELCOME50)" style="flex:1;min-width:8rem;padding:var(--sp-2);border:1px solid var(--border);border-radius:4px;background:var(--bg-input);color:var(--text-primary);">
      <input id="promo-amt" placeholder="{t('stars', 'Stars')}" type="number" style="width:5rem;padding:var(--sp-2);border:1px solid var(--border);border-radius:4px;background:var(--bg-input);color:var(--text-primary);text-align:center;">
      <input id="promo-uses" placeholder="Max uses" type="number" value="10" style="width:5rem;padding:var(--sp-2);border:1px solid var(--border);border-radius:4px;background:var(--bg-input);color:var(--text-primary);text-align:center;">
      <button id="promo-btn" style="padding:var(--sp-2) var(--sp-3);background:#27ae60;color:#fff;border:none;border-radius:4px;cursor:pointer;white-space:nowrap;">Create</button>
    </div>
  `;
  content.appendChild(promoSection);
  
  econCard.appendChild(content);
  container.appendChild(econCard);

  // Event handlers
  grantSection.querySelector('#grant-btn').addEventListener('click', async () => {
    const uid = parseInt(grantSection.querySelector('#grant-uid').value);
    const amt = parseInt(grantSection.querySelector('#grant-amt').value);
    if (!uid || !amt) { showToast(t('owner_enter_uid_amt', 'Enter user ID and amount'), 'error'); return; }
    try {
      await apiFetch('/api/billing/grant-bonus', { method: 'POST', body: JSON.stringify({ user_id: uid, amount: amt, reason: 'Owner grant via miniapp' }) });
      showToast('Granted ' + amt + ' Stars to ' + uid, 'success');
      grantSection.querySelector('#grant-uid').value = '';
      grantSection.querySelector('#grant-amt').value = '';
    } catch(e) { showToast('Failed: ' + e.message, 'error'); }
  });

  promoSection.querySelector('#promo-btn').addEventListener('click', async () => {
    const code = promoSection.querySelector('#promo-code').value.trim().toUpperCase();
    const amt = parseInt(promoSection.querySelector('#promo-amt').value);
    const uses = parseInt(promoSection.querySelector('#promo-uses').value) || 10;
    if (!code || !amt) { showToast(t('owner_enter_code_amt', 'Enter code and amount'), 'error'); return; }
    try {
      await apiFetch('/api/billing/create-promo', { method: 'POST', body: JSON.stringify({ code, amount: amt, max_uses: uses }) });
      showToast('Promo ' + code + ' created (' + amt + ' Stars, ' + uses + ' uses)', 'success');
      promoSection.querySelector('#promo-code').value = '';
      promoSection.querySelector('#promo-amt').value = '';
    } catch(e) { showToast('Failed: ' + e.message, 'error'); }
  });
}

async function renderNotificationSettings(container) {
  const notifCard = Card({ title: '🔔 ' + t('owner_notifications', 'Notification Settings'), subtitle: t('owner_notifications_sub', 'Configure error notifications') });
  
  const content = document.createElement('div');
  content.style.cssText = 'padding:var(--sp-2) 0;';
  content.innerHTML = '<div style="text-align:center;color:var(--text-muted);">Loading...</div>';
  
  notifCard.appendChild(content);
  container.appendChild(notifCard);
  
  try {
    const prefs = await apiFetch('/api/owner/notifications');
    content.innerHTML = '';
    
    // Group by category
    const categories = {};
    (prefs.preferences || []).forEach(p => {
      const cat = p.category || 'other';
      if (!categories[cat]) categories[cat] = [];
      categories[cat].push(p);
    });
    
    const categoryLabels = {
      clone: '🤖 Clone Errors',
      system: '⚙️ System Errors',
      ml: '🤖 ML Errors',
      other: '❓ Other'
    };
    
    Object.entries(categories).forEach(([cat, items]) => {
      const catSection = document.createElement('div');
      catSection.style.cssText = 'margin-bottom:var(--sp-4);';
      catSection.innerHTML = `<div style="font-size:var(--text-xs);font-weight:700;color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);">${categoryLabels[cat] || cat}</div>`;
      
      const itemGrid = document.createElement('div');
      itemGrid.style.cssText = 'display:grid;grid-template-columns:repeat(2,1fr);gap:var(--sp-2);';
      
      items.forEach(item => {
        const toggle = document.createElement('label');
        toggle.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2);background:var(--bg-input);border-radius:var(--r-lg);cursor:pointer;font-size:var(--text-xs);';
        toggle.innerHTML = `
          <span style="flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${item.error_type.replace(/_/g, ' ')}</span>
          <input type="checkbox" data-error="${item.error_type}" ${!item.muted ? 'checked' : ''} style="margin-left:var(--sp-2);">
        `;
        toggle.querySelector('input').addEventListener('change', async (e) => {
          try {
            await apiFetch(`/api/owner/notifications/${item.error_type}`, {
              method: 'PUT',
              body: JSON.stringify({ muted: !e.target.checked })
            });
            showToast('Setting updated', 'success');
          } catch (err) {
            showToast('Failed to update', 'error');
            e.target.checked = !e.target.checked;
          }
        });
        itemGrid.appendChild(toggle);
      });
      
      catSection.appendChild(itemGrid);
      content.appendChild(catSection);
    });
  } catch (e) {
    content.innerHTML = '<div style="text-align:center;color:var(--text-muted);">Could not load notification settings</div>';
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}