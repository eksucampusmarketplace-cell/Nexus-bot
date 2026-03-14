/**
 * miniapp/src/pages/music.js
 *
 * Music player control page for the Mini App.
 * Shows current queue, playback controls, music settings, and userbot management.
 *
 * Dependencies:
 *   - lib/components.js (Card, Toggle, EmptyState, Button, showToast)
 *   - store/index.js (useStore)
 */

import { Card, EmptyState, showToast, Modal, TabBar, Spinner, Avatar, Badge } from '../../lib/components.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';

const store = useStore;

// Store music worker status globally
let musicWorkerStatus = { available: false, reason: '' };

/**
 * Render the Music player page
 * @param {HTMLElement} container - Container element to render into
 */
export async function renderMusicPage(container) {
  const state = store.getState();
  const chatId = state.activeChatId;

  // Always clear container first
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  // If no chatId, try to get first available group
  if (!chatId && state.groups && state.groups.length > 0) {
    const firstGroup = state.groups[0];
    state.setActiveChatId(firstGroup.chat_id);
  }

  // Check again after auto-selecting
  const finalChatId = store.getState().activeChatId;

  if (!finalChatId) {
    container.appendChild(EmptyState({
      icon: '👆',
      title: 'Select a group',
      description: 'Choose a group to control music playback'
    }));
    return;
  }

  const initData = window.Telegram?.WebApp?.initData || '';

  // Show loading state
  container.innerHTML = `
    <div style="text-align: center; padding: var(--sp-8);">
      <div style="font-size: 48px; margin-bottom: var(--sp-4);">⏳</div>
      <div style="color: var(--text-muted);">Loading music queue...</div>
    </div>
  `;

  // Check music worker status first
  try {
    musicWorkerStatus = await apiFetch('/api/music/status');
  } catch (e) {
    musicWorkerStatus = { available: false, reason: 'Could not check music status' };
  }

  // Fetch music data
  await fetchMusicData(finalChatId, initData, container);
}

async function fetchMusicData(chatId, initData, container) {
  try {
    const data = await apiFetch(`/api/music/${chatId}/queue`);
    renderMusicInterface(container, data, chatId, initData);

    // Also load userbots section (async, don't wait)
    renderUserbotsSection(container, chatId);

    // Load play history (async, don't wait)
    renderPlayHistory(container, chatId);
  } catch (error) {
    console.error('[Music] Error loading data:', error);
    container.innerHTML = '';
    container.appendChild(EmptyState({
      icon: '⚠️',
      title: 'Failed to load music',
      description: 'Please try refreshing the page'
    }));
  }
}

function formatRelativeTime(dateString) {
  if (!dateString) return 'Never';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return `${diffMin} minute${diffMin > 1 ? 's' : ''} ago`;
  if (diffHour < 24) return `${diffHour} hour${diffHour > 1 ? 's' : ''} ago`;
  if (diffDay < 7) return `${diffDay} day${diffDay > 1 ? 's' : ''} ago`;
  return date.toLocaleDateString();
}

function renderMusicInterface(container, data, chatId, initData) {
  container.innerHTML = '';

  // Music Worker Status Banner
  const statusBanner = document.createElement('div');
  if (!musicWorkerStatus.available) {
    statusBanner.style.cssText = `
      background: var(--warning-dim, #FFF3CD);
      border: 1px solid var(--warning, #FFC107);
      border-radius: var(--r-lg);
      padding: var(--sp-3);
      margin-bottom: var(--sp-4);
      display: flex;
      align-items: center;
      gap: var(--sp-2);
    `;
    statusBanner.innerHTML = `
      <span>⚠️</span>
      <span style="flex: 1; font-size: var(--text-sm); color: var(--text-primary);">
        ${musicWorkerStatus.reason || 'Music worker is offline. Start it on your PC to enable streaming.'}
      </span>
      <button onclick="this.parentElement.remove()" style="background: none; border: none; cursor: pointer; padding: 4px;">✕</button>
    `;
  } else {
    statusBanner.style.cssText = `
      background: var(--success-dim, #D4EDDA);
      border: 1px solid var(--success, #28A745);
      border-radius: var(--r-lg);
      padding: var(--sp-2) var(--sp-3);
      margin-bottom: var(--sp-4);
      display: flex;
      align-items: center;
      gap: var(--sp-2);
      font-size: var(--text-sm);
      color: var(--success, #28A745);
    `;
    statusBanner.innerHTML = `
      <span>🟢</span>
      <span>Worker online</span>
    `;
  }
  container.appendChild(statusBanner);

  // Now Playing Card
  const nowPlayingCard = document.createElement('div');
  nowPlayingCard.style.cssText = `
    background: var(--bg-surface);
    border-radius: var(--r-xl);
    padding: var(--sp-4);
    margin-bottom: var(--sp-4);
    border: 1px solid var(--border);
  `;

  if (data.current) {
    const mins = Math.floor(data.current.duration / 60);
    const secs = data.current.duration % 60;
    const duration = `${mins}:${secs.toString().padStart(2, '0')}`;
    const sourceEmoji = getSourceEmoji(data.current.type);
    const ubText = data.userbot_id ? `<span style="color: var(--accent); margin-left: 8px;">🎭 Userbot ID: ${data.userbot_id}</span>` : '';

    nowPlayingCard.innerHTML = `
      <div style="
        display: flex;
        align-items: center;
        gap: var(--sp-4);
        margin-bottom: var(--sp-4);
      ">
        <div style="
          width: 64px;
          height: 64px;
          background: var(--accent-dim);
          border-radius: var(--r-lg);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 32px;
        ">
          🎵
        </div>
        <div style="flex: 1; min-width: 0;">
          <div style="
            font-weight: var(--fw-semibold);
            font-size: var(--text-base);
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          ">${escapeHtml(data.current.title)}</div>
          <div style="font-size: var(--text-sm); color: var(--text-muted);">
            ${data.current.performer ? escapeHtml(data.current.performer) : 'Unknown Artist'}
          </div>
          <div style="font-size: var(--text-xs); color: var(--text-muted); margin-top: 4px;">
            ${sourceEmoji} • ⏱ ${duration} • 🔊 ${data.volume}% ${ubText}
          </div>
        </div>
      </div>

      <!-- Progress Bar (decorative) -->
      <div style="
        height: 4px;
        background: var(--bg-input);
        border-radius: var(--r-full);
        margin-bottom: var(--sp-4);
        overflow: hidden;
      ">
        <div style="
          width: ${data.is_playing ? '60%' : '0%'};
          height: 100%;
          background: var(--accent);
          border-radius: var(--r-full);
          transition: width 1s linear;
        "></div>
      </div>

      <!-- Controls -->
      <div style="
        display: flex;
        justify-content: center;
        gap: var(--sp-2);
      ">
        <button class="music-btn" data-action="prev" style="${getButtonStyle()}">⏮</button>
        <button class="music-btn" data-action="pause" style="${getButtonStyle(true)}">
          ${data.is_playing ? '⏸' : '▶️'}
        </button>
        <button class="music-btn" data-action="skip" style="${getButtonStyle()}">⏭</button>
        <button class="music-btn" data-action="stop" style="${getButtonStyle()}">⏹</button>
      </div>

      <div style="
        display: flex;
        justify-content: center;
        gap: var(--sp-2);
        margin-top: var(--sp-3);
      ">
        <button class="music-btn" data-action="loop" style="${getSmallButtonStyle(data.repeat_mode !== 'none')}">
          🔁 ${data.repeat_mode !== 'none' ? '✓' : ''}
        </button>
        <button class="music-btn" data-action="shuffle" style="${getSmallButtonStyle(data.shuffle_mode)}">
          🔀 ${data.shuffle_mode ? '✓' : ''}
        </button>
        <button class="music-btn" data-action="vol-down" style="${getSmallButtonStyle()}">🔉</button>
        <button class="music-btn" data-action="vol-up" style="${getSmallButtonStyle()}">🔊</button>
      </div>
    `;
  } else {
    nowPlayingCard.innerHTML = `
      <div style="text-align: center; padding: var(--sp-6);">
        <div style="font-size: 48px; margin-bottom: var(--sp-3);">🎵</div>
        <div style="font-weight: var(--fw-semibold); color: var(--text-primary); margin-bottom: var(--sp-1);">
          Nothing Playing
        </div>
        <div style="font-size: var(--text-sm); color: var(--text-muted);">
          Use /play in the group to start music
        </div>
      </div>
    `;
  }

  container.appendChild(nowPlayingCard);

  // Queue Card with management controls
  if (data.queue && data.queue.length > 0) {
    const queueCard = Card({
      title: `📋 Queue (${data.queue.length})`,
      children: `
        <div class="queue-list" style="display: flex; flex-direction: column; gap: var(--sp-2);">
          ${data.queue.slice(0, 10).map((track, i) => {
            const mins = Math.floor(track.duration / 60);
            const secs = track.duration % 60;
            return `
              <div class="queue-item" data-position="${i}" style="
                display: flex;
                align-items: center;
                gap: var(--sp-3);
                padding: var(--sp-2);
                background: var(--bg-input);
                border-radius: var(--r-lg);
              " draggable="true">
                <span style="color: var(--text-muted); font-size: var(--text-sm); min-width: 24px; cursor: move;">☰</span>
                <span style="color: var(--text-muted); font-size: var(--text-sm); min-width: 20px;">${i + 1}.</span>
                <div style="flex: 1; min-width: 0;">
                  <div style="font-size: var(--text-sm); font-weight: var(--fw-medium); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    ${escapeHtml(track.title)}
                  </div>
                  <div style="font-size: var(--text-xs); color: var(--text-muted);">
                    ${escapeHtml(track.performer || 'Unknown')} • ${mins}:${secs.toString().padStart(2, '0')}
                  </div>
                </div>
                <button class="queue-delete-btn" data-position="${i}" style="
                  background: none;
                  border: none;
                  cursor: pointer;
                  padding: 4px;
                  font-size: 16px;
                  color: var(--danger);
                ">🗑️</button>
              </div>
            `;
          }).join('')}
          ${data.queue.length > 10 ? `<div style="text-align: center; color: var(--text-muted); font-size: var(--text-sm);">...and ${data.queue.length - 10} more</div>` : ''}
        </div>
      `
    });
    container.appendChild(queueCard);

    // Add drag-and-drop handlers for reordering
    setTimeout(() => {
      initDragAndDrop(container, chatId);
    }, 0);
  }

  // Quick Actions Card
  const actionsCard = Card({
    title: '⚡ Quick Actions',
    children: `
      <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--sp-2);">
        <button class="action-btn" data-cmd="play" style="${getActionButtonStyle()}">
          <div style="font-size: 20px;">▶️</div>
          <div style="font-size: var(--text-sm);">Play</div>
        </button>
        <button class="action-btn" data-cmd="pause" style="${getActionButtonStyle()}">
          <div style="font-size: 20px;">⏸</div>
          <div style="font-size: var(--text-sm);">Pause</div>
        </button>
        <button class="action-btn" data-cmd="skip" style="${getActionButtonStyle()}">
          <div style="font-size: 20px;">⏭</div>
          <div style="font-size: var(--text-sm);">Skip</div>
        </button>
        <button class="action-btn" data-cmd="stop" style="${getActionButtonStyle()}">
          <div style="font-size: 20px;">⏹</div>
          <div style="font-size: var(--text-sm);">Stop</div>
        </button>
      </div>
    `
  });
  container.appendChild(actionsCard);

  // Settings Card with rotation controls
  const settingsCard = Card({
    title: '⚙️ Music Settings',
    children: `
      <div style="display: flex; flex-direction: column; gap: var(--sp-3);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: var(--text-sm); color: var(--text-primary);">Volume</span>
          <span id="volume-display" style="font-size: var(--text-sm); color: var(--accent); font-weight: var(--fw-semibold);">${data.volume}%</span>
        </div>
        <input
          type="range"
          min="0"
          max="200"
          value="${data.volume}"
          class="volume-slider"
          style="width: 100%;"
        >

        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: var(--sp-2);">
          <span style="font-size: var(--text-sm); color: var(--text-primary);">Who can play music</span>
          <select class="music-mode-select" style="
            padding: var(--sp-2) var(--sp-3);
            background: var(--bg-input);
            border: 1px solid var(--border);
            border-radius: var(--r-lg);
            color: var(--text-primary);
            font-size: var(--text-sm);
          ">
            <option value="all" ${data.play_mode === 'all' ? 'selected' : ''}>Everyone</option>
            <option value="admins" ${data.play_mode === 'admins' ? 'selected' : ''}>Admins only</option>
          </select>
        </div>

        <div style="border-top: 1px solid var(--border); margin-top: var(--sp-2); padding-top: var(--sp-3);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--sp-2);">
            <div>
              <span style="font-size: var(--text-sm); color: var(--text-primary); display: block;">Auto-rotate userbots</span>
              <span style="font-size: var(--text-xs); color: var(--text-muted);">Automatically switch between userbots for load balancing</span>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" class="auto-rotate-toggle" ${data.auto_rotate ? 'checked' : ''}>
              <span class="toggle-slider"></span>
            </label>
          </div>

          <div class="rotation-mode-container" style="display: ${data.auto_rotate ? 'block' : 'none'}; margin-top: var(--sp-2);">
            <span style="font-size: var(--text-sm); color: var(--text-primary);">Rotation mode</span>
            <select class="rotation-mode-select" style="
              width: 100%;
              margin-top: var(--sp-1);
              padding: var(--sp-2) var(--sp-3);
              background: var(--bg-input);
              border: 1px solid var(--border);
              border-radius: var(--r-lg);
              color: var(--text-primary);
              font-size: var(--text-sm);
            ">
              <option value="round_robin" ${data.rotation_mode === 'round_robin' ? 'selected' : ''}>Round Robin</option>
              <option value="least_used" ${data.rotation_mode === 'least_used' ? 'selected' : ''}>Least Used</option>
              <option value="random" ${data.rotation_mode === 'random' ? 'selected' : ''}>Random</option>
            </select>
          </div>
        </div>
      </div>
    `
  });
  container.appendChild(settingsCard);

  // Add event listeners
  addEventListeners(container, chatId, initData);
}

function initDragAndDrop(container, chatId) {
  const queueList = container.querySelector('.queue-list');
  if (!queueList) return;

  let draggedItem = null;
  let draggedPosition = null;

  queueList.querySelectorAll('.queue-item').forEach(item => {
    item.addEventListener('dragstart', (e) => {
      draggedItem = item;
      draggedPosition = parseInt(item.dataset.position);
      item.style.opacity = '0.5';
    });

    item.addEventListener('dragend', async (e) => {
      item.style.opacity = '1';
      draggedItem = null;
    });

    item.addEventListener('dragover', (e) => {
      e.preventDefault();
      if (!draggedItem) return;

      const afterElement = getDragAfterElement(queueList, e.clientY);
      if (afterElement) {
        queueList.insertBefore(draggedItem, afterElement);
      } else {
        queueList.appendChild(draggedItem);
      }
    });

    item.addEventListener('drop', async (e) => {
      e.preventDefault();
      if (draggedPosition === null) return;

      // Calculate new position
      const items = [...queueList.querySelectorAll('.queue-item')];
      const newPosition = items.indexOf(draggedItem);

      if (newPosition !== draggedPosition) {
        // Call API to reorder
        try {
          await apiFetch(`/api/music/${chatId}/queue/reorder`, {
            method: 'POST',
            body: JSON.stringify({ track_id: draggedItem.dataset.trackId, new_position: newPosition })
          });
          showToast('Queue reordered!', 'success');
        } catch (err) {
          showToast('Failed to reorder', 'error');
          // Refresh to reset
          renderMusicPage(document.getElementById('page-music'));
        }
      }
    });
  });

  // Delete buttons
  queueList.querySelectorAll('.queue-delete-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const position = btn.dataset.position;
      try {
        // Get track ID from the queue item
        const queueItem = btn.closest('.queue-item');
        const trackId = queueItem?.dataset.trackId;
        if (trackId) {
          await apiFetch(`/api/music/${chatId}/queue/${trackId}`, { method: 'DELETE' });
          showToast('Track removed!', 'success');
          renderMusicPage(document.getElementById('page-music'));
        }
      } catch (err) {
        showToast('Failed to remove track', 'error');
      }
    });
  });
}

function getDragAfterElement(container, y) {
  const draggableElements = [...container.querySelectorAll('.queue-item:not([style*="opacity: 0.5"])')];

  return draggableElements.reduce((closest, child) => {
    const box = child.getBoundingClientRect();
    const offset = y - box.top - box.height / 2;
    if (offset < 0 && offset > closest.offset) {
      return { offset: offset, element: child };
    } else {
      return closest;
    }
  }, { offset: Number.NEGATIVE_INFINITY }).element;
}

function addEventListeners(container, chatId, initData) {
  // Music control buttons
  container.querySelectorAll('.music-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const action = btn.dataset.action;
      await sendMusicCommand(chatId, action, initData);
    });
  });

  // Quick action buttons
  container.querySelectorAll('.action-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const cmd = btn.dataset.cmd;
      await sendMusicCommand(chatId, cmd, initData);
    });
  });

  // Volume slider
  const volumeSlider = container.querySelector('.volume-slider');
  if (volumeSlider) {
    volumeSlider.addEventListener('change', async () => {
      const volume = parseInt(volumeSlider.value);
      const volumeDisplay = container.querySelector('#volume-display');
      if (volumeDisplay) volumeDisplay.textContent = `${volume}%`;
      await updateMusicSettings(chatId, { volume }, initData);
    });
  }

  // Music mode select
  const modeSelect = container.querySelector('.music-mode-select');
  if (modeSelect) {
    modeSelect.addEventListener('change', async () => {
      await sendMusicCommand(chatId, 'musicmode', initData, modeSelect.value);
    });
  }

  // Auto-rotate toggle
  const autoRotateToggle = container.querySelector('.auto-rotate-toggle');
  if (autoRotateToggle) {
    autoRotateToggle.addEventListener('change', async () => {
      const autoRotate = autoRotateToggle.checked;
      const rotationModeContainer = container.querySelector('.rotation-mode-container');
      if (rotationModeContainer) {
        rotationModeContainer.style.display = autoRotate ? 'block' : 'none';
      }

      const rotationMode = container.querySelector('.rotation-mode-select')?.value || 'round_robin';
      await updateMusicSettings(chatId, { auto_rotate: autoRotate, rotation_mode: rotationMode }, initData);
    });
  }

  // Rotation mode select
  const rotationModeSelect = container.querySelector('.rotation-mode-select');
  if (rotationModeSelect) {
    rotationModeSelect.addEventListener('change', async () => {
      const autoRotate = container.querySelector('.auto-rotate-toggle')?.checked || false;
      await updateMusicSettings(chatId, { auto_rotate: autoRotate, rotation_mode: rotationModeSelect.value }, initData);
    });
  }
}

async function renderPlayHistory(container, chatId) {
  try {
    const response = await apiFetch(`/api/music/${chatId}/history?limit=20`);
    if (!response.history || response.history.length === 0) return;

    const historyCard = Card({
      title: `📜 History (${response.count})`,
      children: `
        <div class="history-list" style="
          display: flex;
          flex-direction: column;
          gap: var(--sp-2);
          max-height: 300px;
          overflow-y: auto;
        ">
          ${response.history.map(entry => {
            const mins = Math.floor(entry.duration / 60);
            const secs = entry.duration % 60;
            const sourceEmoji = getSourceEmoji(entry.source);
            const playedAt = new Date(entry.added_at).toLocaleString();
            return `
              <div style="
                display: flex;
                align-items: center;
                gap: var(--sp-3);
                padding: var(--sp-2);
                background: var(--bg-input);
                border-radius: var(--r-lg);
                opacity: 0.8;
              ">
                <span style="font-size: 16px;">${sourceEmoji}</span>
                <div style="flex: 1; min-width: 0;">
                  <div style="font-size: var(--text-sm); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    ${escapeHtml(entry.title)}
                  </div>
                  <div style="font-size: var(--text-xs); color: var(--text-muted);">
                    ${escapeHtml(entry.performer || 'Unknown')} • ${mins}:${secs.toString().padStart(2, '0')} • ${playedAt}
                  </div>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      `
    });
    container.appendChild(historyCard);
  } catch (e) {
    console.error('[Music] Error loading history:', e);
  }
}

async function sendMusicCommand(chatId, action, initData, value = null) {
  try {
    // Map UI actions to API commands
    const commandMap = {
      'pause': 'pause',
      'play': 'resume',
      'skip': 'skip',
      'stop': 'stop',
      'prev': 'skip',  // API doesn't support prev directly
      'loop': 'loop',
      'shuffle': 'shuffle',
      'vol-up': 'volume_up',
      'vol-down': 'volume_down',
    };

    const cmd = commandMap[action] || action;

    await apiFetch(`/api/music/${chatId}/command`, {
      method: 'POST',
      body: JSON.stringify({ command: cmd, value }),
    });
    showToast('Command sent!', 'success');
  } catch (e) {
    console.error('Music command failed:', e);
    showToast('Command failed', 'error');
  }
}

async function updateMusicSettings(chatId, settings, initData) {
  try {
    await apiFetch(`/api/music/${chatId}/settings`, {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
    showToast('Settings updated!', 'success');
  } catch (e) {
    console.error('Settings update failed:', e);
    showToast('Update failed', 'error');
  }
}

function getButtonStyle(isPrimary = false) {
  return `
    width: 56px;
    height: 56px;
    border-radius: 50%;
    border: none;
    background: ${isPrimary ? 'var(--accent)' : 'var(--bg-input)'};
    color: ${isPrimary ? '#000' : 'var(--text-primary)'};
    font-size: 24px;
    cursor: pointer;
    transition: all var(--dur-fast);
    display: flex;
    align-items: center;
    justify-content: center;
  `;
}

function getSmallButtonStyle(active = false) {
  return `
    padding: var(--sp-2) var(--sp-3);
    border-radius: var(--r-lg);
    border: none;
    background: ${active ? 'var(--accent-dim)' : 'var(--bg-input)'};
    color: ${active ? 'var(--accent)' : 'var(--text-primary)'};
    font-size: var(--text-sm);
    cursor: pointer;
    transition: all var(--dur-fast);
  `;
}

function getActionButtonStyle() {
  return `
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--sp-1);
    padding: var(--sp-3);
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    color: var(--text-primary);
    cursor: pointer;
    transition: all var(--dur-fast);
  `;
}

function getSourceEmoji(type) {
  const emojis = {
    'youtube': '▶️',
    'soundcloud': '🔶',
    'spotify': '🟢',
    'direct': '🔗',
    'voice': '🎤',
  };
  return emojis[type] || '🎵';
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ── Userbot Management Section ─────────────────────────────────────────────

async function renderUserbotsSection(container, chatId) {
  const state = store.getState();
  const userContext = state.userContext;
  const activeBotId = userContext?.bot_info?.id;

  if (!activeBotId) {
    // Try to get bot_id from store if not in userContext
    const botId = state.bot_info?.id;
    if (!botId) {
      return; // No bot associated with this user
    }
  }

  // Userbot section
  const userbotsCard = Card({
    title: '🎭 Userbot Sessions',
    subtitle: 'Manage music streaming accounts',
    children: '<div id="userbots-container"></div>'
  });
  container.appendChild(userbotsCard);

  const userbotsContainer = userbotsCard.querySelector('#userbots-container');

  // Check if user owns this bot
  const isBotOwner = userContext?.role === 'owner' || userContext?.is_bot_owner;

  // Use the bot ID we found
  const finalBotId = activeBotId || state.bot_info?.id;

  if (!isBotOwner) {
    userbotsContainer.innerHTML = `
      <div style="text-align: center; padding: var(--sp-4); color: var(--text-muted);">
        🔒 Only bot owners can manage userbot sessions
      </div>
    `;
    return;
  }

  // Load userbots
  try {
    const response = await apiFetch(`/api/bots/${finalBotId}/music/userbots`);
    // Get current settings to know which userbot is active for this group
    const settingsResponse = await apiFetch(`/api/music/${chatId}/settings`).catch(() => ({}));
    const activeUserbotId = settingsResponse.userbot_id;
    renderUserbotsList(userbotsContainer, response.userbots || [], finalBotId, activeUserbotId);
  } catch (e) {
    userbotsContainer.innerHTML = `
      <div style="text-align: center; padding: var(--sp-4); color: var(--text-muted);">
        Failed to load userbots
      </div>
    `;
  }
}

function renderUserbotsList(container, userbots, botId, activeUserbotId) {
  const activeChatId = store.getState().activeChatId;

  if (userbots.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: var(--sp-4);">
        <div style="font-size: 32px; margin-bottom: var(--sp-2);">👤</div>
        <div style="color: var(--text-muted); margin-bottom: var(--sp-3);">No userbots added yet</div>
        <button class="btn btn-primary" onclick="window.openUserbotGenerator(${botId})">
          ➕ Add Userbot
        </button>
      </div>
    `;
    return;
  }

  container.innerHTML = '';

  const list = document.createElement('div');
  list.style.cssText = 'display: flex; flex-direction: column; gap: var(--sp-2); margin-bottom: var(--sp-3);';

  userbots.forEach(ub => {
    const isActiveForGroup = ub.id === activeUserbotId;
    const statusColor = ub.is_banned ? 'var(--danger)' : (ub.is_active ? 'var(--success, #28A745)' : 'var(--text-muted)');
    const statusText = ub.is_banned ? 'Banned' : (ub.is_active ? 'Active' : 'Inactive');

    const item = document.createElement('div');
    item.style.cssText = `
      padding: var(--sp-3);
      background: var(--bg-input);
      border-radius: var(--r-lg);
      border: 2px solid ${isActiveForGroup ? 'var(--accent)' : (ub.is_banned ? 'var(--danger)' : 'var(--border)')};
      display: flex;
      flex-direction: column;
      gap: var(--sp-2);
    `;

    const top = document.createElement('div');
    top.style.cssText = 'display: flex; justify-content: space-between; align-items: center;';

    const info = document.createElement('div');
    info.style.cssText = 'display: flex; align-items: center; gap: var(--sp-2);';
    info.appendChild(Avatar({ name: ub.tg_name, size: 32 }));

    const nameWrap = document.createElement('div');
    nameWrap.innerHTML = `
      <div style="font-weight: var(--fw-medium); font-size: var(--text-sm); display: flex; align-items: center; gap: var(--sp-1);">
        ${escapeHtml(ub.tg_name || 'Unknown')}
        ${isActiveForGroup ? '<span style="background: var(--accent-dim); color: var(--accent); padding: 2px 6px; border-radius: var(--r-sm); font-size: 10px;">✅ Active for this group</span>' : ''}
      </div>
      <div style="font-size: var(--text-xs); color: var(--text-muted);">
        ${ub.tg_username ? `@${escapeHtml(ub.tg_username)}` : 'No username'}
      </div>
    `;
    info.appendChild(nameWrap);

    const stats = document.createElement('div');
    stats.style.textAlign = 'right';
    stats.innerHTML = `
      <div style="font-size: var(--text-xs); color: var(--text-muted);">Risk Free</div>
      <div style="font-weight: var(--fw-semibold); color: var(--accent); font-size: var(--text-sm);">${ub.risk_free || 0} ⭐</div>
    `;

    top.appendChild(info);
    top.appendChild(stats);
    item.appendChild(top);

    // Status row
    const statusRow = document.createElement('div');
    statusRow.style.cssText = 'display: flex; align-items: center; gap: var(--sp-2); font-size: var(--text-xs);';
    statusRow.innerHTML = `
      <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ${statusColor};"></span>
      <span style="color: ${statusColor};">${statusText}</span>
      <span style="color: var(--text-muted);">•</span>
      <span style="color: var(--text-muted);">${ub.play_count || 0} plays</span>
      <span style="color: var(--text-muted);">•</span>
      <span style="color: var(--text-muted);">Last used: ${formatRelativeTime(ub.last_used_at)}</span>
    `;
    item.appendChild(statusRow);

    if (ub.is_banned) {
      const banInfo = document.createElement('div');
      banInfo.style.cssText = 'font-size: var(--text-xs); color: var(--danger); background: var(--danger-dim); padding: var(--sp-1) var(--sp-2); border-radius: var(--r-sm);';
      banInfo.textContent = `🚫 Banned: ${ub.ban_reason || 'No reason'}`;
      item.appendChild(banInfo);
    }

    const actions = document.createElement('div');
    actions.style.cssText = 'display: flex; gap: var(--sp-2); flex-wrap: wrap;';

    // Assign to group button
    const assignBtn = document.createElement('button');
    assignBtn.className = 'btn btn-secondary';
    assignBtn.style.cssText = 'padding: 4px 8px; font-size: 11px; flex: 1;';
    assignBtn.textContent = isActiveForGroup ? '✓ Currently Active' : '📍 Use for this Group';
    if (isActiveForGroup) {
      assignBtn.disabled = true;
      assignBtn.style.opacity = '0.7';
    }
    assignBtn.onclick = () => window.assignUserbot(botId, activeChatId, ub.id);
    actions.appendChild(assignBtn);

    const feeBtn = document.createElement('button');
    feeBtn.className = 'btn btn-secondary';
    feeBtn.style.cssText = 'padding: 4px 8px; font-size: 11px;';
    feeBtn.textContent = '💰 Risk Free';
    feeBtn.onclick = () => window.editRiskFree(botId, ub.id, ub.risk_free || 0);
    actions.appendChild(feeBtn);

    if (ub.is_banned) {
      const unbanBtn = document.createElement('button');
      unbanBtn.className = 'btn btn-secondary';
      unbanBtn.style.cssText = 'padding: 4px 8px; font-size: 11px;';
      unbanBtn.textContent = '✅ Unban';
      unbanBtn.onclick = () => window.unbanUserbot(botId, ub.id);
      actions.appendChild(unbanBtn);
    } else {
      const banBtn = document.createElement('button');
      banBtn.className = 'btn btn-secondary';
      banBtn.style.cssText = 'padding: 4px 8px; font-size: 11px; color: var(--danger);';
      banBtn.textContent = '🚫 Ban';
      banBtn.onclick = () => window.banUserbot(botId, ub.id);
      actions.appendChild(banBtn);
    }

    // Activate/Deactivate toggle
    const toggleBtn = document.createElement('button');
    toggleBtn.className = 'btn btn-secondary';
    toggleBtn.style.cssText = `padding: 4px 8px; font-size: 11px; ${ub.is_active ? '' : 'color: var(--accent);'}`;
    toggleBtn.textContent = ub.is_active ? '🔴 Deactivate' : '🟢 Activate';
    toggleBtn.onclick = () => window.toggleUserbotActive(botId, ub.id);
    actions.appendChild(toggleBtn);

    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn-secondary';
    delBtn.style.cssText = 'padding: 4px 8px; font-size: 11px; color: var(--danger);';
    delBtn.textContent = '🗑️';
    delBtn.onclick = () => window.deleteUserbot(botId, ub.id);
    actions.appendChild(delBtn);

    item.appendChild(actions);
    list.appendChild(item);
  });

  container.appendChild(list);

  const addMoreBtn = document.createElement('button');
  addMoreBtn.className = 'btn btn-primary';
  addMoreBtn.style.width = '100%';
  addMoreBtn.textContent = '➕ Add Another Userbot';
  addMoreBtn.onclick = () => window.openUserbotGenerator(botId);
  container.appendChild(addMoreBtn);
}

window.assignUserbot = async function(botId, chatId, userbotId) {
  try {
    // First fetch current settings
    const currentSettings = await apiFetch(`/api/music/${chatId}/settings`).catch(() => ({}));

    // Merge with new userbot_id
    const newSettings = {
      ...currentSettings,
      userbot_id: userbotId
    };

    await apiFetch(`/api/music/${chatId}/settings`, {
      method: 'PUT',
      body: JSON.stringify(newSettings),
    });
    showToast('Userbot assigned to this group!', 'success');
    renderMusicPage(document.getElementById('page-music'));
  } catch (e) {
    showToast('Failed to assign userbot', 'error');
  }
};

// Global functions for userbot management
window.openUserbotGenerator = async function(botId) {
  const content = document.createElement('div');
  content.id = 'auth-modal-content';

  let currentTab = 'qr';
  let pollingInterval = null;

  const renderTab = (tabId) => {
    currentTab = tabId;
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }

    const container = content.querySelector('#tab-container');
    container.innerHTML = '';

    if (tabId === 'qr') {
      renderQRTab(container);
    } else if (tabId === 'phone') {
      renderPhoneTab(container);
    } else if (tabId === 'session') {
      renderSessionTab(container);
    }
  };

  const renderQRTab = async (container) => {
    container.innerHTML = `
      <div style="text-align: center; padding: var(--sp-4);">
        <div id="qr-loading">${Spinner({ size: 40 }).outerHTML}</div>
        <div id="qr-display" style="display: none; margin-top: var(--sp-4);">
          <img id="qr-image" style="width: 200px; height: 200px; border-radius: var(--r-lg); margin-bottom: var(--sp-4);">
          <div style="font-size: var(--text-sm); color: var(--text-muted);">
            Scan this QR code with your Telegram app:<br>
            <b>Settings > Devices > Link Desktop Device</b>
          </div>
        </div>
      </div>
    `;

    try {
      const res = await apiFetch(`/api/bots/${botId}/music/auth/start-qr`, { method: 'POST' });
      if (res.ok) {
        container.querySelector('#qr-loading').style.display = 'none';
        const display = container.querySelector('#qr-display');
        display.style.display = 'block';
        container.querySelector('#qr-image').src = `data:image/png;base64,${res.qr_image_base64}`;

        // Start polling
        pollingInterval = setInterval(async () => {
          try {
            const status = await apiFetch(`/api/bots/${botId}/music/auth/qr-status`);
            if (status.ok && status.scanned) {
              clearInterval(pollingInterval);
              showToast(`✅ Added ${status.tg_name}!`, 'success');
              modal.close();
              renderMusicPage(document.getElementById('page-music'));
            } else if (status.error === 'QR Expired') {
              clearInterval(pollingInterval);
              renderQRTab(container); // Refresh
            }
          } catch (e) {
            console.error('QR polling failed:', e);
          }
        }, 3000);
      }
    } catch (e) {
      container.innerHTML = `<div style="color: var(--danger); text-align: center;">Failed to start QR auth: ${e.message}</div>`;
    }
  };

  const renderPhoneTab = (container) => {
    container.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: var(--sp-3); padding-top: var(--sp-2);">
        <div style="font-size: var(--text-sm); color: var(--text-muted);">
          Enter your phone number with country code.
        </div>
        <input type="text" id="phone-input" placeholder="+1234567890" style="
          padding: var(--sp-3); background: var(--bg-input); border: 1px solid var(--border);
          border-radius: var(--r-lg); color: var(--text-primary);
        ">
        <button id="send-otp-btn" class="btn btn-primary">Send Code</button>
        <div id="otp-section" style="display: none; flex-direction: column; gap: var(--sp-3); margin-top: var(--sp-2);">
          <div style="height: 1px; background: var(--border); margin: var(--sp-2) 0;"></div>
          <div style="font-size: var(--text-sm); color: var(--text-muted);">
            Enter the code sent to your Telegram account.
          </div>
          <input type="text" id="otp-input" placeholder="12345" style="
            padding: var(--sp-3); background: var(--bg-input); border: 1px solid var(--border);
            border-radius: var(--r-lg); color: var(--text-primary);
          ">
          <button id="verify-otp-btn" class="btn btn-primary">Verify Code</button>
        </div>
        <div id="2fa-section" style="display: none; flex-direction: column; gap: var(--sp-3); margin-top: var(--sp-2);">
          <div style="font-size: var(--text-sm); color: var(--text-muted);">
            Your account has 2nd-step verification enabled.
          </div>
          <input type="password" id="2fa-input" placeholder="Password" style="
            padding: var(--sp-3); background: var(--bg-input); border: 1px solid var(--border);
            border-radius: var(--r-lg); color: var(--text-primary);
          ">
          <button id="verify-2fa-btn" class="btn btn-primary">Login</button>
        </div>
      </div>
    `;

    const phoneInput = container.querySelector('#phone-input');
    const otpInput = container.querySelector('#otp-input');
    const passInput = container.querySelector('#2fa-input');

    container.querySelector('#send-otp-btn').onclick = async () => {
      const phone = phoneInput.value.trim();
      if (!phone) return showToast('Enter phone number', 'warning');

      try {
        const res = await apiFetch(`/api/bots/${botId}/music/auth/start-phone`, {
          method: 'POST', body: JSON.stringify({ phone })
        });
        if (res.ok) {
          container.querySelector('#otp-section').style.display = 'flex';
          container.querySelector('#send-otp-btn').style.display = 'none';
          phoneInput.disabled = true;
          showToast('Code sent!', 'success');
        }
      } catch (e) { showToast(e.message, 'error'); }
    };

    container.querySelector('#verify-otp-btn').onclick = async () => {
      const code = otpInput.value.trim();
      if (!code) return showToast('Enter code', 'warning');

      try {
        const res = await apiFetch(`/api/bots/${botId}/music/auth/verify-otp`, {
          method: 'POST', body: JSON.stringify({ code })
        });
        if (res.requires_2fa) {
          container.querySelector('#otp-section').style.display = 'none';
          container.querySelector('#2fa-section').style.display = 'flex';
        } else if (res.ok) {
          showToast(`✅ Added ${res.tg_name}!`, 'success');
          modal.close();
          renderMusicPage(document.getElementById('page-music'));
        }
      } catch (e) { showToast(e.message, 'error'); }
    };

    container.querySelector('#verify-2fa-btn').onclick = async () => {
      const password = passInput.value.trim();
      if (!password) return showToast('Enter password', 'warning');

      try {
        const res = await apiFetch(`/api/bots/${botId}/music/auth/verify-2fa`, {
          method: 'POST', body: JSON.stringify({ password })
        });
        if (res.ok) {
          showToast(`✅ Added ${res.tg_name}!`, 'success');
          modal.close();
          renderMusicPage(document.getElementById('page-music'));
        }
      } catch (e) { showToast(e.message, 'error'); }
    };
  };

  const renderSessionTab = (container) => {
    container.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: var(--sp-3); padding-top: var(--sp-2);">
        <div style="font-size: var(--text-sm); color: var(--text-muted);">
          Paste a Pyrogram session string.
        </div>
        <textarea id="session-input" rows="4" placeholder="Paste string here..." style="
          padding: var(--sp-3); background: var(--bg-input); border: 1px solid var(--border);
          border-radius: var(--r-lg); color: var(--text-primary); font-family: monospace; font-size: 12px;
          resize: none;
        "></textarea>
        <button id="save-session-btn" class="btn btn-primary">Add Userbot</button>
      </div>
    `;

    container.querySelector('#save-session-btn').onclick = async () => {
      const str = container.querySelector('#session-input').value.trim();
      if (!str) return showToast('Paste session string', 'warning');

      try {
        const res = await apiFetch(`/api/bots/${botId}/music/auth/session-string`, {
          method: 'POST', body: JSON.stringify({ session_string: str })
        });
        if (res.ok) {
          showToast(`✅ Added ${res.tg_name}!`, 'success');
          modal.close();
          renderMusicPage(document.getElementById('page-music'));
        }
      } catch (e) { showToast(e.message, 'error'); }
    };
  };

  content.innerHTML = `
    <div id="tabs-placeholder"></div>
    <div id="tab-container" style="min-height: 280px;"></div>
  `;

  const modal = Modal({
    title: '🎭 Add Music Userbot',
    content: content,
    onClose: () => {
      if (pollingInterval) clearInterval(pollingInterval);
    }
  });

  const tabBar = TabBar({
    tabs: [
      { id: 'qr', label: '📱 QR Code' },
      { id: 'phone', label: '📞 Phone' },
      { id: 'session', label: '📄 String' }
    ],
    active: currentTab,
    onChange: renderTab
  });

  content.querySelector('#tabs-placeholder').appendChild(tabBar);
  renderTab(currentTab);
};

window.editRiskFree = async function(botId, userbotId, currentFree) {
  const newFree = prompt('Enter risk free amount (in Stars):', currentFree.toString());
  if (newFree === null) return;

  try {
    await apiFetch(`/api/bots/${botId}/music/userbot/risk-free`, {
      method: 'PUT',
      body: JSON.stringify({ userbot_id: userbotId, risk_free: parseInt(newFree) || 0 })
    });
    showToast('Risk free updated!', 'success');
    renderMusicPage(document.getElementById('page-music'));
  } catch (e) {
    showToast('Failed to update risk free', 'error');
  }
};

window.banUserbot = async function(botId, userbotId) {
  const reason = prompt('Enter ban reason (optional):', 'Risk free not paid');
  if (reason === null) return;

  try {
    await apiFetch(`/api/bots/${botId}/music/userbot/ban`, {
      method: 'POST',
      body: JSON.stringify({ userbot_id: userbotId, ban_reason: reason || 'Risk free not paid' })
    });
    showToast('Userbot banned!', 'success');
    renderMusicPage(document.getElementById('page-music'));
  } catch (e) {
    showToast('Failed to ban userbot', 'error');
  }
};

window.unbanUserbot = async function(botId, userbotId) {
  try {
    await apiFetch(`/api/bots/${botId}/music/userbot/unban`, {
      method: 'POST',
      body: JSON.stringify({ userbot_id: userbotId })
    });
    showToast('Userbot unbanned!', 'success');
    renderMusicPage(document.getElementById('page-music'));
  } catch (e) {
    showToast('Failed to unban userbot', 'error');
  }
};

window.deleteUserbot = async function(botId, userbotId) {
  if (!confirm('Are you sure you want to delete this userbot?')) return;

  try {
    await apiFetch(`/api/bots/${botId}/music/userbot/${userbotId}`, {
      method: 'DELETE'
    });
    showToast('Userbot deleted!', 'success');
    renderMusicPage(document.getElementById('page-music'));
  } catch (e) {
    showToast('Failed to delete userbot', 'error');
  }
};

window.toggleUserbotActive = async function(botId, userbotId) {
  try {
    const res = await apiFetch(`/api/bots/${botId}/music/userbots/${userbotId}/activate`, {
      method: 'PUT'
    });
    if (res.ok) {
      showToast(res.is_active ? 'Userbot activated!' : 'Userbot deactivated!', 'success');
      renderMusicPage(document.getElementById('page-music'));
    }
  } catch (e) {
    showToast('Failed to toggle userbot status', 'error');
  }
};
