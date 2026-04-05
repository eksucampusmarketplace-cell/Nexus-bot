/**
 * miniapp/src/pages/history.js
 * 
 * Name history (Sangmata) page with expanded features:
 * F-01: Stats tab (leaderboard)
 * F-02: Real-time alerts (backend implemented)
 * F-03: Search by old name
 * F-04: User timeline
 * F-05: Export CSV
 * F-06: Retention settings
 */

import { t } from '../../lib/i18n.js?v=1.6.0';
import { showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { Toggle } from '../../lib/components.js?v=1.6.0';

let activeTab = 'recent'; // 'recent', 'stats', 'search'

export async function renderHistoryPage(container) {
  const chatId = useStore.getState().activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.innerHTML = `
      <div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">
        <div style="font-size:3rem;margin-bottom:var(--sp-3)">📜</div>
        <div>${t('select_group', 'Select a group first')}</div>
      </div>
    `;
    return;
  }

  // Load current settings
  let currentEnabled = false;
  let currentLimit = 10;
  let currentRetention = 0;
  let alertEnabled = false;
  let alertThreshold = 1;
  let federationSync = false;
  let trackPhotos = true;

  try {
    const resp = await apiFetch(`/api/groups/${chatId}/name-history`);
    currentEnabled = resp?.enabled ?? false;
    currentLimit = resp?.limit ?? 10;
    currentRetention = resp?.retention_days ?? 0;
    alertEnabled = resp?.alert_enabled ?? false;
    alertThreshold = resp?.alert_threshold ?? 1;
    federationSync = resp?.federation_sync ?? false;
    trackPhotos = resp?.track_photos ?? true;
  } catch (err) {
    console.debug('Failed to load history settings:', err);
  }

  const header = document.createElement('div');
  header.innerHTML = `
    <div style="display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);">
      <div style="font-size:2rem">📜</div>
      <div>
        <div style="font-size:1.2rem;font-weight:700">${t('nav_history', 'Name History')}</div>
        <div style="font-size:0.85rem;color:var(--text-muted)">${t('history_subtitle', 'Track user name changes')}</div>
      </div>
    </div>
  `;
  container.appendChild(header);

  // Tab navigation
  const tabsSection = document.createElement('div');
  tabsSection.style.cssText = 'display:flex;gap:var(--sp-2);margin-bottom:var(--sp-4);border-bottom:1px solid var(--border);';
  tabsSection.innerHTML = `
    <button class="tab-btn ${activeTab === 'recent' ? 'active' : ''}" data-tab="recent" style="padding:var(--sp-2) var(--sp-4);background:none;border:none;color:${activeTab === 'recent' ? 'var(--accent)' : 'var(--text-muted)'};cursor:pointer;font-weight:500;border-bottom:2px solid ${activeTab === 'recent' ? 'var(--accent)' : 'transparent'};">Recent</button>
    <button class="tab-btn ${activeTab === 'stats' ? 'active' : ''}" data-tab="stats" style="padding:var(--sp-2) var(--sp-4);background:none;border:none;color:${activeTab === 'stats' ? 'var(--accent)' : 'var(--text-muted)'};cursor:pointer;font-weight:500;border-bottom:2px solid ${activeTab === 'stats' ? 'var(--accent)' : 'transparent'};">Stats</button>
    <button class="tab-btn ${activeTab === 'search' ? 'active' : ''}" data-tab="search" style="padding:var(--sp-2) var(--sp-4);background:none;border:none;color:${activeTab === 'search' ? 'var(--accent)' : 'var(--text-muted)'};cursor:pointer;font-weight:500;border-bottom:2px solid ${activeTab === 'search' ? 'var(--accent)' : 'transparent'};">Search</button>
    <button class="tab-btn ${activeTab === 'settings' ? 'active' : ''}" data-tab="settings" style="padding:var(--sp-2) var(--sp-4);background:none;border:none;color:${activeTab === 'settings' ? 'var(--accent)' : 'var(--text-muted)'};cursor:pointer;font-weight:500;border-bottom:2px solid ${activeTab === 'settings' ? 'var(--accent)' : 'transparent'};">Settings</button>
  `;
  container.appendChild(tabsSection);

  // Tab content container
  const contentSection = document.createElement('div');
  contentSection.id = 'history-content';
  container.appendChild(contentSection);

  // Tab click handlers
  tabsSection.querySelectorAll('.tab-btn').forEach(btn => {
    btn.onclick = () => {
      activeTab = btn.dataset.tab;
      renderHistoryPage(container);
    };
  });

  // Render active tab content
  if (activeTab === 'recent') {
    await renderRecentTab(contentSection, chatId, currentEnabled);
  } else if (activeTab === 'stats') {
    await renderStatsTab(contentSection, chatId, currentEnabled);
  } else if (activeTab === 'search') {
    await renderSearchTab(contentSection, chatId, currentEnabled);
  } else if (activeTab === 'settings') {
    await renderSettingsTab(contentSection, chatId, currentEnabled, currentLimit, currentRetention, alertEnabled, alertThreshold, federationSync, trackPhotos);
  }
}

async function renderRecentTab(container, chatId, isEnabled) {
  if (!isEnabled) {
    container.innerHTML = `
      <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);font-size:0.85rem">
        ${t('history_disabled', 'Enable tracking in Settings to start recording name changes')}
      </div>
    `;
    return;
  }

  // Export CSV button
  const exportBtn = document.createElement('button');
  exportBtn.className = 'btn btn-secondary';
  exportBtn.style.cssText = 'margin-bottom:var(--sp-3);width:auto;';
  exportBtn.innerHTML = '📥 Export CSV';
  exportBtn.onclick = () => exportHistoryCSV(chatId);
  container.appendChild(exportBtn);

  const listContainer = document.createElement('div');
  listContainer.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';
  listContainer.innerHTML = `<div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);font-size:0.85rem">${t('loading', 'Loading...')}</div>`;
  container.appendChild(listContainer);

  try {
    const history = await apiFetch(`/api/groups/${chatId}/name-history/recent`).catch(() => []);

    if (!history || history.length === 0) {
      listContainer.innerHTML = `
        <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);font-size:0.85rem">
          ${t('no_history', 'No recent name changes')}
        </div>
      `;
      return;
    }

    listContainer.innerHTML = '';
    history.forEach((entry, index) => {
      const item = document.createElement('div');
      item.style.cssText = 'display:flex;align-items:center;gap:var(--sp-2);padding:var(--sp-3);background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-lg);font-size:0.85rem;cursor:pointer;transition:background var(--dur-fast);';
      
      // Show federation badge if entry is federated and from a different group
      const fedBadge = (entry.is_federated && entry.source_chat_id && entry.source_chat_id !== chatId) 
        ? `<span style="font-size:0.65rem;background:var(--accent);color:#000;padding:2px 6px;border-radius:4px;margin-left:var(--sp-1)">FED</span>` 
        : '';
      const groupLabel = (entry.is_federated && entry.group_name && entry.source_chat_id !== chatId)
        ? `<span style="font-size:0.7rem;color:var(--accent);margin-left:auto">${escapeText(entry.group_name)}</span>`
        : `<span style="color:var(--text-muted);margin-left:auto;font-size:0.75rem">${entry.changed_at ? new Date(entry.changed_at).toLocaleDateString() : '—'}</span>`;
      
      item.innerHTML = `
        <span style="color:var(--text-muted)">${escapeText(entry.old_name || '(unknown)')}</span>
        <span style="color:var(--accent)">→</span>
        <span style="font-weight:600">${escapeText(entry.user_name || 'Unknown')}</span>
        ${fedBadge}
        ${groupLabel}
      `;
      item.onmouseenter = () => item.style.background = 'var(--bg-hover)';
      item.onmouseleave = () => item.style.background = 'var(--bg-card)';
      item.onclick = () => openUserTimeline(entry.source_chat_id || chatId, entry.user_id, entry.user_name);
      listContainer.appendChild(item);
    });
  } catch (err) {
    console.error('Failed to load history:', err);
    listContainer.innerHTML = `
      <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);font-size:0.85rem">
        ${t('error', 'Failed to load history')}
      </div>
    `;
  }
}

async function renderStatsTab(container, chatId, isEnabled) {
  if (!isEnabled) {
    container.innerHTML = `
      <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);font-size:0.85rem">
        ${t('history_disabled', 'Enable tracking in Settings to see statistics')}
      </div>
    `;
    return;
  }

  container.innerHTML = `<div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);font-size:0.85rem">${t('loading', 'Loading...')}</div>`;

  try {
    const stats = await apiFetch(`/api/groups/${chatId}/name-history/stats`).catch(() => []);

    if (!stats || stats.length === 0) {
      container.innerHTML = `
        <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);font-size:0.85rem">
          No statistics available yet
        </div>
      `;
      return;
    }

    // Build leaderboard table
    const table = document.createElement('div');
    table.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);overflow:hidden;';
    
    // Header
    const header = document.createElement('div');
    header.style.cssText = 'display:grid;grid-template-columns:60px 1fr 80px 120px;gap:var(--sp-2);padding:var(--sp-3) var(--sp-4);background:var(--bg-elevated);font-weight:600;font-size:0.8rem;color:var(--text-muted);border-bottom:1px solid var(--border);';
    header.innerHTML = `
      <span>Rank</span>
      <span>User</span>
      <span style="text-align:center">Changes</span>
      <span style="text-align:right">Last Changed</span>
    `;
    table.appendChild(header);

    // Rows
    stats.forEach((entry, index) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:grid;grid-template-columns:60px 1fr 80px 120px;gap:var(--sp-2);padding:var(--sp-3) var(--sp-4);border-bottom:1px solid var(--border);font-size:0.85rem;align-items:center;cursor:pointer;';
      row.style.borderBottom = index < stats.length - 1 ? '1px solid var(--border)' : 'none';
      row.onmouseenter = () => row.style.background = 'var(--bg-hover)';
      row.onmouseleave = () => row.style.background = 'transparent';
      row.onclick = () => openUserTimeline(chatId, entry.user_id, entry.user_name);
      
      const rank = index + 1;
      const rankBadge = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`;
      
      row.innerHTML = `
        <span style="font-weight:700;color:${rank <= 3 ? 'var(--accent)' : 'var(--text-muted)'}">${rankBadge}</span>
        <span style="font-weight:500">${escapeText(entry.user_name || 'Unknown')}</span>
        <span style="text-align:center;font-weight:600;color:var(--accent)">${entry.change_count}</span>
        <span style="text-align:right;color:var(--text-muted);font-size:0.75rem">${entry.last_changed ? new Date(entry.last_changed).toLocaleDateString() : '—'}</span>
      `;
      table.appendChild(row);
    });

    container.innerHTML = '';
    container.appendChild(table);
  } catch (err) {
    console.error('Failed to load stats:', err);
    container.innerHTML = `
      <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);font-size:0.85rem">
        Failed to load statistics
      </div>
    `;
  }
}

async function renderSearchTab(container, chatId, isEnabled) {
  if (!isEnabled) {
    container.innerHTML = `
      <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);font-size:0.85rem">
        ${t('history_disabled', 'Enable tracking in Settings to search name history')}
      </div>
    `;
    return;
  }

  const searchSection = document.createElement('div');
  searchSection.style.cssText = 'display:flex;gap:var(--sp-2);margin-bottom:var(--sp-4);';
  searchSection.innerHTML = `
    <input type="text" id="history-search-input" class="input" placeholder="Search by old name or username..." style="flex:1;">
    <button id="history-search-btn" class="btn btn-primary">Search</button>
  `;
  container.appendChild(searchSection);

  const resultsContainer = document.createElement('div');
  resultsContainer.id = 'search-results';
  resultsContainer.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';
  container.appendChild(resultsContainer);

  const doSearch = async () => {
    const query = searchSection.querySelector('#history-search-input').value.trim();
    if (!query || query.length < 2) {
      showToast('Enter at least 2 characters', 'error');
      return;
    }

    resultsContainer.innerHTML = `<div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);">Searching...</div>`;

    try {
      const results = await apiFetch(`/api/groups/${chatId}/name-history/search?q=${encodeURIComponent(query)}`).catch(() => []);

      if (!results || results.length === 0) {
        resultsContainer.innerHTML = `
          <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);">
            No results found for "${escapeText(query)}"
          </div>
        `;
        return;
      }

      resultsContainer.innerHTML = '';
      results.forEach(r => {
        const card = document.createElement('div');
        card.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-3);';
        card.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div style="font-weight:600">${escapeText(r.current_name)}</div>
              <div style="font-size:0.8rem;color:var(--text-muted);">
                Matched ${r.matched_field}: <code>${escapeText(r.matched_value)}</code>
              </div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:0.75rem;color:var(--text-muted);">${new Date(r.changed_at).toLocaleDateString()}</div>
              <button class="open-profile-btn" style="margin-top:var(--sp-1);padding:var(--sp-1) var(--sp-2);background:var(--accent);color:#000;border:none;border-radius:var(--r-sm);font-size:0.75rem;cursor:pointer;">Open Profile</button>
            </div>
          </div>
        `;
        card.querySelector('.open-profile-btn').onclick = () => {
          // Navigate to moderation page with user search
          window.navigateToPage('moderation');
          // Store the user_id to search for (moderation page can check this)
          sessionStorage.setItem('moderation_search_user_id', r.user_id);
        };
        resultsContainer.appendChild(card);
      });
    } catch (err) {
      console.error('Search failed:', err);
      resultsContainer.innerHTML = `
        <div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);">Search failed</div>
      `;
    }
  };

  searchSection.querySelector('#history-search-btn').onclick = doSearch;
  searchSection.querySelector('#history-search-input').onkeypress = (e) => {
    if (e.key === 'Enter') doSearch();
  };
}

async function renderSettingsTab(container, chatId, currentEnabled, currentLimit, currentRetention, alertEnabled, alertThreshold, federationSync, trackPhotos) {
  const section = document.createElement('div');
  section.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-4);';
  section.innerHTML = `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);">
      <div style="font-weight:600;margin-bottom:var(--sp-4)">${t('settings', 'Tracking Settings')}</div>
      
      <div class="toggle-row" style="display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) 0;">
        <span>${t('enable_label', 'Track Name Changes')}</span>
        <div id="history-toggle-wrapper"></div>
      </div>

      <div class="toggle-row" style="display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) 0;margin-top:var(--sp-2);">
        <span>Track Profile Photo Changes</span>
        <div id="photo-toggle-wrapper"></div>
      </div>

      <div style="margin-top:var(--sp-4)">
        <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
          ${t('history_limit', 'History Limit (displayed entries)')}
        </label>
        <input type="number" class="input" id="history-limit" value="${currentLimit}" min="1" max="50">
      </div>

      <div style="margin-top:var(--sp-4)">
        <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
          Retention Period (auto-purge old history)
        </label>
        <select class="input" id="history-retention">
          <option value="0" ${currentRetention === 0 ? 'selected' : ''}>Never purge</option>
          <option value="30" ${currentRetention === 30 ? 'selected' : ''}>30 days</option>
          <option value="90" ${currentRetention === 90 ? 'selected' : ''}>90 days</option>
          <option value="180" ${currentRetention === 180 ? 'selected' : ''}>6 months</option>
          <option value="365" ${currentRetention === 365 ? 'selected' : ''}>1 year</option>
        </select>
      </div>

      <button class="btn btn-primary" style="margin-top:var(--sp-4);width:100%" id="save-history">
        ${t('save_btn', 'Save Settings')}
      </button>
    </div>

    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);">
      <div style="font-weight:600;margin-bottom:var(--sp-4)">Real-time Alerts</div>
      
      <div class="toggle-row" style="display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) 0;">
        <span>Alert in group on name change</span>
        <div id="alert-toggle-wrapper"></div>
      </div>

      <div style="margin-top:var(--sp-4)">
        <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:var(--sp-2)">
          Minimum changes to alert
        </label>
        <input type="number" class="input" id="alert-threshold" value="${alertThreshold}" min="1" max="100">
        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:var(--sp-1)">
          Only alert after user has changed names this many times
        </div>
      </div>
    </div>

    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);">
      <div style="font-weight:600;margin-bottom:var(--sp-4)">Federation Settings</div>
      
      <div class="toggle-row" style="display:flex;align-items:center;justify-content:space-between;padding:var(--sp-2) 0;">
        <span>Sync name history across federation</span>
        <div id="federation-toggle-wrapper"></div>
      </div>
      
      <div style="font-size:0.75rem;color:var(--text-muted);margin-top:var(--sp-2)">
        Share name history with all groups in your federation
      </div>
    </div>
  `;
  container.appendChild(section);

  // Toggles
  let enabled = currentEnabled;
  let alertsEnabled = alertEnabled;
  let federationEnabled = federationSync;
  let photosEnabled = trackPhotos;
  
  section.querySelector('#history-toggle-wrapper').appendChild(Toggle({
    checked: currentEnabled,
    onChange: (val) => { enabled = val; }
  }));
  
  section.querySelector('#alert-toggle-wrapper').appendChild(Toggle({
    checked: alertEnabled,
    onChange: (val) => { alertsEnabled = val; }
  }));

  section.querySelector('#federation-toggle-wrapper').appendChild(Toggle({
    checked: federationSync,
    onChange: (val) => { federationEnabled = val; }
  }));

  section.querySelector('#photo-toggle-wrapper').appendChild(Toggle({
    checked: trackPhotos,
    onChange: (val) => { photosEnabled = val; }
  }));

  // Save tracking settings (now includes all settings in one call)
  section.querySelector('#save-history').onclick = async () => {
    const limit = parseInt(section.querySelector('#history-limit').value);
    const retention = parseInt(section.querySelector('#history-retention').value);
    const threshold = parseInt(section.querySelector('#alert-threshold').value);

    try {
      showToast(t('loading', 'Saving...'));
      await apiFetch(`/api/groups/${chatId}/name-history`, {
        method: 'POST',
        body: { 
          enabled, 
          limit, 
          retention_days: retention,
          alert_enabled: alertsEnabled,
          alert_threshold: threshold,
          federation_sync: federationEnabled,
          track_photos: photosEnabled
        }
      });
      showToast(t('toast_save_success', 'Saved successfully!'));
    } catch (err) {
      console.error('Failed to save history settings:', err);
      showToast(t('error', 'Failed to save'));
    }
  };
}

async function exportHistoryCSV(chatId) {
  try {
    showToast('Fetching data...');
    const data = await apiFetch(`/api/groups/${chatId}/name-history/export`).catch(() => []);
    
    if (!data || data.length === 0) {
      showToast('No data to export', 'error');
      return;
    }

    // Confirm if large dataset
    if (data.length > 500) {
      if (!confirm(`Export ${data.length} records? This may take a moment.`)) {
        return;
      }
    }

    // Convert to CSV
    const headers = ['user_id', 'old_name', 'new_name', 'old_username', 'new_username', 'changed_at'];
    const csvRows = [headers.join(',')];
    
    data.forEach(row => {
      const values = [
        row.user_id,
        `"${(row.old_name || '').replace(/"/g, '""')}"`,
        `"${(row.new_name || '').replace(/"/g, '""')}"`,
        row.old_username || '',
        row.new_username || '',
        row.changed_at || ''
      ];
      csvRows.push(values.join(','));
    });
    
    const csvContent = csvRows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    
    const date = new Date().toISOString().split('T')[0];
    const filename = `name_history_${chatId}_${date}.csv`;
    
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast(`Exported ${data.length} records`, 'success');
  } catch (err) {
    console.error('Export failed:', err);
    showToast('Export failed', 'error');
  }
}

function openUserTimeline(chatId, userId, userName) {
  // Create slide-in panel
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;z-index:2000;background:rgba(0,0,0,0.5);';
  
  const panel = document.createElement('div');
  panel.style.cssText = 'position:fixed;top:0;right:0;bottom:0;width:100%;max-width:360px;background:var(--bg-elevated);border-left:1px solid var(--border);z-index:2001;display:flex;flex-direction:column;';
  
  panel.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;padding:var(--sp-4);border-bottom:1px solid var(--border);">
      <div style="font-weight:600;">${escapeText(userName || 'Unknown')}</div>
      <button id="close-timeline" style="background:none;border:none;color:var(--text-muted);font-size:20px;cursor:pointer;">✕</button>
    </div>
    <div id="timeline-content" style="flex:1;overflow-y:auto;padding:var(--sp-4);">
      <div style="text-align:center;color:var(--text-muted);">Loading...</div>
    </div>
  `;
  
  document.body.appendChild(overlay);
  document.body.appendChild(panel);
  
  const close = () => {
    overlay.remove();
    panel.remove();
  };
  
  overlay.onclick = close;
  panel.querySelector('#close-timeline').onclick = close;
  
  // Load timeline
  loadTimeline(chatId, userId, panel.querySelector('#timeline-content'));
}

async function loadTimeline(chatId, userId, container) {
  try {
    const timeline = await apiFetch(`/api/groups/${chatId}/name-history/user/${userId}`).catch(() => []);
    
    if (!timeline || timeline.length === 0) {
      container.innerHTML = `<div style="text-align:center;color:var(--text-muted);">No history found</div>`;
      return;
    }
    
    container.innerHTML = '';
    
    // Timeline wrapper
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'position:relative;padding-left:30px;';
    
    // Vertical line
    const line = document.createElement('div');
    line.style.cssText = 'position:absolute;left:10px;top:0;bottom:0;width:2px;background:var(--border);';
    wrapper.appendChild(line);
    
    timeline.forEach((entry, index) => {
      const node = document.createElement('div');
      node.style.cssText = 'position:relative;margin-bottom:var(--sp-4);';
      
      // Dot color based on change type
      const dotColor = entry.change_type === 'username' ? 'var(--accent)' : 
                       entry.change_type === 'name' ? '#4CAF50' : '#FF9800';
      
      node.innerHTML = `
        <div style="position:absolute;left:-24px;top:4px;width:12px;height:12px;border-radius:50%;background:${dotColor};border:2px solid var(--bg-elevated);"></div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:var(--sp-1);">${new Date(entry.changed_at).toLocaleDateString()}</div>
        <div style="font-size:0.85rem;">
          <div style="color:var(--text-muted);text-decoration:line-through;">${escapeText(entry.old_name)}</div>
          <div style="color:var(--text-primary);font-weight:500;">${escapeText(entry.new_name)}</div>
        </div>
      `;
      wrapper.appendChild(node);
    });
    
    container.appendChild(wrapper);
  } catch (err) {
    console.error('Failed to load timeline:', err);
    container.innerHTML = `<div style="text-align:center;color:var(--text-muted);">Failed to load timeline</div>`;
  }
}

function escapeText(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}
