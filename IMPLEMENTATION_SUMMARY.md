# Admin Requests Feature - Implementation Summary

## Overview
Implemented a comprehensive @admins mention system that allows users to request admin help by mentioning @admins (or variations) in group messages.

## Files Created

### 1. Database Migration
**File:** `db/migrations/add_admin_requests.sql`
- Creates `admin_requests` table with full tracking
- Adds `admin_request_count` and `last_admin_request_at` columns to `users` table
- Adds `admin_requests_enabled`, `admin_requests_rate_limit`, `admin_requests_rate_period` columns to `groups` table
- Creates indexes for performance

### 2. Database Operations
**File:** `db/ops/admin_requests.py`
- `create_admin_request()` - Create new admin request
- `get_open_requests()` - Get all open requests for a group
- `get_request()` - Get single request by ID
- `update_request_status()` - Update request status
- `get_user_recent_request_count()` - Check rate limit compliance
- `increment_user_request_count()` - Update user stats
- `get_group_request_stats()` - Get statistics (total, open, closed, avg response time)
- `cleanup_old_requests()` - Remove old closed requests
- `get_group_setting()` / `set_group_setting()` - Configuration management

### 3. Message Handler
**File:** `bot/handlers/admin_request.py`
- `handle_admin_mention()` - Main handler for @admins mentions
- `contains_admin_mention()` - Detects 7+ mention patterns
- `extract_mention_context()` - Extracts relevant message context
- `cmd_admin_requests()` - List open requests (admin only)
- `cmd_admin_req_stats()` - Show statistics (admin only)
- `cmd_set_admin_requests()` - Configure feature (admin only)
- `admin_request_callback()` - Handle inline button actions
- Private notification system with quick-action buttons
- Rate limiting (default: 3 requests/hour, configurable)
- Status tracking (open, responding, closed)

### 4. Documentation
**File:** `ADMIN_REQUESTS_FEATURE.md`
- Complete feature documentation
- Usage examples
- Database schema
- Configuration guide
- Testing scenarios
- Troubleshooting tips

### 5. Test Scripts
**File:** `test_admin_requests_simple.py`
- Comprehensive test suite (no dependencies)
- Tests all patterns, files, and integration

## Files Modified

### 1. `bot/factory.py`
- Added imports for admin_request module
- Registered admin request command handlers
- Registered message handler (group=-1, before automod)
- Registered callback handler for inline buttons

### 2. `bot/utils/aliases.py`
- Added command aliases:
  - `/areq` → `/admin_requests`
  - `/areq_stats` → `/admin_req_stats`
  - `/set_areq` → `/set_admin_requests`

### 3. `bot/handlers/help.py`
- Added "📢 Admin Requests" category to help system
- Added help text for all admin request commands
- Added callback mapping for `help_areq`

## Features Implemented

### 1. Automatic Detection
- Detects mentions: `@admins`, `@admin`, `@moderators`, `@mods`
- Detects spaced mentions: `@ admins`, `@ moderator`, `@ moderators`
- Case-insensitive matching
- Ignores bot messages and commands

### 2. Request Creation
- Extracts up to 500 characters of message context
- Supports reply-to-message (captures target message ID)
- Generates unique request ID
- Stores full message in database

### 3. Admin Notifications
- Private DM to all group admins (except bots)
- Includes:
  - Request ID
  - User information (name, ID)
  - Group name
  - Message preview
  - Direct link to original message
  - Timestamp
- Inline buttons for quick actions:
  - "📝 Responding" - Mark as responding
  - "✅ Close" - Mark as closed
  - "🔗 View in Chat" - Open message in Telegram

### 4. Rate Limiting
- Per-user request counting
- Configurable rate limit (default: 3 per hour)
- Graceful warning when limit exceeded
- Tracks last request time

### 5. Status Tracking
- **open** - New request, awaiting admin attention
- **responding** - Admin is working on the request
- **closed** - Request resolved
- Status updates visible in notification message

### 6. Admin Commands
- `/admin_requests` - List open requests
- `/admin_req_stats` - Show statistics
- `/set_admin_requests [on|off] [limit] [period]` - Configure feature

### 7. User Feedback
- Confirmation message when request created
- Rate limit warning when exceeded
- Clear error messages for failures

## Database Schema

### admin_requests table
```sql
- id (BIGSERIAL PRIMARY KEY)
- chat_id (BIGINT NOT NULL)
- user_id (BIGINT NOT NULL)
- message_id (BIGINT NOT NULL)
- message_text (TEXT NOT NULL)
- reply_to_msg_id (BIGINT)
- status (TEXT NOT NULL DEFAULT 'open')
- responded_by (BIGINT)
- response_text (TEXT)
- created_at (TIMESTAMPTZ NOT NULL DEFAULT NOW())
- responded_at (TIMESTAMPTZ)
```

### Indexes
- idx_admin_requests_chat_id
- idx_admin_requests_status (composite: chat_id, status)
- idx_admin_requests_user_id
- idx_admin_requests_created_at

## Integration Points

### Handler Priority
- Message handler runs at group=-1 (highest priority)
- Runs before automod, ensuring requests are processed even if message is spam
- Command handlers run at default priority
- Callback handlers at default priority

### Existing Systems
- Complements `/report` command (formal vs informal)
- Uses existing permission system (`is_admin()`)
- Integrates with log channel system
- Compatible with Mini App configuration

## Testing

All tests passed:
- ✅ Mention pattern detection (7 patterns)
- ✅ File structure validation
- ✅ Handler implementation
- ✅ Database operations
- ✅ Factory integration
- ✅ Command aliases
- ✅ Help system integration
- ✅ Documentation completeness
- ✅ Migration SQL syntax
- ✅ Python syntax validation

## Configuration

### Default Settings
- Feature enabled: `TRUE`
- Rate limit: `3` requests
- Rate period: `3600` seconds (1 hour)

### Per-Group Configuration
```python
# Enable with defaults
/set_admin_requests on

# Enable with custom limits (5 requests per 30 minutes)
/set_admin_requests on 5 30

# Disable feature
/set_admin_requests off

# View current settings
/set_admin_requests
```

## Migration

The migration will run automatically on next bot startup. Manual migration:
```bash
python -m db.migrate
```

## Security Considerations

1. **Admin-only commands** - All admin commands verify permissions
2. **Rate limiting** - Prevents spam/abuse
3. **Bot message filtering** - Ignores bot messages
4. **Command filtering** - Skips messages that are commands
5. **DM handling** - Gracefully handles blocked bot DMs
6. **SQL injection protection** - Uses parameterized queries

## Future Enhancements (Not Implemented)

Potential improvements for future versions:
- Priority levels (urgent, normal, low)
- Request categories (spam, bug, question)
- Auto-assignment of admins
- Request escalation for unhandled requests
- User feedback system
- Request templates
- Integration with external ticket systems
- Analytics dashboard in Mini App

## Compatibility

- Works with both primary and clone bots
- Compatible with webhook mode
- No breaking changes to existing functionality
- Follows existing code patterns and conventions
- Uses existing database connection pool
