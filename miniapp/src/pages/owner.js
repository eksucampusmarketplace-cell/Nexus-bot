/**
 * miniapp/src/pages/owner.js
 * 
 * Owner Panel page with clone status indicators and group detection.
 */

import { Card, StatCard, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

const store = useStore;
const getState = store.getState;

export async function renderOwnerPage(container) {
  container.innerHTML = '';
  container.style.cssText = 'padding:var(--sp-4);max-width:var(--content-max);margin:0 auto;';

  const header = document.createElement('div');
  header.style.cssText = 'display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);';
  header.innerHTML = '<div style="font-size:2rem">&#x1F451;</div><div style="font-size:1.2rem;font-weight:700">Owner Panel</div>';
  container.appendChild(header);

  let statsRes = null;
  try {
    statsRes = await apiFetch('/api/admin/stats');
  } catch (e) {
    const msg = document.createElement('div');
    msg.style.cssText = 'text-align:center;padding:var(--sp-8);color:var(--text-muted);';
    msg.textContent = 'Owner access only.';
    container.appendChild(msg);
    return;
  }

  if (statsRes) {
    const row = document.createElement('div');
    row.style.cssText = 'display:grid;grid-template-columns:repeat(3,1fr);gap:var(--sp-3);margin-bottom:var(--sp-5);';
    [{label:'Clones',val:statsRes.bots,icon:'🤖'},{label:'Groups',val:statsRes.groups,icon:'👥'},{label:'Users',val:statsRes.users,icon:'👤'}]
      .forEach(s => {
        const c = document.createElement('div');
        c.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-3);text-align:center;';
        c.innerHTML = '<div style="font-size:1.5rem">'+s.icon+'</div><div style="font-size:1.5rem;font-weight:700">'+(s.val||0)+'</div><div style="font-size:0.75rem;color:var(--text-muted)">'+s.label+'</div>';
        row.appendChild(c);
      });
    container.appendChild(row);
  }

  const actRow = document.createElement('div');
  actRow.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);margin-bottom:var(--sp-4);';
  [{label:'📋 View All Clones', page:'bots'},{label:'📢 Broadcast to All', page:'broadcast'}]
    .forEach(a => {
      const btn = document.createElement('button');
      btn.textContent = a.label;
      btn.style.cssText = 'padding:var(--sp-3);background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);cursor:pointer;text-align:left;font-size:0.9rem;color:var(--text-primary);';
      btn.onclick = () => window.navigateToPage(a.page);
      actRow.appendChild(btn);
    });
  container.appendChild(actRow);

  // Clone Status Section
  try {
    const botsRes = await apiFetch('/api/bots').catch(() => null);
    const botsArray = Array.isArray(botsRes) ? botsRes : (botsRes?.bots || []);
    
    if (botsArray.length > 0) {
      const cloneCard = Card({ title: '🤖 Clone Status', subtitle: 'Real-time status of all bot clones' });
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
        const statusText = isOnline ? 'Online' : isDead ? 'Error' : 'Offline';

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

  // Group Detection Section
  try {
    const groups = getState().groups || [];
    if (groups.length > 0) {
      const groupCard = Card({ title: '👥 Detected Groups', subtitle: 'Groups where your bots are active' });
      const groupList = document.createElement('div');
      groupList.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);padding-top:var(--sp-2);';

      groups.forEach(group => {
        const item = document.createElement('div');
        item.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);cursor:pointer;';
        item.innerHTML = `
          <div>
            <div style="font-weight:var(--fw-semibold);font-size:var(--text-sm);">${escapeHtml(group.title || 'Unnamed Group')}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);">${group.member_count ? group.member_count + ' members' : 'ID: ' + group.chat_id}</div>
          </div>
          <span style="font-size:var(--text-xs);color:var(--accent);cursor:pointer;">Open →</span>
        `;
        item.onclick = () => {
          getState().setActiveChatId(group.chat_id);
          window.navigateToPage('dashboard');
        };
        groupList.appendChild(item);
      });

      groupCard.appendChild(groupList);
      container.appendChild(groupCard);
    }
  } catch(e) {
    console.debug('Failed to load groups:', e);
  }

  // Economy Controls
  const econCard = document.createElement('div');
  econCard.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);margin-bottom:var(--sp-4);';
  econCard.innerHTML = `
    <div style="font-weight:700;margin-bottom:var(--sp-3);">💰 Economy Controls</div>
    <div style="display:flex;flex-direction:column;gap:var(--sp-3);">
      <div>
        <div style="font-size:var(--text-xs);font-weight:700;color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);">Grant Bonus Stars</div>
        <div style="display:flex;gap:8px;">
          <input id="grant-uid" placeholder="User ID" type="number" style="flex:1;padding:var(--sp-2);border:1px solid var(--border);border-radius:4px;background:var(--bg-input);color:var(--text-primary);">
          <input id="grant-amt" placeholder="Stars" type="number" style="width:5rem;padding:var(--sp-2);border:1px solid var(--border);border-radius:4px;background:var(--bg-input);color:var(--text-primary);text-align:center;">
          <button id="grant-btn" style="padding:var(--sp-2) var(--sp-3);background:var(--accent);color:#fff;border:none;border-radius:4px;cursor:pointer;">Grant ⭐</button>
        </div>
      </div>
      <div>
        <div style="font-size:var(--text-xs);font-weight:700;color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);">Create Promo Code</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <input id="promo-code" placeholder="Code (e.g. WELCOME50)" style="flex:1;min-width:8rem;padding:var(--sp-2);border:1px solid var(--border);border-radius:4px;background:var(--bg-input);color:var(--text-primary);">
          <input id="promo-amt" placeholder="Stars" type="number" style="width:5rem;padding:var(--sp-2);border:1px solid var(--border);border-radius:4px;background:var(--bg-input);color:var(--text-primary);text-align:center;">
          <input id="promo-uses" placeholder="Max uses" type="number" value="10" style="width:5rem;padding:var(--sp-2);border:1px solid var(--border);border-radius:4px;background:var(--bg-input);color:var(--text-primary);text-align:center;">
          <button id="promo-btn" style="padding:var(--sp-2) var(--sp-3);background:#27ae60;color:#fff;border:none;border-radius:4px;cursor:pointer;">Create Promo</button>
        </div>
      </div>
    </div>
  `;
  container.appendChild(econCard);

  econCard.querySelector('#grant-btn').addEventListener('click', async () => {
    const uid = parseInt(econCard.querySelector('#grant-uid').value);
    const amt = parseInt(econCard.querySelector('#grant-amt').value);
    if (!uid || !amt) { showToast('Enter user ID and amount', 'error'); return; }
    try {
      await apiFetch('/api/billing/grant-bonus', { method: 'POST', body: JSON.stringify({ user_id: uid, amount: amt, reason: 'Owner grant via miniapp' }) });
      showToast('Granted ' + amt + ' Stars to ' + uid, 'success');
      econCard.querySelector('#grant-uid').value = '';
      econCard.querySelector('#grant-amt').value = '';
    } catch(e) { showToast('Failed: ' + e.message, 'error'); }
  });

  econCard.querySelector('#promo-btn').addEventListener('click', async () => {
    const code = econCard.querySelector('#promo-code').value.trim().toUpperCase();
    const amt = parseInt(econCard.querySelector('#promo-amt').value);
    const uses = parseInt(econCard.querySelector('#promo-uses').value) || 10;
    if (!code || !amt) { showToast('Enter code and amount', 'error'); return; }
    try {
      await apiFetch('/api/billing/create-promo', { method: 'POST', body: JSON.stringify({ code, amount: amt, max_uses: uses }) });
      showToast('Promo ' + code + ' created (' + amt + ' Stars, ' + uses + ' uses)', 'success');
      econCard.querySelector('#promo-code').value = '';
      econCard.querySelector('#promo-amt').value = '';
    } catch(e) { showToast('Failed: ' + e.message, 'error'); }
  });
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}
