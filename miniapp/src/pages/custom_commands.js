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
  { value: 'new_member', label: 'New member joins' },
  { value: 'left_member', label: 'Member leaves' },
  { value: 'message', label: 'Any message' },
  { value: 'has_attachment', label: 'Has attachment' },
  { value: 'has_photo', label: 'Has photo' },
  { value: 'has_video', label: 'Has video' },
  { value: 'has_document', label: 'Has document' },
  { value: 'has_voice', label: 'Has voice note' },
  { value: 'has_sticker', label: 'Has sticker' },
  { value: 'has_link', label: 'Contains link' },
  { value: 'forwarded', label: 'Is forwarded' },
  { value: 'is_reply', label: 'Is a reply' },
];

// Preset examples for quick command creation
const COMMAND_EXAMPLES = [
  {
    name: 'welcome',
    description: 'Welcome new members to the group',
    triggers: [{ trigger_type: 'new_member', trigger_value: '', case_sensitive: false }],
    actions: [
      {
        action_type: 'reply',
        action_config: { text: '👋 Welcome {target.name} to {group.name}! We\'re glad to have you here.' },
        sort_order: 0,
        delay_secs: 0
      }
    ]
  },
  {
    name: 'rules',
    description: 'Show group rules',
    triggers: [
      { trigger_type: 'command', trigger_value: 'rules', case_sensitive: false }
    ],
    actions: [
      {
        action_type: 'reply',
        action_config: { text: '📋 Group Rules:\n\n1. Be respectful\n2. No spam\n3. Keep it family-friendly\n4. No advertising' },
        sort_order: 0,
        delay_secs: 0
      }
    ]
  },
  {
    name: 'info',
    description: 'Show group info and stats',
    triggers: [
      { trigger_type: 'command', trigger_value: 'info', case_sensitive: false }
    ],
    actions: [
      {
        action_type: 'reply',
        action_config: { text: '📊 Group Info:\n\n👥 Members: {group.member_count}\n📅 Date: {date}\n⏰ Time: {time}' },
        sort_order: 0,
        delay_secs: 0
      }
    ]
  },
  {
    name: 'greet',
    description: 'Greet users who say hello',
    triggers: [
      { trigger_type: 'keyword', trigger_value: 'hello', case_sensitive: false }
    ],
    actions: [
      {
        action_type: 'reply',
        action_config: { text: 'Hey {user.name}! 👋 How can I help you today?' },
        sort_order: 0,
        delay_secs: 0
      }
    ]
  },
  {
    name: 'antispam',
    description: 'Auto-delete messages with links from non-admins',
    triggers: [
      { trigger_type: 'has_link', trigger_value: '', case_sensitive: false }
    ],
    actions: [
      {
        action_type: 'delete',
        action_config: {},
        sort_order: 0,
        delay_secs: 0,
        condition: { type: 'role_check', role: 'admin' }
      },
      {
        action_type: 'reply',
        action_config: { text: '{user.mention} Links are not allowed in this chat.' },
        sort_order: 1,
        delay_secs: 0,
        condition: { type: 'role_check', role: 'admin' }
      }
    ]
  },
  {
    name: 'purge_photos',
    description: 'Delete all photos when triggered',
    triggers: [
      { trigger_type: 'has_photo', trigger_value: '', case_sensitive: false }
    ],
    actions: [
      {
        action_type: 'delete',
        action_config: {},
        sort_order: 0,
        delay_secs: 0
      }
    ]
  },
  {
    name: 'userinfo',
    description: 'Get info about a user (reply to user)',
    triggers: [
      { trigger_type: 'command', trigger_value: 'userinfo', case_sensitive: false }
    ],
    actions: [
      {
        action_type: 'reply',
        action_config: { text: 'User info:\n👤 Name: {target.name}\n🆔 ID: {target.id}\n👥 Username: {target.username}' },
        sort_order: 0,
        delay_secs: 0,
        condition: { type: 'reply_check' }
      }
    ]
  },
  {
    name: 'dice',
    description: 'Roll a dice game',
    triggers: [
      { trigger_type: 'command', trigger_value: 'dice', case_sensitive: false }
    ],
    actions: [
      {
        action_type: 'send_dice',
        action_config: { emoji: '🎲' },
        sort_order: 0,
        delay_secs: 0
      }
    ]
  },
  {
    name: 'guess',
    description: 'Guess a number game',
    triggers: [
      { trigger_type: 'keyword', trigger_value: 'guess', case_sensitive: false }
    ],
    actions: [
      {
        action_type: 'reply',
        action_config: { text: '🎯 My guess: {random}' },
        sort_order: 0,
        delay_secs: 0
      }
    ]
  },
  {
    name: 'goodbye',
    description: 'Goodbye message when member leaves',
    triggers: [
      { trigger_type: 'left_member', trigger_value: '', case_sensitive: false }
    ],
    actions: [
      {
        action_type: 'reply',
        action_config: { text: '😢 Goodbye {target.name}! We hope to see you again.' },
        sort_order: 0,
        delay_secs: 0
      }
    ]
  }
];

const ACTION_TYPES = [
  { value: 'reply', label: 'Send reply' },
  { value: 'delete', label: 'Delete message' },
  { value: 'react', label: 'Add reaction' },
  { value: 'warn', label: 'Warn user' },
  { value: 'mute', label: 'Mute user' },
  { value: 'unmute', label: 'Unmute user' },
  { value: 'kick', label: 'Kick user' },
  { value: 'ban', label: 'Ban user' },
  { value: 'unban', label: 'Unban user' },
  { value: 'promote', label: 'Promote to admin' },
  { value: 'demote', label: 'Remove admin' },
  { value: 'pin', label: 'Pin message' },
  { value: 'unpin_all', label: 'Unpin all messages' },
  { value: 'set_variable', label: 'Set variable' },
  { value: 'send_photo', label: 'Send photo' },
  { value: 'send_audio', label: 'Send audio' },
  { value: 'send_video', label: 'Send video' },
  { value: 'send_document', label: 'Send document' },
  { value: 'send_voice', label: 'Send voice note' },
  { value: 'send_sticker', label: 'Send sticker' },
  { value: 'send_dice', label: 'Send dice/emoji' },
  { value: 'send_location', label: 'Send location' },
  { value: 'send_venue', label: 'Send venue' },
  { value: 'send_contact', label: 'Send contact' },
  { value: 'forward', label: 'Forward to chat' },
  { value: 'webhook', label: 'Call webhook' },
  { value: 'set_title', label: 'Set chat title' },
  { value: 'set_description', label: 'Set chat description' },
  { value: 'leave', label: 'Leave chat' },
];

const BUILTIN_VARS = [
  // User variables
  '{user.name}', '{user.first_name}', '{user.last_name}', '{user.username}', '{user.id}', '{user.mention}',
  // Target variables (for replies)
  '{target.name}', '{target.first_name}', '{target.last_name}', '{target.username}', '{target.id}', '{target.mention}',
  // Group variables
  '{group.name}', '{group.id}', '{group.member_count}',
  // Bot variables
  '{bot.name}', '{bot.username}',
  // Time & fun variables
  '{time}', '{date}', '{datetime}', '{random}', '{newline}',
  // Arguments
  '{args}', '{arg1}', '{arg2}', '{arg3}',
];

// Variable guide with fun descriptions
const VARIABLE_GUIDE = [
  {
    category: '👤 User Variables',
    description: 'Info about the person who triggered the command',
    vars: [
      { name: 'user.name', desc: 'Full display name', example: 'John Doe' },
      { name: 'user.first_name', desc: 'First name only', example: 'John' },
      { name: 'user.last_name', desc: 'Last name only', example: 'Doe' },
      { name: 'user.username', desc: '@username or full name', example: '@johndoe' },
      { name: 'user.id', desc: 'Telegram user ID', example: '123456789' },
      { name: 'user.mention', desc: 'Clickable mention', example: '@johndoe (clickable!)' },
    ]
  },
  {
    category: '🎯 Target Variables',
    description: 'Info about the user being replied to (when someone replies to another user)',
    vars: [
      { name: 'target.name', desc: 'Their full name', example: 'Jane Smith' },
      { name: 'target.first_name', desc: 'Their first name', example: 'Jane' },
      { name: 'target.last_name', desc: 'Their last name', example: 'Smith' },
      { name: 'target.username', desc: 'Their @username', example: '@janesmith' },
      { name: 'target.id', desc: 'Their user ID', example: '987654321' },
      { name: 'target.mention', desc: 'Clickable mention of them', example: '@janesmith (clickable!)' },
    ]
  },
  {
    category: '👥 Group Variables',
    description: 'Info about the current group chat',
    vars: [
      { name: 'group.name', desc: 'Group title', example: 'My Awesome Group' },
      { name: 'group.id', desc: 'Chat ID', example: '-1001234567890' },
      { name: 'group.member_count', desc: 'How many members', example: '42 humans (and 3 bots)' },
    ]
  },
  {
    category: '🤖 Bot Variables',
    description: 'Info about this bot',
    vars: [
      { name: 'bot.name', desc: 'Bot display name', example: 'Nexus Bot' },
      { name: 'bot.username', desc: 'Bot @username', example: '@MyNexusBot' },
    ]
  },
  {
    category: '⏰ Time Variables',
    description: 'Current time (UTC timezone)',
    vars: [
      { name: 'time', desc: 'Current time', example: '14:30 UTC' },
      { name: 'date', desc: 'Today\'s date', example: '2024-01-15' },
      { name: 'datetime', desc: 'Full timestamp', example: '2024-01-15 14:30 UTC' },
    ]
  },
  {
    category: '🎲 Fun & Utility',
    description: 'Make your messages more dynamic!',
    vars: [
      { name: 'random', desc: 'Random number 1-100', example: '42 🎲 (for games!)' },
      { name: 'newline', desc: 'Line break', example: 'Use for multi-line messages' },
      { name: 'args', desc: 'Everything after the command', example: '/warn @user spam → "@user spam"' },
      { name: 'arg1', desc: 'First word after command', example: '/warn @user → "@user"' },
      { name: 'arg2', desc: 'Second word after command', example: '/warn @user spam → "spam"' },
      { name: 'arg3', desc: 'Third word after command', example: 'The third piece of text' },
    ]
  },
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
  header.style.cssText = 'margin-bottom:var(--sp-4);display:flex;justify-content:space-between;align-items:flex-start;';
  header.innerHTML = `
    <div>
      <h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">Custom Commands</h2>
      <p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">Build custom bot commands with triggers, conditions, and actions</p>
    </div>
    <div style="display:flex;gap:var(--sp-2);">
      <button id="cc-refresh-btn" class="btn btn-secondary" style="padding:var(--sp-2);"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg></button>
    </div>
  `;
  container.appendChild(header);

  header.querySelector('#cc-refresh-btn').onclick = () => {
    const activeTab = tabBar.querySelector('button[style*="var(--bg-card)"]')?.dataset.tab || 'commands';
    _switchTab(activeTab, content, chatId, tabBar);
  };

  const searchContainer = document.createElement('div');
  searchContainer.style.cssText = 'margin-bottom:var(--sp-4);';
  const searchInput = document.createElement('input');
  searchInput.type = 'text';
  searchInput.className = 'input';
  searchInput.placeholder = 'Search commands by name or trigger...';
  searchInput.style.width = '100%';
  searchContainer.appendChild(searchInput);
  container.appendChild(searchContainer);

  searchInput.oninput = () => {
    const term = searchInput.value.toLowerCase();
    const cards = content.querySelectorAll('.command-card');
    cards.forEach(card => {
      const text = card.textContent.toLowerCase();
      card.style.display = text.includes(term) ? 'block' : 'none';
    });
  };

  // Tab bar
  const tabs = ['Commands', 'Create', 'Variables', 'Help'];
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
    case 'help':      return _renderHelpTab(container);
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
    card.className = 'command-card';
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
        <button class="btn btn-secondary cmd-clone-btn" data-id="${cmd.id}" style="font-size:var(--text-xs);padding:var(--sp-1) var(--sp-2);">Clone</button>
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
            method: 'PUT', body: { enabled: v }
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

    // Clone handler
    card.querySelector('.cmd-clone-btn').addEventListener('click', async () => {
      try {
        // Fetch full command
        const resp = await apiFetch(`/api/groups/${chatId}/custom-commands/${cmd.id}`);
        const fullCmd = resp.command;
        
        const cloneData = {
          name: fullCmd.name + '_copy',
          description: fullCmd.description,
          cooldown_secs: fullCmd.cooldown_secs,
          priority: fullCmd.priority,
          triggers: (fullCmd.triggers || []).map(t => ({
            trigger_type: t.trigger_type,
            trigger_value: t.trigger_value + '_copy',
            case_sensitive: t.case_sensitive
          })),
          actions: (fullCmd.actions || []).map(a => ({
            action_type: a.action_type,
            action_config: a.action_config,
            sort_order: a.sort_order,
            condition: a.condition,
            delay_secs: a.delay_secs
          }))
        };
        
        await apiFetch(`/api/groups/${chatId}/custom-commands`, {
          method: 'POST',
          body: cloneData
        });
        showToast('Command cloned!', 'success');
        _renderCommandsList(container, chatId, tabBar);
      } catch (e) { showToast('Clone failed: ' + e.message, 'error'); }
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
        body: data
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
        body: { name: data.name, description: data.description, cooldown_secs: data.cooldown_secs, priority: data.priority }
      });

      // Delete existing triggers and re-add
      for (const t of (fullCmd.triggers || [])) {
        await apiFetch(`/api/groups/${chatId}/custom-commands/${cmd.id}/triggers/${t.id}`, { method: 'DELETE' });
      }
      for (const t of (data.triggers || [])) {
        await apiFetch(`/api/groups/${chatId}/custom-commands/${cmd.id}/triggers`, {
          method: 'POST', body: t
        });
      }

      // Delete existing actions and re-add
      for (const a of (fullCmd.actions || [])) {
        await apiFetch(`/api/groups/${chatId}/custom-commands/${cmd.id}/actions/${a.id}`, { method: 'DELETE' });
      }
      for (const a of (data.actions || [])) {
        await apiFetch(`/api/groups/${chatId}/custom-commands/${cmd.id}/actions`, {
          method: 'POST', body: a
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

  // Template selector (only for new commands)
  let templateSelectHtml = '';
  if (!isEdit) {
    templateSelectHtml = `
      <div style="margin-bottom:var(--sp-3);">
        <label style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;display:block;margin-bottom:var(--sp-1);">Use Template</label>
        <select id="cc-template" class="input" style="width:100%;box-sizing:border-box;">
          <option value="">-- Select a template or start blank --</option>
          ${COMMAND_EXAMPLES.map(ex => `<option value="${ex.name}">${ex.name} - ${ex.description}</option>`).join('')}
        </select>
      </div>
    `;
  }

  infoCard.innerHTML += `
    <div style="display:flex;flex-direction:column;gap:var(--sp-3);padding-top:var(--sp-2);">
      ${templateSelectHtml}
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

  // Handle template selection
  if (!isEdit) {
    const templateSel = infoCard.querySelector('#cc-template');
    if (templateSel) {
      templateSel.onchange = () => {
        const templateName = templateSel.value;
        if (!templateName) return;
        const template = COMMAND_EXAMPLES.find(t => t.name === templateName);
        if (!template) return;

        // Fill form with template data
        infoCard.querySelector('#cc-name').value = template.name;
        infoCard.querySelector('#cc-desc').value = template.description;

        // Populate triggers and actions
        triggers.length = 0;
        for (const t of template.triggers) {
          triggers.push({ ...t });
        }
        actions.length = 0;
        for (const a of template.actions) {
          actions.push({ ...a, action_config: { ...a.action_config } });
        }

        renderTriggers();
        renderActions();
      };
    }
  }
  wrapper.appendChild(infoCard);

  // ── Triggers ──
  const triggersCard = Card({ title: 'Triggers', subtitle: 'What activates this command?' });
  const triggersContainer = document.createElement('div');
  triggersContainer.id = 'cc-triggers-list';
  triggersContainer.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);padding-top:var(--sp-2);';
  triggersCard.appendChild(triggersContainer);

  // Trigger types that don't require a value input
  const NO_VALUE_TRIGGERS = ['new_member', 'left_member', 'message', 'has_attachment', 'has_photo', 'has_video', 'has_document', 'has_voice', 'has_sticker', 'has_link', 'forwarded', 'is_reply'];

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
      sel.onchange = () => { trig.trigger_type = sel.value; renderTriggers(); };

      const isNoValue = NO_VALUE_TRIGGERS.includes(trig.trigger_type);
      const isCommand = trig.trigger_type === 'command';
      
      const inpWrapper = document.createElement('div');
      inpWrapper.style.cssText = isNoValue ? 'display:none;' : 'flex:1;display:flex;align-items:center;gap:var(--sp-1);';
      
      // Add / prefix for command type
      if (isCommand) {
        const slashPrefix = document.createElement('span');
        slashPrefix.textContent = '/';
        slashPrefix.style.cssText = 'color:var(--text-muted);font-size:var(--text-sm);font-weight:var(--fw-bold);';
        inpWrapper.appendChild(slashPrefix);
      }
      
      const inp = document.createElement('input');
      inp.type = 'text';
      inp.className = 'input';
      inp.style.cssText = 'flex:1;';
      inp.placeholder = isCommand ? 'commandname' : 'pattern or keyword';
      inp.value = trig.trigger_value || '';
      inp.oninput = () => { trig.trigger_value = inp.value; };
      inpWrapper.appendChild(inp);

      const csLabel = document.createElement('label');
      csLabel.style.cssText = isNoValue ? 'display:none;' : 'display:flex;align-items:center;gap:4px;font-size:10px;color:var(--text-muted);cursor:pointer;white-space:nowrap;';
      const csInp = document.createElement('input');
      csInp.type = 'checkbox';
      csInp.checked = !!trig.case_sensitive;
      csInp.onchange = () => { trig.case_sensitive = csInp.checked; };
      csLabel.appendChild(csInp);
      csLabel.appendChild(document.createTextNode('Case sens.'));

      const del = document.createElement('button');
      del.className = 'btn btn-danger';
      del.style.cssText = 'padding:var(--sp-1) var(--sp-2);font-size:var(--text-xs);flex-shrink:0;';
      del.textContent = 'X';
      del.onclick = () => { triggers.splice(i, 1); renderTriggers(); };

      row.appendChild(sel);
      if (!isNoValue) {
        row.appendChild(inpWrapper);
      }
      row.appendChild(csLabel);
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
        varsHint.style.cssText = 'font-size:9px;color:var(--text-muted);margin-top:4px;word-break:break-all;display:flex;flex-wrap:wrap;gap:4px;';
        BUILTIN_VARS.forEach(v => {
          const vBtn = document.createElement('span');
          vBtn.textContent = v;
          vBtn.style.cssText = 'cursor:pointer;background:var(--bg-card);padding:1px 4px;border-radius:4px;border:1px solid var(--border);';
          vBtn.onclick = () => {
            const start = ta.selectionStart;
            const end = ta.selectionEnd;
            ta.value = ta.value.substring(0, start) + v + ta.value.substring(end);
            ta.selectionStart = ta.selectionEnd = start + v.length;
            ta.focus();
            act.action_config = { ...config, text: ta.value };
          };
          varsHint.appendChild(vBtn);
        });
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
      } else if (act.action_type === 'mute' || act.action_type === 'ban') {
        const inp = document.createElement('input');
        inp.type = 'number';
        inp.className = 'input';
        inp.style.cssText = 'width:100%;box-sizing:border-box;';
        inp.placeholder = 'Duration in seconds (0 for permanent)';
        inp.value = config.duration || 0;
        inp.oninput = () => { act.action_config = { ...config, duration: parseInt(inp.value) || 0 }; };
        row.appendChild(inp);
      } else if (act.action_type === 'unban') {
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'input';
        inp.style.cssText = 'width:100%;box-sizing:border-box;';
        inp.placeholder = 'User ID (or reply to a user)';
        inp.value = config.user_id || '';
        inp.oninput = () => { act.action_config = { ...config, user_id: inp.value }; };
        row.appendChild(inp);
      } else if (act.action_type === 'send_photo') {
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'input';
        inp.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:var(--sp-2);';
        inp.placeholder = 'Photo URL';
        inp.value = config.photo_url || '';
        inp.oninput = () => { act.action_config = { ...config, photo_url: inp.value }; };
        row.appendChild(inp);
        const cap = document.createElement('input');
        cap.type = 'text';
        cap.className = 'input';
        cap.style.cssText = 'width:100%;box-sizing:border-box;';
        cap.placeholder = 'Caption (optional)';
        cap.value = config.caption || '';
        cap.oninput = () => { act.action_config = { ...config, caption: cap.value }; };
        row.appendChild(cap);
      } else if (act.action_type === 'webhook') {
        const urlInp = document.createElement('input');
        urlInp.className = 'input';
        urlInp.style.cssText = 'width:100%;margin-bottom:var(--sp-2);';
        urlInp.placeholder = 'Webhook URL';
        urlInp.value = config.url || '';
        urlInp.oninput = () => { act.action_config = { ...config, url: urlInp.value }; };
        row.appendChild(urlInp);

        const meth = document.createElement('select');
        meth.className = 'input';
        meth.style.cssText = 'width:100%;margin-bottom:var(--sp-2);';
        ['POST', 'GET'].forEach(m => {
          const o = document.createElement('option');
          o.value = m; o.textContent = m;
          o.selected = config.method === m;
          meth.appendChild(o);
        });
        meth.onchange = () => { act.action_config = { ...config, method: meth.value }; };
        row.appendChild(meth);

        const pay = document.createElement('textarea');
        pay.className = 'input';
        pay.style.cssText = 'width:100%;min-height:60px;';
        pay.placeholder = 'JSON Payload';
        pay.value = config.payload || '{}';
        pay.oninput = () => { act.action_config = { ...config, payload: pay.value }; };
        row.appendChild(pay);
      } else if (act.action_type === 'send_audio') {
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'input';
        inp.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:var(--sp-2);';
        inp.placeholder = 'Audio URL';
        inp.value = config.audio_url || '';
        inp.oninput = () => { act.action_config = { ...config, audio_url: inp.value }; };
        row.appendChild(inp);
        const cap = document.createElement('input');
        cap.type = 'text';
        cap.className = 'input';
        cap.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:var(--sp-2);';
        cap.placeholder = 'Caption (optional)';
        cap.value = config.caption || '';
        cap.oninput = () => { act.action_config = { ...config, caption: cap.value }; };
        row.appendChild(cap);
        const perf = document.createElement('input');
        perf.type = 'text';
        perf.className = 'input';
        perf.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:var(--sp-2);';
        perf.placeholder = 'Performer (optional)';
        perf.value = config.performer || '';
        perf.oninput = () => { act.action_config = { ...config, performer: perf.value }; };
        row.appendChild(perf);
        const tit = document.createElement('input');
        tit.type = 'text';
        tit.className = 'input';
        tit.style.cssText = 'width:100%;box-sizing:border-box;';
        tit.placeholder = 'Title (optional)';
        tit.value = config.title || '';
        tit.oninput = () => { act.action_config = { ...config, title: tit.value }; };
        row.appendChild(tit);
      } else if (act.action_type === 'send_video') {
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'input';
        inp.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:var(--sp-2);';
        inp.placeholder = 'Video URL';
        inp.value = config.video_url || '';
        inp.oninput = () => { act.action_config = { ...config, video_url: inp.value }; };
        row.appendChild(inp);
        const cap = document.createElement('input');
        cap.type = 'text';
        cap.className = 'input';
        cap.style.cssText = 'width:100%;box-sizing:border-box;';
        cap.placeholder = 'Caption (optional)';
        cap.value = config.caption || '';
        cap.oninput = () => { act.action_config = { ...config, caption: cap.value }; };
        row.appendChild(cap);
      } else if (act.action_type === 'send_document') {
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'input';
        inp.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:var(--sp-2);';
        inp.placeholder = 'Document URL';
        inp.value = config.document_url || '';
        inp.oninput = () => { act.action_config = { ...config, document_url: inp.value }; };
        row.appendChild(inp);
        const cap = document.createElement('input');
        cap.type = 'text';
        cap.className = 'input';
        cap.style.cssText = 'width:100%;box-sizing:border-box;';
        cap.placeholder = 'Caption (optional)';
        cap.value = config.caption || '';
        cap.oninput = () => { act.action_config = { ...config, caption: cap.value }; };
        row.appendChild(cap);
      } else if (act.action_type === 'send_voice') {
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'input';
        inp.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:var(--sp-2);';
        inp.placeholder = 'Voice URL';
        inp.value = config.voice_url || '';
        inp.oninput = () => { act.action_config = { ...config, voice_url: inp.value }; };
        row.appendChild(inp);
        const cap = document.createElement('input');
        cap.type = 'text';
        cap.className = 'input';
        cap.style.cssText = 'width:100%;box-sizing:border-box;';
        cap.placeholder = 'Caption (optional)';
        cap.value = config.caption || '';
        cap.oninput = () => { act.action_config = { ...config, caption: cap.value }; };
        row.appendChild(cap);
      } else if (act.action_type === 'send_location') {
        const lat = document.createElement('input');
        lat.type = 'text';
        lat.className = 'input';
        lat.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:var(--sp-2);';
        lat.placeholder = 'Latitude';
        lat.value = config.latitude || '';
        lat.oninput = () => { act.action_config = { ...config, latitude: lat.value }; };
        row.appendChild(lat);
        const lng = document.createElement('input');
        lng.type = 'text';
        lng.className = 'input';
        lng.style.cssText = 'width:100%;box-sizing:border-box;';
        lng.placeholder = 'Longitude';
        lng.value = config.longitude || '';
        lng.oninput = () => { act.action_config = { ...config, longitude: lng.value }; };
        row.appendChild(lng);
      } else if (act.action_type === 'send_venue') {
        const lat = document.createElement('input');
        lat.type = 'text';
        lat.className = 'input';
        lat.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:var(--sp-2);';
        lat.placeholder = 'Latitude';
        lat.value = config.latitude || '';
        lat.oninput = () => { act.action_config = { ...config, latitude: lat.value }; };
        row.appendChild(lat);
        const lng = document.createElement('input');
        lng.type = 'text';
        lng.className = 'input';
        lng.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:var(--sp-2);';
        lng.placeholder = 'Longitude';
        lng.value = config.longitude || '';
        lng.oninput = () => { act.action_config = { ...config, longitude: lng.value }; };
        row.appendChild(lng);
        const title = document.createElement('input');
        title.type = 'text';
        title.className = 'input';
        title.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:var(--sp-2);';
        title.placeholder = 'Title';
        title.value = config.title || '';
        title.oninput = () => { act.action_config = { ...config, title: title.value }; };
        row.appendChild(title);
        const addr = document.createElement('input');
        addr.type = 'text';
        addr.className = 'input';
        addr.style.cssText = 'width:100%;box-sizing:border-box;';
        addr.placeholder = 'Address';
        addr.value = config.address || '';
        addr.oninput = () => { act.action_config = { ...config, address: addr.value }; };
        row.appendChild(addr);
      } else if (act.action_type === 'send_contact') {
        const phone = document.createElement('input');
        phone.type = 'text';
        phone.className = 'input';
        phone.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:var(--sp-2);';
        phone.placeholder = 'Phone Number';
        phone.value = config.phone_number || '';
        phone.oninput = () => { act.action_config = { ...config, phone_number: phone.value }; };
        row.appendChild(phone);
        const fname = document.createElement('input');
        fname.type = 'text';
        fname.className = 'input';
        fname.style.cssText = 'width:100%;box-sizing:border-box;margin-bottom:var(--sp-2);';
        fname.placeholder = 'First Name';
        fname.value = config.first_name || '';
        fname.oninput = () => { act.action_config = { ...config, first_name: fname.value }; };
        row.appendChild(fname);
        const lname = document.createElement('input');
        lname.type = 'text';
        lname.className = 'input';
        lname.style.cssText = 'width:100%;box-sizing:border-box;';
        lname.placeholder = 'Last Name (optional)';
        lname.value = config.last_name || '';
        lname.oninput = () => { act.action_config = { ...config, last_name: lname.value }; };
        row.appendChild(lname);
      } else if (act.action_type === 'forward') {
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'input';
        inp.style.cssText = 'width:100%;box-sizing:border-box;';
        inp.placeholder = 'Destination Chat ID';
        inp.value = config.to_chat_id || '';
        inp.oninput = () => { act.action_config = { ...config, to_chat_id: inp.value }; };
        row.appendChild(inp);
      } else if (act.action_type === 'send_sticker') {
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'input';
        inp.style.cssText = 'width:100%;box-sizing:border-box;';
        inp.placeholder = 'Sticker URL';
        inp.value = config.sticker_url || '';
        inp.oninput = () => { act.action_config = { ...config, sticker_url: inp.value }; };
        row.appendChild(inp);
      } else if (act.action_type === 'send_dice') {
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'input';
        inp.style.cssText = 'width:100%;box-sizing:border-box;';
        inp.placeholder = 'Emoji (🎲, 🎯, 🏀, ⚽, 🎳, 🎰)';
        inp.value = config.emoji || '🎲';
        inp.oninput = () => { act.action_config = { ...config, emoji: inp.value }; };
        row.appendChild(inp);
      } else if (act.action_type === 'set_title') {
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'input';
        inp.style.cssText = 'width:100%;box-sizing:border-box;';
        inp.placeholder = 'New group title';
        inp.value = config.title || '';
        inp.oninput = () => { act.action_config = { ...config, title: inp.value }; };
        row.appendChild(inp);
      } else if (act.action_type === 'set_description') {
        const ta = document.createElement('textarea');
        ta.className = 'input';
        ta.style.cssText = 'width:100%;box-sizing:border-box;min-height:60px;';
        ta.placeholder = 'New group description';
        ta.value = config.description || '';
        ta.oninput = () => { act.action_config = { ...config, description: ta.value }; };
        row.appendChild(ta);
      }

      // Condition field
      const condRow = document.createElement('div');
      condRow.style.cssText = 'margin-top:var(--sp-2);';
      const condInp = document.createElement('input');
      condInp.type = 'text';
      condInp.className = 'input';
      condInp.style.cssText = 'width:100%;font-size:var(--text-xs);';
      condInp.placeholder = 'Condition (JSON), e.g. {"role": "admin"}';
      condInp.value = act.condition ? JSON.stringify(act.condition) : '';
      condInp.oninput = () => {
        try {
          act.condition = condInp.value ? JSON.parse(condInp.value) : null;
          condInp.style.borderColor = '';
        } catch (e) {
          condInp.style.borderColor = 'var(--danger)';
        }
      };
      condRow.appendChild(condInp);
      row.appendChild(condRow);

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
  container.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-4);';

  // Variable Guide with categories
  VARIABLE_GUIDE.forEach(category => {
    const card = Card({ 
      title: category.category, 
      subtitle: category.description 
    });
    
    const table = document.createElement('div');
    table.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);padding-top:var(--sp-2);';
    
    category.vars.forEach(v => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:var(--sp-3);padding:var(--sp-2);background:var(--bg-input);border-radius:var(--r-lg);font-size:var(--text-xs);';
      row.innerHTML = `
        <code style="background:var(--accent-dim);color:var(--accent);padding:2px 6px;border-radius:var(--r-md);font-size:var(--text-xs);white-space:nowrap;">{${v.name}}</code>
        <span style="color:var(--text-secondary);flex:1;">${v.desc}</span>
        <span style="color:var(--text-muted);font-style:italic;">${v.example}</span>
      `;
      table.appendChild(row);
    });
    
    card.appendChild(table);
    container.appendChild(card);
  });

  // Custom variables section
  const customCard = Card({ title: '🎨 Custom Variables', subtitle: 'Create your own variables for this group' });
  const customContainer = document.createElement('div');
  customContainer.style.cssText = 'padding-top:var(--sp-2);';
  
  // Add variable form
  const addRow = document.createElement('div');
  addRow.style.cssText = 'display:flex;gap:var(--sp-2);margin-bottom:var(--sp-3);';
  addRow.innerHTML = `
    <input type="text" id="cv-name" class="input" placeholder="Variable name (e.g. welcome_msg)" style="flex:1;">
    <input type="text" id="cv-value" class="input" placeholder="Value" style="flex:1;">
    <button id="cv-add-btn" class="btn btn-primary" style="font-size:var(--text-xs);flex-shrink:0;">Add</button>
  `;
  customCard.appendChild(addRow);
  customCard.appendChild(customContainer);

  addRow.querySelector('#cv-add-btn').onclick = async () => {
    const name = addRow.querySelector('#cv-name').value.trim();
    const value = addRow.querySelector('#cv-value').value.trim();
    if (!name) { showToast('Enter variable name', 'error'); return; }
    try {
      await apiFetch(`/api/groups/${chatId}/custom-commands/0/variables`, {
        method: 'POST',
        body: { var_name: name, var_value: value, var_type: 'string' }
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

// ── Help Tab ─────────────────────────────────────────────────────────────

function _renderHelpTab(container) {
  container.innerHTML = '';
  container.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-4);';

  // Quick Start Guide
  const quickStartCard = Card({ 
    title: '🚀 Quick Start Guide', 
    subtitle: 'Create your first custom command in 3 easy steps!' 
  });
  quickStartCard.innerHTML += `
    <div style="display:flex;flex-direction:column;gap:var(--sp-3);padding-top:var(--sp-2);">
      <div style="display:flex;gap:var(--sp-3);align-items:flex-start;">
        <div style="background:var(--accent);color:#000;width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:var(--text-xs);flex-shrink:0;">1</div>
        <div>
          <div style="font-weight:var(--fw-semibold);font-size:var(--text-sm);">Choose a Trigger</div>
          <div style="font-size:var(--text-xs);color:var(--text-muted);">Pick what activates your command - a /command, keyword, or event like "new member joins"</div>
        </div>
      </div>
      <div style="display:flex;gap:var(--sp-3);align-items:flex-start;">
        <div style="background:var(--accent);color:#000;width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:var(--text-xs);flex-shrink:0;">2</div>
        <div>
          <div style="font-weight:var(--fw-semibold);font-size:var(--text-sm);">Add Actions</div>
          <div style="font-size:var(--text-xs);color:var(--text-muted);">Decide what happens - send a message, delete the trigger, warn/mute users, and more!</div>
        </div>
      </div>
      <div style="display:flex;gap:var(--sp-3);align-items:flex-start;">
        <div style="background:var(--accent);color:#000;width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:var(--text-xs);flex-shrink:0;">3</div>
        <div>
          <div style="font-weight:var(--fw-semibold);font-size:var(--text-sm);">Test & Enjoy!</div>
          <div style="font-size:var(--text-xs);color:var(--text-muted);">Save your command and test it in your group. Use variables like {user.name} to personalize!</div>
        </div>
      </div>
    </div>
  `;
  container.appendChild(quickStartCard);

  // Trigger Types Explained
  const triggersCard = Card({ 
    title: '⚡ Trigger Types Explained', 
    subtitle: 'What activates your command?' 
  });
  const triggerGuide = [
    { icon: '/', name: 'Command', desc: 'Triggered by /commandname. Most common type!' },
    { icon: '🔤', name: 'Keyword', desc: 'Activates when someone types a specific word anywhere in their message' },
    { icon: '🔍', name: 'Regex', desc: 'Advanced pattern matching for power users' },
    { icon: '🆕', name: 'New Member', desc: 'Runs when someone joins the group (great for welcomes!)' },
    { icon: '👋', name: 'Left Member', desc: 'Runs when someone leaves (goodbye messages)' },
    { icon: '💬', name: 'Any Message', desc: 'Fires on every single message' },
    { icon: '📎', name: 'Has Attachment', desc: 'When someone sends any file/media' },
    { icon: '📷', name: 'Has Photo', desc: 'Specifically for images' },
    { icon: '🎥', name: 'Has Video', desc: 'For video files' },
    { icon: '📄', name: 'Has Document', desc: 'For files/documents' },
    { icon: '🎤', name: 'Has Voice', desc: 'For voice messages' },
    { icon: '🎭', name: 'Has Sticker', desc: 'When stickers are sent' },
    { icon: '🔗', name: 'Has Link', desc: 'When URLs are detected' },
    { icon: '📤', name: 'Forwarded', desc: 'When someone forwards a message' },
    { icon: '↩️', name: 'Is Reply', desc: 'Only when replying to another message' },
  ];
  const triggerList = document.createElement('div');
  triggerList.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:var(--sp-2);padding-top:var(--sp-2);';
  triggerGuide.forEach(t => {
    triggerList.innerHTML += `
      <div style="background:var(--bg-input);padding:var(--sp-2);border-radius:var(--r-lg);font-size:var(--text-xs);">
        <div style="font-weight:var(--fw-semibold);margin-bottom:2px;">${t.icon} ${t.name}</div>
        <div style="color:var(--text-muted);">${t.desc}</div>
      </div>
    `;
  });
  triggersCard.appendChild(triggerList);
  container.appendChild(triggersCard);

  // Action Types Explained
  const actionsCard = Card({ 
    title: '🎬 Action Types Explained', 
    subtitle: 'What your command can do' 
  });
  const actionGuide = [
    { icon: '💬', name: 'Send Reply', desc: 'Send a text message back', example: 'Welcome to the group!' },
    { icon: '🗑️', name: 'Delete Message', desc: 'Remove the triggering message', example: 'Auto-delete spam' },
    { icon: '❤️', name: 'Add Reaction', desc: 'React with an emoji', example: '👍 on good posts' },
    { icon: '⚠️', name: 'Warn User', desc: 'Give a warning to the user', example: 'Warn for rule-breaking' },
    { icon: '🔇', name: 'Mute User', desc: 'Temporarily silence someone', example: 'Mute for 1 hour' },
    { icon: '🔊', name: 'Unmute User', desc: 'Restore messaging rights', example: 'Unmute after time served' },
    { icon: '👢', name: 'Kick User', desc: 'Remove from group (can rejoin)', example: 'Kick troublemakers' },
    { icon: '🚫', name: 'Ban User', desc: 'Permanently ban from group', example: 'Ban spammers' },
    { icon: '✅', name: 'Unban User', desc: 'Allow banned user back', example: 'Forgive and forget' },
    { icon: '⬆️', name: 'Promote', desc: 'Make someone admin', example: 'Promote trusted members' },
    { icon: '⬇️', name: 'Demote', desc: 'Remove admin rights', example: 'Demote inactive admins' },
    { icon: '📌', name: 'Pin Message', desc: 'Pin the replied-to message', example: 'Pin important announcements' },
    { icon: '📍', name: 'Unpin All', desc: 'Clear all pinned messages', example: 'Clean up old pins' },
    { icon: '📸', name: 'Send Photo', desc: 'Send an image', example: 'Send group rules image' },
    { icon: '🎵', name: 'Send Audio', desc: 'Send music/audio file', example: 'Play intro music' },
    { icon: '🎬', name: 'Send Video', desc: 'Send a video', example: 'Share tutorial videos' },
    { icon: '📄', name: 'Send Document', desc: 'Send any file', example: 'Share PDF resources' },
    { icon: '🎤', name: 'Send Voice', desc: 'Send voice message', example: 'Voice announcements' },
    { icon: '🎭', name: 'Send Sticker', desc: 'Send a sticker', example: 'Fun reactions' },
    { icon: '🎲', name: 'Send Dice', desc: 'Roll a dice/game', example: '🎲 🎯 🏀 games' },
    { icon: '📍', name: 'Send Location', desc: 'Share coordinates', example: 'Share meetup spot' },
    { icon: '🏛️', name: 'Send Venue', desc: 'Share place with name', example: 'Share event location' },
    { icon: '👤', name: 'Send Contact', desc: 'Share a contact', example: 'Share admin contact' },
    { icon: '↪️', name: 'Forward', desc: 'Forward to another chat', example: 'Relay to mod chat' },
    { icon: '🌐', name: 'Webhook', desc: 'Call external API', example: 'Integrate with services' },
    { icon: '📝', name: 'Set Title', desc: 'Change group name', example: 'Update for events' },
    { icon: '📋', name: 'Set Description', desc: 'Change group bio', example: 'Update description' },
    { icon: '🚪', name: 'Leave', desc: 'Bot leaves the chat', example: 'Emergency exit' },
    { icon: '🔧', name: 'Set Variable', desc: 'Store data for later', example: 'Save counter values' },
  ];
  const actionList = document.createElement('div');
  actionList.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:var(--sp-2);padding-top:var(--sp-2);';
  actionGuide.forEach(a => {
    actionList.innerHTML += `
      <div style="background:var(--bg-input);padding:var(--sp-2);border-radius:var(--r-lg);font-size:var(--text-xs);">
        <div style="font-weight:var(--fw-semibold);margin-bottom:2px;">${a.icon} ${a.name}</div>
        <div style="color:var(--text-secondary);margin-bottom:2px;">${a.desc}</div>
        <div style="color:var(--text-muted);font-style:italic;">e.g. ${a.example}</div>
      </div>
    `;
  });
  actionsCard.appendChild(actionList);
  container.appendChild(actionsCard);

  // Pro Tips
  const tipsCard = Card({ 
    title: '💡 Pro Tips', 
    subtitle: 'Level up your commands!' 
  });
  tipsCard.innerHTML += `
    <div style="display:flex;flex-direction:column;gap:var(--sp-3);padding-top:var(--sp-2);font-size:var(--text-xs);">
      <div style="background:var(--bg-input);padding:var(--sp-3);border-radius:var(--r-lg);border-left:3px solid var(--accent);">
        <div style="font-weight:var(--fw-semibold);margin-bottom:var(--sp-1);">🔗 Chain Multiple Actions</div>
        <div style="color:var(--text-muted);">Your command can do many things! Delete the spam message AND warn the user AND send a log to admins - all at once!</div>
      </div>
      <div style="background:var(--bg-input);padding:var(--sp-3);border-radius:var(--r-lg);border-left:3px solid var(--accent);">
        <div style="font-weight:var(--fw-semibold);margin-bottom:var(--sp-1);">🎯 Use Conditions</div>
        <div style="color:var(--text-muted);">Make actions conditional! Only delete links from non-admins, or only welcome users on their first join.</div>
      </div>
      <div style="background:var(--bg-input);padding:var(--sp-3);border-radius:var(--r-lg);border-left:3px solid var(--accent);">
        <div style="font-weight:var(--fw-semibold);margin-bottom:var(--sp-1);">⏱️ Add Delays</div>
        <div style="color:var(--text-muted);">Space out your actions! Welcome message immediately, then a rules reminder after 5 seconds.</div>
      </div>
      <div style="background:var(--bg-input);padding:var(--sp-3);border-radius:var(--r-lg);border-left:3px solid var(--accent);">
        <div style="font-weight:var(--fw-semibold);margin-bottom:var(--sp-1);">🎲 Make It Fun!</div>
        <div style="color:var(--text-muted);">Use {random} for games, {user.mention} to ping people nicely, and {newline} for formatting!</div>
      </div>
    </div>
  `;
  container.appendChild(tipsCard);
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
