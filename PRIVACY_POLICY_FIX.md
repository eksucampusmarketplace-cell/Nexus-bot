# Privacy Policy Link Fix

## Summary
Fixed and verified the privacy policy link functionality across the bot. The privacy policy is now accessible via multiple entry points, all correctly directing users to `miniapp/privacy.html`.

## Changes Made

### 1. `/privacy` Command Handler (`bot/handlers/privacy.py`)
**Issue:** Privacy policy button was using `web_app` type which opens in Telegram Mini App, causing confusion for direct browser access.

**Fix:** Changed button type from `web_app={"url": ...}` to `url=...` (line 63)
- Opens privacy policy directly in browser instead of Mini App
- Better user experience for viewing full policy

### 2. Support Keyboard (`bot/utils/keyboards.py`)
**Issue:** Privacy policy button fell back to `{webhook_url}/privacy` which didn't exist as a route.

**Fix:** Kept the fallback to `/privacy` (lines 57-62)
- Now the `/privacy` route exists and redirects to `miniapp/privacy.html`
- Allows custom `PRIVACY_POLICY_URL` override if needed

### 3. New `/privacy` Web Route (`main.py`)
**Added:** New route that redirects to the privacy page (lines 605-608)
```python
@app.get("/privacy")
async def privacy():
    return RedirectResponse(url="/miniapp/privacy.html")
```
- Provides a clean URL for support keyboard fallback
- Maintains backward compatibility
- All links now point to valid routes

### 4. Updated Documentation (`.env.example`)
**Updated:** Clarified privacy policy URL configuration (line 16)
```
PRIVACY_POLICY_URL=  # Optional: Privacy Policy URL. If not set, defaults to {RENDER_EXTERNAL_URL}/privacy (redirects to miniapp/privacy.html)
```

## Privacy Policy Link Flow

### `/privacy` Command
1. User types `/privacy` in bot
2. Bot shows privacy summary
3. Button links to: `{mini_app_url}privacy.html`
4. Direct browser access (not Mini App)

### Support Keyboard (in /start, /help, etc.)
1. User sees "🔒 Privacy Policy" button
2. If `PRIVACY_POLICY_URL` is set → uses custom URL
3. Otherwise → links to `{webhook_url}/privacy`
4. Server redirects `/privacy` → `/miniapp/privacy.html`

### Direct Access
1. User visits: `https://your-app.onrender.com/privacy`
2. Server redirects to: `https://your-app.onrender.com/miniapp/privacy.html`
3. User sees full privacy policy

## File Locations

- **Privacy Policy Page:** `miniapp/privacy.html` (already exists, comprehensive GDPR-compliant policy)
- **Handler:** `bot/handlers/privacy.py` (command handler)
- **Keyboard:** `bot/utils/keyboards.py` (support keyboard)
- **Route:** `main.py` (web redirect route)
- **Config:** `config.py` (settings)
- **Env Example:** `.env.example` (documentation)

## Configuration Options

### Option 1: Default (Recommended)
Leave `PRIVACY_POLICY_URL` empty. Uses automatic fallback:
- `{RENDER_EXTERNAL_URL}/privacy` → redirects to `/miniapp/privacy.html`

### Option 2: Custom URL
Set `PRIVACY_POLICY_URL` to your custom privacy policy URL:
```
PRIVACY_POLICY_URL=https://your-site.com/privacy
```

### Option 3: Custom Mini App Domain
Set `MINI_APP_URL` to your custom domain:
```
MINI_APP_URL=https://panel.your-bot.com
```
Then `/privacy` command links to: `https://panel.your-bot.com/privacy.html`

## Testing

All privacy policy access points now correctly redirect to the full policy:

1. `/privacy` command → Direct link to miniapp/privacy.html
2. Support keyboard button → /privacy redirect → miniapp/privacy.html
3. Direct browser access → /privacy redirect → miniapp/privacy.html

## Backward Compatibility

- Existing `PRIVACY_POLICY_URL` settings continue to work
- Support keyboard maintains `/privacy` fallback
- No breaking changes to existing functionality
