/**
 * miniapp/src/pages/music.js
 *
 * Music player control page for the Mini App.
 * Shows current queue, playback controls, and music settings.
 *
 * Dependencies:
 *   - lib/components.js (Card, Toggle, EmptyState, Button, showToast)
 *   - store/index.js (useStore)
 */

import { Card, EmptyState, showToast } from '../../lib/components.js';
import { useStore } from '../../store/index.js';
import { apiFetch } from '../../lib/api.js';

const store = useStore;

/**
 * Render the Music player page
 * @param {HTMLElement} container - Container element to render into
 */
export function renderMusicPage(container) {
  const chatId = store.getState().activeChatId;
  const initData = window.Telegram?.WebApp?.initData || '';
  
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '👆',
      title: 'Select a group',
      description: 'Choose a group to control music playback'
    }));
    return;
  }

  // Show loading state
  container.innerHTML = `
    <div style="text-align: center; padding: var(--sp-8);">
      <div style="font-size: 48px; margin-bottom: var(--sp-4);">⏳</div>
      <div style="color: var(--text-muted);">Loading music queue...</div>
    </div>
  `;

  // Fetch music data
  fetchMusicData(chatId, initData, container);
}

async function fetchMusicData(chatId, initData, container) {
  try {
    const data = await apiFetch(`/api/music/${chatId}/queue`);
    renderMusicInterface(container, data, chatId, initData);
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

function renderMusicInterface(container, data, chatId, initData) {
  container.innerHTML = '';

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
            ${sourceEmoji} • ⏱ ${duration} • 🔊 ${data.volume}%
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

  // Queue Card
  if (data.queue && data.queue.length > 0) {
    const queueCard = Card({
      title: `📋 Queue (${data.queue.length})`,
      children: `
        <div class="queue-list" style="display: flex; flex-direction: column; gap: var(--sp-2);">
          ${data.queue.slice(0, 10).map((track, i) => {
            const mins = Math.floor(track.duration / 60);
            const secs = track.duration % 60;
            return `
              <div style="
                display: flex;
                align-items: center;
                gap: var(--sp-3);
                padding: var(--sp-2);
                background: var(--bg-input);
                border-radius: var(--r-lg);
              ">
                <span style="color: var(--text-muted); font-size: var(--text-sm); min-width: 24px;">${i + 1}.</span>
                <div style="flex: 1; min-width: 0;">
                  <div style="font-size: var(--text-sm); font-weight: var(--fw-medium); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    ${escapeHtml(track.title)}
                  </div>
                  <div style="font-size: var(--text-xs); color: var(--text-muted);">
                    ${escapeHtml(track.performer || 'Unknown')} • ${mins}:${secs.toString().padStart(2, '0')}
                  </div>
                </div>
              </div>
            `;
          }).join('')}
          ${data.queue.length > 10 ? `<div style="text-align: center; color: var(--text-muted); font-size: var(--text-sm);">...and ${data.queue.length - 10} more</div>` : ''}
        </div>
      `
    });
    container.appendChild(queueCard);
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

  // Settings Card
  const settingsCard = Card({
    title: '⚙️ Music Settings',
    children: `
      <div style="display: flex; flex-direction: column; gap: var(--sp-3);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: var(--text-sm); color: var(--text-primary);">Volume</span>
          <span style="font-size: var(--text-sm); color: var(--accent); font-weight: var(--fw-semibold);">${data.volume}%</span>
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
      </div>
    `
  });
  container.appendChild(settingsCard);

  // Add event listeners
  addEventListeners(container, chatId, initData);
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
