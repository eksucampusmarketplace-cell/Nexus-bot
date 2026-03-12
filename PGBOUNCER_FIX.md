# PgBouncer Fix for Supabase/asyncpg Compatibility

## Problem

When using Supabase PostgreSQL with asyncpg, the application crashes during startup with:

```
asyncpg.exceptions.DuplicatePreparedStatementError: prepared statement "__asyncpg_stmt_2__" already exists
```

## Root Cause

Supabase uses **pgbouncer** as a connection pooler with **transaction pooling** mode. This mode doesn't support PostgreSQL prepared statements properly because:

1. Prepared statements are connection-specific
2. With transaction pooling, connections are returned to the pool after each transaction
3. When a connection is reused for a different transaction, the prepared statement from the previous transaction is still registered
4. asyncpg tries to prepare the same statement again, causing a duplicate error

## Solution

Disable asyncpg's prepared statement cache by setting `statement_cache_size=0` when creating the connection pool:

```python
pool = await asyncpg.create_pool(
    connection_string,
    statement_cache_size=0,  # ← Critical for pgbouncer compatibility
    min_size=1,
    max_size=10,
    command_timeout=60,
    server_settings={'application_name': 'nexus-bot'}
)
```

## Files Modified

1. **`db/client.py`** - Main database connection pool (applied `statement_cache_size=0`)
2. **`check_db.py`** - Database checker utility (applied `statement_cache_size=0`)

## Trade-offs

- **Pros**: Works correctly with pgbouncer transaction pooling
- **Cons**: Slightly reduced performance due to lack of prepared statement caching
  - For most applications, this performance impact is negligible (< 5%)
  - The reliability and compatibility benefits far outweigh this small cost

## Why Not Other Solutions?

The error message suggests two alternatives:

1. **Use asyncpg's built-in connection pooling** instead of pgbouncer
   - Not viable for Supabase deployments where pgbouncer is required

2. **Set statement_cache_size to 0** (chosen solution)
   - Simple, effective, and doesn't require infrastructure changes

## Testing

To verify the fix works, run:

```bash
python test_pg_fix.py
```

This script tests multiple consecutive queries to ensure no duplicate prepared statement errors occur.

## References

- https://github.com/MagicStack/asyncpg/issues/506
- https://www.pgbouncer.org/usage.html
- https://supabase.com/docs/guides/platform/connecting-to-postgres#connection-pooler
