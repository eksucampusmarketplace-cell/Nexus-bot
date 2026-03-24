/**
 * miniapp/src/pages/language.js
 * 
 * Language settings page - allows users to change their mini app display language.
 * This changes the UI language for the current user only (stored in localStorage).
 */

import { t, AVAILABLE_LANGUAGES, changeLanguage } from '../../lib/i18n.js?v=1.6.0';
import { showToast } from '../../lib/components.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';

export async function renderLanguagePage(container) {
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  // Blue info notice box
  const notice = document.createElement('div');
  notice.style.cssText = `
    background: var(--accent-dim, #e8f4fd);
    border: 1px solid var(--accent, #2196f3);
    border-radius: var(--r-xl);
    padding: var(--sp-4);
    margin-bottom: var(--sp-5);
    font-size: 0.875rem;
    line-height: 1.6;
    color: var(--text-primary);
  `;
  notice.innerHTML = `
    <div style="display:flex;gap:var(--sp-2);align-items:flex-start;">
      <span style="font-size:1.1rem;flex-shrink:0;">ℹ️</span>
      <div>
        <div style="font-weight:600;margin-bottom:var(--sp-1);">${t('lang_notice_title', 'This changes the mini app interface language for you only.')}</div>
        <div style="color:var(--text-secondary);">${t('lang_notice_body', 'To change the language the bot uses when sending messages to your group, go to')} <strong>${t('lang_notice_link', 'Settings → Group Identity → Bot Message Language')}</strong>.</div>
      </div>
    </div>
  `;
  container.appendChild(notice);

  // Header
  const header = document.createElement('div');
  header.innerHTML = `
    <div style="display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);">
      <div style="font-size:2rem">🌍</div>
      <div>
        <div style="font-size:1.2rem;font-weight:700">${t('nav_language', 'Language')}</div>
        <div style="font-size:0.85rem;color:var(--text-muted)">${t('lang_subtitle', 'Choose your preferred interface language')}</div>
      </div>
    </div>
  `;
  container.appendChild(header);

  // Fetch current language from server
  let currentLang = 'en';
  try {
    const res = await apiFetch('/api/users/me/language');
    currentLang = res.language_code || 'en';
  } catch (e) {
    console.warn('[language] Failed to fetch user language from server:', e);
    // Fallback to localStorage if server request fails
    currentLang = localStorage.getItem('nexus_lang') || 'en';
  }

  // Build language grid
  const grid = document.createElement('div');
  grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:var(--sp-3);';

  Object.entries(AVAILABLE_LANGUAGES).forEach(([code, label]) => {
    const isSelected = code === currentLang;

    const card = document.createElement('div');
    card.style.cssText = `
      background:var(--bg-card);
      border:1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'};
      border-radius:var(--r-xl);
      padding:var(--sp-4);
      cursor:pointer;
      transition:all var(--dur-fast);
      ${isSelected ? 'background:var(--accent-dim)' : ''}
    `;
    card.innerHTML = `
      <div style="display:flex;align-items:center;gap:var(--sp-3);margin-bottom:var(--sp-2);">
        <span style="font-size:1.5rem">${label.split(' ')[0]}</span>
        <span style="font-weight:600;font-size:var(--text-sm)">${label.split(' ').slice(1).join(' ')}</span>
      </div>
      ${isSelected ? '<div style="color:var(--accent);font-size:0.75rem;font-weight:600">✓ ' + t('current', 'Current') + '</div>' : ''}
    `;

    if (!isSelected) {
      card.onmouseenter = () => {
        card.style.borderColor = 'var(--accent)';
        card.style.transform = 'translateY(-2px)';
      };
      card.onmouseleave = () => {
        card.style.borderColor = 'var(--border)';
        card.style.transform = 'translateY(0)';
      };
      card.onclick = async () => {
        card.style.opacity = '0.6';
        card.style.pointerEvents = 'none';

        try {
          await changeLanguage(code);
          showToast(t('lang_set', 'Language changed successfully!'));
        } catch (err) {
          console.error('Failed to change language:', err);
          card.style.opacity = '1';
          card.style.pointerEvents = 'auto';
          showToast(t('error', 'Failed to change language'));
        }
      };
    }

    grid.appendChild(card);
  });

  container.appendChild(grid);
}
