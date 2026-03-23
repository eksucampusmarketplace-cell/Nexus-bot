/**
 * miniapp/src/pages/notes.js
 * 
 * Notes management page with create/delete functionality.
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
  header.innerHTML = '<h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">📝 Notes</h2><p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">Save and retrieve custom notes/triggers</p>';
  container.appendChild(header);

  // Create note form
  const createCard = Card({ title: 'Create Note', subtitle: 'Add a new note to this group' });
  createCard.innerHTML += `
    <div style="display:flex;flex-direction:column;gap:var(--sp-3);padding-top:var(--sp-2);">
      <div>
        <label style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:var(--sp-1);">Note Name</label>
        <input type="text" id="note-name-input" class="input" placeholder="Note name (e.g. rules, faq)" style="width:100%;box-sizing:border-box;">
      </div>
      <div>
        <label style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:var(--sp-1);">Note Content</label>
        <textarea id="note-content-input" class="input" placeholder="Note content..." rows="4" style="width:100%;box-sizing:border-box;resize:vertical;"></textarea>
      </div>
      <button id="save-note-btn" class="btn btn-primary" style="align-self:flex-start;">
        💾 Save Note
      </button>
    </div>
  `;
  container.appendChild(createCard);

  createCard.querySelector('#save-note-btn').onclick = async () => {
    const name = createCard.querySelector('#note-name-input').value.trim();
    const content = createCard.querySelector('#note-content-input').value.trim();
    if (!name) { showToast('Enter a note name', 'error'); return; }
    if (!content) { showToast('Enter note content', 'error'); return; }
    try {
      await apiFetch(`/api/groups/${chatId}/notes`, {
        method: 'POST',
        body: JSON.stringify({ name, content })
      });
      showToast('Note saved!', 'success');
      createCard.querySelector('#note-name-input').value = '';
      createCard.querySelector('#note-content-input').value = '';
      // Re-render notes list
      await loadNotesList(chatId, listContainer);
    } catch (e) {
      showToast('Failed to save note: ' + (e.message || 'Error'), 'error');
    }
  };

  // Notes list
  const listCard = Card({ title: 'Saved Notes', subtitle: 'Notes are retrieved with /note or via inline mode' });
  const listContainer = document.createElement('div');
  listContainer.id = 'notes-list-container';
  listCard.appendChild(listContainer);
  container.appendChild(listCard);

  await loadNotesList(chatId, listContainer);
}

async function loadNotesList(chatId, listContainer) {
  listContainer.innerHTML = '<div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);">Loading notes...</div>';
  try {
    const notes = await apiFetch(`/api/groups/${chatId}/notes`);
    listContainer.innerHTML = '';
    if (!notes || notes.length === 0) {
      listContainer.innerHTML = '<div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);">No notes yet</div>';
      return;
    }
    const list = document.createElement('div');
    list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);padding-top:var(--sp-2);';
    notes.forEach(n => {
      const item = document.createElement('div');
      item.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:var(--sp-2) var(--sp-3);background:var(--bg-input);border-radius:var(--r-md);';
      const nameSpan = document.createElement('span');
      nameSpan.style.cssText = 'font-weight:var(--fw-semibold);font-size:var(--text-sm);';
      nameSpan.textContent = '#' + n.name;
      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-danger';
      delBtn.style.cssText = 'padding:2px 8px;font-size:10px;';
      delBtn.textContent = 'Delete';
      delBtn.onclick = async () => {
        if (!confirm('Delete note "' + n.name + '"?')) return;
        try {
          await apiFetch(`/api/groups/${chatId}/notes/${encodeURIComponent(n.name)}`, { method: 'DELETE' });
          showToast('Note deleted', 'success');
          await loadNotesList(chatId, listContainer);
        } catch (e) {
          showToast('Failed to delete: ' + (e.message || 'Error'), 'error');
        }
      };
      item.appendChild(nameSpan);
      item.appendChild(delBtn);
      list.appendChild(item);
    });
    listContainer.appendChild(list);
  } catch (e) {
    listContainer.innerHTML = '';
    listContainer.innerHTML = '<div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);">⚠️ Failed to load notes</div>';
  }
}
