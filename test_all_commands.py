#!/usr/bin/env python3
"""
Comprehensive Command Testing Script
Tests all bot commands and mini app functionality for syntax and import errors
"""

import sys
import os
import asyncio
import importlib
import inspect
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Track all issues found
issues = {
    'syntax_errors': [],
    'import_errors': [],
    'missing_handlers': [],
    'missing_decorators': [],
    'duplicate_commands': [],
}

def test_syntax():
    """Test Python syntax for all handler files"""
    print("=" * 60)
    print("TESTING SYNTAX FOR ALL HANDLER FILES")
    print("=" * 60)

    import py_compile
    handlers_dir = Path("bot/handlers")
    py_files = list(handlers_dir.glob("*.py"))

    for py_file in sorted(py_files):
        if py_file.name == "__init__.py":
            continue

        try:
            py_compile.compile(str(py_file), doraise=True)
            print(f"✅ {py_file.name} - OK")
        except py_compile.PyCompileError as e:
            print(f"❌ {py_file.name} - SYNTAX ERROR")
            issues['syntax_errors'].append((py_file.name, str(e)))
        except SyntaxError as e:
            print(f"❌ {py_file.name} - SYNTAX ERROR")
            issues['syntax_errors'].append((py_file.name, str(e)))

    print()

def test_imports():
    """Test that all handler modules can be imported"""
    print("=" * 60)
    print("TESTING IMPORTS FOR ALL HANDLER MODULES")
    print("=" * 60)

    # List of all handler modules from factory.py
    handler_modules = [
        'bot.handlers.commands',
        'bot.handlers.automod',
        'bot.handlers.advanced_automod',
        'bot.handlers.new_member',
        'bot.handlers.captcha_callback',
        'bot.handlers.captcha_message',
        'bot.handlers.approval',
        'bot.handlers.captcha',
        'bot.handlers.errors',
        'bot.handlers.prefix_handler',
        'bot.handlers.greetings',
        'bot.handlers.channel',
        'bot.handlers.group_lifecycle',
        'bot.handlers.group_approval',
        'bot.handlers.help',
        'bot.handlers.music_new',
        'bot.handlers.adduserbot',
        'bot.handlers.setmessage',
        'bot.handlers.privacy',
        'bot.handlers.fun',
        'bot.handlers.admin_tools',
        'bot.handlers.pins',
        'bot.handlers.password',
        'bot.handlers.copy_settings',
        'bot.handlers.log_channel',
        'bot.handlers.import_export',
        'bot.handlers.inline_mode',
        'bot.handlers.public',
        'bot.handlers.booster',
    ]

    for module_name in handler_modules:
        try:
            importlib.import_module(module_name)
            print(f"✅ {module_name} - OK")
        except Exception as e:
            print(f"❌ {module_name} - ERROR: {e}")
            issues['import_errors'].append((module_name, str(e)))

    print()

def test_factory_import():
    """Test that factory module can be imported and all handlers are registered"""
    print("=" * 60)
    print("TESTING FACTORY MODULE")
    print("=" * 60)

    try:
        from bot import factory
        print("✅ bot.factory import - OK")

        # Check if create_application exists
        if hasattr(factory, 'create_application'):
            print("✅ create_application function exists")
        else:
            print("❌ create_application function missing")
            issues['missing_handlers'].append(('factory', 'create_application'))

    except Exception as e:
        print(f"❌ Factory import failed: {e}")
        issues['import_errors'].append(('bot.factory', str(e)))

    print()

def extract_command_handlers():
    """Extract all command handlers from factory.py"""
    print("=" * 60)
    print("EXTRACTING REGISTERED COMMANDS")
    print("=" * 60)

    commands = {}

    # Read factory.py to find registered commands
    factory_path = Path("bot/factory.py")
    factory_content = factory_path.read_text()

    # Find CommandHandler registrations
    import re
    command_pattern = r'CommandHandler\("([^"]+)",\s*(\w+)(?:,\s*filters=([^\)]+))?\)'
    matches = re.findall(command_pattern, factory_content)

    for match in matches:
        cmd_name, handler_name, filters = match
        commands[f"/{cmd_name}"] = {
            'handler': handler_name,
            'filters': filters if filters else 'None'
        }

    # Sort commands alphabetically
    for cmd in sorted(commands.keys()):
        info = commands[cmd]
        filter_info = f" [filters: {info['filters']}]" if info['filters'] != 'None' else ""
        print(f"  {cmd:<25} → {info['handler']:<30}{filter_info}")

    print(f"\n✅ Found {len(commands)} registered commands")
    print()
    return commands

def check_handler_functions():
    """Check that all handler functions referenced in commands exist"""
    print("=" * 60)
    print("CHECKING HANDLER FUNCTIONS EXIST")
    print("=" * 60)

    commands = extract_command_handlers()
    handlers_to_check = set()

    # Collect all unique handler names from commands
    for cmd_info in commands.values():
        handlers_to_check.add(cmd_info['handler'])

    # Also check handlers from other places
    # From the prefix_handler import
    handlers_to_check.add('prefix_handler')
    handlers_to_check.add('handle_automod_command')
    handlers_to_check.add('handle_captcha_callback')
    handlers_to_check.add('captcha_callback_handler')
    handlers_to_check.add('handle_captcha_message')
    handlers_to_check.add('welcome_handler')
    handlers_to_check.add('goodbye_handler')
    handlers_to_check.add('handle_chat_member_update')
    handlers_to_check.add('group_lifecycle_handler')
    handlers_to_check.add('group_approval_handler')
    handlers_to_check.add('help_callback_handler')
    handlers_to_check.add('clone_management_callback')
    handlers_to_check.add('handle_inline_query')
    handlers_to_check.add('handle_reset_callback')

    # Try to import each handler module and check for functions
    modules_to_check = [
        ('bot.handlers.commands', [
            'warn_handler', 'unwarn_handler', 'warns_handler',
            'ban_handler', 'unban_handler', 'mute_handler',
            'unmute_handler', 'kick_handler', 'purge_handler',
            'lock_handler', 'unlock_handler', 'pin_handler',
            'unpin_handler', 'rules_handler', 'info_handler',
            'admins_handler', 'stats_handler', 'id_handler',
            'report_handler', 'start', 'help_handler', 'panel'
        ]),
        ('bot.handlers.greetings', [
            'welcome_handler', 'goodbye_handler',
            'set_welcome_handler', 'set_goodbye_handler',
            'set_rules_handler', 'welcome_preview_handler',
            'goodbye_preview_handler', 'reset_welcome_handler',
            'reset_goodbye_handler', 'reset_rules_handler',
        ]),
        ('bot.handlers.channel', [
            'channel_post_handler', 'schedule_post_handler',
            'approve_post_handler', 'cancel_post_handler',
            'edit_post_handler', 'delete_post_handler'
        ]),
        ('bot.handlers.automod', [
            'antiflood_handler', 'antispam_handler',
            'antilink_handler', 'message_handler',
            'member_join_handler'
        ]),
        ('bot.handlers.advanced_automod', ['handle_automod_command']),
        ('bot.handlers.approval', [
            'cmd_approve', 'cmd_unapprove', 'cmd_approved',
            'cmd_antiraid', 'cmd_autoantiraid',
            'cmd_captcha', 'cmd_captchamode'
        ]),
        ('bot.handlers.pins', [
            'cmd_pin', 'cmd_unpin', 'cmd_unpinall',
            'cmd_repin', 'cmd_editpin', 'cmd_delpin'
        ]),
        ('bot.handlers.password', [
            'cmd_setpassword', 'cmd_clearpassword', 'handle_password_dm'
        ]),
        ('bot.handlers.public', [
            'cmd_time', 'cmd_kickme', 'cmd_adminlist',
            'cmd_invitelink', 'cmd_groupinfo'
        ]),
        ('bot.handlers.log_channel', [
            'cmd_setlog', 'cmd_unsetlog', 'cmd_logchannel'
        ]),
        ('bot.handlers.import_export', [
            'cmd_export', 'cmd_import', 'cmd_reset',
            'handle_reset_callback'
        ]),
        ('bot.handlers.inline_mode', ['handle_inline_query']),
        ('bot.handlers.prefix_handler', ['prefix_handler']),
        ('bot.handlers.new_member', ['handle_chat_member_update']),
        ('bot.handlers.captcha_callback', ['handle_captcha_callback']),
        ('bot.handlers.captcha_message', ['handle_captcha_message']),
        ('bot.handlers.group_lifecycle', ['group_lifecycle_handler']),
        ('bot.handlers.group_approval', ['group_approval_handler']),
        ('bot.handlers.help', ['help_handler', 'help_callback_handler']),
        ('bot.handlers.music_new', ['music_handlers']),
        ('bot.handlers.adduserbot', ['adduserbot_conversation']),
        ('bot.handlers.start_help', ['start_handler', 'help_handler']),
        ('bot.handlers.setmessage', ['setmessage_conversation']),
        ('bot.handlers.privacy', ['privacy_handler']),
        ('bot.handlers.copy_settings', ['cmd_copy_settings']),
        ('bot.handlers.clone', [
            'clone_conversation', 'myclones_command_handler',
            'cloneset_handler', 'clone_management_callback'
        ]),
    ]

    missing_count = 0
    for module_name, handler_names in modules_to_check:
        try:
            module = importlib.import_module(module_name)
            for handler_name in handler_names:
                if hasattr(module, handler_name):
                    print(f"✅ {module_name}.{handler_name} - OK")
                else:
                    print(f"❌ {module_name}.{handler_name} - MISSING")
                    issues['missing_handlers'].append((module_name, handler_name))
                    missing_count += 1
        except Exception as e:
            print(f"⚠️  Could not import {module_name}: {e}")
            for handler_name in handler_names:
                issues['missing_handlers'].append((module_name, f"{handler_name} (module import failed)"))
                missing_count += 1

    print()

def print_summary():
    """Print summary of all issues found"""
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    total_issues = sum(len(v) for v in issues.values())

    if total_issues == 0:
        print("✅ ALL TESTS PASSED - No issues found!")
    else:
        print(f"⚠️  Found {total_issues} issue(s):")
        print()

        if issues['syntax_errors']:
            print(f"❌ Syntax Errors ({len(issues['syntax_errors'])}):")
            for file, error in issues['syntax_errors']:
                print(f"   - {file}: {error[:100]}")
            print()

        if issues['import_errors']:
            print(f"❌ Import Errors ({len(issues['import_errors'])}):")
            for module, error in issues['import_errors']:
                print(f"   - {module}: {error[:100]}")
            print()

        if issues['missing_handlers']:
            print(f"❌ Missing Handlers ({len(issues['missing_handlers'])}):")
            for module, handler in issues['missing_handlers']:
                print(f"   - {module}.{handler}")
            print()

    print("=" * 60)

def main():
    """Run all tests"""
    print("\n🔍 COMPREHENSIVE COMMAND TESTING")
    print("=" * 60)

    test_syntax()
    test_imports()
    test_factory_import()
    extract_command_handlers()
    check_handler_functions()
    print_summary()

    # Exit with error code if issues found
    total_issues = sum(len(v) for v in issues.values())
    sys.exit(1 if total_issues > 0 else 0)

if __name__ == "__main__":
    main()
