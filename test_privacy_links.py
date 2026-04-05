#!/usr/bin/env python3
"""Test script to verify privacy policy link construction."""

from config import settings

print("=" * 60)
print("Privacy Policy Link Configuration Test")
print("=" * 60)

print(f"\nSettings:")
print(f"  MINI_APP_URL: {settings.MINI_APP_URL}")
print(f"  RENDER_EXTERNAL_URL: {settings.RENDER_EXTERNAL_URL}")
print(f"  PRIVACY_POLICY_URL: {settings.PRIVACY_POLICY_URL}")
print(f"  webhook_url: {settings.webhook_url}")
print(f"  mini_app_url property: {settings.mini_app_url}")

print("\n" + "=" * 60)
print("Generated Privacy URLs:")
print("=" * 60)

# From /privacy command handler (privacy.py)
privacy_url_from_handler = f"{settings.mini_app_url}privacy.html" if settings.mini_app_url else None
print(f"\n1. /privacy command handler:")
print(f"   URL: {privacy_url_from_handler}")

# From support keyboard (keyboards.py)
privacy_url_from_keyboard = settings.PRIVACY_POLICY_URL or (
    f"{settings.webhook_url}/miniapp/privacy.html" if settings.RENDER_EXTERNAL_URL else None
)
print(f"\n2. Support keyboard:")
print(f"   URL: {privacy_url_from_keyboard}")

print("\n" + "=" * 60)
print("Expected URL structure (when deployed):")
print("=" * 60)
print("https://your-app.onrender.com/miniapp/privacy.html")
print("\nOr with MINI_APP_URL set:")
print("https://custom-domain.com/privacy.html")
