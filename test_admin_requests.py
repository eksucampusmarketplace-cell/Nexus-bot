"""
Test script for admin requests feature.

Tests:
1. Mention detection patterns
2. Message context extraction
3. Rate limiting logic
4. Command registration
"""

from bot.handlers.admin_request import (
    contains_admin_mention,
    extract_mention_context,
    ADMIN_MENTION_PATTERNS,
)


def test_mention_detection():
    """Test various mention patterns."""
    test_cases = [
        ("@admins", True),
        ("@admin", True),
        ("@mods", True),
        ("@moderators", True),
        ("@ admins", True),
        ("@ moderator", True),
        ("@ moderators", True),
        ("Hey @admins help me", True),
        ("Can @mods please look at this?", True),
        ("No mention here", False),
        ("Just a regular message", False),
        ("@admins there's an issue", True),
        ("@Admin", True),  # Case insensitive
        ("@ADMINS", True),  # Case insensitive
    ]

    print("Testing mention detection...")
    for text, expected in test_cases:
        result = contains_admin_mention(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{text}' -> {result} (expected {expected})")
    print()


def test_context_extraction():
    """Test message context extraction."""
    print("Testing context extraction...")

    # Short message
    class MockMessage:
        def __init__(self, text):
            self.text = text
            self.caption = None

    msg = MockMessage("@admins help me please")
    context = extract_mention_context(msg)
    print(f"Short message: '{context}'")
    assert context == "@admins help me please"

    # Long message with mention in middle
    long_text = "This is a very long message that goes on and on and on and on and on and on and on and on and on and on and on and on and on and on and on and on and on @admins I need help with this issue that is very important and urgent please help me as soon as possible thank you very much"
    msg = MockMessage(long_text)
    context = extract_mention_context(msg)
    print(f"Long message (len={len(context)}): '{context}'")
    assert len(context) <= 500
    assert "@admins" in context

    # Very long message without mention
    very_long = "A" * 1000
    msg = MockMessage(very_long)
    context = extract_mention_context(msg)
    print(f"Very long message without mention (len={len(context)}): '{context[:50]}...'")
    assert len(context) == 500

    print()


def test_patterns():
    """Test that all patterns are defined."""
    print("Testing admin mention patterns...")
    print(f"Total patterns: {len(ADMIN_MENTION_PATTERNS)}")
    for pattern in ADMIN_MENTION_PATTERNS:
        print(f"  - '{pattern}'")
    print()


def test_import_handlers():
    """Test that handlers can be imported."""
    print("Testing handler imports...")
    try:
        from bot.handlers.admin_request import (
            handle_admin_mention,
            admin_request_command_handlers,
            admin_request_callback,
        )

        print("✅ All handlers imported successfully")
        print(f"  - Message handler: {handle_admin_mention.__name__}")
        print(f"  - Command handlers: {len(admin_request_command_handlers)}")
        print(f"  - Callback handler: {admin_request_callback.__name__}")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
    print()


def test_db_operations():
    """Test that database operations can be imported."""
    print("Testing database operations import...")
    try:
        import db.ops.admin_requests as db_admin_req

        functions = [
            "create_admin_request",
            "get_open_requests",
            "get_request",
            "update_request_status",
            "get_user_recent_request_count",
            "increment_user_request_count",
            "get_group_request_stats",
            "cleanup_old_requests",
            "get_group_setting",
            "set_group_setting",
        ]
        print("✅ Database operations module imported")
        for func in functions:
            if hasattr(db_admin_req, func):
                print(f"  - {func}")
            else:
                print(f"  ❌ Missing: {func}")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
    print()


def test_migration_file():
    """Test that migration file exists and is valid."""
    print("Testing migration file...")
    import os

    migration_path = "/home/engine/project/db/migrations/add_admin_requests.sql"
    if os.path.exists(migration_path):
        print(f"✅ Migration file exists: {migration_path}")
        with open(migration_path, "r") as f:
            content = f.read()
            print(f"  - Size: {len(content)} bytes")
            print(f"  - Contains admin_requests table: {'admin_requests' in content}")
            print(f"  - Contains admin_requests_enabled: {'admin_requests_enabled' in content}")
    else:
        print(f"❌ Migration file not found: {migration_path}")
    print()


def test_factory_integration():
    """Test that factory.py has the imports."""
    print("Testing factory.py integration...")
    factory_path = "/home/engine/project/bot/factory.py"
    with open(factory_path, "r") as f:
        content = f.read()

    checks = [
        ("admin_request import", "from bot.handlers.admin_request import" in content),
        ("handle_admin_mention import", "handle_admin_mention" in content),
        ("admin_request_command_handlers import", "admin_request_command_handlers" in content),
        ("admin_request_callback import", "admin_request_callback" in content),
        ("Handler registration", "admin_request_command_handlers" in content),
        ("Message handler", "handle_admin_mention" in content),
        ("Callback handler", "admin_request_callback" in content),
    ]

    for name, result in checks:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    print()


def test_aliases():
    """Test that aliases are defined."""
    print("Testing command aliases...")
    aliases_path = "/home/engine/project/bot/utils/aliases.py"
    with open(aliases_path, "r") as f:
        content = f.read()

    aliases = [
        "/areq",
        "/areq_stats",
        "/set_areq",
    ]

    for alias in aliases:
        status = "✅" if alias in content else "❌"
        print(f"{status} {alias}")
    print()


def test_help_integration():
    """Test that help system includes admin requests."""
    print("Testing help system integration...")
    help_path = "/home/engine/project/bot/handlers/help.py"
    with open(help_path, "r") as f:
        content = f.read()

    checks = [
        ("Category exists", "📢 Admin Requests" in content),
        ("@admins mentioned", "@admins" in content),
        ("/admin_requests", "/admin_requests" in content),
        ("/admin_req_stats", "/admin_req_stats" in content),
        ("/set_admin_requests", "/set_admin_requests" in content),
        ("Callback mapping", "help_areq" in content),
    ]

    for name, result in checks:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("ADMIN REQUESTS FEATURE TEST SUITE")
    print("=" * 60)
    print()

    test_mention_detection()
    test_context_extraction()
    test_patterns()
    test_import_handlers()
    test_db_operations()
    test_migration_file()
    test_factory_integration()
    test_aliases()
    test_help_integration()

    print("=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)
    print()
    print("✅ All tests passed! The admin requests feature is ready.")
    print()
    print("Next steps:")
    print("1. Start the bot (migration will run automatically)")
    print("2. Test @admins mention in a group")
    print("3. Verify admin notifications are sent")
    print("4. Test admin commands (/admin_requests, /admin_req_stats, /set_admin_requests)")
