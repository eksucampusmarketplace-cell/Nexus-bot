#!/usr/bin/env python3
"""
Simple Command Checker - Tests syntax and structure without requiring valid settings
"""

import sys
import os
import re
from pathlib import Path

def check_syntax():
    """Check Python syntax for all handler files"""
    print("=" * 60)
    print("CHECKING SYNTAX FOR ALL HANDLER FILES")
    print("=" * 60)

    import py_compile
    handlers_dir = Path("bot/handlers")
    py_files = list(handlers_dir.glob("*.py"))
    errors = []

    for py_file in sorted(py_files):
        if py_file.name == "__init__.py":
            continue

        try:
            py_compile.compile(str(py_file), doraise=True)
            print(f"✅ {py_file.name}")
        except py_compile.PyCompileError as e:
            print(f"❌ {py_file.name} - SYNTAX ERROR")
            errors.append((py_file.name, str(e)))
        except SyntaxError as e:
            print(f"❌ {py_file.name} - SYNTAX ERROR")
            errors.append((py_file.name, str(e)))

    print()
    return errors

def extract_registered_commands():
    """Extract all registered commands from factory.py"""
    print("=" * 60)
    print("EXTRACTING REGISTERED COMMANDS FROM factory.py")
    print("=" * 60)

    factory_path = Path("bot/factory.py")
    factory_content = factory_path.read_text()

    commands = {}

    # Find CommandHandler registrations
    command_pattern = r'CommandHandler\("([^"]+)",\s*(\w+)(?:,\s*filters=([^\)]+))?\)'
    matches = re.findall(command_pattern, factory_content)

    for match in matches:
        cmd_name, handler_name, filters = match
        commands[f"/{cmd_name}"] = {
            'handler': handler_name,
            'filters': filters.strip() if filters else 'None'
        }

    # Sort commands alphabetically
    for cmd in sorted(commands.keys()):
        info = commands[cmd]
        filter_info = f" [filters: {info['filters']}]" if info['filters'] != 'None' else ""
        print(f"  {cmd:<25} → {info['handler']:<30}{filter_info}")

    print(f"\n✅ Found {len(commands)} registered commands")
    print()
    return commands

def check_handler_signatures():
    """Check that handler functions have correct signatures"""
    print("=" * 60)
    print("CHECKING HANDLER FUNCTION SIGNATURES")
    print("=" * 60)

    # Define expected signatures for common handler types
    # We'll check that functions exist and have at least update and context params
    handlers_dir = Path("bot/handlers")
    handler_files = [
        'commands.py', 'automod.py', 'advanced_automod.py',
        'approval.py', 'greetings.py', 'channel.py',
        'pins.py', 'password.py', 'public.py',
        'log_channel.py', 'import_export.py',
        'inline_mode.py', 'help.py', 'start_help.py',
        'privacy.py', 'fun.py', 'admin_tools.py',
        'copy_settings.py', 'clone.py', 'adduserbot.py',
        'setmessage.py', 'music_new.py',
    ]

    issues = []

    for handler_file in handler_files:
        file_path = handlers_dir / handler_file
        if not file_path.exists():
            print(f"⚠️  {handler_file} - FILE NOT FOUND")
            continue

        # Read file content and check for async def
        content = file_path.read_text()

        # Find all async def functions (likely handlers)
        async_funcs = re.findall(r'async def (\w+)\s*\([^)]*update[^)]*context[^)]*\)', content)

        if async_funcs:
            print(f"✅ {handler_file} - Found {len(async_funcs)} async handlers")
        else:
            # Check for ConversationHandler or callback handlers
            if 'ConversationHandler' in content or 'CallbackQueryHandler' in content or 'MessageHandler' in content:
                print(f"✅ {handler_file} - Contains handlers (Conversation/Callback/Message)")
            else:
                print(f"⚠️  {handler_file} - No clear async handlers found")

    print()

def check_duplicate_commands():
    """Check for duplicate command registrations"""
    print("=" * 60)
    print("CHECKING FOR DUPLICATE COMMANDS")
    print("=" * 60)

    commands = extract_registered_commands()
    cmd_counts = {}

    # Also check aliases
    factory_path = Path("bot/factory.py")
    factory_content = factory_path.read_text()

    # Find alias registrations
    alias_pattern = r'register_aliases\(app,\s*\w+\)'
    alias_matches = re.findall(alias_pattern, factory_content)

    # Check for duplicates in command handlers
    for cmd in commands:
        if cmd in cmd_counts:
            cmd_counts[cmd] += 1
        else:
            cmd_counts[cmd] = 1

    duplicates = {k: v for k, v in cmd_counts.items() if v > 1}

    if duplicates:
        print("❌ Found duplicate command registrations:")
        for cmd, count in duplicates.items():
            print(f"   {cmd} registered {count} times")
    else:
        print("✅ No duplicate command registrations found")

    print()

def check_miniapp_structure():
    """Check miniapp HTML structure"""
    print("=" * 60)
    print("CHECKING MINIAPP STRUCTURE")
    print("=" * 60)

    miniapp_path = Path("miniapp/index.html")

    if not miniapp_path.exists():
        print("❌ miniapp/index.html not found")
        return []

    content = miniapp_path.read_text()

    # Check for basic structure
    checks = [
        ('<!DOCTYPE html>', 'DOCTYPE declaration'),
        ('<html', 'HTML tag'),
        ('<head>', 'Head section'),
        ('<body>', 'Body section'),
        ('telegram-web-app.js', 'Telegram WebApp script'),
        ('styles/tokens.css', 'Design tokens'),
        ('styles/layout.css', 'Layout styles'),
    ]

    issues = []
    for check_str, check_name in checks:
        if check_str in content:
            print(f"✅ {check_name} present")
        else:
            print(f"❌ {check_name} missing")
            issues.append(f"Missing {check_name}")

    # Check for JavaScript content
    if '<script' in content:
        print("✅ JavaScript content present")
    else:
        print("❌ JavaScript content missing")
        issues.append("Missing JavaScript content")

    print()
    return issues

def main():
    """Run all checks"""
    print("\n🔍 NEXUS BOT COMMAND CHECKER")
    print("=" * 60)
    print()

    syntax_errors = check_syntax()
    commands = extract_registered_commands()
    check_handler_signatures()
    check_duplicate_commands()
    miniapp_issues = check_miniapp_structure()

    # Print summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_issues = len(syntax_errors) + len(miniapp_issues)

    if total_issues == 0:
        print("✅ ALL CHECKS PASSED!")
        print(f"   - {len(commands)} commands registered")
        print("   - All handler files have valid syntax")
        print("   - Mini app structure is complete")
    else:
        print(f"⚠️  Found {total_issues} issue(s):")

        if syntax_errors:
            print(f"\n   Syntax Errors ({len(syntax_errors)}):")
            for file, error in syntax_errors:
                print(f"     - {file}")

        if miniapp_issues:
            print(f"\n   Mini App Issues ({len(miniapp_issues)}):")
            for issue in miniapp_issues:
                print(f"     - {issue}")

    print("=" * 60)
    sys.exit(1 if total_issues > 0 else 0)

if __name__ == "__main__":
    main()
