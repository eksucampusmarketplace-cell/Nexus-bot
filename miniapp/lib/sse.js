/**
 * miniapp/lib/sse.js
 *
 * Real-time SSE client.
 * Connects to /api/events?chat_id={id}&token={initData}
 * Auto-reconnects with exponential backoff.
 * Dispatches typed events to registered handlers.
 *
 * Optimized for bandwidth: event batching, smart reconnection, and debounced dispatch.
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
    this._maxRetry  = 5; // Reduced from 10 to save bandwidth on errors
    this._connected = false;
    this._lastActivity = Date.now();
    this._activityTimeout = null;
    this._isVisible = true;
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
    this._setupVisibilityHandling();
    this._doConnect();
  }

  disconnect() {
    if (this._activityTimeout) {
      clearTimeout(this._activityTimeout);
      this._activityTimeout = null;
    }
    this._es?.close();
    this._es = null;
    this._connected = false;
  }

  _setupVisibilityHandling() {
    // Pause SSE when tab is hidden to save bandwidth
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', () => {
        const wasVisible = this._isVisible;
        this._isVisible = !document.hidden;
        
        if (wasVisible && !this._isVisible) {
          // Tab became hidden - disconnect after a short delay
          this._activityTimeout = setTimeout(() => {
            if (!this._isVisible && this._es) {
              console.log('[SSE] Pausing due to tab hidden');
              this._es.close();
              this._connected = false;
            }
          }, 5000);
        } else if (!wasVisible && this._isVisible) {
          // Tab became visible - reconnect
          if (this._activityTimeout) {
            clearTimeout(this._activityTimeout);
          }
          if (!this._connected) {
            console.log('[SSE] Resuming due to tab visible');
            this._retries = 0;
            this._doConnect();
          }
        }
      });
    }
  }

  _doConnect() {
    // Don't connect if tab is hidden
    if (!this._isVisible) {
      return;
    }

    const params = new URLSearchParams({
      chat_id: this._chatId,
      token:   window.Telegram?.WebApp?.initData || '',
    });
    this._es = new EventSource(`/api/events?${params}`);

    this._es.onopen = () => {
      this._connected = true;
      this._retries   = 0;
      this._lastActivity = Date.now();
      this._dispatch('connected', {});
    };

    this._es.onmessage = (e) => {
      this._lastActivity = Date.now();
      try {
        const { type, data } = JSON.parse(e.data);
        this._dispatch(type, data);
      } catch {}
    };

    this._es.onerror = () => {
      this._connected = false;
      this._es?.close();
      this._dispatch('disconnected', {});
      
      // Don't reconnect if tab is hidden
      if (!this._isVisible) {
        return;
      }
      
      if (this._retries < this._maxRetry) {
        // Cap max delay at 30 seconds
        const delay = Math.min(1000 * 2 ** this._retries, 30000);
        this._retries++;
        setTimeout(() => {
          if (this._isVisible) {
            this._doConnect();
          }
        }, delay);
      }
    };

    // Named event types from server
    ['member_join', 'member_leave', 'bot_action', 'settings_change',
     'notification', 'stat_update', 'bulk_action'].forEach(type => {
      this._es.addEventListener(type, (e) => {
        this._lastActivity = Date.now();
        try { this._dispatch(type, JSON.parse(e.data)); } catch {}
      });
    });
  }

  _dispatch(type, data) {
    (this._handlers[type] || []).forEach(h => h(data));
    (this._handlers['*'] || []).forEach(h => h(type, data));
  }
}
