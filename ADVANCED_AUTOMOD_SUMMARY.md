# Advanced Automod Engine - Implementation Summary

## Overview
Implemented a complete advanced automod engine for Nexus Bot, covering all missing features from Baymax and Group Booster.

## ✅ Completed Components

### 1. Database Layer (`db/migrations/add_advanced_automod.sql`)
- `rule_time_windows` - Per-rule active time windows (e.g., link lock only 23:30-08:10)
- `rule_penalties` - Custom penalties per rule (delete/silence/kick/ban with duration)
- `silent_times` - 3 silent time slots per group
- `message_hashes` - Duplicate message tracking with MD5 hashing
- `regex_patterns` - Custom REGEX patterns for content filtering
- `necessary_words` - Required word lists (every message must contain one)
- `rule_priority` - Drag-and-drop rule evaluation order
- `rule_templates` - Built-in presets (Gaming, Study, Crypto, News, Support, Strict)
- Updated `groups` table with advanced automod settings columns

### 2. Database Operations (`db/ops/automod.py`)
Functions for all advanced automod features:
- Time window management
- Penalty configuration
- Silent time slot management
- Message hash tracking and duplicate detection
- REGEX pattern CRUD
- Necessary words CRUD
- Rule priority ordering
- Bulk settings updates
- Whitelist and warning tracking

### 3. Automod Engine (`bot/automod/engine.py`)
Central evaluation engine called for every non-admin message:

**Evaluation Order (respects rule_priority table):**
1. Whitelist check → skip if whitelisted
2. Lock admins check → skip if admin AND lock_admins=False
3. Silent time check → delete if in silent window
4. Content type locks (with time window check)
5. Unofficial Telegram detection
6. Duplicate message check (MD5 hash + time window)
7. Word/line/char count checks
8. Necessary words check
9. REGEX pattern check
10. Legacy automod (backward compatibility)

**For each violation:**
- Get per-rule penalty from rule_penalties table
- Fall back to group default penalty
- Apply penalty (delete/silence/kick/ban)
- Send admonition if enabled (with self-destruct timer)
- Push SSE event to Mini App

### 4. Detectors (`bot/automod/detectors.py`)
- `detect_content_type()` - Classifies message type (photo, video, sticker, etc.)
- `detect_unofficial_telegram()` - Detects spam from unofficial TG clients
- `is_in_time_window()` - Time window checking with midnight-spanning support

### 5. Penalties (`bot/automod/penalties.py`)
- `PenaltyType` enum: delete, silence, kick, ban
- `apply_penalty()` - Applies penalties with optional duration
  - silence: restrict can_send_messages
  - kick: ban then unban immediately
  - ban: permanent or timed ban

### 6. Advanced Automod Commands (`bot/handlers/advanced_automod.py`)
All commands parse via triple-prefix system (!/!!/):

**Timed Rules:**
- `!lock link from 23:30 to 8:10`
- `!unlock link from 23:30 to 8:10`

**Per-Violation Penalties:**
- `!kick link`
- `!silence photo 24` (24h duration)
- `!delete forward`
- `!ban website`

**Silent Times:**
- `!first silent time from 23 to 8`
- `!disable first silent time`
- `!second silent time from 10 to 14`
- `!third silent time from 18 to 20`
- `!delete all silent times`

**Self-Destruct:**
- `!enable self-destruct`
- `!disable self-destruct`
- `!self-destruct time set on 2`

**Duplicate Limiting:**
- `!duplicate set on 3`
- `!duplicate set on disable`
- `!duplicate in every 2 hours` / `!duplicate in every 30 min`

**Word/Line/Char Counts:**
- `!minimum number of words set on 3`
- `!maximum number of words set on 10`
- `!min.text.line 2` / `!max.text.line 10`
- `!min.text.length 10` / `!max.text.length 500`

**REGEX:**
- `!regex add ^\d{10}$`
- `!regex remove ^\d{10}$`
- `!regex list`
- `!regex test ^\d{10}$ some string`

**Necessary Words:**
- `!be.in.text hello`
- `!!be.in.text hello` (remove)
- `!beintexts` (clear all)

**Lock Admins:**
- `!lock admins`
- `!unlock admins`

**Timed Locks:**
- `!timedlock image 08:00 12:00`
- `!!timedlock image`

### 7. API Routes (`api/routes/automod.py`)
- `GET /api/groups/{chat_id}/automod/advanced` - Get all settings
- `PUT /api/groups/{chat_id}/automod/advanced` - Bulk update settings
- `GET /api/groups/{chat_id}/automod/templates` - List templates
- `POST /api/groups/{chat_id}/automod/templates/apply` - Apply template
- `PUT /api/groups/{chat_id}/automod/rule-priority` - Save drag-drop order
- `GET /api/groups/{chat_id}/automod/conflicts` - Detect rule contradictions

### 8. Mini App - AutoMod Page
Two versions created:

**React Version** (`src/pages/AutoMod.jsx`):
- Full React implementation with @dnd-kit for drag-and-drop
- Uses Framer Motion for animations
- Complete UI with all sections

**Vanilla JS Version** (`src/pages/automod.js`):
- Compatible with existing Vanilla JS foundation
- No external dependencies beyond Zustand
- Full feature parity with React version

**UI Sections:**
1. **Rule Templates** - One-tap presets (Gaming, Study, Crypto, etc.)
2. **Silent Times** - 3 configurable time slots
3. **Message Controls** - Word/line/char limits, duplicate settings
4. **Rule Priority** - Drag-and-drop reordering
5. **REGEX Manager** - Add/test/remove patterns
6. **Necessary Words** - Required word list management
7. **Advanced Settings** - Self-destruct, lock admins, unofficial TG, bot inviter ban, REGEX toggle
8. **Conflict Detector** - Live warning panel for contradictory rules

### 9. Integration Updates
- `main.py` - Added automod router
- `bot/factory.py` - Added advanced_automod handler import and registration
- `bot/handlers/automod.py` - Integrated engine check_message() call
- `miniapp/index.html` - Added AutoMod page to navigation and rendering
- `requirements.txt` - Added pytz and emoji dependencies

## Features Implemented

### ✅ Per-Rule Timed Enforcement
- Time windows per rule (e.g., link lock only active 23:30-08:10)
- Midnight-spanning windows supported
- Timezone-aware checking

### ✅ Per-Violation Custom Penalties
- Custom penalty per rule (delete/silence/kick/ban)
- Duration support for silence/ban
- Falls back to group default penalty

### ✅ Silent Time Slots
- 3 configurable time slots per group
- Custom start/end text per slot
- Active/inactive toggle per slot

### ✅ Self-Destruct Bot Messages
- Toggle to enable/disable
- Configurable timer (minutes)
- Auto-deletes bot replies after violation

### ✅ Duplicate Message Limiting
- MD5 hash-based detection
- Configurable limit (N messages)
- Configurable time window (X minutes)
- Automatic cleanup of old hashes

### ✅ Min/Max Word Count
- Minimum word count enforcement
- Maximum word count enforcement
- Disabled with 0

### ✅ Min/Max Line Count
- Minimum line count enforcement
- Maximum line count enforcement

### ✅ Min/Max Char Count
- Minimum character count enforcement
- Maximum character count enforcement

### ✅ REGEX Pattern Matching
- Python re-compatible patterns
- Per-pattern penalty configuration
- Active/inactive toggle per pattern
- Built-in test function

### ✅ Necessary Words
- Required word list
- Every message must contain at least one word
- Active/inactive toggle

### ✅ Lock Admins Mode
- Apply all rules to admins
- Group creator exemption only

### ✅ Unofficial Telegram Detection
- Detects known spam client signatures
- Configurable penalty

### ✅ Bot Inviter Ban
- Ban whoever adds a bot to the group
- Configurable action

### ✅ Timed Locks
- Time-based rule activation
- Separate from per-rule time windows

### ✅ Rule Conflict Detector
- Detects contradictions (text locked + min_words)
- Detects redundancy (no_caption + photo lock)
- Detects impossible rules (min > max)
- Live warnings in Mini App

### ✅ Drag-and-Drop Rule Priority
- Reorder rule evaluation order
- Saved to database
- Reflected in engine evaluation

### ✅ Rule Templates
- 6 built-in templates: Gaming, Study, Crypto, News Channel Group, Support, Strict
- One-tap apply
- Merges settings with existing

### ✅ Command Builder UI (via text commands)
- All advanced automod commands support triple-prefix (!/!!)
- Clear command syntax validation
- Friendly error messages

## Architecture Notes

### Logging Prefixes
- `[AUTOMOD]` - Main engine
- `[AUTOMOD_CMD]` - Command handler
- `[PENALTIES]` - Penalty application

### Timezone Support
- All time-based features use group's configured timezone
- Falls back to UTC if not configured

### SSE Events
- Push events to Mini App on enforcement
- Event types: message_delete, member_silence, member_kick, member_ban

### Backward Compatibility
- Legacy automod (antiflood, antilink, etc.) preserved
- Existing commands continue to work
- Engine check runs before legacy checks

### Performance
- MD5 hashing for efficient duplicate detection
- Index on message_hashes for fast lookups
- Async non-blocking self-destruct tasks
- Connection pooling via asyncpg

## Database Schema

### New Tables
```sql
rule_time_windows (chat_id, rule_key, start_time, end_time, is_active)
rule_penalties (chat_id, rule_key, penalty, duration_hours)
silent_times (chat_id, slot, start_time, end_time, is_active, start_text, end_text)
message_hashes (chat_id, msg_hash, user_id, sent_at)
regex_patterns (chat_id, pattern, penalty, is_active)
necessary_words (chat_id, word, is_active)
rule_priority (chat_id, rule_order)
rule_templates (id, name, description, settings, is_builtin)
```

### Updated Tables
```sql
groups (added: self_destruct_enabled, self_destruct_minutes, lock_admins,
        unofficial_tg_lock, bot_inviter_ban, duplicate_limit,
        duplicate_window_mins, min_words, max_words, min_lines,
        max_lines, min_chars, max_chars, necessary_words_active,
        regex_active, timed_locks)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|-----------|-------------|
| GET | `/api/groups/{chat_id}/automod/advanced` | Get all advanced settings |
| PUT | `/api/groups/{chat_id}/automod/advanced` | Bulk update settings |
| GET | `/api/groups/{chat_id}/automod/templates` | List templates |
| POST | `/api/groups/{chat_id}/automod/templates/apply` | Apply template |
| PUT | `/api/groups/{chat_id}/automod/rule-priority` | Save rule order |
| GET | `/api/groups/{chat_id}/automod/conflicts` | Detect conflicts |

## Testing Notes

### Manual Testing
1. Run migration: `psql -f add_advanced_automod.sql`
2. Test commands via Telegram (use ! prefix)
3. Open Mini App AutoMod page
4. Test rule templates
5. Test conflict detection (create contradictory rules)
6. Verify SSE events on violations

### Key Test Cases
- Timed lock outside window → should not trigger
- Timed lock inside window → should trigger
- Duplicate within limit → allowed
- Duplicate over limit → should trigger
- Necessary words missing → should trigger
- REGEX match → should trigger
- REGEX non-match → should allow

## Dependencies Added
- `pytz>=2023.3` - Timezone support
- `emoji>=2.10.0` - Emoji detection in text analysis

## Future Enhancements (Not in Scope)
- ML-based spam detection
- Content-aware regex suggestions
- Bulk rule import/export
- Multi-language conflict detection
- Analytics on rule effectiveness
