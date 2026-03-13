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

## Expected Bandwidth Savings

| Component | Before | After | Savings |
|-----------|--------|-------|---------|
| HTTP Responses | 15 MB | ~5-7 MB | ~50-65% |
| Service-Initiated (SSE) | 8 MB | ~3-5 MB | ~40-60% |
| **Total** | **23 MB** | **~8-12 MB** | **~50-70%** |

## Additional Recommendations

### 1. **Reduce Analytics Refresh Frequency**
Currently the analytics page fetches data on every visit. Consider:
- Only refreshing when explicitly requested (add a refresh button)
- Caching analytics data for longer (e.g., 5 minutes)

### 2. **Paginate Large Lists**
For groups with many members:
- Implement pagination for member lists
- Use virtual scrolling for large tables

### 3. **Optimize Images**
If adding image uploads:
- Compress images before upload
- Use WebP format
- Implement responsive image sizes

### 4. **CDN for Static Assets**
For production deployment:
- Use a CDN for static files (miniapp assets)
- Enable browser caching with long cache headers

### 5. **Rate Limiting**
Consider adding rate limiting for:
- API endpoints to prevent abuse
- SSE connections per user

## Monitoring

To track bandwidth usage after these changes:

1. **Check Render Dashboard**: Monitor the bandwidth graph
2. **Browser DevTools**: 
   - Open Network tab
   - Enable "Preserve log"
   - Check "Transferred" column for compressed sizes
3. **Server Logs**: Look for compression ratio in FastAPI logs (if enabled)

## Rollback

If any issues occur, you can disable features:

1. **Disable Caching**: Pass `{ enabled: false }` to `apiFetch()` calls
2. **Disable GZip**: Remove `GZipMiddleware` from `main.py`
3. **Revert SSE**: Restore original `sse.js` and `events.py`

The frontend maintains backward compatibility with both API response formats.
