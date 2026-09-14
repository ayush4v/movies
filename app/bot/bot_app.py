"""Telegram bot application builder and command registration."""

from typing import Optional
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from app.bot.handlers.admin_handlers import (
    add_command,
    admin_panel_command,
    delete_command,
    handle_admin_message_link,
    resync_command,
    stats_command,
)
from app.bot.handlers.callbacks import handle_callback_query
from app.bot.handlers.user_handlers import (
    help_command,
    latest_command,
    search_command,
    start_command,
)
from app.config import Settings, get_settings
from app.logger import logger


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unhandled Telegram exceptions with context."""
    logger.error(f"Unhandled Telegram exception: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An internal error occurred while processing your request. Please try again later."
            )
        except Exception:
            pass


def build_telegram_application(
    token: Optional[str] = None, settings: Optional[Settings] = None
) -> Application:
    """Construct and configure the Telegram bot application instance."""
    curr_settings = settings or get_settings()
    bot_token = token or curr_settings.telegram_bot_token

    if not bot_token:
        err = "CRITICAL: TELEGRAM_BOT_TOKEN is missing or empty! Please add TELEGRAM_BOT_TOKEN in Render Environment Variables."
        logger.critical(err)
        raise ValueError(err)

    app = ApplicationBuilder().token(bot_token).build()

    # User commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("latest", latest_command))
    app.add_handler(CommandHandler("search", search_command))

    # Admin commands
    app.add_handler(CommandHandler("admin", admin_panel_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("resync", resync_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("delete", delete_command))

    # Inline button callback queries
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # Automatic link listener (catches TeraBox links and media URLs sent in chat)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message_link))

    # Global error handler
    app.add_error_handler(global_error_handler)

    return app
