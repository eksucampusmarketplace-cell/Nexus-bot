"""
bot/handlers/lang_cmd.py

Re-export shim for lang_setting handlers.
This allows factory.py to import lang_handlers from bot.handlers.lang_cmd
while the actual implementation lives in lang_setting.py.

v22: Created as re-export shim for factory.py compatibility.
"""

from bot.handlers.lang_setting import lang_setting_handlers

__all__ = ['lang_setting_handlers']
