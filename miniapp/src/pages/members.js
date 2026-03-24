/**
 * miniapp/src/pages/members.js
 * Task 7 of 12 — Members page
 * Extracted from index.html renderMembers() and filterMembers()
 */

import { EmptyState, SearchInput, MemberRow, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

const store = useStore;
const getState = store.getState;

let _searchTimer = null;
let _membersPage = 0;
const PAGE_SIZE = 50;

const ACTION_LABELS = {
  warn: 'warn',
  mute: 'mute for 1 hour',
  kick: 'kick from group',
  ban: 'permanently ban',
};

function filterMembers(query, all, container) {
  const q = query.toLowerCase().trim();
  if (!q) {
    const list = container.querySelector('.member-list');
    if (!list) return;
    list.innerHTML = '';
    all.forEach(m => list.appendChild(MemberRow({
      member: { id: m.user_id || m.id, name: m.first_name || 'User', username: m.username, avatar: (m.first_name?.[0] || '?').toUpperCase(), trust_score: m.trust_score || 50, message_count: m.message_count || 0, warns: Array.isArray(m.warns) ? m.warns.length : (m.warns || 0) },
      selectable: true,
      onSelect: (m) => getState().toggleMemberSelection(m.id)
    })));
    return;
  }

  const filtered = all.filter(m =>
    (m.first_name || '').toLowerCase().includes(q) ||
    (m.username || '').toLowerCase().includes(q) ||
    (m.user_id?.toString() || m.id?.toString() || '').includes(q)
  );

  const list = container.querySelector('.member-list');
  if (!list) return;

  list.innerHTML = '';
  if (filtered.length === 0) {
    const emptyMsg = document.createElement('div');
    emptyMsg.style.cssText = 'text-align: center; padding: var(--sp-8); color: var(--text-muted);';
    emptyMsg.textContent = 'No members found matching "' + query + '"';
    list.appendChild(emptyMsg);
    return;
  }

  filtered.forEach(m => list.appendChild(MemberRow({
    member: { id: m.user_id || m.id, name: m.first_name || 'User', username: m.username, avatar: (m.first_name?.[0] || '?').toUpperCase(), trust_score: m.trust_score || 50, message_count: m.message_count || 0, warns: Array.isArray(m.warns) ? m.warns.length : (m.warns || 0) },
    selectable: true,
    onSelect: (m) => getState().toggleMemberSelection(m.id)
  })));
}

export async function renderMembers(container) {
  const state = getState();
  const chatId = state.activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({ icon: '👆', title: 'Select a group', description: 'Choose a group to view members' }));
    return;
  }

  container.innerHTML = `
    <div style="text-align: center; padding: var(--sp-8);">
      <div style="font-size: 48px; margin-bottom: var(--sp-4);">⏳</div>
      <div style="color: var(--text-muted);">Loading members...</div>
    </div>
  `;

  try {
    _membersPage = 0;
    const members = await apiFetch(`/api/groups/${chatId}/members?limit=${PAGE_SIZE}&offset=0`);
    state.setMembers(members);

    container.innerHTML = '';
    container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

    const header = document.createElement('div');
    header.style.cssText = 'display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--sp-4);';
    header.innerHTML = `
      <div>
        <h2 style="font-size: 20px; font-weight: 700; margin: 0;">👥 Members</h2>
        <p style="color: var(--text-muted); font-size: 13px; margin: 4px 0 0;">${members.length} total members</p>
      </div>
    `;
    container.appendChild(header);

    container.appendChild(SearchInput({ placeholder: 'Search members...', onChange: (val) => {
      clearTimeout(_searchTimer);
      _searchTimer = setTimeout(() => filterMembers(val, members, container), 300);
    }}));

    const list = document.createElement('div');
    list.className = 'member-list';
    list.style.cssText = 'display: flex; flex-direction: column; gap: var(--sp-2);';

    const _hMAction = async (mid, action, cid, member) => {
      if (!mid) {
        showToast('Cannot perform action: member ID missing', 'error');
        return;
      }
      // Confirmation for destructive actions
      if (['kick', 'ban', 'mute'].includes(action)) {
        const label = ACTION_LABELS[action] || action;
        const name = member.first_name || member.username || 'this member';
        const confirmed = confirm(`Are you sure you want to ${label} ${name}?`);
        if (!confirmed) return;
      }
      try {
        if (action === 'warn') await apiFetch(`/api/groups/${cid}/warnings`, { method: 'POST', body: { user_id: mid, reason: 'Manual warning' } });
        else if (action === 'mute') await apiFetch(`/api/groups/${cid}/mutes`, { method: 'POST', body: { user_id: mid, duration: '1h' } });
        else if (action === 'kick') await apiFetch(`/api/groups/${cid}/actions/kick`, { method: 'POST', body: { user_id: mid } });
        else if (action === 'ban') await apiFetch(`/api/groups/${cid}/bans`, { method: 'POST', body: { user_id: mid, reason: 'Manual ban' } });
        showToast('Action success', 'success');
      } catch (e) { showToast(e.message, 'error'); }
    };

    const renderMemberRows = (memberList, targetList, append = false) => {
      if (!append) targetList.innerHTML = '';
      memberList.forEach(m => {
        const mID = m.user_id ?? m.id ?? null;
        targetList.appendChild(MemberRow({
          member: { id: mID, name: m.first_name || 'User', avatar: (m.first_name?.[0] || '?').toUpperCase(), warns: Array.isArray(m.warns) ? m.warns.length : (m.warns || 0) },
          selectable: true,
          onSelect: (m) => state.toggleMemberSelection(m.id),
          actions: [
            { icon: '\u26A0\uFE0F', label: 'Warn', onClick: () => _hMAction(mID, 'warn', chatId, m), variant: 'warning' },
            { icon: '\uD83D\uDD07', label: 'Mute', onClick: () => _hMAction(mID, 'mute', chatId, m), variant: 'warning' },
            { icon: '\uD83D\uDC62', label: 'Kick', onClick: () => _hMAction(mID, 'kick', chatId, m), variant: 'danger' },
            { icon: '\uD83D\uDEAB', label: 'Ban',  onClick: () => _hMAction(mID, 'ban',  chatId, m), variant: 'danger' }
          ]
        }));
      });
    };

    renderMemberRows(members, list);
    container.appendChild(list);

    // Pagination: Load More button
    if (members.length === PAGE_SIZE) {
      const loadMoreWrap = document.createElement('div');
      loadMoreWrap.style.cssText = 'text-align: center; padding: var(--sp-4);';
      const loadMore = document.createElement('button');
      loadMore.textContent = 'Load More Members';
      loadMore.className = 'btn btn-secondary';
      loadMore.style.cssText = 'padding: var(--sp-2) var(--sp-6); border-radius: var(--r-lg); cursor: pointer;';
      loadMore.onclick = async () => {
        _membersPage++;
        try {
          const more = await apiFetch(`/api/groups/${chatId}/members?limit=${PAGE_SIZE}&offset=${_membersPage * PAGE_SIZE}`);
          renderMemberRows(more, list, true);
          if (more.length < PAGE_SIZE) loadMoreWrap.remove();
        } catch (e) { showToast(e.message, 'error'); }
      };
      loadMoreWrap.appendChild(loadMore);
      container.appendChild(loadMoreWrap);
    }
  } catch (e) {
    container.innerHTML = '';
    container.appendChild(EmptyState({ icon: '⚠️', title: 'Failed to load members', description: e.message || 'Please try again' }));
  }
}
