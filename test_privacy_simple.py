#!/usr/bin/env python3
"""Simple test of privacy URL construction."""

# Mock settings for testing
class MockSettings:
    MINI_APP_URL = None
    RENDER_EXTERNAL_URL = "https://your-app.onrender.com"
    PRIVACY_POLICY_URL = None

    @property
    def webhook_url(self):
        return f"{self.RENDER_EXTERNAL_URL.rstrip('/')}"

    @property
    def mini_app_url(self):
        if self.MINI_APP_URL:
            return self.MINI_APP_URL
        elif self.RENDER_EXTERNAL_URL:
            return f"{self.RENDER_EXTERNAL_URL.rstrip('/')}/miniapp"
        return None

settings = MockSettings()

# Test 1: /privacy command handler
privacy_url_handler = f"{settings.mini_app_url}privacy.html" if settings.mini_app_url else None
print(f"Test 1 - /privacy command handler:")
print(f"  Result: {privacy_url_handler}")
print(f"  Expected: https://your-app.onrender.com/miniapp/privacy.html")
print(f"  Status: {'✓ PASS' if privacy_url_handler == 'https://your-app.onrender.com/miniapp/privacy.html' else '✗ FAIL'}")
print()

# Test 2: Support keyboard fallback
privacy_url_keyboard = settings.PRIVACY_POLICY_URL or (
    f"{settings.webhook_url}/privacy" if settings.RENDER_EXTERNAL_URL else None
)
print(f"Test 2 - Support keyboard:")
print(f"  Result: {privacy_url_keyboard}")
print(f"  Expected: https://your-app.onrender.com/privacy (redirects to miniapp/privacy.html)")
print(f"  Status: {'✓ PASS' if privacy_url_keyboard == 'https://your-app.onrender.com/privacy' else '✗ FAIL'}")
print()

# Test 3: With PRIVACY_POLICY_URL set
settings2 = MockSettings()
settings2.PRIVACY_POLICY_URL = "https://custom.com/privacy"
privacy_url_custom = settings2.PRIVACY_POLICY_URL or (
    f"{settings2.webhook_url}/privacy" if settings2.RENDER_EXTERNAL_URL else None
)
print(f"Test 3 - With custom PRIVACY_POLICY_URL:")
print(f"  Result: {privacy_url_custom}")
print(f"  Expected: https://custom.com/privacy")
print(f"  Status: {'✓ PASS' if privacy_url_custom == 'https://custom.com/privacy' else '✗ FAIL'}")
