// Mini App - Bandwidth Optimization for Frontend
// Add to miniapp/js/main.js or equivalent

// ==========================================
// 1. Client-Side Caching
// ==========================================

/**
 * Cache API responses in localStorage to avoid repeated requests
 */
const API_CACHE = {
  CACHE_TTL: 5 * 60 * 1000, // 5 minutes

  async fetchWithCache(url, options = {}) {
    const cacheKey = `api_cache_${btoa(url)}`;
    const cached = localStorage.getItem(cacheKey);

    if (cached) {
      const { data, timestamp } = JSON.parse(cached);
      const age = Date.now() - timestamp;

      if (age < this.CACHE_TTL) {
        console.log('[Cache] Using cached response for:', url);
        return data;
      } else {
        localStorage.removeItem(cacheKey);
      }
    }

    const response = await fetch(url, options);
    const data = await response.json();

    // Cache successful GET requests
    if (options.method === 'GET' || !options.method) {
      if (response.ok) {
        localStorage.setItem(cacheKey, JSON.stringify({
          data,
          timestamp: Date.now()
        }));
      }
    }

    return data;
  }
};

/**
 * Replace fetch calls with cached version
 */
// Before: fetch('/api/groups/settings')
// After: API_CACHE.fetchWithCache('/api/groups/settings')


// ==========================================
// 2. ETag Support for Conditional Requests
// ==========================================

async function fetchWithETag(url) {
  const etagKey = `etag_${btoa(url)}`;
  const savedETag = localStorage.getItem(etagKey);

  const headers = {};
  if (savedETag) {
    headers['If-None-Match'] = savedETag;
  }

  const response = await fetch(url, { headers });

  if (response.status === 304) {
    // Not modified - use cached data
    const cached = localStorage.getItem(`data_${btoa(url)}`);
    return JSON.parse(cached);
  }

  if (response.ok) {
    const data = await response.json();
    const etag = response.headers.get('ETag');

    if (etag) {
      localStorage.setItem(etagKey, etag);
      localStorage.setItem(`data_${btoa(url)}`, JSON.stringify(data));
    }

    return data;
  }

  throw new Error(`HTTP ${response.status}`);
}


// ==========================================
// 3. Debounce Frequent Requests
// ==========================================

function debounceFetch(func, delay = 1000) {
  let timeoutId;

  return async function(...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(this, args), delay);
  };
}

// Usage:
// const debouncedUpdate = debounceFetch(updateSettings, 1000);


// ==========================================
// 4. Batch Multiple Updates
// ==========================================

class BatchUpdateQueue {
  constructor(apiEndpoint, flushInterval = 2000) {
    this.queue = [];
    this.apiEndpoint = apiEndpoint;
    this.flushInterval = flushInterval;
    this.timer = null;
  }

  add(update) {
    this.queue.push(update);

    if (!this.timer) {
      this.timer = setTimeout(() => this.flush(), this.flushInterval);
    }
  }

  async flush() {
    if (this.queue.length === 0) {
      this.timer = null;
      return;
    }

    const updates = [...this.queue];
    this.queue = [];
    this.timer = null;

    try {
      await fetch(this.apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates })
      });
    } catch (error) {
      console.error('[Batch] Failed to send updates:', error);
      // Re-queue on failure
      this.queue.unshift(...updates);
    }
  }
}

// Usage:
// const settingsQueue = new BatchUpdateQueue('/api/groups/settings/batch');
// settingsQueue.add({ key: 'value1' });
// settingsQueue.add({ key: 'value2' });


// ==========================================
// 5. Optimize Image Loading
// ==========================================

/**
 * Lazy load images only when visible
 */
function setupLazyLoading() {
  const images = document.querySelectorAll('img[data-src]');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        img.src = img.dataset.src;
        img.removeAttribute('data-src');
        observer.unobserve(img);
      }
    });
  });

  images.forEach(img => observer.observe(img));
}

/**
 * Use compressed image formats
 */
function getOptimizedImageURL(originalURL) {
  // If using a CDN, append compression parameters
  // Example: https://example.com/image.jpg -> https://example.com/image.jpg?format=webp&quality=80
  return originalURL; // Implement based on your image service
}


// ==========================================
// 6. Minify LocalStorage Usage
// ==========================================

function saveCompressed(key, data) {
  const json = JSON.stringify(data);
  const compressed = btoa(json); // Simple base64 compression
  localStorage.setItem(key, compressed);
}

function loadCompressed(key) {
  const compressed = localStorage.getItem(key);
  if (!compressed) return null;

  try {
    const json = atob(compressed);
    return JSON.parse(json);
  } catch (error) {
    return null;
  }
}


// ==========================================
// 7. WebSocket for Real-time Updates
// ==========================================

/**
 * Instead of polling, use WebSocket for real-time updates
 * Reduces API calls significantly
 */
class BandwidthOptimizedWebSocket {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.reconnectDelay = 1000;
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleUpdate(data);
    };

    this.ws.onclose = () => {
      console.log('[WS] Reconnecting in', this.reconnectDelay, 'ms');
      setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
    };

    this.ws.onopen = () => {
      this.reconnectDelay = 1000;
    };
  }

  handleUpdate(data) {
    // Handle real-time updates without polling
    console.log('[WS] Received update:', data);
  }
}


// ==========================================
// 8. Usage Examples
// ==========================================

// Example 1: Cached API call
async function getGroupSettings(groupId) {
  return API_CACHE.fetchWithCache(`/api/groups/${groupId}/settings`);
}

// Example 2: Batched settings updates
const settingsBatcher = new BatchUpdateQueue('/api/groups/settings/batch');

function updateSetting(key, value) {
  settingsBatcher.add({ key, value });
}

// Example 3: Debounced search
const searchHandler = debounceFetch(async (query) => {
  return API_CACHE.fetchWithCache(`/api/search?q=${encodeURIComponent(query)}`);
}, 500);


// ==========================================
// 9. Monitor Bandwidth Usage
// ==========================================

class BandwidthMonitor {
  constructor() {
    this.totalBytes = 0;
    this.requestCount = 0;

    // Override fetch to track usage
    const originalFetch = window.fetch;
    window.fetch = async (...args) => {
      const response = await originalFetch(...args);

      // Track response size
      const cloned = response.clone();
      const blob = await cloned.blob();
      this.totalBytes += blob.size;
      this.requestCount++;

      return response;
    };
  }

  getStats() {
    return {
      totalBytes: this.totalBytes,
      totalMB: (this.totalBytes / 1024 / 1024).toFixed(2),
      requestCount: this.requestCount
    };
  }

  logStats() {
    const stats = this.getStats();
    console.log('[Bandwidth]', stats);
  }
}

// Initialize bandwidth monitor
const bandwidthMonitor = new BandwidthMonitor();

// Log stats periodically
setInterval(() => bandwidthMonitor.logStats(), 60000); // Every minute


// ==========================================
// EXPORT
// ==========================================

// Export for use in main app
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    API_CACHE,
    fetchWithETag,
    debounceFetch,
    BatchUpdateQueue,
    setupLazyLoading,
    saveCompressed,
    loadCompressed,
    BandwidthOptimizedWebSocket,
    BandwidthMonitor
  };
}
