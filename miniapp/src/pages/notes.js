/**
 * miniapp/src/pages/notes.js
 */
import { Card, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

export async function renderNotesPage(container) {
  const chatId = useStore.getState().activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({ icon: '📝', title: 'Select a group', description: 'Choose a group to manage notes.' }));
    return;
  }

  const header = document.createElement('div');
  header.style.cssText = 'margin-bottom: var(--sp-6);';
  header.innerHTML = `<h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">📝 Notes</h2><p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">Save and retrieve custom notes/triggers</p>`;
  container.appendChild(header);

  try {
    const notes = await apiFetch(`/api/groups/${chatId}/notes`);
    const listCard = Card({ title: 'Active Notes', subtitle: 'List of saved notes for this group' });
    if (!notes || notes.length === 0) {
      listCard.innerHTML += '<div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);">No notes saved yet. Use /save in the group.</div>';
    } else {
      const list = document.createElement('div');
      list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);padding-top:var(--sp-2);';
      notes.forEach(n => {
        const item = document.createElement('div');
        item.style.cssText = 'display:flex;justify-content:space-between;padding:var(--sp-2);background:var(--bg-input);border-radius:var(--r-md);';
        item.innerHTML = `<span>#${n.name}</span><button class="btn btn-danger" style="padding:2px 8px;font-size:10px;">Delete</button>`;
        list.appendChild(item);
      });
      listCard.appendChild(list);
    }
    container.appendChild(listCard);
  } catch (e) {
    container.appendChild(EmptyState({ icon: '⚠️', title: 'Note System', description: 'Accessing notes via API failed.' }));
  }
}
