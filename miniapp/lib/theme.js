/**
 * miniapp/lib/theme.js
 *
 * Theme management: dark/light/system + custom accent color.
 * Persists in localStorage.
 * Syncs with Telegram WebApp color scheme.
 *
 * Usage:
 *   import { ThemeEngine } from './theme.js';
 *   ThemeEngine.init();
 *   ThemeEngine.setAccent('#ff6b6b');
 */

export const ThemeEngine = {
  PRESETS: [
    { name: 'Cyan',    value: '#00d4ff' },
    { name: 'Violet',  value: '#7c3aed' },
    { name: 'Green',   value: '#22c55e' },
    { name: 'Orange',  value: '#f97316' },
    { name: 'Pink',    value: '#ec4899' },
    { name: 'Red',     value: '#ef4444' },
    { name: 'Gold',    value: '#f59e0b' },
    { name: 'Custom',  value: null      },
  ],

  init() {
    const savedTheme  = localStorage.getItem('nx_theme')  || 'dark';
    const savedAccent = localStorage.getItem('nx_accent') || '#00d4ff';
    this.setTheme(savedTheme);
    this.setAccent(savedAccent);

    // Sync with Telegram's color scheme
    const tg = window.Telegram?.WebApp;
    if (tg?.colorScheme === 'light' && !localStorage.getItem('nx_theme')) {
      this.setTheme('light');
    }
    tg?.onEvent?.('themeChanged', () => {
      if (!localStorage.getItem('nx_theme')) {
        this.setTheme(tg.colorScheme === 'light' ? 'light' : 'dark');
      }
    });
  },

  setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('nx_theme', theme);
    document.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
  },

  setAccent(color) {
    document.documentElement.style.setProperty('--accent', color);
    document.documentElement.style.setProperty('--accent-dim', color + '22');
    document.documentElement.style.setProperty('--accent-hover', color + 'cc');
    localStorage.setItem('nx_accent', color);
    document.dispatchEvent(new CustomEvent('accentchange', { detail: { color } }));
  },

  getTheme() { return localStorage.getItem('nx_theme') || 'dark'; },
  getAccent() { return localStorage.getItem('nx_accent') || '#00d4ff'; },

  renderPicker(containerEl, onAccentChange) {
    containerEl.innerHTML = `
      <div style="margin-bottom:var(--sp-3)">
        <div style="font-size:var(--text-sm);font-weight:var(--fw-semibold);
                    margin-bottom:var(--sp-2)">Theme</div>
        <div style="display:flex;gap:var(--sp-2)">
          ${['dark','light'].map(t => `
            <button data-theme-btn="${t}" style="
              flex:1;padding:var(--sp-2) var(--sp-3);
              border-radius:var(--r-lg);font-size:var(--text-sm);
              font-weight:var(--fw-medium);cursor:pointer;
              border:2px solid ${this.getTheme()===t?'var(--accent)':'var(--border)'};
              background:${this.getTheme()===t?'var(--accent-dim)':'var(--bg-input)'};
              color:var(--text-primary);transition:all var(--dur-fast);
            ">${t === 'dark' ? '🌙 Dark' : '☀️ Light'}</button>
          `).join('')}
        </div>
      </div>
      <div>
        <div style="font-size:var(--text-sm);font-weight:var(--fw-semibold);
                    margin-bottom:var(--sp-2)">Accent Color</div>
        <div style="display:flex;gap:var(--sp-2);flex-wrap:wrap">
          ${this.PRESETS.map(p => p.value ? `
            <button data-accent-btn="${p.value}" title="${p.name}" style="
              width:32px;height:32px;border-radius:50%;cursor:pointer;
              background:${p.value};
              border:3px solid ${this.getAccent()===p.value?'white':'transparent'};
              transition:border-color var(--dur-fast);
            "></button>
          ` : `
            <label title="Custom" style="
              width:32px;height:32px;border-radius:50%;overflow:hidden;cursor:pointer;
              border:3px solid var(--border);display:flex;align-items:center;
              justify-content:center;font-size:14px;
            ">🎨<input type="color" id="custom-accent"
              value="${this.getAccent()}" style="position:absolute;opacity:0;width:0;height:0"></label>
          `).join('')}
        </div>
      </div>
    `;

    containerEl.querySelectorAll('[data-theme-btn]').forEach(btn => {
      btn.onclick = () => {
        this.setTheme(btn.dataset.themeBtn);
        this.renderPicker(containerEl, onAccentChange);
      };
    });

    containerEl.querySelectorAll('[data-accent-btn]').forEach(btn => {
      btn.onclick = () => {
        this.setAccent(btn.dataset.accentBtn);
        onAccentChange?.(btn.dataset.accentBtn);
        this.renderPicker(containerEl, onAccentChange);
      };
    });

    const custom = containerEl.querySelector('#custom-accent');
    if (custom) {
      custom.oninput = e => {
        this.setAccent(e.target.value);
        onAccentChange?.(e.target.value);
      };
    }
  }
};
