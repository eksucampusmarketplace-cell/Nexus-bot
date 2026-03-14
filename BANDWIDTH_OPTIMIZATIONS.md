# Bandwidth Optimizations

This document explains the changes made to reduce bandwidth usage in the Nexus Bot application.

## Summary of Changes

### 1. **Client-Side API Caching** (`miniapp/lib/api.js`)
- **What**: Added automatic caching for GET requests
- **Impact**: Reduces HTTP responses by ~30-50% for repeated requests
- **How it works**: 
  - GET requests are cached for 30 seconds by default
  - Subsequent requests within the TTL return cached data
  - Manual cache clearing available via `clearCache(path)`
  - Opt-out per request with `cacheOptions: { enabled: false }`

### 2. **GZip Compression** (`main.py`)
- **What**: Added GZip compression middleware for API responses
- **Impact**: Reduces HTTP response size by ~60-80% for JSON data
- **Configuration**:
  - Only compresses responses > 1KB (avoids overhead on small responses)
  - Compression level 6 (good balance between CPU and compression ratio)
  - Automatically applied to all API routes

### 3. **Optimized SSE (Server-Sent Events)** (`api/routes/events.py`, `miniapp/lib/sse.js`)
- **What**: Reduced payload sizes and smarter connection management
- **Impact**: Reduces "Service-Initiated" bandwidth by ~40-60%
- **Changes**:
  - Payload minimization: Filters out large internal fields
  - Compact JSON encoding (no extra whitespace)
  - Tab visibility awareness: Pauses SSE when tab is hidden
  - Reduced max retry attempts (10 → 5)
  - No reconnection attempts when tab is hidden

### 4. **Compact API Response Format** (`api/routes/analytics.py`)
- **What**: Shortened field names and removed null values
- **Impact**: Reduces analytics payload size by ~30-40%
- **Examples**:
  - `"date"` → `"d"` (e.g., `"0325"` instead of `"2025-03-25"`)
  - `"messages"` → `"m"`
  - `"joins"` → `"j"`
  - `"leaves"` → `"l"`
  - `"user_id"` → `"id"`
  - `"username"` → `"u"`
  - `"first_name"` → `"n"`
  - `"message_count"` → `"mc"`
  - `"trust_score"` → `"ts"`
  - Null values are stripped from responses

### 5. **Frontend Compatibility** (`miniapp/src/pages/analytics.js`)
- **What**: Updated frontend to support both compact and legacy API formats
- **Impact**: Ensures smooth transition without breaking changes
- **How**: Uses fallbacks like `day.m || day.messages` to support both formats

### 6. **Analytics Page Caching** (`miniapp/src/pages/analytics.js`)
- **What**: 5-minute client-side cache for analytics data
- **Impact**: Reduces analytics API calls by ~80-90%
- **Features**:
  - Refresh button for manual data updates
  - Cache age indicator ("just now", "5m ago", etc.)
  - Automatic cache invalidation when switching groups
  - Force refresh capability

### 7. **Member List Pagination** (`api/routes/members.py`)
- **What**: Server-side pagination for member lists
- **Impact**: Reduces large member list payload sizes
- **Features**:
  - Configurable page size (default: 50, max: 100)
  - Search/filter support
  - Pagination metadata (total count, total pages, has_next/has_prev)

### 8. **CDN-Ready Static Files** (`main.py`)
- **What**: Optimized cache headers for static assets
- **Impact**: Enables CDN caching for miniapp assets
- **Cache Policies**:
  - JS/CSS/Images: 1 year cache (immutable)
  - HTML: 1 minute cache
  - Other files: 1 hour cache
  - CORS headers for CDN compatibility

### 9. **Rate Limiting** (`main.py`, `api/routes/`)
- **What**: Request rate limiting to prevent abuse
- **Impact**: Prevents bandwidth exhaustion from abuse
- **Limits**:
  - Default: 100 requests/minute per IP
  - Analytics: 30 requests/minute per IP
  - Member Stats: 30 requests/minute per IP
  - Heatmap: 20 requests/minute per IP
  - SSE: Max 5 concurrent connections per IP

## Expected Bandwidth Savings

| Component | Before | After | Savings |
|-----------|--------|-------|---------|
| HTTP Responses | 15 MB | ~4-6 MB | ~60-75% |
| Service-Initiated (SSE) | 8 MB | ~2-4 MB | ~50-75% |
| **Total** | **23 MB** | **~6-10 MB** | **~60-75%** |

## Additional Recommendations

### 1. **Optimize Images**
If adding image uploads:
- Compress images before upload
- Use WebP format
- Implement responsive image sizes

### 2. **Virtual Scrolling**
For very large member lists:
- Implement virtual scrolling in frontend
- Only render visible items

## Monitoring

To track bandwidth usage after these changes:

1. **Check Render Dashboard**: Monitor the bandwidth graph
2. **Browser DevTools**: 
   - Open Network tab
   - Enable "Preserve log"
   - Check "Transferred" column for compressed sizes
3. **Server Logs**: Look for rate limit warnings in logs
4. **Response Headers**: Check for `Content-Encoding: gzip`

## Rollback

If any issues occur, you can disable features:

1. **Disable Caching**: Pass `{ enabled: false }` to `apiFetch()` calls
2. **Disable GZip**: Remove `GZipMiddleware` from `main.py`
3. **Revert SSE**: Restore original `sse.js` and `events.py`
4. **Disable Rate Limiting**: Remove `@limiter.limit()` decorators
5. **Disable Static File Caching**: Restore original StaticFiles usage

The frontend maintains backward compatibility with both API response formats.
