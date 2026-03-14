/**
 * miniapp/lib/inputSanitizer.js
 *
 * Client-side input sanitization and validation.
 * Mirrors backend validation for immediate feedback.
 */

// ============================================================================
// SQL Injection Detection Patterns
// ============================================================================
const SQL_INJECTION_PATTERNS = [
  /(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|UNION|EXEC|EXECUTE)\b)/i,
  /(--|#|\/\*|\*\/)/i,
  /(\bor\b\s+\d+\s*=\s*\d+)/i,
  /(\band\b\s+\d+\s*=\s*\d+)/i,
  /('\s*(OR|AND)\s*'.*')/i,
  /;|\||&&/,
  /(\b(WAITFOR\s+DELAY|BENCHMARK|SLEEP)\b)/i,
  /(\b(INFORMATION_SCHEMA|SYS\.)\b)/i,
  /(\bXOR\b|\bCASE\s+WHEN\b)/i,
  /(\\x[0-9a-fA-F]{2})/i,
];

// ============================================================================
// XSS/HTML Injection Detection Patterns
// ============================================================================
const XSS_PATTERNS = [
  /<\s*script[^>]*>/i,
  /<\s*iframe[^>]*>/i,
  /on\w+\s*=/i,
  /javascript:/i,
  /data:/i,
  /vbscript:/i,
  /fromCharCode/i,
  /eval\s*\(/i,
  /expression\s*\(/i,
  /@import/i,
  /<\s*object[^>]*>/i,
  /<\s*embed[^>]*>/i,
];

// ============================================================================
// Command Injection Detection Patterns
// ============================================================================
const COMMAND_INJECTION_PATTERNS = [
  /[;&|`$]/,
  /\$\(/,
  /\n/,
  /\r/,
  /\t/,
  /\\[\\nrt]/,
];

// ============================================================================
// Dangerous Keywords
// ============================================================================
const DANGEROUS_KEYWORDS = [
  'password', 'passwd', 'pwd', 'secret', 'token', 'api_key',
  'credit_card', 'card_number', 'cvv', 'ssn', 'social_security',
  'drop table', 'delete from', 'truncate', 'grant all', 'revoke',
  'system(', 'exec(', 'eval(', 'passthru(', 'shell_exec(',
  'php://', 'expect://', 'file://',
];

// ============================================================================
// Detection Functions
// ============================================================================

function detectSqlInjection(text) {
  if (!text || typeof text !== 'string') {
    return { isInjection: false, matches: [] };
  }

  const matches = [];
  for (const pattern of SQL_INJECTION_PATTERNS) {
    const found = text.match(pattern);
    if (found) {
      matches.push(found[0]);
    }
  }

  return {
    isInjection: matches.length > 0,
    matches: [...new Set(matches)],
  };
}

function detectXss(text) {
  if (!text || typeof text !== 'string') {
    return { isXss: false, matches: [] };
  }

  const matches = [];
  for (const pattern of XSS_PATTERNS) {
    const found = text.match(pattern);
    if (found) {
      matches.push(found[0]);
    }
  }

  return {
    isXss: matches.length > 0,
    matches: [...new Set(matches)],
  };
}

function detectCommandInjection(text) {
  if (!text || typeof text !== 'string') {
    return { isInjection: false, matches: [] };
  }

  const matches = [];
  for (const pattern of COMMAND_INJECTION_PATTERNS) {
    const found = text.match(pattern);
    if (found) {
      matches.push(found[0]);
    }
  }

  return {
    isInjection: matches.length > 0,
    matches: [...new Set(matches)],
  };
}

function detectSpam(text) {
  if (!text || typeof text !== 'string') {
    return { isSpam: false, reason: '' };
  }

  // Check for character repetition
  if (/(.)(\1{20,})/.test(text)) {
    return { isSpam: true, reason: 'Excessive character repetition' };
  }

  // Check for word repetition
  const words = text.toLowerCase().split(/\s+/);
  const wordCounts = {};
  for (const word of words) {
    if (word.length > 2) {
      wordCounts[word] = (wordCounts[word] || 0) + 1;
    }
  }

  for (const [word, count] of Object.entries(wordCounts)) {
    if (count >= 10) {
      return { isSpam: true, reason: `Word '${word}' repeated ${count} times` };
    }
  }

  // Check for URL spam
  const urls = text.match(/https?:\/\/[^\s]+/g);
  if (urls && urls.length > 5) {
    return { isSpam: true, reason: `Too many URLs (${urls.length})` };
  }

  return { isSpam: false, reason: '' };
}

function detectDangerousKeywords(text) {
  if (!text || typeof text !== 'string') {
    return [];
  }

  const textLower = text.toLowerCase();
  const found = [];

  for (const keyword of DANGEROUS_KEYWORDS) {
    if (textLower.includes(keyword.toLowerCase())) {
      found.push(keyword);
    }
  }

  return found;
}

// ============================================================================
// Main Validation Function
// ============================================================================

export function validateInput(text, options = {}) {
  const {
    maxLength = 1000,
    allowHTML = false,
    checkSQL = true,
    checkXSS = true,
    checkCommand = true,
    checkSpam = true,
    checkKeywords = true,
  } = options;

  if (typeof text !== 'string') {
    return {
      isValid: false,
      error: 'Input must be a string',
      details: { type: 'invalid_type' },
    };
  }

  // Length check
  if (text.length > maxLength) {
    return {
      isValid: false,
      error: `Input too long (max ${maxLength} characters)`,
      details: { type: 'too_long', length: text.length },
    };
  }

  // Empty check
  if (!text.trim()) {
    return {
      isValid: false,
      error: 'Input cannot be empty',
      details: { type: 'empty' },
    };
  }

  // Security checks
  const details = {};

  if (checkSQL) {
    const sqlResult = detectSqlInjection(text);
    if (sqlResult.isInjection) {
      console.warn('[SECURITY] SQL injection detected:', sqlResult.matches);
      return {
        isValid: false,
        error: 'Input contains SQL injection patterns',
        details: { type: 'sql_injection', patterns: sqlResult.matches },
      };
    }
  }

  if (checkXSS && !allowHTML) {
    const xssResult = detectXss(text);
    if (xssResult.isXss) {
      console.warn('[SECURITY] XSS detected:', xssResult.matches);
      return {
        isValid: false,
        error: 'Input contains XSS patterns',
        details: { type: 'xss', patterns: xssResult.matches },
      };
    }
  }

  if (checkCommand) {
    const cmdResult = detectCommandInjection(text);
    if (cmdResult.isInjection) {
      console.warn('[SECURITY] Command injection detected:', cmdResult.matches);
      return {
        isValid: false,
        error: 'Input contains command injection patterns',
        details: { type: 'command_injection', patterns: cmdResult.matches },
      };
    }
  }

  if (checkSpam) {
    const spamResult = detectSpam(text);
    if (spamResult.isSpam) {
      console.warn('[SECURITY] Spam detected:', spamResult.reason);
      return {
        isValid: false,
        error: `Input appears to be spam: ${spamResult.reason}`,
        details: { type: 'spam', reason: spamResult.reason },
      };
    }
  }

  if (checkKeywords) {
    const keywords = detectDangerousKeywords(text);
    if (keywords.length > 0) {
      console.warn('[SECURITY] Dangerous keywords detected:', keywords);
      return {
        isValid: false,
        error: `Input contains restricted keywords: ${keywords.join(', ')}`,
        details: { type: 'dangerous_keywords', keywords },
      };
    }
  }

  details.checks_passed = ['sql', 'xss', 'command', 'spam', 'keywords'];
  return {
    isValid: true,
    error: '',
    details,
  };
}

// ============================================================================
// Sanitization Function
// ============================================================================

export function sanitizeText(text, allowHTML = false) {
  if (typeof text !== 'string') {
    return '';
  }

  let sanitized = text;

  // Remove SQL injection patterns
  for (const pattern of SQL_INJECTION_PATTERNS) {
    sanitized = sanitized.replace(pattern, '');
  }

  // Remove command injection patterns
  for (const pattern of COMMAND_INJECTION_PATTERNS) {
    sanitized = sanitized.replace(pattern, '');
  }

  // Remove XSS patterns (unless HTML is allowed)
  if (!allowHTML) {
    for (const pattern of XSS_PATTERNS) {
      sanitized = sanitized.replace(pattern, '');
    }
    // HTML escape
    const div = document.createElement('div');
    div.textContent = sanitized;
    sanitized = div.innerHTML;
  } else {
    // Still escape dangerous event handlers even if HTML is allowed
    sanitized = sanitized.replace(/on\w+\s*=\s*["'][^"']*["']/gi, '');
    sanitized = sanitized.replace(/javascript:/gi, '');
  }

  // Remove excessive whitespace
  sanitized = sanitized.replace(/\s+/g, ' ').trim();

  return sanitized;
}

// ============================================================================
// Input Rate Limiter Class
// ============================================================================

export class InputRateLimiter {
  constructor(maxAttempts = 10, windowSeconds = 60) {
    this.maxAttempts = maxAttempts;
    this.windowSeconds = windowSeconds;
    this.attempts = new Map();
  }

  checkRateLimit(identifier) {
    const now = Date.now();

    // Clean old attempts
    if (this.attempts.has(identifier)) {
      const attempts = this.attempts.get(identifier);
      const validAttempts = attempts.filter(
        (time) => now - time < this.windowSeconds * 1000
      );
      this.attempts.set(identifier, validAttempts);
    } else {
      this.attempts.set(identifier, []);
    }

    const currentAttempts = this.attempts.get(identifier);
    const currentCount = currentAttempts.length;

    if (currentCount >= this.maxAttempts) {
      const oldestAttempt = currentAttempts[0];
      const resetAfter = Math.ceil(
        (oldestAttempt + this.windowSeconds * 1000 - now) / 1000
      );
      return {
        allowed: false,
        remaining: 0,
        resetAfter: Math.max(0, resetAfter),
      };
    }

    // Add current attempt
    currentAttempts.push(now);
    this.attempts.set(identifier, currentAttempts);

    return {
      allowed: true,
      remaining: this.maxAttempts - currentAttempts.length,
      resetAfter: 0,
    };
  }

  reset(identifier) {
    this.attempts.delete(identifier);
  }
}

// ============================================================================
// Additional Utility Functions
// ============================================================================

export function sanitizeNumericInput(value, minVal = null, maxVal = null) {
  const num = parseInt(value, 10);
  if (isNaN(num)) {
    return null;
  }

  if (minVal !== null && num < minVal) {
    return minVal;
  }
  if (maxVal !== null && num > maxVal) {
    return maxVal;
  }

  return num;
}

export function sanitizeChatId(chatId) {
  const num = parseInt(chatId, 10);
  if (isNaN(num)) {
    return null;
  }
  // Valid Telegram chat IDs
  if (num > 0 || num < -10000000000) {
    return num;
  }
  return null;
}

export function sanitizeUserId(userId) {
  const num = parseInt(userId, 10);
  if (isNaN(num) || num <= 0) {
    return null;
  }
  return num;
}

export function sanitizeBotToken(token) {
  if (typeof token !== 'string') {
    return '';
  }
  // Bot tokens are in format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
  // Only keep alphanumeric and colon, underscore, hyphen
  return token.replace(/[^a-zA-Z0-9:_-]/g, '').trim();
}

export function validateMultipleInputs(inputs, rules) {
  const errors = {};
  let allValid = true;

  for (const [fieldName, fieldValue] of Object.entries(inputs)) {
    const fieldRules = rules[fieldName] || {};

    const result = validateInput(
      fieldValue !== null && fieldValue !== undefined ? String(fieldValue) : '',
      {
        maxLength: fieldRules.maxLength || 1000,
        allowHTML: fieldRules.allowHTML || false,
        checkSQL: fieldRules.checkSQL !== false,
        checkXSS: fieldRules.checkXSS !== false,
        checkCommand: fieldRules.checkCommand !== false,
        checkSpam: fieldRules.checkSpam !== false,
        checkKeywords: fieldRules.checkKeywords !== false,
      }
    );

    if (!result.isValid) {
      allValid = false;
      errors[fieldName] = {
        message: result.error,
        details: result.details,
      };
    }
  }

  return { allValid, errors };
}
