/**
 * src/pages/automod.js
 *
 * Full advanced automod management page - Vanilla JS version
 * Compatible with the existing Zustand + Vanilla JS Mini App foundation
 */

import { useStore } from '../store/index.js';

const store = useStore;

// ── Page ID for navigation ───────────────────────────────────────────
export const PAGE_ID = 'automod';

// ── Render function ─────────────────────────────────────────────────────────
export function renderAutomodPage(container) {
  const chatId = store.getState().activeChatId;
  if (!chatId) {
    container.innerHTML = `
      <div class="empty-state">
        <div style="font-size: 48px;">🔒</div>
        <h3>No Group Selected</h3>
        <p>Please select a group to manage automod settings</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div id="automod-loading" class="loading-screen">
      <div class="loading-logo">⚡</div>
      <p>Loading automod settings...</p>
    </div>
  `;

  loadAutomodData(chatId);
}

// ── Load data and render ────────────────────────────────────────────────────
async function loadAutomodData(chatId) {
  try {
    const [advResp, tmplResp, confResp] = await Promise.all([
      fetch(`/api/groups/${chatId}/automod/advanced`, authHeaders()),
      fetch(`/api/groups/${chatId}/automod/templates`, authHeaders()),
      fetch(`/api/groups/${chatId}/automod/conflicts`, authHeaders())
    ]);

    const data = await advResp.json();
    const templates = await tmplResp.json();
    const conflicts = await confResp.json();

    renderFullPage(data, templates, conflicts);
  } catch (error) {
    console.error('Failed to load automod data:', error);
    document.getElementById('automod-container').innerHTML = `
      <div class="empty-state">
        <div style="font-size: 48px;">❌</div>
        <h3>Failed to Load</h3>
        <p>${error.message}</p>
      </div>
    `;
  }
}

// ── Render full page ────────────────────────────────────────────────────────
function renderFullPage(data, templates, conflicts) {
  const container = document.getElementById('automod-container');
  container.innerHTML = '';

  // Conflicts banner
  if (conflicts.length > 0) {
    container.innerHTML += renderConflictsBanner(conflicts);
  }

  // Templates section
  container.innerHTML += renderTemplatesSection(templates);

  // Silent times section
  container.innerHTML += renderSilentTimesSection(data.silent_times || []);

  // Message controls section
  container.innerHTML += renderMessageControlsSection(data);

  // Rule priority section
  const ruleOrder = data.rule_order || DEFAULT_RULE_ORDER;
  container.innerHTML += renderRulePrioritySection(ruleOrder);

  // REGEX section
  container.innerHTML += renderRegexSection(data.regex_patterns || []);

  // Necessary words section
  container.innerHTML += renderNecessaryWordsSection(data.necessary_words || [], data.necessary_words_active);

  // Advanced settings section
  container.innerHTML += renderAdvancedSection(data);

  // Setup event listeners
  setupEventListeners(data, chatId);
}

// ── Conflict banner ─────────────────────────────────────────────────────────
function renderConflictsBanner(conflicts) {
  const conflictItems = conflicts.map(c => {
    const colors = {
      contradiction: 'bg-red-500/10 border-red-500/30 text-red-400',
      redundant: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
      impossible: 'bg-red-600/10 border-red-600/30 text-red-500'
    };
    const colorClass = colors[c.conflict.conflict_type] || colors.contradiction;
    return `
      <div class="flex items-start gap-2 p-3 rounded-xl border mb-2 text-sm ${colorClass}">
        <span style="font-size: 14px;">⚠️</span>
        <div>
          <p class="font-medium text-xs uppercase tracking-wide opacity-70">${c.conflict.conflict_type}</p>
          <p class="text-xs mt-0.5">${c.message}</p>
        </div>
      </div>
    `;
  }).join('');

  return `
    <div class="mb-4 p-3 bg-amber-500/10 border border-amber-500/30 rounded-2xl">
      <div class="flex items-center gap-2 mb-2">
        <span style="font-size: 16px;">⚠️</span>
        <p class="text-sm font-semibold text-amber-400">
          ${conflicts.length} rule conflict${conflicts.length > 1 ? 's' : ''} detected
        </p>
      </div>
      ${conflictItems}
    </div>
  `;
}

// ── Templates section ───────────────────────────────────────────────────────
function renderTemplatesSection(templates) {
  const TEMPLATE_ICONS = {
    Gaming: '🎮', Study: '📚', Crypto: '₿',
    'News Channel Group': '📰', Support: '💬', Strict: '🔒'
  };

  const cards = templates.map(t => `
    <div class="bg-[rgb(var(--surface-2))] rounded-xl p-3
                    border border-[rgb(var(--border))]" data-template-id="${t.id}">
      <div class="text-2xl mb-1">
        ${TEMPLATE_ICONS[t.name] || '⚙️'}
      </div>
      <p class="text-sm font-semibold text-[rgb(var(--text))]">
        ${t.name}
      </p>
      <p class="text-xs text-[rgb(var(--text-muted))] mt-0.5 mb-3">
        ${t.description}
      </p>
      <button class="template-use-btn w-full py-1.5 bg-accent/10 text-accent text-xs
                               font-semibold rounded-lg border border-accent/20
                               hover:bg-accent/20 transition-colors">
        Use Template
      </button>
    </div>
  `).join('');

  return `
    <div class="section mb-3">
      <div class="section-header" data-section="templates">
        <span style="font-size: 16px;">⚡</span>
        <span class="section-title">Rule Templates</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-content">
        <div class="grid grid-cols-2 md:grid-cols-3 gap-2">
          ${cards}
        </div>
      </div>
    </div>
  `;
}

// ── Silent times section ───────────────────────────────────────────────────
function renderSilentTimesSection(silentTimes) {
  const slots = [1, 2, 3].map(slot => {
    const st = silentTimes.find(s => s.slot === slot) || {};
    return `
      <div class="mb-4 p-3 bg-[rgb(var(--surface-2))] rounded-xl" data-slot="${slot}">
        <div class="flex items-center justify-between mb-2">
          <p class="text-sm font-medium text-[rgb(var(--text))]">
            Slot ${slot}
          </p>
          <button class="silent-toggle-btn text-xs px-2 py-1 rounded-lg font-medium ${st.is_active ? 'bg-accent/10 text-accent' : 'bg-[rgb(var(--surface-3))] text-[rgb(var(--text-muted))]'}">
            ${st.is_active ? 'Active' : 'Inactive'}
          </button>
        </div>
        <div class="flex gap-2">
          <div class="flex-1">
            <label class="text-xs text-[rgb(var(--text-muted))]">Start</label>
            <input type="time" class="time-input w-full mt-1 bg-[rgb(var(--surface-3))] rounded-lg px-3 py-2
                           text-sm text-[rgb(var(--text))] border border-[rgb(var(--border))]"
                   value="${st.start_time || '00:00'}" data-slot="${slot}" data-type="start">
          </div>
          <div class="flex-1">
            <label class="text-xs text-[rgb(var(--text-muted))]">End</label>
            <input type="time" class="time-input w-full mt-1 bg-[rgb(var(--surface-3))] rounded-lg px-3 py-2
                           text-sm text-[rgb(var(--text))] border border-[rgb(var(--border))]"
                   value="${st.end_time || '08:00'}" data-slot="${slot}" data-type="end">
          </div>
        </div>
      </div>
    `;
  }).join('');

  return `
    <div class="section mb-3">
      <div class="section-header" data-section="silent-times">
        <span style="font-size: 16px;">🕐</span>
        <span class="section-title">Silent Times</span>
        <span class="section-toggle">▶</span>
      </div>
      <div class="section-content" style="display: none;">
        ${slots}
      </div>
    </div>
  `;
}

// ── Message controls section ───────────────────────────────────────────────
function renderMessageControlsSection(data) {
  const settings = [
    { label: 'Min words',    key: 'min_words',  desc: '0 = disabled' },
    { label: 'Max words',    key: 'max_words',  desc: '0 = disabled' },
    { label: 'Min lines',    key: 'min_lines',  desc: '0 = disabled' },
    { label: 'Max lines',    key: 'max_lines',  desc: '0 = disabled' },
    { label: 'Min chars',    key: 'min_chars',  desc: '0 = disabled' },
    { label: 'Max chars',    key: 'max_chars',  desc: '0 = disabled' },
    { label: 'Max duplicates', key: 'duplicate_limit', desc: '0 = disabled' },
    { label: 'Duplicate window (mins)', key: 'duplicate_window_mins', desc: '' },
  ];

  const rows = settings.map(({ label, key, desc }) => `
    <div class="flex items-center justify-between py-2.5
                    border-b border-[rgb(var(--border))] last:border-0">
      <div>
        <p class="text-sm text-[rgb(var(--text))]">${label}</p>
        ${desc ? `<p class="text-xs text-[rgb(var(--text-muted))]">${desc}</p>` : ''}
      </div>
      <input type="number" min="0" class="number-input w-20 bg-[rgb(var(--surface-2))] rounded-lg px-3 py-1.5
                     text-sm text-[rgb(var(--text))] text-right
                     border border-[rgb(var(--border))]"
             value="${data[key] || 0}" data-key="${key}">
    </div>
  `).join('');

  return `
    <div class="section mb-3">
      <div class="section-header" data-section="message-controls">
        <span style="font-size: 16px;">🛡️</span>
        <span class="section-title">Message Controls</span>
        <span class="section-toggle">▶</span>
      </div>
      <div class="section-content" style="display: none;">
        ${rows}
      </div>
    </div>
  `;
}

// ── Rule priority section ────────────────────────────────────────────────
function renderRulePrioritySection(ruleOrder) {
  const items = ruleOrder.map(id => {
    const label = RULE_LABELS[id] || id;
    return `
      <div class="rule-priority-item flex items-center gap-3 py-2.5 px-3
                         bg-[rgb(var(--surface-2))] rounded-xl mb-2
                         border border-[rgb(var(--border))]" draggable="true" data-rule-id="${id}">
        <span style="cursor: grab; font-size: 16px; color: rgb(var(--text-subtle));">☰</span>
        <span class="text-sm text-[rgb(var(--text))]">${label}</span>
      </div>
    `;
  }).join('');

  return `
    <div class="section mb-3">
      <div class="section-header" data-section="rule-priority">
        <span style="font-size: 16px;">☰</span>
        <span class="section-title">Rule Priority (Drag to reorder)</span>
        <span class="section-toggle">▶</span>
      </div>
      <div class="section-content" style="display: none;">
        <p class="text-xs text-[rgb(var(--text-muted))] mb-3">
          Rules are evaluated top to bottom. First match wins.
        </p>
        <div id="rule-priority-list">
          ${items}
        </div>
      </div>
    </div>
  `;
}

// ── REGEX section ─────────────────────────────────────────────────────────
function renderRegexSection(patterns) {
  const patternItems = patterns.map(p => `
    <div class="flex items-center gap-2 p-3 bg-[rgb(var(--surface-2))] rounded-xl
                      border border-[rgb(var(--border))]" data-pattern="${p.pattern}">
      <code class="flex-1 text-xs text-accent font-mono truncate">${p.pattern}</code>
      <span class="text-xs px-2 py-0.5 rounded-lg
                       bg-[rgb(var(--surface-3))] text-[rgb(var(--text-muted))]">
        ${p.penalty}
      </span>
      <button class="regex-remove-btn text-red-400 hover:text-red-300">
        🗑️
      </button>
    </div>
  `).join('');

  return `
    <div class="section mb-3">
      <div class="section-header" data-section="regex">
        <span style="font-size: 16px;">🔍</span>
        <span class="section-title">REGEX Patterns</span>
        <span class="section-toggle">▶</span>
      </div>
      <div class="section-content" style="display: none;">
        <div class="space-y-3">
          ${patternItems}
          <div class="p-3 bg-[rgb(var(--surface-2))] rounded-xl space-y-2">
            <input id="regex-input" placeholder="Pattern: ^\d{10}$"
                   class="w-full bg-[rgb(var(--surface-3))] rounded-lg px-3 py-2
                          text-sm font-mono text-[rgb(var(--text))]
                          border border-[rgb(var(--border))]
                          placeholder-[rgb(var(--text-subtle))]">
            <input id="regex-test-input" placeholder="Test string..."
                   class="w-full bg-[rgb(var(--surface-3))] rounded-lg px-3 py-2
                          text-sm text-[rgb(var(--text))]
                          border border-[rgb(var(--border))]
                          placeholder-[rgb(var(--text-subtle))]">
            <div id="regex-result" class="regex-result" style="display: none;"></div>
            <div class="flex gap-2">
              <button id="regex-test-btn" class="flex-1 py-2 bg-[rgb(var(--surface-3))] rounded-lg
                         text-xs text-[rgb(var(--text-muted))] font-medium">
                Test
              </button>
              <button id="regex-add-btn" class="flex-1 py-2 bg-accent text-white rounded-lg
                         text-xs font-bold">
                Add Pattern
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

// ── Necessary words section ───────────────────────────────────────────────
function renderNecessaryWordsSection(words, isActive) {
  const wordTags = words.map(w => `
    <div class="flex items-center gap-1 px-3 py-1.5
                bg-accent/10 border border-accent/20 rounded-xl" data-word="${w}">
      <span class="text-sm text-accent">${w}</span>
      <button class="word-remove-btn text-accent/60 hover:text-accent">✕</button>
    </div>
  `).join('');

  return `
    <div class="section mb-3">
      <div class="section-header" data-section="necessary-words">
        <span style="font-size: 16px;">🛡️</span>
        <span class="section-title">Necessary Words</span>
        <span class="section-toggle">▶</span>
      </div>
      <div class="section-content" style="display: none;">
        <div class="toggle-row mb-3">
          <div>
            <p class="text-sm text-[rgb(var(--text))]">Active</p>
            <p class="text-xs text-[rgb(var(--text-muted))]">
              Every message must contain at least one of these words
            </p>
          </div>
          <button id="necessary-active-toggle"
                  class="toggle-btn ${isActive ? 'bg-accent' : 'bg-[rgb(var(--surface-3))]'}">
            <div class="toggle-dot" style="transform: translateX(${isActive ? '20px' : '2px'});"></div>
          </button>
        </div>
        <div class="flex flex-wrap gap-2" id="necessary-words-list">
          ${wordTags}
        </div>
        <div class="flex gap-2 mt-3">
          <input id="new-word-input" placeholder="Add required word..."
                 class="flex-1 bg-[rgb(var(--surface-2))] rounded-xl px-3 py-2
                        text-sm text-[rgb(var(--text))] border border-[rgb(var(--border))]
                        placeholder-[rgb(var(--text-subtle))]">
          <button id="add-word-btn" class="px-4 py-2 bg-accent text-white rounded-xl text-sm font-bold">
            ➕
          </button>
        </div>
      </div>
    </div>
  `;
}

// ── Advanced section ───────────────────────────────────────────────────────
function renderAdvancedSection(data) {
  return `
    <div class="section mb-3">
      <div class="section-header" data-section="advanced">
        <span style="font-size: 16px;">🛡️</span>
        <span class="section-title">Advanced Settings</span>
        <span class="section-toggle">▶</span>
      </div>
      <div class="section-content" style="display: none;">
        <div class="toggle-row" data-setting="self_destruct_enabled">
          <div>
            <p class="text-sm text-[rgb(var(--text))]">Self-destruct bot messages</p>
            <p class="text-xs text-[rgb(var(--text-muted))]">
              Bot messages auto-delete after set time
            </p>
          </div>
          <button class="toggle-btn ${data.self_destruct_enabled ? 'bg-accent' : 'bg-[rgb(var(--surface-3))]'}">
            <div class="toggle-dot" style="transform: translateX(${data.self_destruct_enabled ? '20px' : '2px'});"></div>
          </button>
        </div>
        ${data.self_destruct_enabled ? `
          <div class="flex items-center justify-between py-2">
            <span class="text-sm text-[rgb(var(--text-muted))]">
              Delete after (minutes)
            </span>
            <input type="number" min="1" max="60"
                   class="number-input w-20 bg-[rgb(var(--surface-2))] rounded-lg px-3 py-1.5
                          text-sm text-[rgb(var(--text))] text-right
                          border border-[rgb(var(--border))]"
                   value="${data.self_destruct_minutes || 2}" data-key="self_destruct_minutes">
          </div>
        ` : ''}
        <div class="toggle-row" data-setting="lock_admins">
          <div>
            <p class="text-sm text-[rgb(var(--text))]">Lock admins</p>
            <p class="text-xs text-[rgb(var(--text-muted))]">
              Apply all rules to admins too
            </p>
          </div>
          <button class="toggle-btn ${data.lock_admins ? 'bg-accent' : 'bg-[rgb(var(--surface-3))]'}">
            <div class="toggle-dot" style="transform: translateX(${data.lock_admins ? '20px' : '2px'});"></div>
          </button>
        </div>
        <div class="toggle-row" data-setting="unofficial_tg_lock">
          <div>
            <p class="text-sm text-[rgb(var(--text))]">Block unofficial Telegram apps</p>
            <p class="text-xs text-[rgb(var(--text-muted))]">
              Ban accounts sending via unofficial clients
            </p>
          </div>
          <button class="toggle-btn ${data.unofficial_tg_lock ? 'bg-accent' : 'bg-[rgb(var(--surface-3))]'}">
            <div class="toggle-dot" style="transform: translateX(${data.unofficial_tg_lock ? '20px' : '2px'});"></div>
          </button>
        </div>
        <div class="toggle-row" data-setting="bot_inviter_ban">
          <div>
            <p class="text-sm text-[rgb(var(--text))]">Ban bot inviters</p>
            <p class="text-xs text-[rgb(var(--text-muted))]">
              Ban whoever adds a bot to the group
            </p>
          </div>
          <button class="toggle-btn ${data.bot_inviter_ban ? 'bg-accent' : 'bg-[rgb(var(--surface-3))]'}">
            <div class="toggle-dot" style="transform: translateX(${data.bot_inviter_ban ? '20px' : '2px'});"></div>
          </button>
        </div>
        <div class="toggle-row" data-setting="regex_active">
          <div>
            <p class="text-sm text-[rgb(var(--text))]">REGEX active</p>
            <p class="text-xs text-[rgb(var(--text-muted))]">
              Apply REGEX pattern checks
            </p>
          </div>
          <button class="toggle-btn ${data.regex_active ? 'bg-accent' : 'bg-[rgb(var(--surface-3))]'}">
            <div class="toggle-dot" style="transform: translateX(${data.regex_active ? '20px' : '2px'});"></div>
          </button>
        </div>
      </div>
    </div>
  `;
}

// ── Setup event listeners ─────────────────────────────────────────────────
function setupEventListeners(data, chatId) {
  // Section toggles
  document.querySelectorAll('.section-header').forEach(header => {
    header.addEventListener('click', () => {
      const content = header.nextElementSibling;
      const toggle = header.querySelector('.section-toggle');
      const isOpen = content.style.display !== 'none';
      content.style.display = isOpen ? 'none' : 'block';
      toggle.textContent = isOpen ? '▶' : '▼';
    });
  });

  // Template apply buttons
  document.querySelectorAll('.template-use-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const templateId = btn.closest('[data-template-id]').dataset.templateId;
      await applyTemplate(templateId, chatId);
    });
  });

  // Silent time toggles
  document.querySelectorAll('.silent-toggle-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const slot = btn.closest('[data-slot]').dataset.slot;
      await saveSetting(chatId, 'silent_times', (data.silent_times || []).map(s => {
        if (s.slot === parseInt(slot)) {
          return { ...s, is_active: !s.is_active };
        }
        return s;
      }));
    });
  });

  // Silent time inputs
  document.querySelectorAll('.time-input').forEach(input => {
    input.addEventListener('change', async () => {
      const slot = parseInt(input.dataset.slot);
      const type = input.dataset.type;
      const silentTimes = data.silent_times || [];
      const existing = silentTimes.find(s => s.slot === slot) || {};
      const updated = { ...existing, slot, [type]: input.value };
      await saveSetting(chatId, 'silent_times', [
        ...silentTimes.filter(s => s.slot !== slot),
        updated
      ]);
    });
  });

  // Number inputs
  document.querySelectorAll('.number-input').forEach(input => {
    input.addEventListener('change', async () => {
      const key = input.dataset.key;
      const value = parseInt(input.value) || 0;
      await saveSetting(chatId, key, value);
    });
  });

  // REGEX test
  const regexInput = document.getElementById('regex-input');
  const regexTestInput = document.getElementById('regex-test-input');
  const regexTestBtn = document.getElementById('regex-test-btn');
  const regexResult = document.getElementById('regex-result');

  if (regexTestBtn) {
    regexTestBtn.addEventListener('click', () => {
      try {
        const match = new RegExp(regexInput.value, 'i').test(regexTestInput.value);
        regexResult.style.display = 'flex';
        regexResult.className = `regex-result flex items-center gap-2 text-sm ${match ? 'text-green-400' : 'text-red-400'}`;
        regexResult.innerHTML = `
          ${match ? '✅' : '❌'} ${match ? 'Match' : 'No match'}
        `;
      } catch {
        regexResult.style.display = 'none';
      }
    });
  }

  // REGEX add
  const regexAddBtn = document.getElementById('regex-add-btn');
  if (regexAddBtn) {
    regexAddBtn.addEventListener('click', async () => {
      if (!regexInput.value.trim()) return;
      await saveSetting(chatId, 'add_regex', regexInput.value.trim());
      regexInput.value = '';
      showToast('Pattern added', 'success');
      // Reload
      const adv = await fetch(`/api/groups/${chatId}/automod/advanced`, authHeaders()).then(r => r.json());
      document.getElementById('automod-container').innerHTML = '';
      renderFullPage(adv, templates, conflicts);
    });
  }

  // REGEX remove
  document.querySelectorAll('.regex-remove-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const pattern = btn.closest('[data-pattern]').dataset.pattern;
      await saveSetting(chatId, 'remove_regex', pattern);
      showToast('Pattern removed', 'success');
      // Reload
      const adv = await fetch(`/api/groups/${chatId}/automod/advanced`, authHeaders()).then(r => r.json());
      document.getElementById('automod-container').innerHTML = '';
      renderFullPage(adv, templates, conflicts);
    });
  });

  // Necessary words toggle
  const necActiveToggle = document.getElementById('necessary-active-toggle');
  if (necActiveToggle) {
    necActiveToggle.addEventListener('click', async () => {
      const newValue = !(necActiveToggle.classList.contains('bg-accent'));
      await saveSetting(chatId, 'necessary_words_active', newValue);
      const adv = await fetch(`/api/groups/${chatId}/automod/advanced`, authHeaders()).then(r => r.json());
      document.getElementById('automod-container').innerHTML = '';
      renderFullPage(adv, templates, conflicts);
    });
  }

  // Word remove
  document.querySelectorAll('.word-remove-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const word = btn.closest('[data-word]').dataset.word;
      const words = data.necessary_words || [];
      await saveSetting(chatId, 'necessary_words', words.filter(w => w !== word));
      const adv = await fetch(`/api/groups/${chatId}/automod/advanced`, authHeaders()).then(r => r.json());
      document.getElementById('automod-container').innerHTML = '';
      renderFullPage(adv, templates, conflicts);
    });
  });

  // Word add
  const newWordInput = document.getElementById('new-word-input');
  const addWordBtn = document.getElementById('add-word-btn');
  if (addWordBtn && newWordInput) {
    const handleAddWord = async () => {
      const word = newWordInput.value.trim();
      if (!word) return;
      const words = [...(data.necessary_words || []), word];
      await saveSetting(chatId, 'necessary_words', words);
      newWordInput.value = '';
      showToast('Required word added', 'success');
      const adv = await fetch(`/api/groups/${chatId}/automod/advanced`, authHeaders()).then(r => r.json());
      document.getElementById('automod-container').innerHTML = '';
      renderFullPage(adv, templates, conflicts);
    };
    addWordBtn.addEventListener('click', handleAddWord);
    newWordInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleAddWord();
    });
  }

  // Advanced toggles
  document.querySelectorAll('[data-setting]').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      if (e.target.tagName === 'INPUT') return; // Don't trigger for number inputs
      const toggleBtn = btn.querySelector('.toggle-btn');
      const key = btn.dataset.setting;
      const newValue = !toggleBtn.classList.contains('bg-accent');
      await saveSetting(chatId, key, newValue);
      const adv = await fetch(`/api/groups/${chatId}/automod/advanced`, authHeaders()).then(r => r.json());
      document.getElementById('automod-container').innerHTML = '';
      renderFullPage(adv, templates, conflicts);
    });
  });

  // Rule priority drag and drop
  setupRulePriorityDragDrop(chatId);
}

// ── Rule priority drag and drop ───────────────────────────────────────
function setupRulePriorityDragDrop(chatId) {
  const container = document.getElementById('rule-priority-list');
  if (!container) return;

  let draggedItem = null;

  container.querySelectorAll('.rule-priority-item').forEach(item => {
    item.addEventListener('dragstart', (e) => {
      draggedItem = item;
      item.style.opacity = '0.5';
    });

    item.addEventListener('dragend', () => {
      item.style.opacity = '1';
      draggedItem = null;
    });

    item.addEventListener('dragover', (e) => {
      e.preventDefault();
    });

    item.addEventListener('drop', async (e) => {
      e.preventDefault();
      if (draggedItem === item) return;

      const items = [...container.querySelectorAll('.rule-priority-item')];
      const oldIndex = items.indexOf(draggedItem);
      const newIndex = items.indexOf(item);

      // Swap elements
      if (oldIndex < newIndex) {
        item.parentNode.insertBefore(draggedItem, item.nextSibling);
      } else {
        item.parentNode.insertBefore(draggedItem, item);
      }

      // Get new order
      const newOrder = [...container.querySelectorAll('.rule-priority-item')]
        .map(i => i.dataset.ruleId);

      // Save to server
      await fetch(`/api/groups/${chatId}/automod/rule-priority`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ order: newOrder })
      });

      showToast('Rule order saved', 'success');
    });
  });
}

// ── Save setting helper ─────────────────────────────────────────────────────
async function saveSetting(chatId, key, value) {
  const updates = {};
  updates[key] = value;

  await fetch(`/api/groups/${chatId}/automod/advanced`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(updates)
  });

  // Refresh conflicts
  const conflicts = await fetch(`/api/groups/${chatId}/automod/conflicts`, authHeaders())
    .then(r => r.json());
}

// ── Apply template ─────────────────────────────────────────────────────────
async function applyTemplate(templateId, chatId) {
  await fetch(`/api/groups/${chatId}/automod/templates/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ template_id: templateId })
  });
  showToast('Template applied!', 'success');
  // Reload
  const adv = await fetch(`/api/groups/${chatId}/automod/advanced`, authHeaders()).then(r => r.json());
  document.getElementById('automod-container').innerHTML = '';
  const templates = await fetch(`/api/groups/${chatId}/automod/templates`, authHeaders()).then(r => r.json());
  const conflicts = await fetch(`/api/groups/${chatId}/automod/conflicts`, authHeaders()).then(r => r.json());
  renderFullPage(adv, templates, conflicts);
}

// ── Auth headers helper ─────────────────────────────────────────────────────
function authHeaders() {
  const tg = window.Telegram?.WebApp;
  return {
    'X-Telegram-Auth': tg?.initData || ''
  };
}

// ── Toast helper ───────────────────────────────────────────────────────────────
function showToast(message, type) {
  // Simple toast implementation
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 12px 24px;
    background: ${type === 'success' ? '#10b981' : '#ef4444'};
    color: white;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 500;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    z-index: 9999;
    animation: slideIn 0.3s ease-out;
  `;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// ── Constants ─────────────────────────────────────────────────────────────────────

const DEFAULT_RULE_ORDER = [
  'link','website','username','hashtag','photo','video',
  'sticker','gif','forward','forward_channel','text','voice',
  'audio','file','software','poll','slash','no_caption',
  'emoji_only','emoji','game','english','arabic_farsi',
  'reply','external_reply','bot','unofficial_tg','spoiler'
];

const RULE_LABELS = {
  link:             '🔗 Telegram Links',
  website:          '🌐 External Websites',
  username:         '@ Usernames',
  hashtag:          '# Hashtags',
  photo:            '📷 Photos',
  video:            '🎬 Videos',
  sticker:          '🎭 Stickers',
  gif:              'GIF Animations',
  forward:          '↩️ Forwarded Messages',
  forward_channel:  '📢 Forwards from Channels',
  text:             '💬 Text Messages',
  voice:            '🎤 Voice Messages',
  audio:            '🎵 Audio Files',
  file:             '📄 Files',
  software:         '📱 APK/Software',
  poll:             '📊 Polls',
  slash:            '/ Bot Commands',
  no_caption:       '🖼 Posts without Caption',
  emoji_only:       '😀 Emoji-only Messages',
  emoji:            '😊 Any Emoji',
  game:             '🎮 Games',
  english:          '🔤 English Text',
  arabic_farsi:     'عربی Arabic/Farsi',
  reply:            '↩ Replies',
  external_reply:   '↩ External Replies',
  bot:              '🤖 Bot Additions',
  unofficial_tg:    '📱 Unofficial Telegram',
  spoiler:          '|| Spoilers',
};
