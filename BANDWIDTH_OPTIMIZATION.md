# Nexus Bot - Bandwidth Optimization Guide

## Understanding Render Bandwidth Billing

Render charges for **outbound data transfer** from their servers. You cannot "mask" or hide this - it's a fundamental aspect of cloud hosting. However, you can **reduce** bandwidth usage through optimization.

## Main Bandwidth Consumers in Nexus

1. **Music streaming** (largest consumer)
   - Downloads audio from YouTube/SoundCloud/Spotify
   - Streams audio via Telegram voice chats

2. **Telegram webhook traffic**
   - Bot receives updates from Telegram

3. **API responses** (Mini app)
   - JSON data responses

4. **Bot API calls**
   - Sending messages, photos, documents

## Optimization Strategies

### 1. Music Streaming Optimizations (Highest Impact)

#### a) Lower Audio Quality
```python
# In music_service.py, line 36
from pytgcalls.types.input_stream.quality import MediumQualityAudio
# Change HighQualityAudio() to MediumQualityAudio()
```

**Impact**: Reduces streaming bandwidth by 30-40%

#### b) Reduce Max Track Duration
```python
# In config.py, line 41
MUSIC_MAX_DURATION: int = 1800  # 30 min instead of 1 hour
```

**Impact**: Prevents users from streaming very long tracks

#### c) Download Limits
```python
# Add rate limiting per group
MUSIC_DOWNLOADS_PER_HOUR: int = 20
```

#### d) Cache Frequently Played Tracks
```python
# Implement caching to avoid re-downloading popular tracks
```

### 2. Response Compression

#### a) Enable Gzip Compression
```python
# In main.py, add middleware
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

**Impact**: 60-80% reduction for JSON API responses

#### b) Minify JSON Responses
```python
# Remove unnecessary fields from API responses
```

### 3. Telegram Bot API Optimizations

#### a) Use InputFile for Media
```python
# Instead of sending file URLs, use InputFile
# This avoids bot server transferring the file
```

#### b) Webhook Response Optimization
```python
# Return empty responses when possible
# Process updates asynchronously
```

### 4. Caching Strategy

#### a) Redis Caching
```python
# Cache frequently accessed data
# Group settings, user info, music metadata
```

#### b) Mini App Caching
```javascript
// Cache API responses in localStorage
// Use ETag headers for conditional requests
```

## Monitoring Bandwidth

### Enable Bandwidth Logging
```python
# Add bandwidth tracking middleware
```

### Set Alerts
```python
# Alert if bandwidth exceeds thresholds
```

## Cost Comparison

| Optimization | Estimated Savings | Implementation Effort |
|-------------|------------------|---------------------|
| Lower audio quality | 30-40% | Low |
| Gzip compression | 15-20% | Very Low |
| Track duration limit | 20-30% | Low |
| Download limits | 10-50% | Medium |
| Caching | 10-25% | Medium |

## Implementation Priority

1. **Immediate** (5 minutes):
   - Enable Gzip compression
   - Lower audio quality to Medium
   - Reduce max track duration

2. **Short-term** (1 hour):
   - Add download rate limiting
   - Implement response caching

3. **Long-term** (1 day):
   - Advanced caching system
   - Bandwidth monitoring dashboard

## Important Notes

- These optimizations **reduce** legitimate bandwidth usage
- They do **not** "mask" or "hide" bandwidth (impossible)
- All changes comply with Render's terms of service
- User experience may change slightly (lower audio quality, etc.)

## Render Billing Tiers

Consider upgrading to:
- **Starter**: $7/mo - Includes 100GB bandwidth
- **Standard**: $25/mo - Includes 500GB bandwidth
- **Pro**: $100/mo - Includes 2TB bandwidth

If your usage consistently exceeds free limits, upgrading is more cost-effective than aggressive optimization.
