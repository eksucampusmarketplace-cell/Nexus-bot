/**
 * miniapp/src/pages/trustnet.js
 * 
 * TrustNet / Federation management page.
 */

import { t, showToast } from '../../lib/i18n.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

export async function renderTrustnetPage(container) {
  const chatId = useStore.getState().activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.innerHTML = `
      <div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">
        <div style="font-size:3rem;margin-bottom:var(--sp-3)">🌐</div>
        <div>Select a group first</div>
      </div>
    `;
    return;
  }

  const header = document.createElement('div');
  header.innerHTML = `
    <div style="display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);">
      <div style="font-size:2rem">🌐</div>
      <div>
        <div style="font-size:1.2rem;font-weight:700">${t('nav_trustnet', 'TrustNet')}</div>
        <div style="font-size:0.85rem;color:var(--text-muted)">Cross-group ban sharing network</div>
      </div>
    </div>
  `;
  container.appendChild(header);

  // Loading
  const loading = document.createElement('div');
  loading.style.cssText = 'text-align:center;padding:var(--sp-8);color:var(--text-muted);';
  loading.textContent = t('loading', 'Loading...');
  container.appendChild(loading);

  try {
    const feds = await apiFetch('/api/federation/my').catch(() => []);
    loading.replaceWith(createFederationList(feds, container));
  } catch (err) {
    loading.textContent = t('error', 'Failed to load federations');
  }

  // Create new federation button (FAB)
  const createBtn = document.createElement('button');
  createBtn.textContent = '+';
  createBtn.title = 'Create Federation';
  createBtn.style.cssText = `
    position:fixed;bottom:20px;right:20px;
    width:56px;height:56px;border-radius:50%;
    background:var(--accent);color:#000;
    font-weight:700;font-size:24px;border:none;
    cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,0.3);
    display:flex;align-items:center;justify-content:center;
  `;
  createBtn.onclick = () => showCreateFederationDialog(chatId, container);
  container.appendChild(createBtn);
}

function showCreateFederationDialog(chatId, container) {
  // Remove existing dialog if any
  const existing = document.getElementById('create-fed-dialog');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.id = 'create-fed-dialog';
  overlay.style.cssText = `
    position:fixed;top:0;left:0;right:0;bottom:0;
    background:rgba(0,0,0,0.5);z-index:1000;
    display:flex;align-items:center;justify-content:center;
    padding:var(--sp-4);
  `;
  overlay.innerHTML = `
    <div style="background:var(--bg-card);border-radius:var(--r-xl);padding:var(--sp-5);width:100%;max-width:400px;">
      <div style="font-weight:700;font-size:1.1rem;margin-bottom:var(--sp-4)">Create Federation</div>
      <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">Federation Name</label>
      <input type="text" class="input" id="fed-name-input" placeholder="My Federation" style="margin-bottom:var(--sp-4)">
      <div style="display:flex;gap:var(--sp-3);justify-content:flex-end">
        <button class="btn btn-secondary" id="fed-cancel">Cancel</button>
        <button class="btn btn-primary" id="fed-create">Create</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  overlay.querySelector('#fed-cancel').onclick = () => overlay.remove();
  overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });

  overlay.querySelector('#fed-create').onclick = async () => {
    const name = overlay.querySelector('#fed-name-input').value.trim();
    if (!name) {
      showToast('Please enter a federation name');
      return;
    }
    try {
      showToast('Creating federation...');
      await apiFetch('/api/federation/create', {
        method: 'POST',
        body: JSON.stringify({ name, chat_id: chatId })
      });
      showToast('Federation created!');
      overlay.remove();
      // Re-render the page to show the new federation
      const pageContainer = container;
      const { renderTrustnetPage } = await import('./trustnet.js');
      await renderTrustnetPage(pageContainer);
    } catch (err) {
      console.error('Failed to create federation:', err);
      showToast('Failed to create federation');
    }
  };
}

function createFederationList(feds, container) {
  if (!feds || feds.length === 0) {
    const empty = document.createElement('div');
    empty.style.cssText = 'text-align:center;padding:var(--sp-8);color:var(--text-muted);';
    empty.innerHTML = `
      <div style="font-size:3rem;margin-bottom:var(--sp-3)">🌐</div>
      <div>No federations yet</div>
      <div style="font-size:0.85rem;margin-top:var(--sp-2)">Create a federation to share bans across groups</div>
    `;
    return empty;
  }

  const list = document.createElement('div');
  list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-3);';

  feds.forEach(fed => {
    const card = document.createElement('div');
    card.style.cssText = `
      background:var(--bg-card);border:1px solid var(--border);
      border-radius:var(--r-xl);padding:var(--sp-4);
    `;
    card.innerHTML = `
      <div style="font-weight:600;font-size:1rem;margin-bottom:var(--sp-2)">${fed.name || 'Unnamed Federation'}</div>
      <div style="font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-1)">
        📊 ${fed.member_count || 0} groups
      </div>
      ${fed.invite_code ? `
        <div style="font-size:0.85rem;color:var(--text-muted);display:flex;align-items:center;gap:var(--sp-2)">
          🔑 ${fed.invite_code}
          <button class="copy-btn" data-code="${fed.invite_code}" style="background:none;border:none;color:var(--accent);cursor:pointer;">
            📋
          </button>
        </div>
      ` : ''}
    `;
    
    card.querySelector('.copy-btn')?.addEventListener('click', async (e) => {
      const code = e.target.dataset.code;
      try {
        await navigator.clipboard.writeText(`/jointrust ${code}`);
        showToast('Copied invite command!');
      } catch (err) {
        showToast('Failed to copy');
      }
    });

    list.appendChild(card);
  });

  return list;
}
