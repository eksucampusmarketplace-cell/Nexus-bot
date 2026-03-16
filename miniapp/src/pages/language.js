/**
 * miniapp/src/pages/language.js
 * 
 * Language settings page - allows users to change their language preference.
 * Integrates with the i18n system.
 */

import { t, showToast, AVAILABLE_LANGUAGES, changeLanguage } from '../lib/i18n.js?v=1.6.0';
import { apiFetch } from '../lib/api.js?v=1.6.0';

export async function renderLanguagePage(container) {
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  // Header
  const header = document.createElement('div');
  header.innerHTML = `
    <div style="display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-5);">
      <div style="font-size:2rem">🌍</div>
      <div>
        <div style="font-size:1.2rem;font-weight:700">${t('nav_language', 'Language')}</div>
        <div style="font-size:0.85rem;color:var(--text-muted)">Choose your preferred language</div>
      </div>
    </div>
  `;
  container.appendChild(header);

  // Loading state
  const loadingDiv = document.createElement('div');
  loadingDiv.style.cssText = 'text-align:center;padding:var(--sp-8);color:var(--text-muted);';
  loadingDiv.textContent = t('loading', 'Loading...');
  container.appendChild(loadingDiv);

  try {
    // Get current language preference
    const userLang = await apiFetch('/api/users/me/lang').catch(() => ({ lang: localStorage.getItem('nexus_lang') || 'en' }));
    const currentLang = userLang.lang || 'en';

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

    // Replace loading with grid
    loadingDiv.replaceWith(grid);

    // Info section
    const info = document.createElement('div');
    info.style.cssText = 'margin-top:var(--sp-6);padding:var(--sp-4);background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);';
    info.innerHTML = `
      <div style="font-weight:600;margin-bottom:var(--sp-2)">ℹ️ ${t('info', 'About Language Detection')}</div>
      <div style="font-size:0.85rem;color:var(--text-secondary);line-height:1.6">
        ${t('lang_info', 'The bot automatically detects your language from Telegram settings. You can manually override it here. Your preference will be saved and used for all bot messages.')}
      </div>
    `;
    container.appendChild(info);

  } catch (error) {
    console.error('Failed to load language page:', error);
    loadingDiv.textContent = t('error', 'Failed to load language settings');
  }
}
