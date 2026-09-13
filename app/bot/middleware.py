"""Middleware and access decorators for Telegram Bot handlers."""

from functools import wraps
from typing import Callable
from telegram import Update
from telegram.ext import ContextTypes
from app.config import get_settings
from app.logger import logger


def admin_required(func: Callable):
    """Decorator to restrict command execution to authorized administrators."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        settings = get_settings()
        user = update.effective_user

        if not user:
            return

        if not settings.is_admin(user.id):
            logger.warning(
                f"Unauthorized admin command attempt by user {user.id} (@{user.username})"
            )
            if update.effective_message:
                await update.effective_message.reply_text(
                    "⛔ *Access Denied*: You are not authorized to run administrative commands.",
                    parse_mode="Markdown",
                )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper
