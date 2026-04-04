# Nexus Bot Access Control Guide

## Role Hierarchy (Highest to Lowest)

```
┌─────────────────────────────────────────────────────────────┐
│  1. OVERLORD (Main Bot Owner)                               │
│     - User ID matches settings.OWNER_ID                     │
│     - Has UNRESTRICTED access to everything                 │
│     - Can manage all bots, all groups, all settings         │
│     - Rate limit: 1000 requests/minute                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. CLONE OWNER                                             │
│     - User who created/owns a clone bot                     │
│     - Can manage THEIR bot's settings                       │
│     - Can view their bot's groups in "My Bots" page         │
│     - To AFFECT a group (ban, mute, etc.):                  │
│       MUST also be Telegram admin in that group             │
│     - Rate limit: 120 requests/minute                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. TELEGRAM ADMIN                                          │
│     - Admin in a specific Telegram group                    │
│     - Can use bot commands in groups where admin            │
│     - Cannot access bot management features                 │
│     - Rate limit: 60 requests/minute                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. MEMBER                                                  │
│     - Regular group member                                  │
│     - Can use basic commands (info, stats, etc.)            │
│     - Cannot use moderation commands                        │
│     - Rate limit: 60 requests/minute                        │
└─────────────────────────────────────────────────────────────┘
```

## Key Concept: Two Types of Access

### 1. Bot Management Access (Mini App "My Bots" page)
- **Overlord**: Can manage ALL bots
- **Clone Owner**: Can manage THEIR OWN clone bots only
- **Regular Users**: Cannot access bot management

### 2. Group Operations Access (In Telegram Groups)
- **Overlord**: Can do anything in any group
- **Clone Owner**: 
  - Can VIEW their bot's groups in Mini App
  - Can only AFFECT groups where they are Telegram admin
  - Example: Clone owner can see Group A in "My Bots", but to ban someone there, they must be admin in Group A
- **Telegram Admin**: Can use bot commands in their groups

## Examples

### Example 1: Clone Owner Scenario
```
Alice creates a clone bot (@AliceCloneBot)

Scenario:
1. Alice adds @AliceCloneBot to "Group X" (she's admin there) ✓
2. Bob adds @AliceCloneBot to "Group Y" (Alice is NOT in Group Y)

In Mini App:
- Alice sees BOTH groups under "My Bots" → "View Groups"
- She can manage bot settings for both

In Telegram:
- In Group X: Alice can use /ban, /mute, etc. (she's admin)
- In Group Y: Alice CANNOT use moderation commands (she's not admin there)
- The bot still works in Group Y, but Alice can't moderate
```

### Example 2: Overlord Scenario
```
The Overlord (main bot owner) has @MainBot

Scenario:
1. Overlord can access EVERYTHING in Mini App
2. Overlord can use ANY command in ANY group
3. Overlord can manage ALL clone bots
```

### Example 3: Regular Admin Scenario
```
Charlie is admin in "Group Z" where @MainBot is added

Scenario:
- Charlie can use moderation commands in Group Z
- Charlie CANNOT access "My Bots" page
- Charlie can only see Group Z in main dashboard (not other groups)
```

## Code Usage

### Check if user is overlord:
```python
from bot.utils.access_control import check_main_bot_owner

if await check_main_bot_owner(user_id):
    # User is overlord - allow anything
```

### Check if user is clone owner:
```python
from bot.utils.access_control import check_clone_owner

if await check_clone_owner(user_id, bot_id):
    # User owns this clone bot
```

### Check if clone owner can affect a group:
```python
from bot.utils.access_control import can_affect_group

if await can_affect_group(user_id, chat_id, bot_id, context):
    # Can perform moderation actions
```

### Protect a handler for overlord only:
```python
from bot.utils.access_control import require_main_bot_owner

@require_main_bot_owner()
async def secret_admin_command(update, context):
    # Only overlord can use this
```

### Protect a handler requiring admin privileges:
```python
from bot.utils.access_control import require_admin_or_owner

@require_admin_or_owner(operation="ban")
async def ban_command(update, context):
    # Requires admin or overlord
    # Clone owners must also be Telegram admins
```

## API Auth Roles

When a user authenticates in the Mini App, they get these fields:

```python
user = {
    "id": 123456789,
    "role": "overlord",  # or "owner", "admin"
    "is_overlord": True,  # only for main bot owner
    "is_clone_owner": True,  # only for clone owners
    "validated_bot_id": 12345,  # the bot they authenticated with
}
```

### Usage in API routes:

```python
from api.auth import require_overlord, require_clone_owner_or_overlord

# Only overlord can access
@router.get("/super-secret")
async def secret_endpoint(user: dict = Depends(require_overlord)):
    ...

# Clone owners or overlord can access
@router.get("/bot-management")
async def management_endpoint(user: dict = Depends(require_clone_owner_or_overlord)):
    ...
```

## Rate Limits

| Role | Requests/Minute |
|------|----------------|
| Overlord | 1000 |
| Clone Owner | 120 |
| Regular User | 60 |

## Summary

1. **Overlord** = God mode (main bot owner)
2. **Clone Owner** = Can manage their bot, but needs Telegram admin rights to moderate groups
3. **Telegram Admin** = Can use bot in their groups only
4. **Member** = Basic usage only

The key distinction is:
- **Bot Management** (Mini App "My Bots") = Based on bot ownership
- **Group Operations** (Telegram commands) = Based on Telegram admin status
