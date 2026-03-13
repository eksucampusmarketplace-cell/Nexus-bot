# Admin Requests Feature (@admins)

## Overview

The Admin Requests feature allows users to easily request admin help by mentioning `@admins` (or variations like `@admin`, `@mods`, etc.) in group messages. When detected, the bot creates a request record and notifies all admins with details and quick-action buttons.

## Features

### 1. Automatic Detection

The bot monitors all group messages and detects the following mention patterns:
- `@admins`
- `@admin`
- `@moderators`
- `@mods`
- `@ admins` (with space)
- `@ moderator` (with space)
- `@ moderators` (with space)

**Example:**
```
User: Hey @admins, can someone help me with this issue?
```

### 2. Request Creation

When a mention is detected:
1. Bot extracts the message context (500 chars max)
2. Creates a database record with request details
3. Increments user's request count
4. Sends confirmation to the user

### 3. Admin Notification

All group admins receive a private message with:
- Request ID
- User information (name, ID)
- Group name
- Message content
- Direct link to the original message
- Timestamp
- Inline buttons for quick actions

**Notification format:**
```
👋 Admin Request #123

From: @username (123456789)
Group: My Awesome Group
Message: Hey @admins, can someone help me...
Time: 2024-03-15 14:30 UTC

[📝 Responding] [✅ Close] [🔗 View in Chat]
```

### 4. Rate Limiting

To prevent spam, the feature includes configurable rate limiting:
- Default: 3 requests per hour per user
- Configurable per group
- Users exceeding limit receive a warning message

### 5. Status Tracking

Each request has a status:
- **open**: New request awaiting admin attention
- **responding**: Admin is working on the request
- **closed**: Request resolved

### 6. Admin Commands

#### `/admin_requests`
View all open admin requests for the group.

**Output:**
```
📋 Open Admin Requests (3)

#123 — 123456789
  Hey @admins, can someone help me...
  📅 03-15 14:30

#124 — 987654321
  Need help with spam...
  📅 03-15 15:45
```

#### `/admin_req_stats`
View statistics about admin requests.

**Output:**
```
📊 Admin Request Statistics

📝 Total Requests: 45
🔓 Open: 3
✅ Closed: 42
⏱️ Avg Response Time: 12.5 min
```

#### `/set_admin_requests [on|off] [limit] [period]`
Configure admin request settings.

**Examples:**
```
/set_admin_requests on                    # Enable with defaults
/set_admin_requests on 5 30               # 5 requests per 30 min
/set_admin_requests off                   # Disable feature
```

**View settings:**
```
/set_admin_requests
```

**Output:**
```
⚙️ Admin Request Settings

🔘 Status: ✅ Enabled
🔢 Rate Limit: 3 requests per 60 minutes

Usage:
/set_admin_requests on [limit] [period_min]
/set_admin_requests off
```

### 7. Quick Actions

Admins can respond to requests via inline buttons:

- **Responding**: Marks request as "responding" (shows admin is helping)
- **Close**: Marks request as closed
- **View in Chat**: Opens the original message in Telegram

### 8. Aliases

For convenience, these command aliases are available:
- `/areq` → `/admin_requests`
- `/areq_stats` → `/admin_req_stats`
- `/set_areq` → `/set_admin_requests`

## Database Schema

### `admin_requests` Table
```sql
CREATE TABLE admin_requests (
    id              BIGSERIAL PRIMARY KEY,
    chat_id         BIGINT      NOT NULL,
    user_id         BIGINT      NOT NULL,
    message_id      BIGINT      NOT NULL,
    message_text    TEXT        NOT NULL,
    reply_to_msg_id BIGINT,
    status          TEXT        NOT NULL DEFAULT 'open',
    responded_by    BIGINT,
    response_text   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at    TIMESTAMPTZ
);
```

### `users` Table (New Columns)
```sql
admin_request_count      INT NOT NULL DEFAULT 0
last_admin_request_at    TIMESTAMPTZ
```

### `groups` Table (New Columns)
```sql
admin_requests_enabled   BOOLEAN NOT NULL DEFAULT TRUE
admin_requests_rate_limit INT NOT NULL DEFAULT 3
admin_requests_rate_period INT NOT NULL DEFAULT 3600
```

## Usage Examples

### User Requesting Help

**Scenario 1: Simple mention**
```
User: @admins there's a spammer in the group
Bot: ✅ Admin request #1 sent!
     An admin will be notified and will help you shortly.

[Admins receive DM with details]
```

**Scenario 2: Replying to a message**
```
[User replies to spam message]
User: @admins please remove this spam
Bot: ✅ Admin request #2 sent!
```

**Scenario 3: Multiple variations**
```
User: Hey @mods, can you help?
User: @ admin I need assistance
User: @moderators someone please help
```

All of these will trigger the admin request system.

### Admin Responding

**From admin's private message:**
```
Admin clicks "📝 Responding"
→ Request status updates to "responding"
→ Message updates with: 📝 Responding: @admin_name
```

**Closing a request:**
```
Admin clicks "✅ Close"
→ Request status updates to "closed"
→ Message updates with: ✅ Closed by: @admin_name
```

## Integration with Existing Features

### Report System

The admin request system complements the existing `/report` command:
- **@admins**: Quick help requests, less formal
- **/report**: Flagging specific messages for moderation, more formal

Both systems notify admins and track status.

### Automod

The admin request handler runs **before** automod (group=-1), ensuring requests are processed even if the message would be caught by anti-spam filters.

## Configuration

### Enable/Disable per Group

```python
# Via command
/set_admin_requests on    # Enable
/set_admin_requests off   # Disable

# Via database (direct)
UPDATE groups SET admin_requests_enabled = TRUE WHERE chat_id = -1001234567890;
```

### Custom Rate Limits

```python
# Allow 5 requests every 30 minutes
/set_admin_requests on 5 30

# Strict: 1 request per hour
/set_admin_requests on 1 60

# Lenient: 10 requests per hour
/set_admin_requests on 10 60
```

## API/Database Functions

### `db/ops/admin_requests.py`

Key functions:
- `create_admin_request()` - Create new request
- `get_open_requests()` - Get open requests for a group
- `update_request_status()` - Update status
- `get_user_recent_request_count()` - Check rate limit
- `increment_user_request_count()` - Update user stats
- `get_group_request_stats()` - Get statistics
- `cleanup_old_requests()` - Remove old closed requests

## Handler Registration

In `bot/factory.py`:
```python
from bot.handlers.admin_request import (
    handle_admin_mention,
    admin_request_command_handlers,
    admin_request_callback
)

# Register commands
for h in admin_request_command_handlers:
    app.add_handler(h)

# Register message handler (runs before automod)
app.add_handler(MessageHandler(GROUP & filters.TEXT, handle_admin_mention), group=-1)

# Register callback handler
app.add_handler(CallbackQueryHandler(admin_request_callback, pattern=r'^admin_req:(responding|close):\d+$'))
```

## Logging

All admin request actions are logged:
- `[ADMIN_REQ] Created request #123 | chat=-100... user=12345...`
- `[ADMIN_REQ] Rate limited | chat=-100... user=12345... recent_count=3`
- `[ADMIN_REQ] Notified 5/6 admins for request #123`
- `[ADMIN_REQ] Closed | request_id=123 by=98765...`

Events are also logged to the group's log channel if configured.

## Security Considerations

1. **Admin-only commands**: All admin commands check permissions
2. **Rate limiting**: Prevents spam/abuse
3. **Bot message filtering**: Ignores bot messages
4. **Command filtering**: Skips messages that are commands
5. **DM handling**: Gracefully handles cases where admin has blocked bot

## Migration

Run the migration to create tables:
```bash
# The migration will be auto-run on next startup
# Or manually:
python -c "from db.migrate import run_migrations; import asyncio; asyncio.run(run_migrations())"
```

## Testing

### Test Scenarios

1. **Basic mention detection**
   - Send message with `@admins`
   - Verify request created
   - Verify admin notification sent

2. **Rate limiting**
   - Send multiple requests quickly
   - Verify rate limit warning after threshold

3. **Admin response**
   - Admin clicks "Responding"
   - Verify status update
   - Admin clicks "Close"
   - Verify request closed

4. **Configuration**
   - Disable feature with `/set_admin_requests off`
   - Verify mentions no longer trigger
   - Re-enable with custom rate limit

## Troubleshooting

### Mentions not detected
- Check if feature is enabled: `/set_admin_requests`
- Verify bot has admin permissions
- Check logs for errors

### Admins not receiving notifications
- Verify admin hasn't blocked the bot
- Check privacy settings allow DMs from bots
- Review logs for notification errors

### Rate limiting too strict
- Adjust with `/set_admin_requests on <limit> <period>`
- Set higher limit or longer period

## Future Enhancements

Potential improvements:
- Priority levels (urgent, normal, low)
- Request categories (spam, bug report, question)
- Auto-assignment of admins
- Request escalation for unhandled requests
- User feedback system
- Request templates
- Integration with ticket systems
- Request analytics dashboard in Mini App
