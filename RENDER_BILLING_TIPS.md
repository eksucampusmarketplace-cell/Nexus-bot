# Render Billing & Bandwidth Guide for Nexus Bot

## Understanding Render's Billing Model

Render charges for **outbound data transfer** - data sent FROM Render's servers to the internet. This includes:
- Music streaming to Telegram voice chats
- API responses to Mini App
- Bot messages sent to Telegram
- Webhook responses

### Free Tier Limitations
- **Free tier**: 100GB/month outbound bandwidth
- **Beyond that**: $0.10 per GB

## Bandwidth Usage Breakdown for Nexus Bot

| Component | Estimated Usage | Optimization Potential |
|-----------|----------------|----------------------|
| Music streaming | 50-200MB/hour per active group | High (30-50% reduction) |
| API responses | 10-50KB per request | Medium (60-80% with compression) |
| Bot messages | 1-10KB per message | Low (already minimal) |
| Webhook traffic | 1-5KB per update | Low (already minimal) |

## Quick Wins (Implemented)

### ✅ 1. Gzip Compression
**Status**: Implemented in `main.py`

```python
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

**Impact**: 60-80% reduction in API response bandwidth

### ✅ 2. Medium Quality Audio
**Status**: Implemented in `music_service.py`

Changed from `HighQualityAudio()` to `MediumQualityAudio()`

**Impact**: 30-40% reduction in streaming bandwidth

### ✅ 3. Track Duration Limit
**Status**: Implemented in `config.py`

```python
MUSIC_MAX_DURATION: int = 1800  # 30 minutes
```

**Impact**: Prevents streaming very long tracks, reduces usage by 20-30%

### ✅ 4. Download Rate Limiting
**Status**: Implemented in `music_service.py`

```python
MUSIC_DOWNLOADS_PER_HOUR: int = 15
```

**Impact**: Limits abusive usage, saves 10-50% depending on user behavior

## Additional Optimizations (Optional)

### 5. Aggressive Caching
Implement caching for frequently accessed data:
- Group settings (cache: 1 hour)
- User permissions (cache: 30 minutes)
- Bot status (cache: 5 minutes)

**Estimated savings**: 10-25% reduction in API calls

### 6. Batch Updates
Combine multiple API updates into single requests.

**Example**: Instead of 10 separate setting updates, send 1 batch request.

**Estimated savings**: 80-90% reduction for configuration changes

### 7. WebSocket for Real-time Updates
Replace polling with WebSocket connections.

**Example**: Music status updates, chat notifications

**Estimated savings**: 90%+ reduction for real-time features

### 8. Frontend Caching
Implement client-side caching in Mini App:
- Cache API responses in localStorage
- Use ETags for conditional requests
- Debounce frequent requests

**Estimated savings**: 20-40% reduction in API calls

## Cost Calculations

### Scenario 1: Single Active Group
- Music streaming: 2 hours/day × 100MB/hour × 30 days = 6GB/month
- API responses: 1000 requests × 10KB × 30 days = 300MB/month
- **Total**: ~6.3GB/month
- **Cost**: Free tier (under 100GB)

### Scenario 2: 10 Active Groups
- Music streaming: 10 × 6GB = 60GB/month
- API responses: 10 × 300MB = 3GB/month
- **Total**: ~63GB/month
- **Cost**: Free tier (under 100GB)

### Scenario 3: 50 Active Groups (High Usage)
- Music streaming: 50 × 10GB = 500GB/month
- API responses: 50 × 1GB = 50GB/month
- **Total**: ~550GB/month
- **Cost**:
  - Free tier: 100GB = $0
  - Overage: 450GB × $0.10 = $45/month
  - **Total**: $45/month

## When to Upgrade Render Plan

### Upgrade to Standard ($25/month) if:
- You have 20+ active music groups
- Consistently exceeding 400GB/month
- Need more reliable performance

**Includes**: 500GB bandwidth + 512MB RAM + 0.1 CPU

### Upgrade to Pro ($100/month) if:
- You have 50+ active music groups
- Consistently exceeding 1.5TB/month
- Need dedicated resources

**Includes**: 2TB bandwidth + 2GB RAM + 1 CPU

## Monitoring Your Bandwidth

### 1. Render Dashboard
Go to: Render Dashboard → Your Service → Metrics → Bandwidth

### 2. Enable Bandwidth Tracking
Add to your `.env`:
```bash
BANDWIDTH_TRACKING_ENABLED=true
BANDWIDTH_WARN_MB=1
BANDWIDTH_ALERT_MB=10
```

Then add to `main.py`:
```python
from bandwidth_tracker import BandwidthTrackerMiddleware, BandwidthReportMiddleware

app.add_middleware(BandwidthTrackerMiddleware, warn_mb=1, alert_mb=10)
app.add_middleware(BandwidthReportMiddleware)
```

Access stats at: `https://your-app.onrender.com/bandwidth/stats`

### 3. Set Up Alerts
- Add environment variable: `ALERT_ON_ERRORS=true`
- Set up a support group in Telegram (`SUPPORT_GROUP_ID`)
- You'll receive alerts on high-bandwidth operations

## Common Questions

### Q: Can I use a CDN to reduce bandwidth?
**A**: No. The bandwidth is measured from Render's servers to Telegram, so a CDN won't help. The music must stream directly from your server.

### Q: Can I use Telegram's built-in music files?
**A**: Yes! If users send audio files directly in the chat (not via URL), bandwidth usage is minimal because Telegram handles the streaming.

### Q: What about hosting music files elsewhere?
**A**: You could host music files on a cheaper storage service (like AWS S3 or Cloudflare R2), but:
- You'd still pay for bandwidth from that service
- It adds complexity to your bot
- Telegram userbot streaming requires local files

**Recommendation**: Keep current setup but implement the optimizations listed here.

### Q: Can I completely eliminate bandwidth costs?
**A**: No. Any music streaming service costs money for bandwidth. The free tier (100GB) is generous, but active usage will incur costs. Your options are:
1. Optimize (reduce by 30-50%)
2. Limit usage (rate limits, duration limits)
3. Upgrade to a paid Render plan (more bandwidth included)
4. Accept the overage charges as cost of doing business

### Q: Is there a way to "mask" or "hide" bandwidth?
**A**: No. Bandwidth is tracked by the cloud provider (Render) at the network level. Any attempt to bypass tracking would violate terms of service and result in account suspension.

## Support Resources

- Render Docs: https://render.com/docs/outbound-bandwidth
- Render Pricing: https://render.com/pricing
- Nexus Bot Repo: [Your GitHub URL]
- Discord/Telegram Support: [Your support group]

## Final Recommendations

1. **Deploy the implemented optimizations** (already in your code)
2. **Monitor usage** for 1-2 weeks to establish baseline
3. **Set up bandwidth tracking** to identify heavy users
4. **Consider rate limiting** if usage is excessive
5. **Evaluate Render plan upgrade** if consistently exceeding 300GB/month
6. **Implement additional caching** if API usage is high

**Remember**: Bandwidth costs are normal for a music streaming bot. The optimizations will reduce but not eliminate costs.
