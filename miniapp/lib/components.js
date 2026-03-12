/**
 * miniapp/lib/components.js
 *
 * Pure JS component factory functions.
 * Each returns a DOM element.
 * No framework dependency.
 *
 * Components:
 *   Card(props)
 *   Toggle(props)
 *   Badge(props)
 *   Avatar(props)
 *   Skeleton(props)
 *   Toast(message, type)
 *   Modal(props)
 *   BottomSheet(props)
 *   StatCard(props)
 *   SectionHeader(props)
 *   EmptyState(props)
 *   Spinner(size)
 *   ProgressBar(value, max)
 *   TabBar(tabs, active, onChange)
 *   SearchInput(props)
 *   MemberRow(member, actions)
 *   RuleRow(rule, onToggle, onDrag)
 */

// ── Card ─────────────────────────────────────────────────────────────────
export function Card({ title, subtitle, children, actions, glass = false } = {}) {
  const el = document.createElement('div');
  el.className = `card${glass ? ' card--glass' : ''}`;
  el.style.cssText = `
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--r-xl);
    padding: var(--sp-4);
    margin-bottom: var(--sp-3);
    transition: border-color var(--dur-fast);
  `;
  if (title) {
    const h = document.createElement('div');
    h.style.cssText = `
      display: flex; align-items: center;
      justify-content: space-between;
      margin-bottom: ${subtitle || children ? 'var(--sp-3)' : '0'};
    `;
    const t = document.createElement('div');
    t.innerHTML = `
      <div style="font-weight:var(--fw-semibold);font-size:var(--text-base);
                  color:var(--text-primary)">${title}</div>
      ${subtitle ? `<div style="font-size:var(--text-sm);color:var(--text-muted);
                               margin-top:2px">${subtitle}</div>` : ''}
    `;
    h.appendChild(t);
    if (actions) h.appendChild(actions);
    el.appendChild(h);
  }
  if (children) {
    if (typeof children === 'string') el.insertAdjacentHTML('beforeend', children);
    else el.appendChild(children);
  }
  return el;
}


// ── Toggle ───────────────────────────────────────────────────────────────
export function Toggle({ checked = false, onChange, disabled = false } = {}) {
  const wrap = document.createElement('label');
  wrap.style.cssText = `
    position: relative; display: inline-flex;
    width: 44px; height: 26px; cursor: ${disabled ? 'not-allowed' : 'pointer'};
    opacity: ${disabled ? '0.5' : '1'};
    flex-shrink: 0;
  `;
  const input = document.createElement('input');
  input.type    = 'checkbox';
  input.checked = checked;
  input.disabled = disabled;
  input.style.cssText = 'position:absolute;opacity:0;width:0;height:0';
  input.addEventListener('change', () => onChange?.(input.checked));

  const track = document.createElement('span');
  track.style.cssText = `
    position: absolute; inset: 0;
    border-radius: var(--r-full);
    background: ${checked ? 'var(--accent)' : 'var(--bg-overlay)'};
    transition: background var(--dur-normal) var(--ease-out);
  `;
  const thumb = document.createElement('span');
  thumb.style.cssText = `
    position: absolute; top: 3px;
    left: ${checked ? '21px' : '3px'};
    width: 20px; height: 20px;
    border-radius: 50%;
    background: white;
    box-shadow: var(--shadow-sm);
    transition: left var(--dur-normal) var(--ease-out),
                background var(--dur-normal);
  `;
  input.addEventListener('change', () => {
    track.style.background = input.checked ? 'var(--accent)' : 'var(--bg-overlay)';
    thumb.style.left       = input.checked ? '21px' : '3px';
  });
  track.appendChild(thumb);
  wrap.appendChild(input);
  wrap.appendChild(track);
  return wrap;
}


// ── Badge ────────────────────────────────────────────────────────────────
export function Badge(text, variant = 'default') {
  const colors = {
    default: 'background:var(--bg-overlay);color:var(--text-secondary)',
    success: 'background:var(--success-dim);color:var(--success)',
    danger:  'background:var(--danger-dim);color:var(--danger)',
    warning: 'background:var(--warning-dim);color:var(--warning)',
    info:    'background:var(--info-dim);color:var(--info)',
    accent:  'background:var(--accent-dim);color:var(--accent)',
  };
  const el = document.createElement('span');
  el.style.cssText = `
    display: inline-flex; align-items: center;
    padding: 2px 8px; border-radius: var(--r-full);
    font-size: var(--text-xs); font-weight: var(--fw-semibold);
    ${colors[variant] || colors.default};
  `;
  el.textContent = text;
  return el;
}


// ── Avatar ───────────────────────────────────────────────────────────────
export function Avatar({ name = '', src = '', size = 36, online = false } = {}) {
  const wrap = document.createElement('div');
  wrap.style.cssText = `
    position: relative; width: ${size}px; height: ${size}px;
    border-radius: 50%; flex-shrink: 0;
  `;
  if (src) {
    const img = document.createElement('img');
    img.src   = src;
    img.style.cssText = `width:100%;height:100%;border-radius:50%;object-fit:cover`;
    wrap.appendChild(img);
  } else {
    const initials = name.split(' ').map(w => w[0]).join('').slice(0,2).toUpperCase();
    const hue = name.split('').reduce((a,c) => a + c.charCodeAt(0), 0) % 360;
    const bg  = document.createElement('div');
    bg.style.cssText = `
      width:100%;height:100%;border-radius:50%;
      background: hsl(${hue},60%,35%);
      display:flex;align-items:center;justify-content:center;
      font-size:${Math.round(size * 0.38)}px;
      font-weight:var(--fw-bold);color:white;
    `;
    bg.textContent = initials;
    wrap.appendChild(bg);
  }
  if (online) {
    const dot = document.createElement('div');
    dot.style.cssText = `
      position:absolute;bottom:1px;right:1px;
      width:${Math.round(size*0.28)}px;height:${Math.round(size*0.28)}px;
      border-radius:50%;background:var(--success);
      border:2px solid var(--bg-card);
    `;
    wrap.appendChild(dot);
  }
  return wrap;
}


// ── Skeleton ─────────────────────────────────────────────────────────────
export function Skeleton({ w = '100%', h = '16px', r = 'var(--r-md)' } = {}) {
  const el = document.createElement('div');
  el.style.cssText = `
    width:${w};height:${h};border-radius:${r};
    background: linear-gradient(
      90deg,
      var(--bg-elevated) 25%,
      var(--bg-overlay) 50%,
      var(--bg-elevated) 75%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
  `;
  return el;
}


// ── Toast ────────────────────────────────────────────────────────────────
let _toastContainer = null;
function _getToastContainer() {
  if (!_toastContainer) {
    _toastContainer = document.createElement('div');
    _toastContainer.style.cssText = `
      position: fixed; bottom: calc(var(--bottomnav-h) + 16px); left: 50%;
      transform: translateX(-50%);
      display: flex; flex-direction: column-reverse; gap: 8px;
      z-index: 9999; pointer-events: none;
      width: min(380px, calc(100vw - 32px));
    `;
    document.body.appendChild(_toastContainer);
  }
  return _toastContainer;
}

export function showToast(message, type = 'default', duration = 3000) {
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️', default: '' };
  const colors = {
    success: 'var(--success)', error: 'var(--danger)',
    warning: 'var(--warning)', info: 'var(--info)', default: 'var(--accent)'
  };
  const toast = document.createElement('div');
  toast.style.cssText = `
    display: flex; align-items: center; gap: var(--sp-3);
    padding: var(--sp-3) var(--sp-4);
    background: var(--bg-elevated);
    border: 1px solid ${colors[type] || colors.default}44;
    border-left: 3px solid ${colors[type] || colors.default};
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-lg);
    font-size: var(--text-sm);
    color: var(--text-primary);
    pointer-events: auto;
    animation: toast-in var(--dur-slow) var(--ease-out) forwards;
  `;
  toast.innerHTML = `
    ${icons[type] ? `<span>${icons[type]}</span>` : ''}
    <span style="flex:1">${message}</span>
  `;
  const container = _getToastContainer();
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = `toast-out var(--dur-normal) var(--ease-in) forwards`;
    setTimeout(() => toast.remove(), 200);
  }, duration);
}


// ── Modal ────────────────────────────────────────────────────────────────
export function Modal({ title, content, actions, onClose } = {}) {
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
    padding:var(--sp-6);
    width:100%;max-width:420px;
    box-shadow:var(--shadow-xl);
    animation:scale-in var(--dur-slow) var(--ease-out);
  `;
  box.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--sp-4)">
      <h3 style="font-size:var(--text-lg);font-weight:var(--fw-bold)">${title||''}</h3>
      <button id="modal-close" style="
        background:none;border:none;color:var(--text-muted);
        font-size:20px;cursor:pointer;padding:4px;border-radius:var(--r-sm)
      ">✕</button>
    </div>
    <div id="modal-content"></div>
    ${actions ? `<div id="modal-actions" style="display:flex;gap:var(--sp-2);margin-top:var(--sp-5);justify-content:flex-end"></div>` : ''}
  `;
  if (content) {
    const mc = box.querySelector('#modal-content');
    if (typeof content === 'string') mc.innerHTML = content;
    else mc.appendChild(content);
  }
  if (actions) {
    const ma = box.querySelector('#modal-actions');
    actions.forEach(a => ma.appendChild(a));
  }
  const close = () => { overlay.remove(); onClose?.(); };
  box.querySelector('#modal-close').onclick = close;
  overlay.onclick = e => { if (e.target === overlay) close(); };
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  return { el: overlay, close };
}


// ── Bottom Sheet ─────────────────────────────────────────────────────────
export function BottomSheet({ title, content, onClose } = {}) {
  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position:fixed;inset:0;z-index:1000;
    background:#00000088;
    display:flex;align-items:flex-end;
  `;
  const sheet = document.createElement('div');
  sheet.style.cssText = `
    background:var(--bg-elevated);
    border-top:1px solid var(--border);
    border-radius:var(--r-2xl) var(--r-2xl) 0 0;
    padding:var(--sp-6);
    width:100%;max-height:85dvh;
    overflow-y:auto;
    animation:sheet-up var(--dur-slow) var(--ease-out);
  `;
  sheet.innerHTML = `
    <div style="width:40px;height:4px;background:var(--border-strong);
                border-radius:var(--r-full);margin:0 auto var(--sp-5)"></div>
    ${title ? `<h3 style="font-size:var(--text-lg);font-weight:var(--fw-bold);
                          margin-bottom:var(--sp-4)">${title}</h3>` : ''}
    <div id="sheet-content"></div>
  `;
  const sc = sheet.querySelector('#sheet-content');
  if (typeof content === 'string') sc.innerHTML = content;
  else if (content) sc.appendChild(content);
  const close = () => {
    sheet.style.animation = `sheet-down var(--dur-normal) var(--ease-in) forwards`;
    setTimeout(() => { overlay.remove(); onClose?.(); }, 200);
  };
  overlay.onclick = e => { if (e.target === overlay) close(); };
  overlay.appendChild(sheet);
  document.body.appendChild(overlay);
  return { el: overlay, close };
}


// ── Stat Card ────────────────────────────────────────────────────────────
export function StatCard({ label, value, delta, icon, color = 'accent' } = {}) {
  const el = document.createElement('div');
  el.style.cssText = `
    background:var(--bg-card);
    border:1px solid var(--border);
    border-radius:var(--r-xl);
    padding:var(--sp-4);
    display:flex;flex-direction:column;gap:var(--sp-2);
  `;
  const isPos = delta > 0;
  const isNeg = delta < 0;
  el.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between">
      <span style="font-size:var(--text-sm);color:var(--text-muted)">${label}</span>
      ${icon ? `<span style="font-size:20px">${icon}</span>` : ''}
    </div>
    <div style="font-size:var(--text-2xl);font-weight:var(--fw-bold);
                color:var(--${color})">${value}</div>
    ${delta !== undefined ? `
      <div style="font-size:var(--text-xs);
                  color:${isPos?'var(--success)':isNeg?'var(--danger)':'var(--text-muted)'}">
        ${isPos?'▲':isNeg?'▼':'─'} ${Math.abs(delta)}% vs yesterday
      </div>` : ''}
  `;
  return el;
}


// ── Member Row ───────────────────────────────────────────────────────────
export function MemberRow({ member, actions = [], selectable = false, onSelect } = {}) {
  const row = document.createElement('div');
  row.style.cssText = `
    display:flex;align-items:center;gap:var(--sp-3);
    padding:var(--sp-3) var(--sp-4);
    border-radius:var(--r-lg);
    cursor:pointer;
    transition:background var(--dur-fast);
    position:relative;
  `;
  row.onmouseenter = () => row.style.background = 'var(--bg-hover)';
  row.onmouseleave = () => row.style.background = 'transparent';

  let checkbox = null;
  if (selectable) {
    checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'member-checkbox';
    checkbox.style.cssText = `width:16px;height:16px;accent-color:var(--accent);flex-shrink:0`;
    checkbox.onclick = e => { e.stopPropagation(); onSelect?.(member, checkbox.checked); };
    row.appendChild(checkbox);
  }

  row.appendChild(Avatar({ name: member.name || member.first_name, size: 38 }));

  const info = document.createElement('div');
  info.style.cssText = 'flex:1;min-width:0';
  info.innerHTML = `
    <div style="font-weight:var(--fw-medium);font-size:var(--text-sm);
                white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
      ${member.name || `${member.first_name||''} ${member.last_name||''}`.trim()}
    </div>
    <div style="font-size:var(--text-xs);color:var(--text-muted)">
      ${member.username ? `@${member.username}` : `ID: ${member.id}`}
    </div>
  `;
  row.appendChild(info);

  if (member.warns > 0) row.appendChild(Badge(`${member.warns} warns`, 'warning'));
  if (member.is_approved) row.appendChild(Badge('approved', 'success'));

  if (actions.length) {
    const btns = document.createElement('div');
    btns.style.cssText = 'display:flex;gap:var(--sp-1)';
    actions.forEach(({ icon, label, onClick, variant = 'default' }) => {
      const btn = document.createElement('button');
      const colors = { danger: 'var(--danger)', success: 'var(--success)', default: 'var(--text-muted)' };
      btn.style.cssText = `
        background:none;border:none;cursor:pointer;
        color:${colors[variant]};font-size:16px;
        padding:var(--sp-2);border-radius:var(--r-sm);
        transition:background var(--dur-fast);
      `;
      btn.title  = label;
      btn.textContent = icon;
      btn.onclick = e => { e.stopPropagation(); onClick?.(member); };
      btns.appendChild(btn);
    });
    row.appendChild(btns);
  }

  row.dataset.memberId = member.id;
  return row;
}


// ── Rule Row (draggable) ─────────────────────────────────────────────────
export function RuleRow({ rule, onToggle, onEdit, onDragStart, onDragOver, onDrop } = {}) {
  const row = document.createElement('div');
  row.draggable = true;
  row.dataset.ruleId = rule.id;
  row.style.cssText = `
    display:flex;align-items:center;gap:var(--sp-3);
    padding:var(--sp-3) var(--sp-4);
    background:var(--bg-card);
    border:1px solid var(--border);
    border-radius:var(--r-lg);
    margin-bottom:var(--sp-2);
    cursor:grab;
    transition:box-shadow var(--dur-fast),opacity var(--dur-fast);
  `;

  const handle = document.createElement('span');
  handle.textContent = '⠿';
  handle.style.cssText = 'color:var(--text-muted);font-size:18px;cursor:grab;flex-shrink:0';

  const info = document.createElement('div');
  info.style.cssText = 'flex:1;min-width:0';
  info.innerHTML = `
    <div style="font-weight:var(--fw-medium);font-size:var(--text-sm)">${rule.label}</div>
    ${rule.description ? `<div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:2px">${rule.description}</div>` : ''}
  `;

  if (rule.schedule) {
    info.appendChild(Badge(`⏰ ${rule.schedule}`, 'info'));
  }

  const toggle = Toggle({ checked: rule.enabled, onChange: v => onToggle?.(rule, v) });
  if (onEdit) {
    const editBtn = document.createElement('button');
    editBtn.textContent = '⚙️';
    editBtn.style.cssText = `background:none;border:none;cursor:pointer;font-size:16px;padding:4px`;
    editBtn.onclick = () => onEdit(rule);
    row.append(handle, info, editBtn, toggle);
  } else {
    row.append(handle, info, toggle);
  }

  // Drag events
  row.addEventListener('dragstart', e => {
    row.style.opacity = '0.5';
    e.dataTransfer.setData('text/plain', rule.id);
    onDragStart?.(rule);
  });
  row.addEventListener('dragend', () => row.style.opacity = '1');
  row.addEventListener('dragover', e => {
    e.preventDefault();
    row.style.boxShadow = '0 0 0 2px var(--accent)';
    onDragOver?.(rule);
  });
  row.addEventListener('dragleave', () => row.style.boxShadow = 'none');
  row.addEventListener('drop', e => {
    e.preventDefault();
    row.style.boxShadow = 'none';
    onDrop?.(e.dataTransfer.getData('text/plain'), rule.id);
  });

  return row;
}


// ── Progress Bar ─────────────────────────────────────────────────────────
export function ProgressBar(value, max, color = 'var(--accent)') {
  const pct = Math.min(100, Math.round((value / max) * 100));
  const wrap = document.createElement('div');
  wrap.style.cssText = `
    width:100%;height:6px;
    background:var(--bg-overlay);
    border-radius:var(--r-full);overflow:hidden;
  `;
  const fill = document.createElement('div');
  fill.style.cssText = `
    height:100%;width:${pct}%;
    background:${color};
    border-radius:var(--r-full);
    transition:width var(--dur-slow) var(--ease-out);
  `;
  wrap.appendChild(fill);
  return wrap;
}


// ── Empty State ─────────────────────────────────────────────────────────
export function EmptyState({ icon = '📭', title = 'Nothing here', description = '' } = {}) {
  const el = document.createElement('div');
  el.style.cssText = `
    text-align:center;
    padding:var(--sp-16) var(--sp-6);
    color:var(--text-muted);
  `;
  el.innerHTML = `
    <div style="font-size:48px;margin-bottom:var(--sp-4)">${icon}</div>
    <div style="font-size:var(--text-lg);font-weight:var(--fw-semibold);margin-bottom:var(--sp-2)">
      ${title}
    </div>
    ${description ? `<div style="font-size:var(--text-sm)">${description}</div>` : ''}
  `;
  return el;
}


// ── Spinner ───────────────────────────────────────────────────────────────
export function Spinner({ size = 24 } = {}) {
  const el = document.createElement('div');
  el.style.cssText = `
    width:${size}px;height:${size}px;
    border:2px solid var(--bg-overlay);
    border-top-color:var(--accent);
    border-radius:50%;
    animation:spin 0.8s linear infinite;
  `;
  return el;
}


// ── Search Input ─────────────────────────────────────────────────────────
export function SearchInput({ placeholder = 'Search...', onChange } = {}) {
  const wrap = document.createElement('div');
  wrap.style.cssText = `
    position:relative;
    margin-bottom:var(--sp-4);
  `;
  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = placeholder;
  input.style.cssText = `
    width:100%;
    padding:var(--sp-3) var(--sp-4);
    padding-left:calc(var(--sp-3) + 24px);
    background:var(--bg-input);
    border:1px solid var(--border);
    border-radius:var(--r-lg);
    color:var(--text-primary);
    font-size:var(--text-sm);
    transition:border-color var(--dur-fast);
  `;
  input.onfocus = () => input.style.borderColor = 'var(--accent)';
  input.onblur = () => input.style.borderColor = 'var(--border)';
  input.addEventListener('input', e => onChange?.(e.target.value));
  
  const icon = document.createElement('span');
  icon.textContent = '🔍';
  icon.style.cssText = `
    position:absolute;left:var(--sp-3);top:50%;
    transform:translateY(-50%);
    color:var(--text-muted);font-size:14px;
  `;
  
  wrap.appendChild(icon);
  wrap.appendChild(input);
  return wrap;
}


// ── Tab Bar ─────────────────────────────────────────────────────────────
export function TabBar({ tabs, active, onChange }) {
  const el = document.createElement('div');
  el.style.cssText = `
    display:flex;
    gap:var(--sp-1);
    padding:var(--sp-1);
    background:var(--bg-input);
    border-radius:var(--r-lg);
    margin-bottom:var(--sp-4);
  `;
  
  tabs.forEach(tab => {
    const btn = document.createElement('button');
    const isActive = tab.id === active;
    btn.textContent = tab.label;
    btn.style.cssText = `
      flex:1;
      padding:var(--sp-2) var(--sp-3);
      border-radius:var(--r-md);
      font-size:var(--text-sm);
      font-weight:var(--fw-medium);
      background:${isActive ? 'var(--accent)' : 'transparent'};
      color:${isActive ? '#000' : 'var(--text-secondary)'};
      cursor:pointer;
      transition:all var(--dur-fast);
      border:none;
    `;
    btn.onclick = () => onChange?.(tab.id);
    el.appendChild(btn);
  });
  
  return el;
}
