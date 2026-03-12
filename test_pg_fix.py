#!/usr/bin/env python3
"""
Test script to verify database connection works with pgbouncer fix.
This script attempts to connect to Supabase and execute a simple query
to ensure the statement_cache_size=0 fix resolves the issue.
"""
import asyncio
import asyncpg
import sys
from config import settings

async def test_connection():
    """Test database connection with statement_cache_size=0."""
    conn_str = settings.SUPABASE_CONNECTION_STRING
    
    print(f"Testing connection to Supabase...")
    print(f"Database: {settings.SUPABASE_URL}")
    
    try:
        # Create connection pool with statement_cache_size=0
        pool = await asyncpg.create_pool(
            conn_str,
            min_size=1,
            max_size=2,
            command_timeout=60,
            statement_cache_size=0,
            server_settings={
                'application_name': 'nexus-bot-test'
            }
        )
        
        print("✓ Connection pool created successfully")
        
        # Test multiple queries to verify prepared statement cache is disabled
        async with pool.acquire() as conn:
            # Query 1
            result = await conn.fetchval("SELECT 1")
            print(f"✓ Test query 1: {result}")
            
            # Query 2 (same query) - should not cause duplicate prepared statement error
            result = await conn.fetchval("SELECT 1")
            print(f"✓ Test query 2: {result}")
            
            # Query 3 (different query)
            result = await conn.fetchval("SELECT NOW()")
            print(f"✓ Test query 3: {result}")
            
            # Query 4 (same as query 1 again)
            result = await conn.fetchval("SELECT 1")
            print(f"✓ Test query 4: {result}")
        
        await pool.close()
        print("\n✅ All tests passed! Database connection works with pgbouncer.")
        return True
        
    except asyncpg.exceptions.DuplicatePreparedStatementError as e:
        print(f"\n❌ DuplicatePreparedStatementError occurred:")
        print(f"   {e}")
        print("\nThe statement_cache_size=0 fix did not resolve the issue.")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected error:")
        print(f"   {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
