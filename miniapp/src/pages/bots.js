
import { Card, Badge, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

const store = useStore;

export async function renderBotsPage(container) {
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  const header = document.createElement('div');
  header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-4);';
  header.innerHTML = `
    <div>
      <h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">🤖 My Bots</h2>
      <p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">Manage your bot instances</p>
    </div>
    <button id="add-clone-btn" class="btn btn-primary" style="font-size:var(--text-sm);">+ Add Clone Bot</button>
  `;
  container.appendChild(header);

  const addClonePanel = document.createElement('div');
  addClonePanel.id = 'add-clone-panel';
  addClonePanel.style.cssText = 'display:none;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);margin-bottom:var(--sp-4);';
  addClonePanel.innerHTML = `
    <h3 style="font-size:var(--text-sm);font-weight:var(--fw-semibold);margin:0 0 var(--sp-3);">Add Clone Bot</h3>
    <p style="font-size:var(--text-xs);color:var(--text-muted);margin:0 0 var(--sp-3);">Paste the bot token from @BotFather</p>
    <div style="display:flex;gap:var(--sp-2);">
      <input type="text" id="clone-token-input" class="input" placeholder="1234567890:ABC..." style="flex:1;font-family:monospace;font-size:var(--text-xs);">
      <button id="clone-submit-btn" class="btn btn-primary" style="white-space:nowrap;">Add Bot</button>
      <button id="clone-cancel-btn" class="btn btn-secondary">Cancel</button>
    </div>
    <div id="clone-error" style="display:none;color:var(--danger);font-size:var(--text-xs);margin-top:var(--sp-2);"></div>
  `;
  container.appendChild(addClonePanel);

  header.querySelector('#add-clone-btn').addEventListener('click', () => {
    addClonePanel.style.display = addClonePanel.style.display === 'none' ? 'block' : 'none';
  });

  addClonePanel.querySelector('#clone-cancel-btn').addEventListener('click', () => {
    addClonePanel.style.display = 'none';
    addClonePanel.querySelector('#clone-token-input').value = '';
  });

  addClonePanel.querySelector('#clone-submit-btn').addEventListener('click', async () => {
    const token = addClonePanel.querySelector('#clone-token-input').value.trim();
    const errDiv = addClonePanel.querySelector('#clone-error');
    errDiv.style.display = 'none';
    if (!token) { errDiv.textContent = 'Token is required'; errDiv.style.display = 'block'; return; }
    const btn = addClonePanel.querySelector('#clone-submit-btn');
    btn.textContent = '⏳ Adding...';
    btn.disabled = true;
    try {
      const result = await apiFetch('/api/bots/clone', { method: 'POST', body: { token } });
      showToast(`Bot @${result.username} added successfully!`, 'success');
      addClonePanel.style.display = 'none';
      addClonePanel.querySelector('#clone-token-input').value = '';
      await renderBotsPage(container);
    } catch (e) {
      errDiv.textContent = e.message || 'Failed to add bot';
      errDiv.style.display = 'block';
    } finally {
      btn.textContent = 'Add Bot';
      btn.disabled = false;
    }
  });

  const listContainer = document.createElement('div');
  listContainer.innerHTML = `<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading bots...</div>`;
  container.appendChild(listContainer);

  try {
    // Fetch bots first, then usage (sequential to ensure usage reflects latest state after bot operations)
    const bots = await apiFetch('/api/bots');
    const usage = await apiFetch('/api/me/usage').catch(() => null);

    listContainer.innerHTML = '';

    if (!bots || bots.length === 0) {
      listContainer.appendChild(EmptyState({
        icon: '🤖',
        title: 'No bots found',
        description: 'Add your first clone bot using the button above.'
      }));
    } else {
      const grid = document.createElement('div');
      grid.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-3);';

      bots.forEach(bot => {
        const isDead = bot.status === 'dead';
        const isPrimary = bot.is_primary;
        const statusColor = bot.status === 'active' ? 'var(--success)' : bot.status === 'dead' ? 'var(--danger)' : 'var(--warning)';
        const statusDot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${statusColor};margin-right:4px;"></span>`;

        const card = document.createElement('div');
        card.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);';
        card.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:var(--sp-3);">
            <div>
              <div style="display:flex;align-items:center;gap:var(--sp-2);">
                <span style="font-size:var(--text-sm);font-weight:var(--fw-semibold);">${bot.display_name || bot.first_name || 'Bot'}</span>
                ${isPrimary ? '<span style="font-size:var(--text-xs);background:rgba(var(--accent-rgb),0.15);color:var(--accent);padding:2px 8px;border-radius:var(--r-full);">👑 Primary</span>' : ''}
              </div>
              <div style="font-size:var(--text-xs);color:var(--text-muted);">@${bot.username || 'unknown'}</div>
            </div>
            <div style="font-size:var(--text-xs);display:flex;align-items:center;">${statusDot}${bot.status || 'unknown'}</div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-2);font-size:var(--text-xs);margin-bottom:var(--sp-3);">
            <div style="background:var(--bg-input);padding:var(--sp-2);border-radius:var(--r-lg);">
              <div style="color:var(--text-muted);">Groups</div>
              <div style="font-weight:var(--fw-semibold);">${bot.groups_count || 0} / ${bot.group_limit === 0 ? '∞' : (bot.group_limit || 1)}</div>
            </div>
            <div style="background:var(--bg-input);padding:var(--sp-2);border-radius:var(--r-lg);">
              <div style="color:var(--text-muted);">Bot ID</div>
              <div style="font-weight:var(--fw-semibold);font-family:monospace;">${bot.bot_id || bot.id || '—'}</div>
            </div>
          </div>
          <div id="reauth-panel-${bot.bot_id || bot.id}" style="display:none;margin-bottom:var(--sp-3);">
            <input type="text" class="input reauth-input" placeholder="New bot token from @BotFather" style="font-family:monospace;font-size:var(--text-xs);margin-bottom:var(--sp-2);">
            <div style="display:flex;gap:var(--sp-2);">
              <button class="btn btn-primary reauth-confirm" style="font-size:var(--text-xs);">Verify & Update</button>
              <button class="btn btn-secondary reauth-cancel" style="font-size:var(--text-xs);">Cancel</button>
            </div>
            <div class="reauth-error" style="display:none;color:var(--danger);font-size:var(--text-xs);margin-top:var(--sp-2);"></div>
          </div>
          <div style="display:flex;gap:var(--sp-2);">
            ${isDead ? `<button class="btn btn-danger" data-action="reauth" data-botid="${bot.bot_id || bot.id}" style="font-size:var(--text-xs);">🔑 Reauth</button>` : ''}
            ${!isPrimary ? `<button class="btn btn-secondary" data-action="delete" data-botid="${bot.bot_id || bot.id}" data-botname="@${bot.username}" style="font-size:var(--text-xs);">🗑️ Delete</button>` : ''}
          </div>
        `;

        const reauthPanel = card.querySelector(`#reauth-panel-${bot.bot_id || bot.id}`);
        const reauthBtn = card.querySelector('[data-action="reauth"]');
        const deleteBtn = card.querySelector('[data-action="delete"]');

        if (reauthBtn && reauthPanel) {
          reauthBtn.addEventListener('click', () => {
            reauthPanel.style.display = reauthPanel.style.display === 'none' ? 'block' : 'none';
          });
          reauthPanel.querySelector('.reauth-cancel').addEventListener('click', () => {
            reauthPanel.style.display = 'none';
          });
          reauthPanel.querySelector('.reauth-confirm').addEventListener('click', async () => {
            const newToken = reauthPanel.querySelector('.reauth-input').value.trim();
            const errEl = reauthPanel.querySelector('.reauth-error');
            errEl.style.display = 'none';
            if (!newToken) { errEl.textContent = 'Token is required'; errEl.style.display = 'block'; return; }
            const confirmBtn = reauthPanel.querySelector('.reauth-confirm');
            confirmBtn.textContent = '⏳ Verifying...';
            confirmBtn.disabled = true;
            try {
              await apiFetch(`/api/bots/${bot.bot_id || bot.id}/reauth`, { method: 'POST', body: { token: newToken } });
              showToast('Bot re-authenticated successfully!', 'success');
              await renderBotsPage(container);
            } catch (e) {
              errEl.textContent = e.message || 'Reauth failed';
              errEl.style.display = 'block';
              confirmBtn.textContent = 'Verify & Update';
              confirmBtn.disabled = false;
            }
          });
        }

        if (deleteBtn) {
          deleteBtn.addEventListener('click', async () => {
            const botName = deleteBtn.dataset.botname;
            if (!confirm(`Delete bot ${botName}? This cannot be undone.`)) return;
            try {
              await apiFetch(`/api/bots/${bot.bot_id || bot.id}`, { method: 'DELETE' });
              showToast('Bot deleted', 'success');
              await renderBotsPage(container);
            } catch (e) {
              showToast('Failed to delete: ' + e.message, 'error');
            }
          });
        }

        // Add Groups button for all bots (to see all groups where bot is active)
        const botId = bot.bot_id || bot.id;

        const groupsBtn = document.createElement('button');
        groupsBtn.textContent = `👥 View Groups (${bot.groups_count || 0})`;
        groupsBtn.style.cssText = 'margin-top:var(--sp-2);padding:var(--sp-2) var(--sp-3);background:var(--bg-input);border:1px solid var(--border);border-radius:var(--r-lg);cursor:pointer;font-size:var(--text-xs);width:100%;';

        const groupsPanel = document.createElement('div');
        groupsPanel.style.cssText = 'display:none;margin-top:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);padding:var(--sp-3);max-height:300px;overflow-y:auto;';
        groupsPanel.innerHTML = '<div style="text-align:center;padding:var(--sp-2);color:var(--text-muted);font-size:var(--text-xs);">Loading groups...</div>';

        groupsBtn.addEventListener('click', async () => {
          if (groupsPanel.style.display === 'none') {
            groupsPanel.style.display = 'block';
            // Load groups
            try {
              const groups = await apiFetch(`/api/bots/${botId}/groups`);
              if (!groups || groups.length === 0) {
                groupsPanel.innerHTML = '<div style="text-align:center;padding:var(--sp-4);color:var(--text-muted);font-size:var(--text-xs);">No active groups</div>';
              } else {
                groupsPanel.innerHTML = groups.map(g => `
                  <div style="display:flex;justify-content:space-between;align-items:center;padding:var(--sp-2);border-bottom:1px solid var(--border);font-size:var(--text-xs);">
                    <div style="flex:1;min-width:0;">
                      <div style="font-weight:var(--fw-medium);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${g.chat_title || 'Unknown'}</div>
                      <div style="color:var(--text-muted);font-size:10px;">ID: ${g.chat_id}</div>
                    </div>
                    <div style="display:flex;gap:var(--sp-1);">
                      ${g.is_owner_group ? '<span style="background:var(--accent-dim);color:var(--accent);padding:2px 6px;border-radius:var(--r-full);font-size:10px;">Owner</span>' : ''}
                      ${g.access_status === 'pending' ? '<span style="background:var(--warning-dim);color:var(--warning);padding:2px 6px;border-radius:var(--r-full);font-size:10px;">Pending</span>' : ''}
                    </div>
                  </div>
                `).join('');
              }
            } catch (e) {
              groupsPanel.innerHTML = `<div style="text-align:center;padding:var(--sp-2);color:var(--danger);font-size:var(--text-xs);">Failed to load groups</div>`;
            }
          } else {
            groupsPanel.style.display = 'none';
          }
        });

        card.appendChild(groupsBtn);
        card.appendChild(groupsPanel);

        if (!isPrimary) {
          const settingsBtn = document.createElement('button');
          settingsBtn.textContent = '⚙️ Bot Settings';
          settingsBtn.style.cssText = 'margin-top:var(--sp-2);padding:var(--sp-2) var(--sp-3);background:var(--bg-input);border:1px solid var(--border);border-radius:var(--r-lg);cursor:pointer;font-size:var(--text-xs);';

          const settingsPanel = document.createElement('div');
          settingsPanel.style.cssText = 'display:none;margin-top:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);padding:var(--sp-3);';
          settingsPanel.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
              <span style="font-size:var(--text-xs);">Group Limit (0 = unlimited)</span>
              <input type="number" id="gl-${botId}" min="0" max="100" value="${bot.group_limit || 1}"
                style="width:4rem;padding:4px;border:1px solid var(--border);border-radius:4px;background:var(--bg-card);color:var(--text-primary);text-align:center;font-size:var(--text-xs);">
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
              <span style="font-size:var(--text-xs);">Access Policy</span>
              <select id="ap-${botId}" style="padding:4px 8px;border:1px solid var(--border);border-radius:4px;background:var(--bg-card);color:var(--text-primary);font-size:var(--text-xs);">
                <option value="open" ${bot.group_access_policy === 'open' ? 'selected' : ''}>Open (anyone)</option>
                <option value="approval" ${bot.group_access_policy === 'approval' ? 'selected' : ''}>Approval required</option>
                <option value="blocked" ${bot.group_access_policy === 'blocked' ? 'selected' : ''}>Blocked</option>
              </select>
            </div>
            <button id="save-cfg-${botId}" style="width:100%;padding:var(--sp-2);background:var(--accent);color:#000;border:none;border-radius:4px;cursor:pointer;font-size:var(--text-xs);font-weight:var(--fw-medium);">Save</button>
          `;

          settingsBtn.addEventListener('click', () => {
            settingsPanel.style.display = settingsPanel.style.display === 'none' ? 'block' : 'none';
          });

          settingsPanel.querySelector(`#save-cfg-${botId}`).addEventListener('click', async () => {
            const limit = parseInt(settingsPanel.querySelector(`#gl-${botId}`).value) || 0;
            const policy = settingsPanel.querySelector(`#ap-${botId}`).value;
            try {
              await apiFetch(`/api/bots/${botId}/config`, {
                method: 'PUT',
                body: { group_limit: limit, group_access_policy: policy },
              });
              showToast('Settings saved', 'success');
            } catch (e) {
              showToast('Failed: ' + e.message, 'error');
            }
          });

          card.appendChild(settingsBtn);
          card.appendChild(settingsPanel);
        }

        grid.appendChild(card);
      });

      listContainer.appendChild(grid);
    }

    if (usage) {
      const usageCard = document.createElement('div');
      usageCard.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-4);margin-top:var(--sp-4);';
      
      // Clone bots: use clone_count (non-primary only) vs plan_limit_bots
      const cloneCount = usage.clone_count ?? (usage.bots_count - 1);
      const botsPercent = usage.plan_limit_bots > 0
        ? Math.min(100, (cloneCount / usage.plan_limit_bots) * 100) : 0;
      const botsIsOverLimit = cloneCount > usage.plan_limit_bots;
      
      // Groups: handle unlimited (0) - show ∞, hide progress bar
      const groupsTotal = usage.plan_limit_groups;
      const groupsDisplay = groupsTotal === 0 ? '∞' : String(groupsTotal);
      const groupsPercent = groupsTotal > 0
        ? Math.min(100, (usage.groups_count / groupsTotal) * 100) : 0;
      const groupsIsOverLimit = groupsTotal > 0 && usage.groups_count > groupsTotal;
      
      usageCard.innerHTML = `
        <div style="font-size:var(--text-sm);font-weight:var(--fw-semibold);margin-bottom:var(--sp-3);">📊 Plan Usage — ${usage.plan_name}</div>
        <div style="margin-bottom:var(--sp-3);">
          <div style="display:flex;justify-content:space-between;font-size:var(--text-xs);margin-bottom:4px;">
            <span>Clone Bots</span><span>${cloneCount} / ${usage.plan_limit_bots}</span>
          </div>
          <div style="height:6px;background:var(--bg-input);border-radius:var(--r-full);overflow:hidden;">
            <div style="width:${botsPercent}%;height:100%;background:${botsIsOverLimit ? 'var(--danger)' : (botsPercent >= 80 ? 'var(--warning)' : 'var(--accent)')};border-radius:var(--r-full);transition:width .3s;"></div>
          </div>
        </div>
        <div>
          <div style="display:flex;justify-content:space-between;font-size:var(--text-xs);margin-bottom:4px;">
            <span>Groups${groupsTotal === 0 ? ' <span style="color:var(--text-muted);font-size:0.9em;">(Primary bot: unlimited)</span>' : ''}</span><span>${usage.groups_count} / ${groupsDisplay}</span>
          </div>
          ${groupsTotal > 0 ? `
          <div style="height:6px;background:var(--bg-input);border-radius:var(--r-full);overflow:hidden;">
            <div style="width:${groupsPercent}%;height:100%;background:${groupsIsOverLimit ? 'var(--danger)' : (groupsPercent >= 80 ? 'var(--warning)' : 'var(--accent)')};border-radius:var(--r-full);transition:width .3s;"></div>
          </div>
          ` : ''}
        </div>
      `;
      container.appendChild(usageCard);
    }
  } catch (error) {
    listContainer.innerHTML = '';
    listContainer.appendChild(EmptyState({
      icon: '⚠️',
      title: 'Failed to load bots',
      description: error.message
    }));
  }
}
