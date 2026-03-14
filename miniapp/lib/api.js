/**
 * miniapp/lib/api.js
 *
 * Authenticated fetch helpers for the Nexus Mini App.
 * All API calls must go through apiFetch() to ensure
 * the Telegram initData auth header is always sent.
 */

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
 * Authenticated fetch wrapper.
 * Throws on non-2xx responses with the error body as message.
 *
 * @param {string} path - API path (e.g. "/api/me")
 * @param {RequestInit} options - fetch options (method, body, etc.)
 * @returns {Promise<any>} - parsed JSON response
 */
export async function apiFetch(path, options = {}) {
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
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch (_) {
    return text;
  }
}
