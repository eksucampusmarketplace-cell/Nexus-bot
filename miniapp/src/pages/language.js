/**
 * miniapp/src/pages/language.js
 *
 * Language settings page - allows users to change their mini app display language.
 * This changes the UI language for the current user only (stored in localStorage).
 * Includes auto-detection from name, bio, and group descriptions.
 */

import { t, AVAILABLE_LANGUAGES, changeLanguage } from '../../lib/i18n.js?v=1.6.0';
import { showToast } from '../../lib/components.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';

// Items per page for pagination
const ITEMS_PER_PAGE = 6;

/**
 * Detect language from text using Unicode script analysis
 */
function detectLanguageFromText(text) {
  if (!text) return null;

  const scripts = {
    ar: [[0x0600, 0x06FF], [0x0750, 0x077F], [0xFB50, 0xFDFF], [0xFE70, 0xFEFF]],
    ru: [[0x0400, 0x04FF], [0x0500, 0x052F], [0x2DE0, 0x2DFF], [0xA640, 0xA69F]],
    hi: [[0x0900, 0x097F], [0xA8E0, 0xA8FF]],
    th: [[0x0E00, 0x0E7F]],
  };

  const turkishChars = new Set('ğşıöüÇĞŞİÖÜ');
  const germanChars = new Set('ß');

  const counts = { ar: 0, ru: 0, hi: 0, th: 0, tr: 0, de: 0 };
  let total = 0;

  for (const char of text.slice(0, 100)) {
    if (!char.trim()) continue;
    total++;

    const code = char.charCodeAt(0);

    for (const [lang, ranges] of Object.entries(scripts)) {
      for (const [start, end] of ranges) {
        if (code >= start && code <= end) {
          counts[lang]++;
          break;
        }
      }
    }

    if (turkishChars.has(char)) counts.tr++;
    if (germanChars.has(char)) counts.de++;
  }

  if (total < 3) return null;

  const threshold = Math.max(1, total * 0.3);
  for (const [lang, count] of Object.entries(counts)) {
    if (count >= threshold) return lang;
  }

  return null;
}

/**
 * Detect language from user's context (name, bio, etc.)
 */
function detectUserLanguage() {
  const tg = window.Telegram?.WebApp?.initDataUnsafe;
  if (!tg?.user) return null;

  const { first_name, last_name } = tg.user;

  // Try name first
  const nameText = [first_name, last_name].filter(Boolean).join(' ');
  let detected = detectLanguageFromText(nameText);
  if (detected) return detected;

  // Try bio if available
  if (tg.user.bio) {
    detected = detectLanguageFromText(tg.user.bio);
    if (detected) return detected;
  }

  return null;
}

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

  // Check for auto-detected language (first visit only)
  const hasShownDetection = localStorage.getItem('nexus_lang_detection_shown');
  const detectedLang = !hasShownDetection ? detectUserLanguage() : null;

  // Fetch current language from server
  let currentLang = 'en';
  try {
    const res = await apiFetch('/api/users/me/language');
    currentLang = res.language_code || 'en';
  } catch (e) {
    console.warn('[language] Failed to fetch user language from server:', e);
    currentLang = localStorage.getItem('nexus_lang') || 'en';
  }

  // Show detection confirmation if we detected a non-English language and user is on English
  if (detectedLang && detectedLang !== 'en' && currentLang === 'en' && AVAILABLE_LANGUAGES[detectedLang]) {
    localStorage.setItem('nexus_lang_detection_shown', 'true');

    const detectionBanner = document.createElement('div');
    detectionBanner.style.cssText = `
      background: linear-gradient(135deg, var(--accent-dim), var(--bg-card));
      border: 2px solid var(--accent);
      border-radius: var(--r-xl);
      padding: var(--sp-4);
      margin-bottom: var(--sp-5);
    `;
    detectionBanner.innerHTML = `
      <div style="display:flex;gap:var(--sp-3);align-items:flex-start;">
        <span style="font-size:1.5rem;flex-shrink:0;">🔍</span>
        <div style="flex:1;">
          <div style="font-weight:700;margin-bottom:var(--sp-2);">${t('lang_detected_title', 'Language Detected')}</div>
          <div style="margin-bottom:var(--sp-3);">${t('lang_detected_body', 'We detected you may be using {lang}. Would you like to use this language?').replace('{lang}', AVAILABLE_LANGUAGES[detectedLang])}</div>
          <div style="display:flex;gap:var(--sp-2);flex-wrap:wrap;">
            <button id="btn-use-detected" class="btn btn-primary">
              ${t('lang_use_detected', 'Yes, use this language')}
            </button>
            <button id="btn-keep-english" class="btn btn-secondary">
              ${t('lang_keep_english', 'No, keep English')}
            </button>
          </div>
        </div>
      </div>
    `;
    container.appendChild(detectionBanner);

    detectionBanner.querySelector('#btn-use-detected').onclick = async () => {
      try {
        await changeLanguage(detectedLang);
        showToast(t('lang_set', 'Language changed successfully!'));
      } catch (err) {
        showToast(t('error', 'Failed to change language'));
      }
    };

    detectionBanner.querySelector('#btn-keep-english').onclick = () => {
      detectionBanner.remove();
    };
  }

  // Pagination state
  let currentPage = 0;
  const languages = Object.entries(AVAILABLE_LANGUAGES);
  const totalPages = Math.ceil(languages.length / ITEMS_PER_PAGE);

  // Language grid container
  const gridContainer = document.createElement('div');
  gridContainer.style.cssText = 'display:flex;flex-direction:column;gap:var(--sp-4);';
  container.appendChild(gridContainer);

  // Build language grid
  const grid = document.createElement('div');
  grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:var(--sp-3);';

  function renderPage(page) {
    grid.innerHTML = '';
    const start = page * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const pageLanguages = languages.slice(start, end);

    pageLanguages.forEach(([code, label]) => {
      const isSelected = code === currentLang;

      const card = document.createElement('div');
      card.style.cssText = `
        background:var(--bg-card);
        border:2px solid ${isSelected ? 'var(--accent)' : 'var(--border)'};
        border-radius:var(--r-xl);
        padding:var(--sp-4);
        cursor:${isSelected ? 'default' : 'pointer'};
        transition:all var(--dur-fast);
        ${isSelected ? 'background:var(--accent-dim)' : ''}
      `;

      const flag = label.split(' ')[0];
      const name = label.split(' ').slice(1).join(' ');

      card.innerHTML = `
        <div style="display:flex;align-items:center;gap:var(--sp-3);">
          <span style="font-size:2rem">${flag}</span>
          <div style="flex:1;">
            <div style="font-weight:600;font-size:var(--text-base)">${name}</div>
            ${isSelected ? `<div style="color:var(--accent);font-size:0.75rem;font-weight:600;margin-top:2px;">✓ ${t('current', 'Current')}</div>` : ''}
          </div>
        </div>
      `;

      if (!isSelected) {
        card.onmouseenter = () => {
          card.style.borderColor = 'var(--accent)';
          card.style.transform = 'translateY(-2px)';
          card.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
        };
        card.onmouseleave = () => {
          card.style.borderColor = 'var(--border)';
          card.style.transform = 'translateY(0)';
          card.style.boxShadow = 'none';
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
  }

  renderPage(currentPage);
  gridContainer.appendChild(grid);

  // Pagination controls
  if (totalPages > 1) {
    const pagination = document.createElement('div');
    pagination.style.cssText = `
      display:flex;
      justify-content:center;
      align-items:center;
      gap:var(--sp-3);
      margin-top:var(--sp-3);
    `;

    const prevBtn = document.createElement('button');
    prevBtn.className = 'btn btn-secondary';
    prevBtn.innerHTML = '← ' + t('nav_previous', 'Previous');
    prevBtn.disabled = currentPage === 0;
    prevBtn.style.opacity = currentPage === 0 ? '0.5' : '1';

    const pageIndicator = document.createElement('span');
    pageIndicator.style.cssText = 'color:var(--text-muted);font-size:var(--text-sm);';
    pageIndicator.textContent = `${currentPage + 1} / ${totalPages}`;

    const nextBtn = document.createElement('button');
    nextBtn.className = 'btn btn-secondary';
    nextBtn.innerHTML = t('nav_next', 'Next') + ' →';
    nextBtn.disabled = currentPage === totalPages - 1;
    nextBtn.style.opacity = currentPage === totalPages - 1 ? '0.5' : '1';

    prevBtn.onclick = () => {
      if (currentPage > 0) {
        currentPage--;
        renderPage(currentPage);
        prevBtn.disabled = currentPage === 0;
        nextBtn.disabled = currentPage === totalPages - 1;
        prevBtn.style.opacity = currentPage === 0 ? '0.5' : '1';
        nextBtn.style.opacity = currentPage === totalPages - 1 ? '0.5' : '1';
        pageIndicator.textContent = `${currentPage + 1} / ${totalPages}`;
      }
    };

    nextBtn.onclick = () => {
      if (currentPage < totalPages - 1) {
        currentPage++;
        renderPage(currentPage);
        prevBtn.disabled = currentPage === 0;
        nextBtn.disabled = currentPage === totalPages - 1;
        prevBtn.style.opacity = currentPage === 0 ? '0.5' : '1';
        nextBtn.style.opacity = currentPage === totalPages - 1 ? '0.5' : '1';
        pageIndicator.textContent = `${currentPage + 1} / ${totalPages}`;
      }
    };

    pagination.appendChild(prevBtn);
    pagination.appendChild(pageIndicator);
    pagination.appendChild(nextBtn);
    gridContainer.appendChild(pagination);
  }

  // Language usage hint
  const hint = document.createElement('div');
  hint.style.cssText = `
    margin-top: var(--sp-5);
    padding: var(--sp-4);
    background: var(--bg-subtle);
    border-radius: var(--r-lg);
    font-size: 0.875rem;
    color: var(--text-muted);
    text-align: center;
  `;
  hint.innerHTML = `
    <div style="margin-bottom:var(--sp-2);">💡</div>
    <div>${t('lang_auto_detect_hint', 'Language is automatically detected from your name, bio, and messages.')}</div>
  `;
  container.appendChild(hint);
}
