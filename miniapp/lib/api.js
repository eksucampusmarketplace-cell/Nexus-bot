/**
 * miniapp/lib/api.js
 *
 * Authenticated fetch helpers for the Nexus Mini App.
 * All API calls must go through apiFetch() to ensure
 * the Telegram initData auth header is always sent.
 */

import { validateInput, sanitizeText } from './inputSanitizer.js';

/**
 * Returns auth headers using Telegram WebApp initData.
 * Falls back to x-init-data header (legacy) when Authorization is not available.
 */
export function authHeaders() {
  const initData = window.Telegram?.WebApp?.initData || "";
  if (!initData) {
    console.warn("[API] No initData — are you running outside Telegram?");
  }
  return {
    "Authorization": `tma ${initData}`,
    "x-init-data": initData,
    "Content-Type": "application/json",
  };
}

/**
 * Authenticated fetch wrapper with input validation.
 * Throws on non-2xx responses with the error body as message.
 *
 * @param {string} path - API path (e.g. "/api/me")
 * @param {RequestInit} options - fetch options (method, body, etc.)
 * @returns {Promise<any>} - parsed JSON response
 */
export async function apiFetch(path, options = {}) {
  // Validate and sanitize request body if present
  if (options.body && typeof options.body !== "string") {
    // Only validate if caller opts in (pass validate: true in options)
    if (options.validate !== false) {
      const validationResult = validateRequestBody(options.body);
      if (!validationResult.isValid) {
        // Log for debugging but don't block — moderation payloads
        // contain plain text that triggers false positives
        console.warn('[API] Validation warning:', validationResult.error);
      }
    }
    // Always JSON-stringify (skip sanitizeRequestBody which strips | & ; chars
    // from reason text)
    options.body = JSON.stringify(options.body);
  }

  const mergedHeaders = {
    ...authHeaders(),
    ...(options.headers || {}),
  };

  // Use NEXUS_API_BASE if configured, otherwise fall back to origin
  const base = (typeof window.NEXUS_API_BASE !== 'undefined' && window.NEXUS_API_BASE !== '')
    ? window.NEXUS_API_BASE
    : window.location.origin;
  const absoluteUrl = base + path;

  const res = await fetch(absoluteUrl, {
    ...options,
    headers: mergedHeaders,
  });

  if (res.status === 401) {
    throw new Error(
      "Unauthorized — initData missing or expired. " +
      "Open the Mini App from inside Telegram."
    );
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) {
        detail = typeof body.detail === 'object'
          ? (body.detail.error || JSON.stringify(body.detail))
          : body.detail;
      } else {
        detail = JSON.stringify(body);
      }
    } catch (_) {}
    throw new Error(detail);
  }

  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch (_) {
    return text;
  }
}

/**
 * Validate request body recursively
 */
function validateRequestBody(body, path = "body") {
  if (typeof body === 'string') {
    const result = validateInput(body, {
      maxLength: 10000,
      allowHTML: false,
      checkSQL: true,
      checkXSS: true,
      checkCommand: true,
      checkSpam: true,
      checkKeywords: true,
    });

    if (!result.isValid) {
      return {
        isValid: false,
        error: `${path}: ${result.error}`,
        details: result.details
      };
    }
  } else if (typeof body === 'object' && body !== null) {
    for (const [key, value] of Object.entries(body)) {
      const result = validateRequestBody(value, `${path}.${key}`);
      if (!result.isValid) {
        return result;
      }
    }
  } else if (Array.isArray(body)) {
    for (let i = 0; i < body.length; i++) {
      const result = validateRequestBody(body[i], `${path}[${i}]`);
      if (!result.isValid) {
        return result;
      }
    }
  }

  return { isValid: true, error: '', details: {} };
}

/**
 * Sanitize request body recursively
 */
function sanitizeRequestBody(body) {
  if (typeof body === 'string') {
    return sanitizeText(body);
  } else if (typeof body === 'object' && body !== null && !Array.isArray(body)) {
    const sanitized = {};
    for (const [key, value] of Object.entries(body)) {
      sanitized[key] = sanitizeRequestBody(value);
    }
    return sanitized;
  } else if (Array.isArray(body)) {
    return body.map(item => sanitizeRequestBody(item));
  }

  return body;
}
