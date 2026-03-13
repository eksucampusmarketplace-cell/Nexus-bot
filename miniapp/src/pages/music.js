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
    
    // Also load userbots section (async, don't wait)
    renderUserbotsSection(container, chatId);
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

// ── Userbot Management Section ─────────────────────────────────────────────

async function renderUserbotsSection(container, chatId) {
  const state = store.getState();
  const userContext = state.userContext;
  const activeBotId = userContext?.bot_info?.id;
  
  if (!activeBotId) {
    return; // No bot associated with this user
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
    const response = await apiFetch(`/api/bots/${activeBotId}/music/userbots`);
    renderUserbotsList(userbotsContainer, response.userbots || [], activeBotId);
  } catch (e) {
    userbotsContainer.innerHTML = `
      <div style="text-align: center; padding: var(--sp-4); color: var(--text-muted);">
        Failed to load userbots
      </div>
    `;
  }
}

function renderUserbotsList(container, userbots, botId) {
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

  let html = `
    <div style="display: flex; flex-direction: column; gap: var(--sp-2); margin-bottom: var(--sp-3);">
      ${userbots.map(ub => `
        <div style="
          padding: var(--sp-3);
          background: var(--bg-input);
          border-radius: var(--r-lg);
          border: 1px solid ${ub.is_banned ? 'var(--danger)' : 'var(--border)'};
        ">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div style="font-weight: var(--fw-medium);">
                ${escapeHtml(ub.tg_name || 'Unknown')}
                ${ub.is_banned ? '<span style="color: var(--danger); font-size: 12px;"> (BANNED)</span>' : ''}
              </div>
              <div style="font-size: var(--text-xs); color: var(--text-muted);">
                @${escapeHtml(ub.tg_username || 'no username')}
              </div>
            </div>
            <div style="text-align: right;">
              <div style="font-size: var(--text-xs); color: var(--text-muted);">Risk Fee</div>
              <div style="font-weight: var(--fw-semibold); color: var(--accent);">${ub.risk_fee || 0} ⭐</div>
            </div>
          </div>
          <div style="display: flex; gap: var(--sp-2); margin-top: var(--sp-2);">
            <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 12px;" 
              onclick="window.editRiskFee(${botId}, ${ub.id}, ${ub.risk_fee || 0})">
              💰 Set Fee
            </button>
            ${ub.is_banned ? `
              <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 12px;" 
                onclick="window.unbanUserbot(${botId}, ${ub.id})">
                ✅ Unban
              </button>
            ` : `
              <button class="btn btn-danger" style="padding: 4px 8px; font-size: 12px; background: none; color: var(--danger); border: 1px solid var(--danger);" 
                onclick="window.banUserbot(${botId}, ${ub.id})">
                🚫 Ban
              </button>
            `}
            <button class="btn btn-danger" style="padding: 4px 8px; font-size: 12px;" 
              onclick="window.deleteUserbot(${botId}, ${ub.id})">
              🗑️
            </button>
          </div>
        </div>
      `).join('')}
    </div>
    <button class="btn btn-primary" style="width: 100%;" onclick="window.openUserbotGenerator(${botId})">
      ➕ Add Another Userbot
    </button>
  `;

  container.innerHTML = html;
}

// Global functions for userbot management
window.openUserbotGenerator = async function(botId) {
  const method = prompt('Choose auth method:\n1. Phone + OTP\n2. Session String\n\nEnter 1 or 2:', '1');
  
  if (method === '1') {
    // Phone auth flow
    const phone = prompt('Enter phone number (with country code, e.g. +1234567890):');
    if (!phone) return;
    
    try {
      const result = await apiFetch(`/api/bots/${botId}/music/auth/start-phone`, {
        method: 'POST',
        body: JSON.stringify({ phone })
      });
      
      if (result.ok && result.requires_otp) {
        const code = prompt('Enter the OTP code sent to your phone:');
        if (!code) return;
        
        const verifyResult = await apiFetch(`/api/bots/${botId}/music/auth/verify-otp`, {
          method: 'POST',
          body: JSON.stringify({ code, phone_hash: result.phone_hash })
        });
        
        if (verifyResult.ok) {
          alert('✅ Userbot added successfully!');
          renderMusicPage(document.getElementById('page-music'));
        } else {
          alert('❌ Failed: ' + (verifyResult.detail || 'Unknown error'));
        }
      }
    } catch (e) {
      alert('❌ Error: ' + e.message);
    }
  } else if (method === '2') {
    // Session string flow
    const sessionString = prompt('Enter Pyrogram session string:');
    if (!sessionString) return;
    
    try {
      const result = await apiFetch(`/api/bots/${botId}/music/auth/session-string`, {
        method: 'POST',
        body: JSON.stringify({ session_string: sessionString })
      });
      
      if (result.ok) {
        alert('✅ Userbot added successfully!');
        renderMusicPage(document.getElementById('page-music'));
      } else {
        alert('❌ Failed: ' + (result.detail || 'Unknown error'));
      }
    } catch (e) {
      alert('❌ Error: ' + e.message);
    }
  }
};

window.editRiskFee = async function(botId, userbotId, currentFee) {
  const newFee = prompt('Enter risk fee amount (in Stars):', currentFee.toString());
  if (newFee === null) return;
  
  try {
    await apiFetch(`/api/bots/${botId}/music/userbot/risk-fee`, {
      method: 'PUT',
      body: JSON.stringify({ userbot_id: userbotId, risk_fee: parseInt(newFee) || 0 })
    });
    showToast('Risk fee updated!', 'success');
    renderMusicPage(document.getElementById('page-music'));
  } catch (e) {
    showToast('Failed to update risk fee', 'error');
  }
};

window.banUserbot = async function(botId, userbotId) {
  const reason = prompt('Enter ban reason (optional):', 'Risk fee not paid');
  if (reason === null) return;
  
  try {
    await apiFetch(`/api/bots/${botId}/music/userbot/ban`, {
      method: 'POST',
      body: JSON.stringify({ userbot_id: userbotId, ban_reason: reason || 'Risk fee not paid' })
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
