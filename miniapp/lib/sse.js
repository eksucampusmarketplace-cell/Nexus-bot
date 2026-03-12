/**
 * miniapp/lib/sse.js
 *
 * Real-time SSE client.
 * Connects to /api/events?chat_id={id}&token={initData}
 * Auto-reconnects with exponential backoff.
 * Dispatches typed events to registered handlers.
 *
 * Usage:
 *   import { SSEClient } from './sse.js';
 *   const sse = new SSEClient();
 *   sse.on('member_join', (data) => { ... });
 *   sse.on('bot_action', (data) => { ... });
 *   sse.connect(chatId);
 */

export class SSEClient {
  constructor() {
    this._handlers  = {};
    this._es        = null;
    this._chatId    = null;
    this._retries   = 0;
    this._maxRetry  = 10;
    this._connected = false;
  }

  on(event, handler) {
    if (!this._handlers[event]) this._handlers[event] = [];
    this._handlers[event].push(handler);
    return this;
  }

  off(event, handler) {
    if (!this._handlers[event]) return;
    this._handlers[event] = this._handlers[event].filter(h => h !== handler);
  }

  connect(chatId) {
    this._chatId = chatId;
    this._doConnect();
  }

  disconnect() {
    this._es?.close();
    this._es = null;
    this._connected = false;
  }

  _doConnect() {
    const params = new URLSearchParams({
      chat_id: this._chatId,
      token:   window.Telegram?.WebApp?.initData || '',
    });
    this._es = new EventSource(`/api/events?${params}`);

    this._es.onopen = () => {
      this._connected = true;
      this._retries   = 0;
      this._dispatch('connected', {});
    };

    this._es.onmessage = (e) => {
      try {
        const { type, data } = JSON.parse(e.data);
        this._dispatch(type, data);
      } catch {}
    };

    this._es.onerror = () => {
      this._connected = false;
      this._es?.close();
      this._dispatch('disconnected', {});
      if (this._retries < this._maxRetry) {
        const delay = Math.min(1000 * 2 ** this._retries, 30000);
        this._retries++;
        setTimeout(() => this._doConnect(), delay);
      }
    };

    // Named event types from server
    ['member_join', 'member_leave', 'bot_action', 'settings_change',
     'notification', 'stat_update', 'bulk_action'].forEach(type => {
      this._es.addEventListener(type, (e) => {
        try { this._dispatch(type, JSON.parse(e.data)); } catch {}
      });
    });
  }

  _dispatch(type, data) {
    (this._handlers[type] || []).forEach(h => h(data));
    (this._handlers['*'] || []).forEach(h => h(type, data));
  }
}
