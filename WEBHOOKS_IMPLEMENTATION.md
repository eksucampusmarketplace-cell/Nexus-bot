# Webhook Integrations Implementation

## Overview
A complete webhook system has been implemented for Nexus Bot, allowing real-time event notifications to external services like Discord, Zapier, Make.com, and custom endpoints.

## Files Created

### 1. Database Migration
- **`db/migrations/add_webhooks.sql`** - Creates tables for webhook configurations and delivery logs

### 2. Database Operations
- **`db/ops/webhooks.py`** - CRUD operations for webhooks
  - `create_webhook()` - Create new webhook config
  - `get_webhooks()` - List all webhooks for a group
  - `get_active_webhooks_for_event()` - Get webhooks subscribed to specific events
  - `update_webhook()` - Update webhook configuration
  - `delete_webhook()` - Remove webhook
  - `log_webhook_delivery()` - Track delivery attempts
  - `get_webhook_deliveries()` - Get delivery history
  - `get_chat_webhook_stats()` - Get statistics

### 3. API Routes
- **`api/routes/webhooks.py`** - REST API endpoints
  - `GET /api/groups/{chat_id}/webhooks` - List webhooks
  - `POST /api/groups/{chat_id}/webhooks` - Create webhook
  - `GET /api/groups/{chat_id}/webhooks/{id}` - Get webhook details
  - `PUT /api/groups/{chat_id}/webhooks/{id}` - Update webhook
  - `DELETE /api/groups/{chat_id}/webhooks/{id}` - Delete webhook
  - `POST /api/groups/{chat_id}/webhooks/{id}/test` - Send test event
  - `GET /api/groups/{chat_id}/webhooks/{id}/deliveries` - Get delivery history
  - `GET /api/webhooks/events` - List available event types

### 4. Webhook Dispatcher
- **`bot/utils/webhook_dispatcher.py`** - Event dispatching service
  - `dispatch_event()` - Core dispatch function
  - `notify_member_join()` - Member join notifications
  - `notify_member_leave()` - Member leave notifications
  - `notify_ban()` - Ban notifications
  - `notify_mute()` - Mute notifications
  - `notify_warn()` - Warning notifications
  - `notify_kick()` - Kick notifications
  - `notify_automod()` - AutoMod action notifications
  - `notify_report()` - New report notifications

### 5. Mini App Page
- **`miniapp/src/pages/webhooks.js`** - Frontend UI for managing webhooks
  - List configured webhooks
  - Add/edit/delete webhooks
  - Select events to subscribe to
  - Test webhooks with sample payloads
  - View delivery statistics

## Events Supported

| Event | Description | Payload Fields |
|-------|-------------|----------------|
| `member_join` | New member joins | `user_id`, `username`, `first_name` |
| `member_leave` | Member leaves | `user_id`, `reason` |
| `ban` | Member banned | `user_id`, `admin_id`, `reason` |
| `unban` | Member unbanned | `user_id`, `admin_id` |
| `mute` | Member muted | `user_id`, `admin_id`, `duration_seconds` |
| `unmute` | Member unmuted | `user_id`, `admin_id` |
| `warn` | Warning issued | `user_id`, `admin_id`, `warn_count`, `max_warns`, `reason` |
| `kick` | Member kicked | `user_id`, `admin_id`, `reason` |
| `automod_trigger` | AutoMod action | `user_id`, `rule_triggered`, `action_taken` |
| `report_created` | New report | `report_id`, `reporter_id`, `reported_id`, `reason` |
| `settings_change` | Settings modified | `changed_by`, `changes` |
| `all` | Subscribe to everything | All of above |

## Security Features

1. **HMAC-SHA256 Signatures** - Webhooks can be configured with a secret key. Each payload is signed with `X-Webhook-Signature: sha256=<signature>` header.

2. **HTTPS Required** - Only HTTPS URLs are accepted for production webhooks.

3. **Delivery Logging** - All delivery attempts are logged with response status and timing.

4. **Automatic Retry** - Failed deliveries are tracked; webhooks with consecutive failures can be automatically disabled.

## Usage Example

### Creating a Webhook
```bash
curl -X POST https://your-bot.com/api/groups/-100123456789/webhooks \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Discord Notifications",
    "url": "https://discord.com/api/webhooks/...",
    "events": ["ban", "kick", "warn"],
    "secret": "my-secret-key"
  }'
```

### Received Payload
```json
{
  "event": "ban",
  "timestamp": 1704067200,
  "webhook_id": 123,
  "data": {
    "chat_id": -100123456789,
    "chat_title": "My Group",
    "user_id": 987654321,
    "admin_id": 123456789,
    "admin_name": "AdminUser",
    "reason": "Spam"
  }
}
```

### Verifying Signature (Python)
```python
import hmac
import hashlib

secret = b'my-secret-key'
payload = request.body
signature = 'sha256=' + hmac.new(secret, payload, hashlib.sha256).hexdigest()

if hmac.compare_digest(signature, request.headers['X-Webhook-Signature']):
    # Signature valid, process webhook
    pass
```

## Integration with Moderation Commands

The following handlers now trigger webhook notifications:
- `/warn` → `notify_warn()`
- `/ban` → `notify_ban()`
- `/mute` → `notify_mute()`
- `/kick` → `notify_kick()`

More integrations can be added by importing from `bot.utils.webhook_dispatcher` and calling the appropriate notify function.

## Mini App Integration

The webhooks page is integrated into the Mini App navigation:
- Added "Integrations" tab to sidebar
- Added `#page-webhooks` container
- Added route handler for `webhooks` page

## Future Enhancements

Potential improvements:
1. Retry logic with exponential backoff
2. Webhook batching for high-volume groups
3. Custom payload templates
4. Webhook filtering by user/role
5. Integration marketplace (Discord, Slack, etc.)
