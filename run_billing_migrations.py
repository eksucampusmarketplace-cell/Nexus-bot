#!/usr/bin/env python3
"""
Script to run billing v2 migrations manually.

Run this script to:
1. Add billing columns to bots table
2. Add chat_type column to groups table
3. Create billing tables (subscriptions, payment_events, etc.)

Usage:
    python3 run_billing_migrations.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def run_migrations():
    """Run all billing migrations."""
    from db.client import db

    print("Connecting to database...")
    await db.connect()
    print("✓ Connected to database")

    # Migration 1: Add billing v2 columns to bots and groups
    print("\n--- Running add_billing_v2.sql ---")
    migration_1_sql = open("db/migrations/add_billing_v2.sql").read()
    async with db.pool.acquire() as conn:
        try:
            # Split by semicolons and execute each statement
            statements = [s.strip() for s in migration_1_sql.split(';') if s.strip()]
            for stmt in statements:
                if stmt:
                    await conn.execute(stmt)
            print("✓ Migration 1 completed: add_billing_v2.sql")
        except Exception as e:
            print(f"✗ Migration 1 failed: {e}")
            raise

    # Migration 2: Create billing tables
    print("\n--- Running add_billing_tables.sql ---")
    migration_2_sql = open("db/migrations/add_billing_tables.sql").read()
    async with db.pool.acquire() as conn:
        try:
            statements = [s.strip() for s in migration_2_sql.split(';') if s.strip()]
            for stmt in statements:
                if stmt:
                    await conn.execute(stmt)
            print("✓ Migration 2 completed: add_billing_tables.sql")
        except Exception as e:
            print(f"✗ Migration 2 failed: {e}")
            raise

    print("\n✅ All billing migrations completed successfully!")
    print("\nNext steps:")
    print("  1. Restart your bot application")
    print("  2. Test cloning a bot (should start with 15-day trial)")
    print("  3. Check that plan limits are enforced")

    await db.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(run_migrations())
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
