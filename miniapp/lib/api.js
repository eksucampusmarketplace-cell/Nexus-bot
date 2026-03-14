/**
 * miniapp/lib/api.js
 *
 * Authenticated fetch helpers for the Nexus Mini App.
 * All API calls must go through apiFetch() to ensure
 * the Telegram initData auth header is always sent.
 * 
 * Includes client-side caching to reduce bandwidth usage.
 */

// Simple in-memory cache for GET requests
const cache = new Map();
const DEFAULT_CACHE_TTL = 30000; // 30 seconds default cache

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
 * Clear the entire cache or a specific path
 * @param {string} [path] - Optional specific path to clear
 */
export function clearCache(path) {
  if (path) {
    cache.delete(path);
  } else {
    cache.clear();
  }
}

/**
 * Authenticated fetch wrapper.
 * Throws on non-2xx responses with the error body as message.
 *
 * @param {string} path - API path (e.g. "/api/me")
 * @param {RequestInit} options - fetch options (method, body, etc.)
 * @param {Object} cacheOptions - Cache configuration
 * @param {boolean} cacheOptions.enabled - Enable caching for this request
 * @param {number} cacheOptions.ttl - Cache time-to-live in milliseconds
 * @returns {Promise<any>} - parsed JSON response
 */
export async function apiFetch(path, options = {}, cacheOptions = {}) {
  const isGet = !options.method || options.method === 'GET';
  const cacheEnabled = isGet && cacheOptions.enabled !== false; // Default enabled for GET
  const cacheTtl = cacheOptions.ttl || DEFAULT_CACHE_TTL;
  
  // Check cache for GET requests
  if (cacheEnabled && cache.has(path)) {
    const cached = cache.get(path);
    if (Date.now() - cached.timestamp < cacheTtl) {
      console.log(`[API] Cache hit: ${path}`);
      return cached.data;
    }
    // Expired, remove from cache
    cache.delete(path);
  }

  const mergedHeaders = {
    ...authHeaders(),
    ...(options.headers || {}),
  };

  if (options.body && typeof options.body !== "string") {
    options.body = JSON.stringify(options.body);
  }

  const res = await fetch(path, {
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
      detail = body.detail || JSON.stringify(body);
    } catch (_) {}
    throw new Error(detail);
  }

  const text = await res.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (_) {
      data = text;
    }
  }

  // Cache successful GET responses
  if (cacheEnabled && isGet) {
    cache.set(path, { data, timestamp: Date.now() });
  }

  return data;
}
