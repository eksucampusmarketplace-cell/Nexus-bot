/**
 * miniapp/src/pages/moderation.js
 *
 * Moderation management page.
 */

import { Card, Toggle, showToast } from '../../lib/components.js?v=1.4.0';
import { useStore } from '../../store/index.js?v=1.4.0';
import { apiFetch } from '../../lib/api.js?v=1.4.0';

const store = useStore;

export async function renderModerationPage(container) {
  const chatId = store.get('currentChatId');
  if (!chatId) {
    container.innerHTML = '<div class="p-4 text-center">Please select a group first.</div>';
    return;
  }

  container.innerHTML = `
    <div class="p-4 space-y-6">
      <header class="flex justify-between items-center">
        <h2 class="text-xl font-bold">🛡️ Moderation</h2>
        <div id="sse-status" class="text-xs flex items-center gap-1">
          <span class="w-2 h-2 rounded-full bg-gray-400"></span> Offline
        </div>
      </header>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div id="locks-card"></div>
        <div id="warn-settings-card"></div>
      </div>
      
      <div id="recent-actions-card"></div>
    </div>
  `;

  renderLocks(container.querySelector('#locks-card'), chatId);
  renderWarnSettings(container.querySelector('#warn-settings-card'), chatId);
  renderRecentActions(container.querySelector('#recent-actions-card'), chatId);
  
  setupSSE(chatId);
}

async function renderLocks(container, chatId) {
  const card = Card({
    title: '🔒 Content Locks',
    description: 'Toggle what members can send'
  });
  container.appendChild(card);
  
  const content = card.querySelector('.card-content');
  content.innerHTML = '<div class="space-y-4 py-2" id="locks-list">Loading...</div>';

  try {
    const res = await apiFetch(`/api/groups/${chatId}/locks`);
    const locks = res.data || {};
    
    const lockTypes = [
      { id: 'media', label: '📸 Media' },
      { id: 'stickers', label: '🎭 Stickers' },
      { id: 'gifs', label: '🎬 GIFs' },
      { id: 'links', label: '🔗 Links' },
      { id: 'forwards', label: '↩️ Forwards' }
    ];

    const list = content.querySelector('#locks-list');
    list.innerHTML = '';
    
    lockTypes.forEach(lock => {
      const row = document.createElement('div');
      row.className = 'flex justify-between items-center';
      row.innerHTML = `<span>${lock.label}</span>`;
      
      const toggle = Toggle({
        checked: locks[lock.id] || false,
        onChange: async (checked) => {
          try {
            await apiFetch(`/api/groups/${chatId}/locks`, {
              method: 'PUT',
              body: JSON.stringify({ [lock.id]: checked })
            });
            showToast(`${lock.label} ${checked ? 'locked' : 'unlocked'}`, 'success');
          } catch (e) {
            showToast('Failed to update lock', 'error');
          }
        }
      });
      row.appendChild(toggle);
      list.appendChild(row);
    });
  } catch (e) {
    content.innerHTML = '<div class="text-red-500">Failed to load locks.</div>';
  }
}

async function renderWarnSettings(container, chatId) {
  const card = Card({
    title: '⚠️ Warning Settings',
    description: 'Configure automated actions'
  });
  container.appendChild(card);
  
  const content = card.querySelector('.card-content');
  content.innerHTML = `
    <div class="space-y-4 py-2">
      <div class="flex justify-between items-center">
        <span>Max Warnings</span>
        <input type="number" class="input w-20" value="3" min="1" max="10">
      </div>
      <div class="flex justify-between items-center">
        <span>Action</span>
        <select class="input w-32">
          <option value="mute">Mute</option>
          <option value="kick">Kick</option>
          <option value="ban">Ban</option>
        </select>
      </div>
      <button class="btn btn-primary w-full mt-4">Save Settings</button>
    </div>
  `;
}

async function renderRecentActions(container, chatId) {
  const card = Card({
    title: '📜 Recent Actions',
    description: 'Latest moderation activities'
  });
  container.appendChild(card);
  
  const content = card.querySelector('.card-content');
  content.innerHTML = '<div class="divide-y divide-gray-700" id="actions-feed"><div class="p-4 text-center text-gray-500">No recent actions</div></div>';
}

function setupSSE(chatId) {
  const statusEl = document.getElementById('sse-status');
  const dot = statusEl.querySelector('span');
  
  const source = new EventSource(`/api/events/moderation/${chatId}`);
  
  source.onopen = () => {
    dot.className = 'w-2 h-2 rounded-full bg-green-500 animate-pulse';
    statusEl.lastChild.textContent = ' Live';
  };
  
  source.onerror = () => {
    dot.className = 'w-2 h-2 rounded-full bg-red-500';
    statusEl.lastChild.textContent = ' Offline';
  };
  
  source.addEventListener('mod_action', (e) => {
    const data = JSON.parse(e.data);
    prependAction(data);
  });
}

function prependAction(data) {
  const feed = document.getElementById('actions-feed');
  if (feed.querySelector('.text-gray-500')) feed.innerHTML = '';
  
  const item = document.createElement('div');
  item.className = 'py-3 flex flex-col gap-1';
  item.innerHTML = `
    <div class="flex justify-between">
      <span class="font-bold">${data.action.toUpperCase()}</span>
      <span class="text-xs text-gray-400">Just now</span>
    </div>
    <div class="text-sm">
      <span class="text-blue-400">@${data.admin_name}</span> affected <span class="text-yellow-400">${data.target_name}</span>
    </div>
    ${data.reason ? `<div class="text-xs text-gray-500 italic">"${data.reason}"</div>` : ''}
  `;
  feed.prepend(item);
}
