"""Callback query router for inline button interactions."""

import uuid
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from app.bot.handlers.admin_handlers import STAGED_ADD_ITEMS
from app.bot.publisher import TelegramPublisher
from app.config import get_settings
from app.database.crud import (
    create_media_item,
    get_system_stats,
    mark_as_published,
)
from app.database.session import get_db
from app.logger import logger


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route callback data to specific handler actions."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    data = query.data or ""
    settings = get_settings()
    user_id = query.from_user.id if query.from_user else 0

    # User callbacks
    if data == "cmd:latest":
        from app.bot.handlers.user_handlers import latest_command
        await latest_command(update, context)
        return

    if data == "cmd:help":
        from app.bot.handlers.user_handlers import help_command
        await help_command(update, context)
        return

    # Admin callbacks (Authorization guard)
    if data.startswith("admin:") or data.startswith("staged_"):
        if not settings.is_admin(user_id):
            await query.edit_message_caption(
                caption="⛔ *Unauthorized*: Admin privileges required.",
                parse_mode=ParseMode.MARKDOWN,
            ) if query.message and query.message.caption else (
                await query.edit_message_text("⛔ *Unauthorized*: Admin privileges required.", parse_mode=ParseMode.MARKDOWN)
            )
            return

    if data == "admin:stats":
        async with get_db() as session:
            stats = await get_system_stats(session)
        text = (
            "📊 **System Statistics**\n\n"
            f"• **Total Tracked:** `{stats['total_items']}`\n"
            f"• **Published:** `{stats['published_items']}`\n"
            f"• **Pending:** `{stats['pending_items']}`\n"
            f"• **Failed:** `{stats['failed_items']}`\n"
            f"• **Last Sync:** `{stats['last_sync_time']}`\n"
        )
        if query.message:
            await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return

    if data == "admin:resync":
        from app.bot.handlers.admin_handlers import resync_command
        await resync_command(update, context)
        return

    if data == "admin:add_info":
        if query.message:
            await query.message.reply_text(
                "➕ To stage a video manually, type:\n`/add <share_url or filename>`",
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    # Staged publish workflow
    if data.startswith("staged_pub:"):
        token = data.split(":", 1)[1]
        staged = STAGED_ADD_ITEMS.get(token)
        if not staged:
            if query.message:
                await query.message.reply_text("⚠️ Staging session expired or already handled.")
            return

        metadata = staged["metadata"]
        share_url = staged["share_url"]
        filename = staged["filename"]

        publisher = TelegramPublisher(bot=context.bot)
        success, msg_id, err = await publisher.publish_to_channel(metadata, share_url)

        if success and msg_id:
            # Save to database
            async with get_db() as session:
                item = await create_media_item(
                    session=session,
                    storage_file_id=f"manual_{uuid.uuid4().hex[:12]}",
                    filename=filename,
                    title=metadata.title,
                    share_url=share_url,
                    storage_provider="manual",
                    year=metadata.year,
                    quality=metadata.quality,
                    genre=metadata.genre,
                    rating=metadata.rating,
                    description=metadata.description,
                    poster_url=metadata.poster_url,
                    status="published",
                )
                await mark_as_published(session, item.id, msg_id)

            del STAGED_ADD_ITEMS[token]
            if query.message:
                await query.message.reply_text(
                    f"🎉 Successfully published **{metadata.title}** to channel! (Message ID: `{msg_id}`)",
                    parse_mode=ParseMode.MARKDOWN,
                )
        else:
            if query.message:
                await query.message.reply_text(f"❌ Failed to publish post: {err}")
        return

    if data.startswith("staged_cancel:"):
        token = data.split(":", 1)[1]
        STAGED_ADD_ITEMS.pop(token, None)
        if query.message:
            await query.message.reply_text("❌ Post staging cancelled.")
        return
