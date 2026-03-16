# Dashboard Stats Fix - Implementation Summary

## Issue #1: Stats Showing All Zeros & No Activity

This document summarizes the fixes implemented to resolve the dashboard statistics issues where Total Members, Messages Today, and Actions Today were all showing zeros.

## Fixes Implemented

### Fix 1: Refresh member_count on Dashboard Load
**File**: `api/routes/groups.py`
- **Issue**: The `member_count` field in the groups table was never updated when the bot was already in a group - only updated on join/new group events.
- **Solution**: Added live member count refresh using Telegram API in the `/api/groups/{chat_id}` endpoint
- **Implementation**:
  - Fetches live member count from Telegram using `get_chat_member_count()`
  - Updates the in-memory group object
  - Persists the updated count to the database for future reads
  - Handles multiple bot instances gracefully via the registry

### Fix 2: Schema Mismatch in Analytics Query
**File**: `api/routes/analytics.py`
- **Issue**: Query uses 'day' and 'message_count' columns (new schema from add_ml_pipeline.sql)
- **Status**: Already correct - no changes needed
- **Verification**: The analytics endpoint correctly queries the new schema columns

### Fix 3: Fix Logs Response Parsing in Dashboard
**File**: `miniapp/index.html`
- **Issue**: Frontend checked `Array.isArray(logs)` but the API might return wrapped objects
- **Solution**: Added robust normalization of the logs response
- **Implementation**:
  - Renamed `logs` to `logsRaw` in the destructuring
  - Added normalization logic that handles both bare arrays and wrapped objects
  - Ensures logs is always an array before use

### Fix 4: Write message_count Per Chat on Every Message
**Files**: `bot/handlers/message_tracking.py` (new), `bot/factory.py`
- **Issue**: No code was writing to `bot_stats_daily.message_count` when messages arrived
- **Solution**: Created real-time message tracking handler
- **Implementation**:
  - Created new handler `track_message()` that increments `message_count` for each message
  - Uses UPSERT with ON CONFLICT to safely increment daily counts
  - Registered at group=-999 to run after all other handlers
  - Leverages existing UNIQUE constraint on (chat_id, day)

### Fix 5: Backfill Actions Today from Existing Logs
**File**: `miniapp/index.html`
- **Issue**: Actions Today showed total logs instead of filtering by today's date
- **Solution**: Added date filtering to count only today's actions
- **Implementation**:
  - Filters logs array to only include logs from today
  - Supports both `timestamp` and `created_at` field names for compatibility
  - Counts only today's moderation actions

## Database Schema

The `bot_stats_daily` table already has the correct schema:
- `chat_id` BIGINT NOT NULL
- `day` DATE NOT NULL
- `message_count` INT DEFAULT 0
- UNIQUE constraint on (chat_id, day)

This schema is created by the `add_ml_pipeline.sql` migration which should already be applied.

## Files Modified

1. `api/routes/groups.py` - Added live member count refresh
2. `bot/factory.py` - Registered message tracking handler
3. `miniapp/index.html` - Added logs normalization and Actions Today filtering
4. `bot/handlers/message_tracking.py` - New file for real-time message tracking

## Testing Recommendations

After deploying these fixes, verify:

1. **Total Members**: Open dashboard → check Total Members stat
   - Expected: Should match Telegram group member count (e.g., 4)

2. **Messages Today**: Send a test message in the group, wait 5 seconds, refresh dashboard
   - Expected: Should increment by 1

3. **Actions Today**: Run /ban or /warn on a test account, refresh dashboard
   - Expected: Should show 1 or more

4. **Recent Activity**: After any ban/warn/kick action, refresh dashboard
   - Expected: Should list the action with timestamp

## Migration Note

Ensure the `add_ml_pipeline.sql` migration has been applied to your database:
```bash
python db/migrate.py
```

This migration creates the `bot_stats_daily` table with the correct schema including the `day`, `chat_id`, and `message_count` columns.

## Implementation Date
March 16, 2026
