# Security Features Documentation

## Overview

This document describes the comprehensive security measures implemented in the Nexus Telegram Bot to prevent spam, injection attacks, and malicious input throughout the Mini App and bot interfaces.

---

## Table of Contents

1. [Input Sanitization (Backend)](#backend-input-sanitization)
2. [Input Validation (Frontend)](#frontend-input-validation)
3. [API Security Middleware](#api-security-middleware)
4. [Security Logging System](#security-logging-system)
5. [Rate Limiting](#rate-limiting)
6. [Protection Features](#protection-features)
7. [Database Schema](#database-schema)
8. [Usage Examples](#usage-examples)

---

## Backend Input Sanitization

### Location: `bot/utils/input_sanitizer.py`

The backend sanitization module provides comprehensive protection against:

#### SQL Injection Detection
- Pattern-based detection for SQL keywords (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `DROP`, etc.)
- SQL comment detection (`--`, `#`, `/* */`)
- Common bypass patterns (`OR 1=1`, `AND 1=1`)
- Time-based injection (`WAITFOR DELAY`, `BENCHMARK`, `SLEEP`)
- System table access (`INFORMATION_SCHEMA`, `SYS.`)

#### XSS/HTML Injection Detection
- Script tag detection (`<script>`, `<iframe>`)
- Event handler detection (`onclick`, `onload`, `onerror`, etc.)
- JavaScript protocol detection (`javascript:`, `vbscript:`)
- Common obfuscation patterns (`fromCharCode`, `eval()`)

#### Command Injection Detection
- Shell command separators (`;`, `|`, `&`, `` ` ``)
- Command substitution (`$()`)
- Newline/tab command chaining

#### Spam Detection
- Character repetition (11+ consecutive characters)
- Word repetition (10+ times)
- URL spam (5+ URLs in one message)

#### Dangerous Keywords
- Keywords related to passwords, tokens, credit cards
- Database operations (`DROP TABLE`, `DELETE FROM`)
- System functions (`system()`, `exec()`, `eval()`)

### Key Functions

#### `validate_input(text, options)`
Comprehensive input validation with customizable options:

```python
from bot.utils.input_sanitizer import validate_input

is_valid, error_msg, details = validate_input(
    text="Hello world",
    max_length=1000,
    allow_html=False,
    check_sql=True,
    check_xss=True,
    check_command=True,
    check_spam=True,
    check_keywords=True
)
```

**Parameters:**
- `text`: Input string to validate
- `max_length`: Maximum allowed characters (default: 1000)
- `allow_html`: Whether HTML tags are permitted (default: False)
- `check_sql`: Check for SQL injection (default: True)
- `check_xss`: Check for XSS patterns (default: True)
- `check_command`: Check for command injection (default: True)
- `check_spam`: Check for spam patterns (default: True)
- `check_keywords`: Check for dangerous keywords (default: True)

**Returns:**
- `is_valid`: Boolean indicating if input is safe
- `error_msg`: Error message if validation fails
- `details`: Dictionary with validation details and pattern matches

#### `sanitize_text(text, allow_html=False)`
Removes dangerous patterns from text:

```python
from bot.utils.input_sanitizer import sanitize_text

clean_text = sanitize_text("<script>alert('xss')</script>", allow_html=False)
# Result: "alert('xss')"
```

#### `validate_multiple_inputs(inputs, rules)`
Validate multiple inputs with custom rules:

```python
from bot.utils.input_sanitizer import validate_multiple_inputs

inputs = {
    'username': 'john_doe',
    'message': 'Hello world',
    'chat_id': '123456789'
}

rules = {
    'username': {'max_length': 50, 'check_sql': True},
    'message': {'max_length': 500, 'allow_html': False},
    'chat_id': {'max_length': 20, 'check_xss': True}
}

all_valid, errors = validate_multiple_inputs(inputs, rules)
```

---

## Frontend Input Validation

### Location: `miniapp/lib/inputSanitizer.js`

Client-side validation mirrors backend checks for immediate feedback:

### Key Functions

#### `validateInput(text, options)`
```javascript
import { validateInput } from './lib/inputSanitizer.js';

const result = validateInput(userInput, {
  maxLength: 1000,
  allowHTML: false,
  checkSQL: true,
  checkXSS: true,
  checkCommand: true,
  checkSpam: true,
  checkKeywords: true
});

if (!result.isValid) {
  showToast(result.error, 'error');
}
```

#### `sanitizeText(text, allowHTML)`
```javascript
import { sanitizeText } from './lib/inputSanitizer.js';

const cleanText = sanitizeText(userInput, false);
```

#### `InputRateLimiter` Class
Client-side rate limiting for input submission:

```javascript
import { InputRateLimiter } from './lib/inputSanitizer.js';

const rateLimiter = new InputRateLimiter(10, 60); // 10 attempts per 60 seconds

const result = rateLimiter.checkRateLimit(userId);
if (!result.allowed) {
  showToast(`Too many attempts. Try again in ${result.resetAfter}s`, 'error');
}
```

### API Client Integration

The `apiFetch()` function in `miniapp/lib/api.js` automatically validates and sanitizes all request bodies:

```javascript
import { apiFetch } from './lib/api.js';

// Automatically validated and sanitized
const response = await apiFetch('/api/bots/clone', {
  method: 'POST',
  body: { token: userToken }
});
```

---

## API Security Middleware

### Location: `api/middleware.py`

Three middleware layers protect API endpoints:

#### 1. RateLimitMiddleware
Prevents abuse and DoS attacks:

```python
from api.middleware import RateLimitMiddleware

# Limits:
# - Default: 100 requests/minute
# - Strict (sensitive operations): 30 requests/minute
# - Upload operations: 10 requests/minute
```

**Features:**
- IP-based rate limiting
- Per-endpoint limits
- HTTP headers for rate limit info:
  - `X-RateLimit-Limit`: Total limit
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Window`: Time window in seconds

#### 2. InputValidationMiddleware
Validates all POST/PUT request bodies:

```python
from api.middleware import InputValidationMiddleware

# Automatically checks:
# - SQL injection patterns
# - XSS patterns
# - Command injection patterns
# - Spam patterns
# - Request size limits
```

**Skipped Paths:**
- `/api/me` (read-only)
- `/api/groups/` (read-only endpoints)
- `/api/bots` (read-only)
- `/api/analytics` (read-only)
- `/api/music/status` (read-only)
- `/health` (health check)

#### 3. SecurityHeadersMiddleware
Adds security headers to all responses:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

---

## Security Logging System

### Location: `bot/utils/security_logger.py`

Logs all security violations for monitoring and analysis:

#### Key Functions

##### `log_security_event(...)`
```python
from bot.utils.security_logger import log_security_event

event_id = await log_security_event(
    event_type='sql_injection',
    severity='high',
    user_id=123456789,
    chat_id=-1001234567890,
    ip_address='1.2.3.4',
    endpoint='/api/bots/clone',
    input_data='SELECT * FROM...',
    pattern_matched='SELECT',
    additional_info={'user_agent': '...'}
)
```

##### `is_user_blocked(user_id, chat_id)`
Check if user is blocked:

```python
is_blocked, block_info = await is_user_blocked(user_id, chat_id)
if is_blocked:
    print(f"User blocked: {block_info['reason']}")
```

##### `block_user(...)`
Block a user:

```python
await block_user(
    user_id=123456789,
    chat_id=-1001234567890,
    blocked_by=admin_id,
    reason='Multiple SQL injection attempts',
    block_type='temporary',
    duration_hours=24
)
```

---

## Protection Features

### Bot Commands Protection

#### Admin Commands with Input Validation

All admin commands in `bot/handlers/admin_tools.py` now validate input:

1. **`/announce <message>`**
   - Validates announcement message
   - Allows HTML for formatting
   - Checks for SQL/command injection
   - Max length: 1000 characters

2. **`/addfilter <keyword>`**
   - Validates filter keywords
   - No HTML allowed
   - Max length: 100 characters

3. **`/delfilter <keyword>`**
   - Same validation as addfilter

### API Endpoints Protection

#### Backup/Restore Endpoint
```python
# Location: api/routes/backup.py
@router.post("/{chat_id}/restore")
async def import_backup(chat_id: int, request: Request, ...):
    # Validates:
    # - Backup version
    # - JSON structure
    # - String fields for injection patterns
    # - Settings format
```

---

## Rate Limiting

### Global Rate Limits

| Endpoint Type | Limit | Window |
|--------------|-------|--------|
| Default API | 100 requests | 60 seconds |
| Sensitive (clone/token) | 30 requests | 60 seconds |
| Upload/Restore | 10 requests | 60 seconds |

### Input-Based Rate Limiting

The `InputRateLimiter` class prevents rapid submissions:

```python
from bot.utils.input_sanitizer import input_rate_limiter

allowed, remaining = input_rate_limiter.check_rate_limit(user_id)
if not allowed:
    # User exceeded rate limit
    pass
```

---

## Database Schema

### Tables

#### `security_events`
- `id`: Primary key
- `event_type`: Type of security event
- `severity`: 'low', 'medium', 'high', 'critical'
- `user_id`: Telegram user ID
- `chat_id`: Chat ID
- `ip_address`: Client IP
- `endpoint`: API endpoint or command
- `input_data`: Sanitized input sample
- `pattern_matched`: Pattern that triggered event
- `additional_info`: JSONB with extra details
- `created_at`: Timestamp

#### `blocked_users`
- `id`: Primary key
- `user_id`: User ID (unique per chat)
- `chat_id`: Chat ID (0 for global block)
- `blocked_by`: Admin who blocked
- `reason`: Block reason
- `block_type`: 'temporary', 'permanent', 'auto'
- `blocked_at`: Timestamp
- `expires_at`: Expiry (NULL for permanent)
- `violation_count`: Number of violations
- `additional_info`: JSONB details

#### `input_validation_settings`
- `id`: Primary key
- `chat_id`: Group ID (unique)
- `max_message_length`: Default 4000
- `max_word_count`: Default 1000
- `max_url_count`: Default 5
- `allow_html`: Default False
- `strict_mode`: Default False
- `blocked_patterns`: JSONB custom patterns
- `allowed_patterns`: JSONB whitelist
- `created_at`: Timestamp
- `updated_at`: Timestamp

---

## Usage Examples

### Example 1: Validating User Input in Bot Handler

```python
from bot.utils.input_sanitizer import validate_input, sanitize_text
from bot.utils.security_logger import log_security_event, block_user

async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /command <input>")
        return
    
    user_input = " ".join(context.args)
    
    # Validate input
    is_valid, error_msg, details = validate_input(
        user_input,
        max_length=500,
        allow_html=False
    )
    
    if not is_valid:
        # Log security event
        await log_security_event(
            event_type=details.get('type'),
            severity='medium',
            user_id=update.effective_user.id,
            chat_id=update.effective_chat.id,
            input_data=user_input,
            pattern_matched=str(details.get('patterns', []))
        )
        
        # Check if this is a repeat offender
        from bot.utils.security_logger import get_user_violation_count
        violation_count = await get_user_violation_count(update.effective_user.id, 24)
        
        if violation_count >= 5:
            await block_user(
                user_id=update.effective_user.id,
                chat_id=update.effective_chat.id,
                blocked_by=None,
                reason='Excessive security violations',
                block_type='temporary',
                duration_hours=24
            )
        
        await update.message.reply_text(f"❌ Invalid input: {error_msg}")
        return
    
    # Sanitize and use input
    clean_input = sanitize_text(user_input, allow_html=False)
    # ... process clean_input
```

### Example 2: Validating API Request Body

```python
from api.middleware import InputValidationMiddleware
from bot.utils.input_sanitizer import validate_multiple_inputs

@router.post("/api/some-endpoint")
async def some_endpoint(request: Request, ...):
    body = await request.json()
    
    # Define validation rules
    rules = {
        'title': {'max_length': 100, 'check_sql': True, 'check_xss': True},
        'description': {'max_length': 1000, 'allow_html': True},
        'chat_id': {'max_length': 20, 'check_xss': True}
    }
    
    # Validate
    all_valid, errors = validate_multiple_inputs(body, rules)
    if not all_valid:
        raise HTTPException(400, detail=errors)
    
    # ... process validated data
```

### Example 3: Frontend Validation

```javascript
import { validateInput, InputRateLimiter } from './lib/inputSanitizer.js';

// Validate input before sending
function handleSubmit() {
  const input = document.getElementById('userInput').value;
  
  const result = validateInput(input, {
    maxLength: 500,
    allowHTML: false
  });
  
  if (!result.isValid) {
    alert(result.error);
    return;
  }
  
  // Check rate limit
  const rateLimiter = new InputRateLimiter(10, 60);
  const limitResult = rateLimiter.checkRateLimit(userId);
  
  if (!limitResult.allowed) {
    alert(`Too many attempts. Wait ${limitResult.resetAfter}s`);
    return;
  }
  
  // Submit
  apiFetch('/api/endpoint', {
    method: 'POST',
    body: { input }
  });
}
```

---

## Security Best Practices

### For Developers

1. **Always validate input on both client and server**
2. **Use parameterized queries** (already using asyncpg with parameters)
3. **Log all security violations** for monitoring
4. **Implement rate limiting** on all user actions
5. **Review security logs regularly**
6. **Keep security patterns updated**
7. **Test with common attack payloads**

### For Admins

1. **Monitor security logs** for suspicious activity
2. **Review blocked users** regularly
3. **Adjust rate limits** based on traffic
4. **Enable strict mode** for sensitive groups
5. **Educate users** about security policies

---

## Testing Security

### Test SQL Injection
```bash
# Test payloads
1' OR '1'='1
'; DROP TABLE users; --
1' UNION SELECT * FROM passwords
```

### Test XSS
```bash
# Test payloads
<script>alert('xss')</script>
<img src=x onerror=alert('xss')>
javascript:alert('xss')
```

### Test Command Injection
```bash
# Test payloads
; cat /etc/passwd
| whoami
`rm -rf /`
```

All should be blocked by the sanitization system.

---

## Maintenance

### Cleanup Old Security Events
Run periodically to manage database size:

```python
from bot.utils.security_logger import cleanup_old_events

# Delete events older than 90 days
deleted = await cleanup_old_events()
print(f"Deleted {deleted} old events")
```

### Update Security Patterns
Add new patterns to `bot/utils/input_sanitizer.py`:

```python
SQL_INJECTION_PATTERNS = [
    # ... existing patterns ...
    r'NEW_PATTERN_HERE',  # Add new patterns
]
```

---

## Support and Issues

For security issues or questions:
- Check logs in `[SECURITY]` and `[SECURITY_LOG]` categories
- Review `security_events` table for violations
- Check `blocked_users` table for blocked accounts
- Monitor API rate limit headers for abuse

---

**Version:** 1.0.0
**Last Updated:** 2025
