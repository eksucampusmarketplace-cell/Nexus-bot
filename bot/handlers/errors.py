"""
errors.py

Centralized error handling for Telegram bot handlers.

Provides decorators and utilities for graceful error handling
to prevent webhook failures and improve user experience.
"""

import logging
import traceback
from functools import wraps
from typing import Callable, TypeVar, Any
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Callable)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Global error handler for PTB Application.

    This handler catches unhandled exceptions from all handlers.
    It logs the error with full traceback and attempts to notify the user.

    Usage:
        app.add_error_handler(error_handler)
    """
    error_str = "".join(
        traceback.format_exception(type(context.error), context.error, context.error.__traceback__)
    )
    logger.error(f"[GLOBAL ERROR] {error_str[:1000]}")

    # Try to notify user something went wrong
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Something went wrong while processing your request.\n"
                "Please try again later or contact support if the issue persists."
            )
        elif update and update.callback_query:
            await update.callback_query.answer(
                "❌ An error occurred. Please try again.", show_alert=True
            )
    except Exception as notify_error:
        logger.error(f"Failed to send error notification: {notify_error}")


def safe_handler(handler_func: T) -> T:
    """
    Decorator that gracefully handles errors in bot handlers.

    This decorator:
    1. Catches all exceptions from the handler
    2. Logs the error with full traceback
    3. Sends a user-friendly error message to the user
    4. Returns None to prevent webhook failure (Telegram won't retry)

    Usage:
        @safe_handler
        async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Handler logic here
            pass
    """

    @wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            return await handler_func(update, context)
        except Exception as e:
            # Log the full error with traceback
            logger.exception(f"Error in {handler_func.__name__}: {e}")

            # Send user-friendly error message if we have a message to reply to
            if update and update.effective_message:
                try:
                    error_msg = (
                        "❌ Something went wrong while processing your request.\n"
                        "Please try again later or contact support if the issue persists."
                    )
                    await update.effective_message.reply_text(error_msg)
                except Exception as reply_error:
                    # If we can't even send the error message, just log it
                    logger.error(f"Failed to send error message: {reply_error}")

            return None

    return wrapper


def safe_callback(callback_func: T) -> T:
    """
    Decorator for callback query handlers.

    Similar to safe_handler but specifically handles callback queries,
    which require different response methods (answer_callback_query).

    Usage:
        @safe_callback
        async def my_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Callback logic here
            pass
    """

    @wraps(callback_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            return await callback_func(update, context)
        except Exception as e:
            logger.exception(f"Error in {callback_func.__name__}: {e}")

            if update and update.callback_query:
                try:
                    await update.callback_query.answer(
                        "❌ An error occurred. Please try again.", show_alert=True
                    )
                except Exception as answer_error:
                    logger.error(f"Failed to answer callback query: {answer_error}")

            return None

    return wrapper
