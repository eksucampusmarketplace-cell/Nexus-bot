/**
 * miniapp/src/pages/custom_commands.js
 *
 * Custom Commands Builder — visual no-code command creation.
 * Tabs: Commands | Create | Variables
 */

import { Card, EmptyState, Toggle, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { t } from '../../lib/i18n.js?v=1.6.0';

const store = useStore;
const getState = store.getState;

const TRIGGER_TYPES = [
  { value: 'command', label: '/command' },
  { value: 'keyword', label: 'Keyword match' },
  { value: 'regex', label: 'Regex pattern' },
  { value: 'exact', label: 'Exact match' },
];

const ACTION_TYPES = [
  { value: 'reply', label: 'Send reply' },
  { value: 'delete', label: 'Delete message' },
  { value: 'react', label: 'Add reaction' },
  { value: 'warn', label: 'Warn user' },
  { value: 'mute', label: 'Mute user' },
  { value: 'kick', label: 'Kick user' },
  { value: 'ban', label: 'Ban user' },
  { value: 'pin', label: 'Pin message' },
  { value: 'set_variable', label: 'Set variable' },
];

const BUILTIN_VARS = [
  '{user.name}', '{user.username}', '{user.id}', '{user.mention}',
  '{group.name}', '{group.id}', '{group.member_count}',
  '{bot.name}', '{bot.username}',
  '{time}', '{date}', '{datetime}', '{random}', '{newline}',
];

export async function renderCustomCommandsPage(container) {
  const chatId = getState().activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding:var(--sp-4);max-width:var(--content-max);margin:0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '\u2699\uFE0F',
      title: 'Select a group',
      description: 'Choose a group to manage custom commands.'
    }));
    return;
  }

  const header = document.createElement('div');
  header.style.cssText = 'margin-bottom:var(--sp-4);';
  header.innerHTML = `
    <h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">Custom Commands</h2>
    <p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">Build custom bot commands with triggers, conditions, and actions</p>
  `;
  container.appendChild(header);

  // Tab bar
  const tabs = ['Commands', 'Create', 'Variables'];
  const tabBar = document.createElement('div');
  tabBar.style.cssText = 'display:flex;gap:var(--sp-1);margin-bottom:var(--sp-4);background:var(--bg-input);padding:4px;border-radius:var(--r-xl);';
  tabs.forEach((label, i) => {
    const btn = document.createElement('button');
    btn.textContent = label;
    btn.dataset.tab = label.toLowerCase();
    btn.style.cssText = `flex:1;padding:var(--sp-2) var(--sp-3);border:none;border-radius:var(--r-lg);font-size:var(--text-sm);font-weight:var(--fw-medium);cursor:pointer;transition:all var(--dur-fast);background:${i===0?'var(--bg-card)':'transparent'};color:${i===0?'var(--text-primary)':'var(--text-muted)'};`;
    btn.onclick = () => _switchTab(label.toLowerCase(), content, chatId, tabBar);
    tabBar.appendChild(btn);
  });
  container.appendChild(tabBar);

  const content = document.createElement('div');
  container.appendChild(content);

  await _switchTab('commands', content, chatId, tabBar);
}

function _switchTab(tab, container, chatId, tabBar) {
  tabBar.querySelectorAll('[data-tab]').forEach(btn => {
    const active = btn.dataset.tab === tab;
    btn.style.background = active ? 'var(--bg-card)' : 'transparent';
    btn.style.color = active ? 'var(--text-primary)' : 'var(--text-muted)';
  });
  container.innerHTML = '';
  switch (tab) {
    case 'commands':  return _renderCommandsList(container, chatId, tabBar);
    case 'create':    return _renderCreateForm(container, chatId, tabBar);
    case 'variables': return _renderVariablesTab(container, chatId);
  }
}

// ── Commands List ─────────────────────────────────────────────────────────

async function _renderCommandsList(container, chatId, tabBar) {
  container.innerHTML = '<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading commands...</div>';

  let commands = [];
  try {
    const resp = await apiFetch(`/api/groups/${chatId}/custom-commands`);
    commands = resp.commands || [];
  } catch (_) {}

  container.innerHTML = '';

  if (commands.length === 0) {
    const empty = EmptyState({
      icon: '\u2699\uFE0F',
      title: 'No custom commands yet',
      description: 'Create your first custom command using the Create tab.'
    });
    container.appendChild(empty);
    return;
  }

  const list = document.createElement('div');
  list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-3);';

  commands.forEach(cmd => {
    const card = document.createElement('div');
    card.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-3);';

    const triggers = (cmd.triggers || []).map(t => {
      if (t.trigger_type === 'command') return '/' + t.trigger_value;
      if (t.trigger_type === 'keyword') return '"' + t.trigger_value + '"';
      return t.trigger_value;
    }).join(', ') || 'No triggers';

    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-2);">
        <div>
          <span style="font-weight:var(--fw-bold);font-size:var(--text-sm);">${_escHtml(cmd.name)}</span>
          <span style="font-size:var(--text-xs);color:var(--text-muted);margin-left:var(--sp-2);">${cmd.trigger_count || 0} triggers, ${cmd.action_count || 0} actions</span>
        </div>
        <div style="display:flex;align-items:center;gap:var(--sp-2);">
          <span style="font-size:var(--text-xs);color:var(--text-muted);">x${cmd.execution_count || 0}</span>
        </div>
      </div>
      <div style="font-size:var(--text-xs);color:var(--text-secondary);margin-bottom:var(--sp-2);">${_escHtml(cmd.description || '')}</div>
      <div style="font-size:var(--text-xs);color:var(--text-muted);">Triggers: ${_escHtml(triggers)}</div>
      <div style="display:flex;gap:var(--sp-2);margin-top:var(--sp-2);">
        <button class="btn btn-secondary cmd-edit-btn" data-id="${cmd.id}" style="font-size:var(--text-xs);padding:var(--sp-1) var(--sp-2);">Edit</button>
        <button class="btn btn-danger cmd-del-btn" data-id="${cmd.id}" style="font-size:var(--text-xs);padding:var(--sp-1) var(--sp-2);">Delete</button>
      </div>
    `;

    // Toggle enabled
    const toggleWrap = document.createElement('div');
    toggleWrap.style.cssText = 'position:absolute;top:var(--sp-3);right:var(--sp-3);';
    const tog = Toggle({
      checked: cmd.enabled !== false,
      onChange: async (v) => {
        try {
          await apiFetch(`/api/groups/${chatId}/custom-commands/${cmd.id}`, {
            method: 'PUT', body: JSON.stringify({ enabled: v })
          });
          showToast(v ? 'Enabled' : 'Disabled', 'success');
        } catch (e) { showToast('Failed', 'error'); }
      }
    });
    card.style.position = 'relative';
    toggleWrap.appendChild(tog);
    card.appendChild(toggleWrap);

    // Delete handler
    card.querySelector('.cmd-del-btn').addEventListener('click', async () => {
      if (!confirm('Delete command "' + cmd.name + '"?')) return;
      try {
        await apiFetch(`/api/groups/${chatId}/custom-commands/${cmd.id}`, { method: 'DELETE' });
        showToast('Deleted', 'success');
        _renderCommandsList(container, chatId, tabBar);
      } catch (e) { showToast('Failed: ' + e.message, 'error'); }
    });

    // Edit handler
    card.querySelector('.cmd-edit-btn').addEventListener('click', () => {
      _renderEditForm(container, chatId, cmd, tabBar);
    });

    list.appendChild(card);
  });

  container.appendChild(list);
}

// ── Create Form ──────────────────────────────────────────────────────────

async function _renderCreateForm(container, chatId, tabBar) {
  container.innerHTML = '';

  const form = _buildCommandForm(null);
  container.appendChild(form.element);

  form.onSubmit(async (data) => {
    try {
      await apiFetch(`/api/groups/${chatId}/custom-commands`, {
        method: 'POST',
        body: JSON.stringify(data)
      });
      showToast('Command created!', 'success');
      _switchTab('commands', container, chatId, tabBar);
    } catch (e) {
      showToast('Failed: ' + (e.message || 'Unknown error'), 'error');
    }
  });
}

// ── Edit Form ───────────────────────────────────────────────────────────

async function _renderEditForm(container, chatId, cmd, tabBar) {
  container.innerHTML = '<div style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">Loading...</div>';

  let fullCmd = cmd;
  try {
    const resp = await apiFetch(`/api/groups/${chatId}/custom-commands/${cmd.id}`);
    fullCmd = resp.command || cmd;
  } catch (_) {}

  container.innerHTML = '';

  const backBtn = document.createElement('button');
  backBtn.className = 'btn btn-secondary';
  backBtn.style.cssText = 'margin-bottom:var(--sp-3);font-size:var(--text-xs);';
  backBtn.textContent = 'Back to list';
  backBtn.onclick = () => _switchTab('commands', container, chatId, tabBar);
  container.appendChild(backBtn);

  const form = _buildCommandForm(fullCmd);
  container.appendChild(form.element);

  form.onSubmit(async (data) => {
    try {
      // Update command metadata
      await apiFetch(`/api/groups/${chatId}/custom-commands/${cmd.id}`, {
        method: 'PUT',
        body: JSON.stringify({ name: data.name, description: data.description, cooldown_secs: data.cooldown_secs, priority: data.priority })
      });

      // Delete existing triggers and re-add
      for (const t of (fullCmd.triggers || [])) {
        await apiFetch(`/api/groups/${chatId}/custom-commands/${cmd.id}/triggers/${t.id}`, { method: 'DELETE' });
      }
      for (const t of (data.triggers || [])) {
        await apiFetch(`/api/groups/${chatId}/custom-commands/${cmd.id}/triggers`, {
          method: 'POST', body: JSON.stringify(t)
        });
      }

      // Delete existing actions and re-add
      for (const a of (fullCmd.actions || [])) {
        await apiFetch(`/api/groups/${chatId}/custom-commands/${cmd.id}/actions/${a.id}`, { method: 'DELETE' });
      }
      for (const a of (data.actions || [])) {
        await apiFetch(`/api/groups/${chatId}/custom-commands/${cmd.id}/actions`, {
          method: 'POST', body: JSON.stringify(a)
        });
      }

      showToast('Command updated!', 'success');
      _switchTab('commands', container, chatId, tabBar);
    } catch (e) {
      showToast('Failed: ' + (e.message || 'Unknown error'), 'error');
    }
  });
}

// ── Command Form Builder ────────────────────────────────────────────────

function _buildCommandForm(existingCmd) {
  const isEdit = !!existingCmd;
  const triggers = (existingCmd?.triggers || []).map(t => ({ ...t }));
  const actions = (existingCmd?.actions || []).map(a => ({ ...a }));
  let submitCb = null;

  const wrapper = document.createElement('div');
  wrapper.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-4);';

  // ── Basic Info ──
  const infoCard = Card({ title: isEdit ? 'Edit Command' : 'Create Command', subtitle: 'Define your custom command' });
  infoCard.innerHTML += `
    <div style="display:flex;flex-direction:column;gap:var(--sp-3);padding-top:var(--sp-2);">
      <div>
        <label style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:var(--sp-1);">Command Name</label>
        <input type="text" id="cc-name" class="input" placeholder="e.g. greet, faq, rules-reminder" value="${_escHtml(existingCmd?.name || '')}" style="width:100%;box-sizing:border-box;">
      </div>
      <div>
        <label style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:var(--sp-1);">Description</label>
        <input type="text" id="cc-desc" class="input" placeholder="What does this command do?" value="${_escHtml(existingCmd?.description || '')}" style="width:100%;box-sizing:border-box;">
      </div>
      <div style="display:flex;gap:var(--sp-3);">
        <div style="flex:1;">
          <label style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:var(--sp-1);">Cooldown (secs)</label>
          <input type="number" id="cc-cooldown" class="input" value="${existingCmd?.cooldown_secs || 0}" min="0" max="3600" style="width:100%;box-sizing:border-box;">
        </div>
        <div style="flex:1;">
          <label style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:var(--sp-1);">Priority</label>
          <input type="number" id="cc-priority" class="input" value="${existingCmd?.priority || 0}" min="0" max="100" style="width:100%;box-sizing:border-box;">
        </div>
      </div>
    </div>
  `;
  wrapper.appendChild(infoCard);

  // ── Triggers ──
  const triggersCard = Card({ title: 'Triggers', subtitle: 'What activates this command?' });
  const triggersContainer = document.createElement('div');
  triggersContainer.id = 'cc-triggers-list';
  triggersContainer.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);padding-top:var(--sp-2);';
  triggersCard.appendChild(triggersContainer);

  function renderTriggers() {
    triggersContainer.innerHTML = '';
    triggers.forEach((trig, i) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;gap:var(--sp-2);align-items:center;background:var(--bg-input);padding:var(--sp-2);border-radius:var(--r-lg);';
      const sel = document.createElement('select');
      sel.className = 'input';
      sel.style.cssText = 'flex:0 0 auto;width:auto;';
      TRIGGER_TYPES.forEach(tt => {
        const opt = document.createElement('option');
        opt.value = tt.value;
        opt.textContent = tt.label;
        opt.selected = tt.value === trig.trigger_type;
        sel.appendChild(opt);
      });
      sel.onchange = () => { trig.trigger_type = sel.value; };

      const inp = document.createElement('input');
      inp.type = 'text';
      inp.className = 'input';
      inp.style.cssText = 'flex:1;';
      inp.placeholder = trig.trigger_type === 'command' ? 'command name' : 'pattern or keyword';
      inp.value = trig.trigger_value || '';
      inp.oninput = () => { trig.trigger_value = inp.value; };

      const del = document.createElement('button');
      del.className = 'btn btn-danger';
      del.style.cssText = 'padding:var(--sp-1) var(--sp-2);font-size:var(--text-xs);flex-shrink:0;';
      del.textContent = 'X';
      del.onclick = () => { triggers.splice(i, 1); renderTriggers(); };

      row.appendChild(sel);
      row.appendChild(inp);
      row.appendChild(del);
      triggersContainer.appendChild(row);
    });
  }
  renderTriggers();

  const addTrigBtn = document.createElement('button');
  addTrigBtn.className = 'btn btn-secondary';
  addTrigBtn.style.cssText = 'margin-top:var(--sp-2);font-size:var(--text-xs);align-self:flex-start;';
  addTrigBtn.textContent = '+ Add Trigger';
  addTrigBtn.onclick = () => { triggers.push({ trigger_type: 'command', trigger_value: '' }); renderTriggers(); };
  triggersCard.appendChild(addTrigBtn);
  wrapper.appendChild(triggersCard);

  // ── Actions ──
  const actionsCard = Card({ title: 'Actions', subtitle: 'What happens when triggered?' });
  const actionsContainer = document.createElement('div');
  actionsContainer.id = 'cc-actions-list';
  actionsContainer.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);padding-top:var(--sp-2);';
  actionsCard.appendChild(actionsContainer);

  function renderActions() {
    actionsContainer.innerHTML = '';
    actions.forEach((act, i) => {
      const row = document.createElement('div');
      row.style.cssText = 'background:var(--bg-input);padding:var(--sp-2);border-radius:var(--r-lg);';

      const topRow = document.createElement('div');
      topRow.style.cssText = 'display:flex;gap:var(--sp-2);align-items:center;margin-bottom:var(--sp-2);';

      const sel = document.createElement('select');
      sel.className = 'input';
      sel.style.cssText = 'flex:0 0 auto;width:auto;';
      ACTION_TYPES.forEach(at => {
        const opt = document.createElement('option');
        opt.value = at.value;
        opt.textContent = at.label;
        opt.selected = at.value === act.action_type;
        sel.appendChild(opt);
      });
      sel.onchange = () => { act.action_type = sel.value; renderActions(); };

      const orderLabel = document.createElement('span');
      orderLabel.style.cssText = 'font-size:var(--text-xs);color:var(--text-muted);';
      orderLabel.textContent = '#' + (i + 1);

      const del = document.createElement('button');
      del.className = 'btn btn-danger';
      del.style.cssText = 'padding:var(--sp-1) var(--sp-2);font-size:var(--text-xs);margin-left:auto;flex-shrink:0;';
      del.textContent = 'X';
      del.onclick = () => { actions.splice(i, 1); renderActions(); };

      topRow.appendChild(orderLabel);
      topRow.appendChild(sel);
      topRow.appendChild(del);
      row.appendChild(topRow);

      // Action config based on type
      const config = act.action_config || {};
      if (act.action_type === 'reply') {
        const ta = document.createElement('textarea');
        ta.className = 'input';
        ta.style.cssText = 'width:100%;box-sizing:border-box;resize:vertical;min-height:60px;';
        ta.placeholder = 'Reply text (supports variables like {user.name})';
        ta.value = config.text || '';
        ta.oninput = () => { act.action_config = { ...config, text: ta.value }; };
        row.appendChild(ta);

        const varsHint = document.createElement('div');
        varsHint.style.cssText = 'font-size:9px;color:var(--text-muted);margin-top:4px;word-break:break-all;';
        varsHint.textContent = 'Variables: ' + BUILTIN_VARS.join(' ');
        row.appendChild(varsHint);
      } else if (act.action_type === 'react') {
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'input';
        inp.style.cssText = 'width:100%;box-sizing:border-box;';
        inp.placeholder = 'Emoji to react with';
        inp.value = config.emoji || '';
        inp.oninput = () => { act.action_config = { ...config, emoji: inp.value }; };
        row.appendChild(inp);
      } else if (act.action_type === 'warn') {
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'input';
        inp.style.cssText = 'width:100%;box-sizing:border-box;';
        inp.placeholder = 'Warn reason';
        inp.value = config.reason || '';
        inp.oninput = () => { act.action_config = { ...config, reason: inp.value }; };
        row.appendChild(inp);
      } else if (act.action_type === 'set_variable') {
        const varRow = document.createElement('div');
        varRow.style.cssText = 'display:flex;gap:var(--sp-2);';
        const nameInp = document.createElement('input');
        nameInp.type = 'text';
        nameInp.className = 'input';
        nameInp.style.cssText = 'flex:1;';
        nameInp.placeholder = 'Variable name';
        nameInp.value = config.var_name || '';
        nameInp.oninput = () => { act.action_config = { ...config, var_name: nameInp.value }; };
        const valInp = document.createElement('input');
        valInp.type = 'text';
        valInp.className = 'input';
        valInp.style.cssText = 'flex:1;';
        valInp.placeholder = 'Value';
        valInp.value = config.var_value || '';
        valInp.oninput = () => { act.action_config = { ...config, var_value: valInp.value }; };
        varRow.appendChild(nameInp);
        varRow.appendChild(valInp);
        row.appendChild(varRow);
      }

      // Delay field
      const delayRow = document.createElement('div');
      delayRow.style.cssText = 'display:flex;align-items:center;gap:var(--sp-2);margin-top:var(--sp-2);';
      const delayLabel = document.createElement('span');
      delayLabel.style.cssText = 'font-size:var(--text-xs);color:var(--text-muted);';
      delayLabel.textContent = 'Delay (sec):';
      const delayInp = document.createElement('input');
      delayInp.type = 'number';
      delayInp.className = 'input';
      delayInp.style.cssText = 'width:60px;';
      delayInp.value = act.delay_secs || 0;
      delayInp.min = 0;
      delayInp.max = 30;
      delayInp.onchange = () => { act.delay_secs = parseInt(delayInp.value) || 0; };
      delayRow.appendChild(delayLabel);
      delayRow.appendChild(delayInp);
      row.appendChild(delayRow);

      actionsContainer.appendChild(row);
    });
  }
  renderActions();

  const addActBtn = document.createElement('button');
  addActBtn.className = 'btn btn-secondary';
  addActBtn.style.cssText = 'margin-top:var(--sp-2);font-size:var(--text-xs);align-self:flex-start;';
  addActBtn.textContent = '+ Add Action';
  addActBtn.onclick = () => { actions.push({ action_type: 'reply', action_config: {}, sort_order: actions.length, delay_secs: 0 }); renderActions(); };
  actionsCard.appendChild(addActBtn);
  wrapper.appendChild(actionsCard);

  // ── Submit Button ──
  const submitBtn = document.createElement('button');
  submitBtn.className = 'btn btn-primary';
  submitBtn.style.cssText = 'align-self:flex-start;';
  submitBtn.textContent = isEdit ? 'Save Changes' : 'Create Command';
  submitBtn.onclick = () => {
    const name = wrapper.querySelector('#cc-name').value.trim();
    if (!name) { showToast('Command name is required', 'error'); return; }
    if (triggers.length === 0) { showToast('Add at least one trigger', 'error'); return; }
    if (actions.length === 0) { showToast('Add at least one action', 'error'); return; }

    const data = {
      name,
      description: wrapper.querySelector('#cc-desc').value.trim(),
      cooldown_secs: parseInt(wrapper.querySelector('#cc-cooldown').value) || 0,
      priority: parseInt(wrapper.querySelector('#cc-priority').value) || 0,
      triggers: triggers.map(t => ({
        trigger_type: t.trigger_type,
        trigger_value: t.trigger_value,
        case_sensitive: t.case_sensitive || false,
      })),
      actions: actions.map((a, i) => ({
        action_type: a.action_type,
        action_config: a.action_config || {},
        sort_order: i,
        condition: a.condition || null,
        delay_secs: a.delay_secs || 0,
      })),
    };
    if (submitCb) submitCb(data);
  };
  wrapper.appendChild(submitBtn);

  return {
    element: wrapper,
    onSubmit: (cb) => { submitCb = cb; },
  };
}

// ── Variables Tab ────────────────────────────────────────────────────────

async function _renderVariablesTab(container, chatId) {
  container.innerHTML = '';

  // Built-in variables reference
  const builtinCard = Card({ title: 'Built-in Variables', subtitle: 'Available in all custom commands' });
  const varList = document.createElement('div');
  varList.style.cssText = 'display:flex;flex-wrap:wrap;gap:var(--sp-2);padding-top:var(--sp-2);';
  BUILTIN_VARS.forEach(v => {
    const chip = document.createElement('code');
    chip.style.cssText = 'background:var(--accent-dim);color:var(--accent);padding:var(--sp-1) var(--sp-2);border-radius:var(--r-md);font-size:var(--text-xs);';
    chip.textContent = v;
    varList.appendChild(chip);
  });
  builtinCard.appendChild(varList);
  container.appendChild(builtinCard);

  // Custom variables
  const customCard = Card({ title: 'Custom Variables', subtitle: 'Group-level variables you can use and set in commands' });
  const customContainer = document.createElement('div');
  customContainer.style.cssText = 'padding-top:var(--sp-2);';
  customCard.appendChild(customContainer);

  // Add variable form
  const addRow = document.createElement('div');
  addRow.style.cssText = 'display:flex;gap:var(--sp-2);margin-bottom:var(--sp-3);';
  addRow.innerHTML = `
    <input type="text" id="cv-name" class="input" placeholder="Variable name" style="flex:1;">
    <input type="text" id="cv-value" class="input" placeholder="Value" style="flex:1;">
    <button id="cv-add-btn" class="btn btn-primary" style="font-size:var(--text-xs);flex-shrink:0;">Add</button>
  `;
  customCard.appendChild(addRow);

  addRow.querySelector('#cv-add-btn').onclick = async () => {
    const name = addRow.querySelector('#cv-name').value.trim();
    const value = addRow.querySelector('#cv-value').value.trim();
    if (!name) { showToast('Enter variable name', 'error'); return; }
    try {
      // Use command_id=0 for group-level variables via the API
      await apiFetch(`/api/groups/${chatId}/custom-commands/0/variables`, {
        method: 'POST',
        body: JSON.stringify({ var_name: name, var_value: value, var_type: 'string' })
      });
      showToast('Variable set!', 'success');
      addRow.querySelector('#cv-name').value = '';
      addRow.querySelector('#cv-value').value = '';
      await loadCustomVars(chatId, customContainer);
    } catch (e) { showToast('Failed', 'error'); }
  };

  await loadCustomVars(chatId, customContainer);
  container.appendChild(customCard);
}

async function loadCustomVars(chatId, container) {
  container.innerHTML = '<div style="text-align:center;padding:var(--sp-2);color:var(--text-muted);font-size:var(--text-xs);">Loading...</div>';
  try {
    const resp = await apiFetch(`/api/groups/${chatId}/custom-commands/0/variables`);
    const vars = resp.variables || [];
    container.innerHTML = '';
    if (vars.length === 0) {
      container.innerHTML = '<div style="text-align:center;padding:var(--sp-2);color:var(--text-muted);font-size:var(--text-xs);">No custom variables set</div>';
      return;
    }
    const list = document.createElement('div');
    list.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-1);';
    vars.forEach(v => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:var(--sp-1) var(--sp-2);background:var(--bg-input);border-radius:var(--r-md);font-size:var(--text-xs);';
      row.innerHTML = `<span><code>{${_escHtml(v.var_name)}}</code> = <em>${_escHtml(v.var_value || '')}</em></span>`;
      list.appendChild(row);
    });
    container.appendChild(list);
  } catch (_) {
    container.innerHTML = '<div style="text-align:center;padding:var(--sp-2);color:var(--text-muted);font-size:var(--text-xs);">Could not load variables</div>';
  }
}

function _escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}
