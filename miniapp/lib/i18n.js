/**
 * miniapp/lib/i18n.js
 * 
 * Shared i18n utilities for the Nexus Bot miniapp.
 * Provides translation functions that work across all pages.
 */

// Global translation cache
let _i18n = {
  bot: {},
  ui: {},
  is_rtl: false,
  lang: 'en'
};

// Available languages
const AVAILABLE_LANGUAGES = {
  en: '🇬🇧 English',
  ar: '🇸🇦 العربية',
  es: '🇪🇸 Español',
  fr: '🇫🇷 Français',
  hi: '🇮🇳 हिन्दी',
  pt: '🇧🇷 Português',
  ru: '🇷🇺 Русский',
  tr: '🇹🇷 Türkçe',
  id: '🇮🇩 Indonesia',
  de: '🇩🇪 Deutsch'
};

/**
 * Check if language is RTL
 */
function isRTL(lang) {
  return lang === 'ar';
}

/**
 * Get user's preferred language from localStorage or Telegram
 */
function detectLanguage() {
  // 1. Check localStorage first (manual preference)
  const savedLang = localStorage.getItem('nexus_lang');
  if (savedLang && AVAILABLE_LANGUAGES[savedLang]) {
    console.log('[i18n] Using saved language:', savedLang);
    return savedLang;
  }

  // 2. Check Telegram's language from initData
  try {
    const tg = window.Telegram?.WebApp;
    if (tg?.initDataUnsafe?.user?.language_code) {
      const tgLang = tg.initDataUnsafe.user.language_code.split('-')[0];
      if (AVAILABLE_LANGUAGES[tgLang]) {
        console.log('[i18n] Using Telegram language:', tgLang);
        localStorage.setItem('nexus_lang', tgLang);
        return tgLang;
      }
    }
  } catch (e) {
    console.warn('[i18n] Failed to get Telegram language:', e);
  }

  // 3. Default to English
  console.log('[i18n] Using default language: en');
  localStorage.setItem('nexus_lang', 'en');
  return 'en';
}

/**
 * Load translations from API
 */
async function loadLang(lang) {
  try {
    console.log(`[i18n] Loading translations for ${lang}...`);
    
    const response = await fetch(`/api/i18n?lang=${lang}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    
    // Cache translations
    _i18n = {
      bot: data.bot || {},
      ui: data.ui || {},
      is_rtl: data.is_rtl || false,
      lang: lang
    };

    // Apply RTL if needed
    applyRTL(data.is_rtl);

    console.log('[i18n] Translations loaded:', {
      botKeys: Object.keys(data.bot || {}).length,
      uiKeys: Object.keys(data.ui || {}).length,
      isRTL: data.is_rtl
    });

    return data;
  } catch (error) {
    console.error('[i18n] Failed to load translations:', error);
    // Fall back to English
    if (lang !== 'en') {
      return loadLang('en');
    }
    throw error;
  }
}

/**
 * Apply RTL direction to document
 */
function applyRTL(isRTL) {
  document.documentElement.dir = isRTL ? 'rtl' : 'ltr';
  document.documentElement.lang = _i18n.lang;
  console.log('[i18n] RTL applied:', isRTL);
}

/**
 * Translate a key
 */
function t(key, fallback = key) {
  // Check bot strings first
  if (_i18n.bot[key]) {
    return _i18n.bot[key];
  }
  
  // Then check UI strings
  if (_i18n.ui[key]) {
    return _i18n.ui[key];
  }
  
  // Return fallback or the key itself
  console.warn(`[i18n] Missing translation key: ${key}`);
  return fallback;
}

/**
 * Show a toast notification
 */
function showToast(message, duration = 3000) {
  // Remove existing toasts
  const existingToast = document.querySelector('.toast-notification');
  if (existingToast) {
    existingToast.remove();
  }

  // Create toast element
  const toast = document.createElement('div');
  toast.className = 'toast-notification';
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: #333;
    color: white;
    padding: 12px 24px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    z-index: 10000;
    animation: slideUp 0.3s ease;
    max-width: 90%;
    text-align: center;
  `;

  // Add animation keyframes if not present
  if (!document.querySelector('#toast-animations')) {
    const style = document.createElement('style');
    style.id = 'toast-animations';
    style.textContent = `
      @keyframes slideUp {
        from { opacity: 0; transform: translate(-50%, 20px); }
        to { opacity: 1; transform: translate(-50%, 0); }
      }
    `;
    document.head.appendChild(style);
  }

  document.body.appendChild(toast);

  // Auto-remove
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

/**
 * Initialize i18n system (called on page load)
 */
async function initI18n() {
  const lang = detectLanguage();
  await loadLang(lang);
  
  // Make tr() globally available
  window.tr = t;
  
  return _i18n;
}

/**
 * Change language and reload page
 */
async function changeLanguage(newLang) {
  if (!AVAILABLE_LANGUAGES[newLang]) {
    console.error('[i18n] Invalid language:', newLang);
    return;
  }

  try {
    // Save to localStorage
    localStorage.setItem('nexus_lang', newLang);
    
    // Load new translations
    await loadLang(newLang);
    
    // Update server-side preference
    try {
      const initData = window.Telegram?.WebApp?.initData || '';

      await fetch(
        `/api/users/me/language?language_code=${encodeURIComponent(newLang)}`,
        {
          method: 'PUT',
          headers: {
            'Authorization': `tma ${initData}`
          }
          // no body
        }
      );
    } catch (e) {
      console.warn('[i18n] Failed to save server preference:', e);
    }

    console.log('[i18n] Language changed to:', newLang);
    
    // Reload page to apply translations
    window.location.reload();
  } catch (error) {
    console.error('[i18n] Failed to change language:', error);
    if (typeof window !== 'undefined' && window.showToast) {
      window.showToast(t('error', 'Failed to change language'), 'error');
    }
  }
}

// Export functions
export {
  t,
  loadLang,
  isRTL,
  initI18n,
  changeLanguage,
  AVAILABLE_LANGUAGES
};

// Also make available globally for inline scripts
if (typeof window !== 'undefined') {
  window.i18n = {
    t,
    loadLang,
    isRTL,
    initI18n,
    changeLanguage,
    AVAILABLE_LANGUAGES
  };
}
