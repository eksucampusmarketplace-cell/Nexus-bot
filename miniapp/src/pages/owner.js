/**
 * miniapp/src/pages/owner.js
 * Task 1 of 12 — Owner Panel page
 * Extracted from index.html renderOwnerPage()
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
      btn.style.cssText = 'padding:var(--sp-3);background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);cursor:pointer;text-align:left;font-size:0.9rem;';
      btn.onclick = () => navigateToPage(a.page);
      actRow.appendChild(btn);
    });
  container.appendChild(actRow);

  // Dead Clones Warning
  try {
    const deadRes = await apiFetch('/api/bots').catch(() => null);
    const botsArray = Array.isArray(deadRes) ? deadRes : (deadRes?.bots || []);
    const deadBots = botsArray.filter(b => b.status === 'dead' || b.status === 'error');
    if (deadBots.length > 0) {
      const warn = document.createElement('div');
      warn.style.cssText = 'background:#FEF9E7;border:1px solid #F39C12;border-radius:var(--r-xl);padding:var(--sp-3);margin-bottom:var(--sp-4);';
      warn.innerHTML = '<div style="font-weight:700;color:#E67E22;">⚠️ ' + deadBots.length + ' Dead Clone(s)</div>' +
        deadBots.map(b => '<div style="font-size:0.82rem;color:var(--text-muted);">@' + (b.username || b.bot_id) + ' — ' + (b.death_reason || b.error || 'invalid token') + '</div>').join('');
      container.appendChild(warn);
    }
  } catch(e) {}

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
