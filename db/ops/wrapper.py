"""
wrapper.py

Safe database operation wrappers with error handling.

Provides decorators and wrapper functions to handle database errors
gracefully instead of crashing handlers.
"""

import logging
from typing import Callable, TypeVar, Optional
import asyncpg

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def safe_db_operation(
    operation: Callable[..., T], *args, default_return: T = None, log_error: bool = True, **kwargs
) -> Optional[T]:
    """
    Safely execute a database operation with error handling.

    Instead of letting database errors propagate and crash the handler,
    this wrapper catches them and returns None (or a default value).

    Args:
        operation: The async database operation function
        *args: Positional arguments to pass to the operation
        default_return: Value to return on error (default: None)
        log_error: Whether to log the error (default: True)
        **kwargs: Keyword arguments to pass to the operation

    Returns:
        The operation result, or default_return on error

    Example:
        user = await safe_db_operation(
            db.ops.users.get,
            user_id=123
        )
        if not user:
            await update.message.reply_text("User not found")
    """
    try:
        return await operation(*args, **kwargs)
    except asyncpg.PostgresError as e:
        if log_error:
            logger.error(f"Database error in {operation.__name__}: {e}")
        return default_return
    except Exception as e:
        if log_error:
            logger.exception(f"Unexpected error in {operation.__name__}: {e}")
        return default_return


def safe_db_query(default_return: T = None, log_error: bool = True):
    """
    Decorator for database query functions.

    Args:
        default_return: Value to return on error
        log_error: Whether to log errors

    Example:
        @safe_db_query(default_return=[])
        async def get_users(pool):
            return await pool.fetch("SELECT * FROM users")
    """

    def decorator(operation: Callable[..., T]) -> Callable[..., Optional[T]]:
        async def wrapper(*args, **kwargs):
            return await safe_db_operation(
                operation, *args, default_return=default_return, log_error=log_error, **kwargs
            )

        return wrapper

    return decorator
