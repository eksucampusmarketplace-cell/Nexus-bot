/**
 * miniapp/src/pages/greetings.js
 *
 * Greetings & Custom Messages editor page.
 * Allows admins to customize:
 *   - Welcome message (with media support, DM toggle)
 *   - Goodbye message
 *   - Group rules
 *   - All other bot custom messages (mute/ban notifications, etc.)
 *
 * Reads/writes /api/groups/{chatId}/text-config
 *
 * Available variables shown per message type with inline hints.
 * Live character counter. Preview panel. Reset to default.
 */

import { Card, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';

const store = useStore;

const MESSAGE_TYPES = [
  {
    id: 'welcome',
    label: '👋 Welcome Message',
    description: 'Sent when a new member joins the group.',
    defaultText: 'Welcome {mention} to {chatname}! 🎉',
    variables: [
      { v: '{mention}',   desc: 'Clickable mention of the user' },
      { v: '{first_name}',desc: "User's first name" },
      { v: '{last_name}', desc: "User's last name" },
      { v: '{fullname}',  desc: 'Full name' },
      { v: '{username}',  desc: 'Username (or name if none)' },
      { v: '{chatname}',  desc: 'Group name' },
      { v: '{count}',     desc: 'Member number they are' },
    ],
    extras: ['welcome_dm', 'welcome_media'],
    supportsMedia: true,
  },
  {
    id: 'goodbye',
    label: '👋 Goodbye Message',
    description: 'Sent when a member leaves or is removed.',
    defaultText: 'Goodbye {fullname}! 👋',
    variables: [
      { v: '{mention}',   desc: 'Clickable mention' },
      { v: '{first_name}',desc: "User's first name" },
      { v: '{fullname}',  desc: 'Full name' },
      { v: '{username}',  desc: 'Username' },
      { v: '{chatname}',  desc: 'Group name' },
    ],
  },
  {
    id: 'rules',
    label: '📋 Group Rules',
    description: 'Shown when a user runs /rules.',
    defaultText: '1. Be respectful\n2. No spam\n3. No NSFW content',
    variables: [
      { v: '{chatname}', desc: 'Group name' },
    ],
    isTextarea: true,
    noPreview: true,
  },
  {
    id: 'warn_dm',
    label: '⚠️ Warning Notification (DM)',
    description: 'Sent to user when they receive a warning.',
    defaultText: 'You have been warned in {group_name}.\nReason: {reason}\nWarnings: {warn_count}/{warn_limit}',
    variables: [
      { v: '{first_name}', desc: "User's first name" },
      { v: '{group_name}', desc: 'Group name' },
      { v: '{reason}',     desc: 'Warning reason' },
      { v: '{warn_count}', desc: 'Current warn count' },
      { v: '{warn_limit}', desc: 'Max warns before action' },
    ],
  },
  {
    id: 'member_muted',
    label: '🔇 Mute Notification (DM)',
    description: 'Sent to user when they are muted.',
    defaultText: 'You have been muted in {group_name}.\nReason: {reason}\nDuration: {duration}',
    variables: [
      { v: '{first_name}', desc: "User's first name" },
      { v: '{group_name}', desc: 'Group name' },
      { v: '{reason}',     desc: 'Mute reason' },
      { v: '{duration}',   desc: 'Mute duration (e.g. 1 hour)' },
    ],
  },
  {
    id: 'member_banned',
    label: '🚫 Ban Notification (DM)',
    description: 'Sent to user when they are banned.',
    defaultText: 'You have been banned from {group_name}.\nReason: {reason}',
    variables: [
      { v: '{first_name}', desc: "User's first name" },
      { v: '{group_name}', desc: 'Group name' },
      { v: '{reason}',     desc: 'Ban reason' },
    ],
  },
  {
    id: 'captcha_prompt',
    label: '🔐 Captcha Prompt',
    description: 'Shown to new members for CAPTCHA verification.',
    defaultText: 'Welcome {first_name}! Please verify you are human by pressing the button below. You have {timeout} seconds.',
    variables: [
      { v: '{first_name}', desc: "User's first name" },
      { v: '{timeout}',    desc: 'Seconds to complete CAPTCHA' },
      { v: '{chatname}',   desc: 'Group name' },
    ],
  },
  {
    id: 'channel_gate',
    label: '📢 Channel Gate Message',
    description: 'Shown when user must join a channel first.',
    defaultText: 'Hi {first_name}! To access this group, please join our channel first:\n{channel_link}',
    variables: [
      { v: '{first_name}',   desc: "User's first name" },
      { v: '{channel_name}', desc: 'Required channel name' },
      { v: '{channel_link}', desc: 'Channel join link' },
    ],
  },
  {
    id: 'boost_gate',
    label: '🚀 Boost Gate Message',
    description: 'Shown when user must invite members to gain access.',
    defaultText: 'Hi {first_name}! You need to invite {remaining} more member(s) to unlock access.\n\nYour invite link:\n{link}\n\nProgress: {bar}',
    variables: [
      { v: '{first_name}', desc: "User's first name" },
      { v: '{required}',   desc: 'Total invites needed' },
      { v: '{current}',    desc: "User's current invite count" },
      { v: '{remaining}',  desc: 'Invites still needed' },
      { v: '{link}',       desc: "User's personal invite link" },
      { v: '{bar}',        desc: 'Visual progress bar' },
    ],
  },
  {
    id: 'boost_unlocked',
    label: '🎉 Boost Unlocked Message',
    description: 'Sent to user when they complete their invite goal.',
    defaultText: 'Congratulations {first_name}! You have unlocked access to {group_name}! 🎉',
    variables: [
      { v: '{first_name}', desc: "User's first name" },
      { v: '{group_name}', desc: 'Group name' },
    ],
  },
];

const MAX_LEN = 1000;

export async function renderGreetingsPage(container) {
  const chatId = store.getState().activeChatId;
  const initData = window.Telegram?.WebApp?.initData || '';

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '👆',
      title: 'Select a group',
      description: 'Choose a group from the dropdown above to edit messages'
    }));
    return;
  }

  container.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:center;padding:40px;">
      <div style="text-align:center;color:var(--text-muted);">
        <div style="font-size:24px;margin-bottom:12px;">⏳</div>
        <div style="font-size:var(--text-sm);">Loading messages...</div>
      </div>
    </div>
  `;

  let textConfig = {};
  try {
    const resp = await apiFetch(`/api/groups/${chatId}/text-config`) || {};
    textConfig = resp.config || resp || {};
  } catch (e) {
    console.warn('[Greetings] Could not load text config:', e);
  }

  container.innerHTML = '';

  const introCard = Card({
    title: '✏️ Custom Messages',
    subtitle: 'Customize every message the bot sends. Use variables like {first_name} for dynamic content.',
  });
  container.appendChild(introCard);

  MESSAGE_TYPES.forEach(msgType => {
    const card = _buildMessageCard(msgType, textConfig, chatId, initData);
    container.appendChild(card);
  });

  const notesSection = await _renderNotesSection(chatId);
  container.appendChild(notesSection);
}

function _buildMessageCard(msgType, textConfig, chatId, initData) {
  const currentText = textConfig[msgType.id] || '';
  const isCustomized = !!currentText;
  const displayText = currentText || msgType.defaultText;

  const card = document.createElement('div');
  card.style.cssText = `
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--r-xl);
    margin-bottom: var(--sp-3);
    overflow: hidden;
    transition: border-color var(--dur-fast);
  `;

  const header = document.createElement('div');
  header.style.cssText = `
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--sp-4);
    cursor: pointer;
    user-select: none;
  `;

  const headerLeft = document.createElement('div');
  headerLeft.style.cssText = 'flex: 1; min-width: 0;';
  headerLeft.innerHTML = `
    <div style="font-weight:var(--fw-semibold);font-size:var(--text-base);color:var(--text-primary)">
      ${msgType.label}
      ${isCustomized ? '<span style="font-size:10px;padding:2px 6px;background:var(--accent-dim);color:var(--accent);border-radius:999px;margin-left:6px;font-weight:600;">CUSTOM</span>' : ''}
    </div>
    <div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:2px">${msgType.description}</div>
  `;

  const chevron = document.createElement('span');
  chevron.textContent = '▸';
  chevron.style.cssText = 'color:var(--text-muted);font-size:12px;transition:transform 0.2s;margin-left:var(--sp-3);flex-shrink:0;';

  header.appendChild(headerLeft);
  header.appendChild(chevron);
  card.appendChild(header);

  const body = document.createElement('div');
  body.style.cssText = 'display:none;padding:0 var(--sp-4) var(--sp-4);border-top:1px solid var(--border);padding-top:var(--sp-4);';
  card.appendChild(body);

  let isOpen = false;
  header.onclick = () => {
    isOpen = !isOpen;
    body.style.display = isOpen ? 'block' : 'none';
    chevron.style.transform = isOpen ? 'rotate(90deg)' : 'rotate(0deg)';
    if (isOpen && body.children.length === 0) {
      _populateCardBody(body, msgType, displayText, isCustomized, textConfig, chatId, initData, card, header);
    }
  };

  return card;
}

function _populateCardBody(body, msgType, displayText, isCustomized, textConfig, chatId, initData, card, header) {
  const editorWrap = document.createElement('div');

  const varHints = document.createElement('div');
  varHints.style.cssText = `
    display: flex;
    flex-wrap: wrap;
    gap: var(--sp-1);
    margin-bottom: var(--sp-3);
  `;
  msgType.variables.forEach(v => {
    const chip = document.createElement('span');
    chip.style.cssText = `
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: var(--bg-input);
      border: 1px solid var(--border);
      border-radius: var(--r-full);
      padding: 2px 8px;
      font-size: 11px;
      cursor: pointer;
      transition: all var(--dur-fast);
      color: var(--text-secondary);
    `;
    chip.title = v.desc;
    chip.innerHTML = `<code style="color:var(--accent);font-size:11px;">${v.v}</code> <span style="color:var(--text-muted);">${v.desc}</span>`;
    chip.onclick = () => {
      const ta = editorWrap.querySelector('textarea');
      if (!ta) return;
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      const before = ta.value.slice(0, start);
      const after = ta.value.slice(end);
      ta.value = before + v.v + after;
      ta.selectionStart = ta.selectionEnd = start + v.v.length;
      ta.focus();
      ta.dispatchEvent(new Event('input'));
    };
    varHints.appendChild(chip);
  });
  editorWrap.appendChild(varHints);

  const inputLabel = document.createElement('div');
  inputLabel.style.cssText = 'font-size:var(--text-xs);font-weight:var(--fw-semibold);color:var(--text-muted);margin-bottom:var(--sp-2);text-transform:uppercase;letter-spacing:0.05em;';
  inputLabel.textContent = 'Message Text';
  editorWrap.appendChild(inputLabel);

  const textarea = document.createElement('textarea');
  textarea.value = displayText;
  textarea.rows = msgType.isTextarea ? 8 : 4;
  textarea.placeholder = msgType.defaultText;
  textarea.style.cssText = `
    width: 100%;
    box-sizing: border-box;
    padding: var(--sp-3);
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    color: var(--text-primary);
    font-size: var(--text-sm);
    font-family: inherit;
    line-height: 1.5;
    resize: vertical;
    transition: border-color var(--dur-fast);
  `;
  textarea.onfocus = () => textarea.style.borderColor = 'var(--accent)';
  textarea.onblur = () => textarea.style.borderColor = 'var(--border)';
  editorWrap.appendChild(textarea);

  const counter = document.createElement('div');
  counter.style.cssText = 'font-size:var(--text-xs);color:var(--text-muted);text-align:right;margin-top:4px;';
  counter.textContent = `${textarea.value.length} / ${MAX_LEN}`;
  editorWrap.appendChild(counter);

  textarea.addEventListener('input', () => {
    const len = textarea.value.length;
    counter.textContent = `${len} / ${MAX_LEN}`;
    counter.style.color = len > MAX_LEN ? 'var(--danger)' : 'var(--text-muted)';
  });

  if (msgType.supportsMedia) {
    const dmRow = document.createElement('div');
    dmRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;margin-top:var(--sp-3);padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);border:1px solid var(--border);';
    dmRow.innerHTML = `
      <div>
        <div style="font-size:var(--text-sm);font-weight:var(--fw-medium);color:var(--text-primary)">Send as DM</div>
        <div style="font-size:var(--text-xs);color:var(--text-muted)">Bot will DM the user instead of posting in group</div>
      </div>
    `;
    const dmVal = textConfig['welcome_dm'] || false;
    const Toggle_el = _makeToggle(dmVal, async (checked) => {
      await _saveKey(chatId, initData, 'welcome_dm', checked);
    });
    dmRow.appendChild(Toggle_el);
    editorWrap.appendChild(dmRow);
  }

  if (msgType.id === 'welcome') {
    const currentDeleteVal = textConfig.welcome_delete_after || 0;
    const deleteRow = document.createElement('div');
    deleteRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;margin-top:var(--sp-2);padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);border:1px solid var(--border);';
    const deleteOpts = [{v:0,l:'Never'},{v:30,l:'30 sec'},{v:60,l:'1 min'},{v:300,l:'5 min'},{v:600,l:'10 min'}];
    deleteRow.innerHTML = `
      <div>
        <div style="font-size:var(--text-sm);font-weight:var(--fw-medium);">Auto-delete welcome</div>
        <div style="font-size:var(--text-xs);color:var(--text-muted);">Delete welcome message after sending</div>
      </div>
      <select class="input" id="welcome-delete-select" style="width:auto;padding:var(--sp-2) var(--sp-3);">
        ${deleteOpts.map(o => `<option value="${o.v}" ${currentDeleteVal == o.v ? 'selected' : ''}>${o.l}</option>`).join('')}
      </select>
    `;
    deleteRow.querySelector('#welcome-delete-select').onchange = async (e) => {
      try {
        await apiFetch(`/api/groups/${chatId}/text-config`, {
          method: 'PUT',
          body: { welcome_delete_after: parseInt(e.target.value) },
        });
        showToast('Auto-delete saved', 'success');
      } catch (err) {
        showToast('Failed to save', 'error');
      }
    };
    editorWrap.appendChild(deleteRow);

    _renderButtonBuilder(editorWrap, textConfig, chatId);
  }

  body.appendChild(editorWrap);

  const htmlNote = document.createElement('div');
  htmlNote.style.cssText = 'font-size:var(--text-xs);color:var(--text-muted);margin-top:var(--sp-2);margin-bottom:var(--sp-3);';
  htmlNote.innerHTML = `💡 Supports HTML: <code style="color:var(--accent)">&lt;b&gt;bold&lt;/b&gt;</code>, <code style="color:var(--accent)">&lt;i&gt;italic&lt;/i&gt;</code>, <code style="color:var(--accent)">&lt;a href="..."&gt;link&lt;/a&gt;</code>`;
  body.appendChild(htmlNote);

  const btnRow = document.createElement('div');
  btnRow.style.cssText = 'display:flex;gap:var(--sp-2);flex-wrap:wrap;';

  const saveBtn = _makeBtn('💾 Save', 'var(--accent)', '#000');
  const resetBtn = _makeBtn('🔄 Reset to default', 'var(--bg-input)', 'var(--text-secondary)', true);
  const previewBtn = _makeBtn('👁️ Preview', 'var(--bg-input)', 'var(--text-secondary)', true);

  saveBtn.onclick = async () => {
    const text = textarea.value.trim();
    if (text.length > MAX_LEN) {
      showToast(`Message too long (${text.length} / ${MAX_LEN} chars)`, 'error');
      return;
    }
    saveBtn.disabled = true;
    saveBtn.textContent = '⏳ Saving...';
    try {
      await _saveKey(chatId, initData, msgType.id, text);
      showToast('Message saved!', 'success');
      _markCustomized(header, true);
    } catch (e) {
      showToast('Failed to save', 'error');
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = '💾 Save';
    }
  };

  resetBtn.onclick = async () => {
    if (!confirm('Reset to default message?')) return;
    resetBtn.disabled = true;
    try {
      await _saveKey(chatId, initData, msgType.id, '');
      textarea.value = msgType.defaultText;
      counter.textContent = `${textarea.value.length} / ${MAX_LEN}`;
      showToast('Reset to default', 'success');
      _markCustomized(header, false);
    } catch (e) {
      showToast('Failed to reset', 'error');
    } finally {
      resetBtn.disabled = false;
    }
  };

  previewBtn.onclick = () => {
    const text = textarea.value || msgType.defaultText;
    const preview = _substitutePreviewVars(text);
    _showPreviewModal(msgType.label, preview);
  };

  btnRow.appendChild(saveBtn);
  btnRow.appendChild(resetBtn);
  if (!msgType.noPreview) btnRow.appendChild(previewBtn);
  body.appendChild(btnRow);
}

function _makeToggle(checked, onChange) {
  const label = document.createElement('label');
  label.style.cssText = 'position:relative;display:inline-flex;width:44px;height:26px;cursor:pointer;flex-shrink:0;';
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.checked = checked;
  input.style.cssText = 'position:absolute;opacity:0;width:0;height:0';
  input.addEventListener('change', () => onChange(input.checked));
  const track = document.createElement('span');
  track.style.cssText = `position:absolute;inset:0;border-radius:999px;background:${checked ? 'var(--accent)' : 'var(--bg-overlay)'};transition:background var(--dur-normal);`;
  const thumb = document.createElement('span');
  thumb.style.cssText = `position:absolute;top:3px;left:${checked ? '21px' : '3px'};width:20px;height:20px;border-radius:50%;background:white;box-shadow:var(--shadow-sm);transition:left var(--dur-normal);`;
  input.addEventListener('change', () => {
    track.style.background = input.checked ? 'var(--accent)' : 'var(--bg-overlay)';
    thumb.style.left = input.checked ? '21px' : '3px';
  });
  track.appendChild(thumb);
  label.appendChild(input);
  label.appendChild(track);
  return label;
}

function _makeBtn(text, bg, color, border = false) {
  const btn = document.createElement('button');
  btn.textContent = text;
  btn.style.cssText = `
    padding: var(--sp-2) var(--sp-4);
    background: ${bg};
    color: ${color};
    border: ${border ? '1px solid var(--border)' : 'none'};
    border-radius: var(--r-lg);
    font-size: var(--text-sm);
    font-weight: var(--fw-medium);
    cursor: pointer;
    transition: all var(--dur-fast);
    white-space: nowrap;
  `;
  return btn;
}

async function _saveKey(chatId, initData, key, value) {
  const body = {};
  body[key] = (value === '' || value === null) ? null : value;
  await apiFetch(`/api/groups/${chatId}/text-config`, {
    method: 'PUT',
    body: body,
  });
}

function _markCustomized(header, isCustomized) {
  const titleDiv = header.querySelector('div > div:first-child');
  if (!titleDiv) return;
  const existing = titleDiv.querySelector('span[data-custom-badge]');
  if (existing) existing.remove();
  if (isCustomized) {
    const badge = document.createElement('span');
    badge.setAttribute('data-custom-badge', '1');
    badge.style.cssText = 'font-size:10px;padding:2px 6px;background:var(--accent-dim);color:var(--accent);border-radius:999px;margin-left:6px;font-weight:600;';
    badge.textContent = 'CUSTOM';
    titleDiv.appendChild(badge);
  }
}

function _substitutePreviewVars(text) {
  return text
    .replace(/\{mention\}/g, '<b>@John_Doe</b>')
    .replace(/\{first_name\}/g, 'John')
    .replace(/\{last_name\}/g, 'Doe')
    .replace(/\{fullname\}/g, 'John Doe')
    .replace(/\{username\}/g, 'john_doe')
    .replace(/\{chatname\}/g, 'My Group')
    .replace(/\{group_name\}/g, 'My Group')
    .replace(/\{count\}/g, '42')
    .replace(/\{reason\}/g, 'Spamming')
    .replace(/\{warn_count\}/g, '2')
    .replace(/\{warn_limit\}/g, '3')
    .replace(/\{duration\}/g, '1 hour')
    .replace(/\{timeout\}/g, '60')
    .replace(/\{channel_name\}/g, 'Our Channel')
    .replace(/\{channel_link\}/g, '[channel link]')
    .replace(/\{required\}/g, '5')
    .replace(/\{current\}/g, '3')
    .replace(/\{remaining\}/g, '2')
    .replace(/\{link\}/g, '[invite link]')
    .replace(/\{bar\}/g, '██████░░░░ 60%')
    .replace(/\n/g, '<br>');
}

function _showPreviewModal(title, htmlContent) {
  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position:fixed;inset:0;z-index:1000;
    background:#00000088;backdrop-filter:blur(4px);
    display:flex;align-items:center;justify-content:center;
    padding:var(--sp-4);
    animation:fade-in var(--dur-normal) var(--ease-out);
  `;
  const box = document.createElement('div');
  box.style.cssText = `
    background:var(--bg-elevated);
    border:1px solid var(--border);
    border-radius:var(--r-2xl);
    padding:var(--sp-5);
    width:100%;max-width:380px;
    box-shadow:var(--shadow-xl);
  `;
  box.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--sp-4)">
      <div style="font-weight:var(--fw-semibold);font-size:var(--text-base)">👁️ Preview — ${title}</div>
      <button id="preview-close" style="background:none;border:none;color:var(--text-muted);font-size:20px;cursor:pointer;">✕</button>
    </div>
    <div style="
      background:var(--bg-input);
      border:1px solid var(--border);
      border-radius:var(--r-lg);
      padding:var(--sp-4);
      font-size:var(--text-sm);
      line-height:1.6;
      color:var(--text-primary);
      white-space:pre-wrap;
      word-break:break-word;
    ">${htmlContent}</div>
    <div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:var(--sp-3)">
      ⚠️ Variables replaced with example values for preview
    </div>
  `;
  const close = () => overlay.remove();
  box.querySelector('#preview-close').onclick = close;
  overlay.onclick = e => { if (e.target === overlay) close(); };
  overlay.appendChild(box);
  document.body.appendChild(overlay);
}

function _renderButtonBuilder(container, textConfig, chatId) {
  const buttons = textConfig.welcome_buttons || [];

  const section = document.createElement('div');
  section.style.cssText = 'margin-top:var(--sp-3);padding-top:var(--sp-3);border-top:1px solid var(--border);';
  section.innerHTML = `
    <div style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);">
      Inline Buttons (optional)
    </div>
    <div id="btn-list" style="display:flex;flex-direction:column;gap:var(--sp-2);margin-bottom:var(--sp-2);"></div>
    <button id="add-btn-row" class="btn btn-secondary" style="font-size:var(--text-xs);width:100%;">+ Add Button</button>
  `;

  const btnList = section.querySelector('#btn-list');
  let currentButtons = buttons.map(b => ({ ...b }));

  const renderBtnList = () => {
    btnList.innerHTML = '';
    currentButtons.forEach((b, i) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;gap:var(--sp-2);align-items:center;';
      row.innerHTML = `
        <input class="input" value="${b.text || ''}" placeholder="Button label" style="flex:1;">
        <input class="input" value="${b.url || ''}" placeholder="https://..." style="flex:2;">
        <button style="background:none;border:none;color:var(--danger);cursor:pointer;font-size:16px;">×</button>
      `;
      row.querySelectorAll('input')[0].oninput = e => { currentButtons[i].text = e.target.value; };
      row.querySelectorAll('input')[1].oninput = e => { currentButtons[i].url = e.target.value; };
      row.querySelector('button').onclick = () => {
        currentButtons.splice(i, 1);
        renderBtnList();
        _saveButtons(chatId, currentButtons);
      };
      btnList.appendChild(row);
    });
  };

  section.querySelector('#add-btn-row').onclick = () => {
    currentButtons.push({ text: '', url: '' });
    renderBtnList();
  };

  section.addEventListener('focusout', () => _saveButtons(chatId, currentButtons));

  renderBtnList();
  container.appendChild(section);
}

async function _saveButtons(chatId, buttons) {
  const valid = buttons.filter(b => b.text && b.url);
  try {
    await apiFetch(`/api/groups/${chatId}/text-config`, {
      method: 'PUT',
      body: { welcome_buttons: valid },
    });
  } catch (e) {
    showToast('Failed to save buttons', 'error');
  }
}

async function _renderNotesSection(chatId) {
  const wrapper = document.createElement('div');

  let notes = [];
  try {
    const res = await apiFetch(`/api/groups/${chatId}/notes`);
    notes = res.data || res.notes || res || [];
  } catch (e) {
    notes = [];
  }

  const card = Card({
    title: '📝 Saved Notes',
    subtitle: 'Notes are retrieved with /note <name> or via inline mode',
  });

  const form = document.createElement('div');
  form.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);margin-bottom:var(--sp-3);';
  form.innerHTML = `
    <div style="display:flex;gap:var(--sp-2);">
      <input id="note-name" class="input" placeholder="Note name (e.g. rules, faq)" style="flex:1;">
    </div>
    <textarea id="note-content" class="input" placeholder="Note content..." style="min-height:60px;resize:vertical;font-family:inherit;"></textarea>
    <button id="note-save-btn" class="btn btn-primary" style="align-self:flex-start;">💾 Save Note</button>
  `;
  card.appendChild(form);

  const notesList = document.createElement('div');
  notesList.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-2);';

  const renderNotes = (noteData) => {
    notesList.innerHTML = '';
    if (!noteData.length) {
      notesList.innerHTML = '<div style="color:var(--text-muted);font-size:var(--text-sm);text-align:center;padding:var(--sp-3);">No notes yet</div>';
      return;
    }
    noteData.forEach(n => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:var(--sp-3);background:var(--bg-input);border-radius:var(--r-lg);border:1px solid var(--border);';
      row.innerHTML = `
        <div style="flex:1;min-width:0;">
          <span style="font-weight:var(--fw-semibold);font-size:var(--text-sm);">#${n.name}</span>
          <span style="color:var(--text-muted);font-size:var(--text-xs);margin-left:var(--sp-2);">${n.media_type ? '📎 ' + n.media_type : (n.content || '').slice(0, 60)}</span>
        </div>
        <button data-del="${n.name}" style="background:none;border:1px solid var(--danger);border-radius:var(--r-lg);padding:2px 8px;font-size:var(--text-xs);color:var(--danger);cursor:pointer;">Delete</button>
      `;
      row.querySelector('[data-del]').onclick = async () => {
        try {
          await apiFetch(`/api/groups/${chatId}/notes/${n.name}`, { method: 'DELETE' });
          showToast(`Note #${n.name} deleted`, 'success');
          notes = notes.filter(x => x.name !== n.name);
          renderNotes(notes);
        } catch (e) {
          showToast('Failed to delete note', 'error');
        }
      };
      notesList.appendChild(row);
    });
  };

  card.appendChild(notesList);
  renderNotes(notes);

  form.querySelector('#note-save-btn').onclick = async () => {
    const name = form.querySelector('#note-name').value.trim().toLowerCase();
    const content = form.querySelector('#note-content').value.trim();
    if (!name) { showToast('Note name required', 'error'); return; }
    try {
      await apiFetch(`/api/groups/${chatId}/notes`, {
        method: 'POST',
        body: { name, content },
      });
      showToast(`Note #${name} saved`, 'success');
      form.querySelector('#note-name').value = '';
      form.querySelector('#note-content').value = '';
      const res = await apiFetch(`/api/groups/${chatId}/notes`);
      notes = res.data || res.notes || res || [];
      renderNotes(notes);
    } catch (e) {
      showToast('Failed to save note', 'error');
    }
  };

  wrapper.appendChild(card);
  return wrapper;
}
