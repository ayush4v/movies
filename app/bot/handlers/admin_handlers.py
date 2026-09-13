"""Administrative command handlers for authorized operators."""

import re
import uuid
from typing import Dict
import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from app.bot.middleware import admin_required
from app.bot.publisher import TelegramPublisher
from app.config import get_settings
from app.database.crud import (
    get_media_by_message_id,
    get_system_stats,
    mark_as_deleted,
)
from app.database.session import get_db
from app.logger import logger
from app.metadata.processor import MetadataProcessor
from app.parser.filename_parser import parse_media_filename

# In-memory staging cache for manual /add workflow: staging_token -> {metadata, share_url, filename}
STAGED_ADD_ITEMS: Dict[str, dict] = {}


async def resolve_filename_from_url(url: str) -> str:
    """Extract real file title from web share pages like TeraBox or standard web links."""
    if any(k in url.lower() for k in ("terabox", "1024tera", "teraboxshare", "terabox.app")):
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=8), allow_redirects=True) as r:
                    if r.status == 200:
                        html = await r.text()
                        m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
                        if m:
                            title_text = m.group(1).strip()
                            clean = re.split(r"[-–—|]\s*(?:Share Files|TeraBox)", title_text, flags=re.IGNORECASE)[0].strip()
                            if clean and len(clean) > 3 and "." in clean:
                                return clean
        except Exception as e:
            logger.debug(f"Could not resolve TeraBox page title: {e}")

    # Fallback to URL path basename
    path = url.split("?")[0].rstrip("/")
    base = path.split("/")[-1]
    return base if base else "unknown_video.mp4"


@admin_required
async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /admin command with interactive management buttons."""
    text = (
        "⚙️ **Admin Control Panel**\n\n"
        "Select an action below to manage storage sync, monitor system health, or inspect publishing pipelines."
    )

    keyboard = [
        [
            InlineKeyboardButton("📊 System Stats", callback_data="admin:stats"),
            InlineKeyboardButton("🔄 Trigger Resync", callback_data="admin:resync"),
        ],
        [
            InlineKeyboardButton("➕ Add Video Manually", callback_data="admin:add_info"),
            InlineKeyboardButton("ℹ️ Help Reference", callback_data="cmd:help"),
        ],
    ]

    if update.effective_message:
        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


@admin_required
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command displaying system statistics."""
    async with get_db() as session:
        stats = await get_system_stats(session)

    # Format byte size
    total_bytes = stats["total_bytes"]
    if total_bytes > 1024**3:
        size_str = f"{total_bytes / (1024**3):.2f} GB"
    elif total_bytes > 1024**2:
        size_str = f"{total_bytes / (1024**2):.2f} MB"
    else:
        size_str = f"{total_bytes / 1024:.2f} KB"

    settings = get_settings()

    text = (
        "📊 **System & Publishing Statistics**\n\n"
        f"• **Storage Provider:** `{settings.storage_provider.upper()}`\n"
        f"• **Target Channel:** `{settings.telegram_channel_id}`\n"
        f"• **Total Indexed Media:** `{stats['total_items']}`\n"
        f"• **Published Posts:** `{stats['published_items']}`\n"
        f"• **Pending Items:** `{stats['pending_items']}`\n"
        f"• **Failed Publishes:** `{stats['failed_items']}`\n"
        f"• **Total Tracked Size:** `{size_str}`\n"
        f"• **Last Sync Completed:** `{stats['last_sync_time']}`\n"
        f"• **Last Sync Status:** `{stats['last_sync_status']}`\n"
    )

    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Stats", callback_data="admin:stats")],
    ]

    if update.effective_message:
        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


@admin_required
async def resync_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /resync command to run an on-demand synchronization pass."""
    from app.services.sync_service import SyncService

    if update.effective_message:
        status_msg = await update.effective_message.reply_text(
            "⏳ **Initiating cloud storage synchronization...**\nPlease wait.",
            parse_mode=ParseMode.MARKDOWN,
        )

    try:
        service = SyncService(bot=context.bot)
        result = await service.run_sync(sync_source="manual_admin")

        report = (
            "✅ **Synchronization Complete!**\n\n"
            f"• **Files Detected:** `{result['files_detected']}`\n"
            f"• **New Processed & Published:** `{result['new_processed']}`\n"
            f"• **Duplicates Filtered:** `{result['duplicates_skipped']}`\n"
            f"• **Errors Encountered:** `{result['errors_count']}`\n"
        )
        if update.effective_message:
            await update.effective_message.reply_text(report, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Manual resync failed: {e}", exc_info=True)
        if update.effective_message:
            await update.effective_message.reply_text(
                f"❌ **Sync Error:** {e}", parse_mode=ParseMode.MARKDOWN
            )


@admin_required
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin interactive /add workflow:

    /add <share_url_or_filename>
    -> parses title/year
    -> fetches metadata from TMDB/OMDB
    -> generates preview post
    -> renders [Publish] and [Cancel] buttons
    """
    args = context.args
    if not args:
        if update.effective_message:
            await update.effective_message.reply_text(
                "➕ **Manual Post Staging Workflow**\n\n"
                "Please provide an authorized share URL or filename after the command.\n\n"
                "**Usage:**\n"
                "`/add https://storage.example.com/videos/The.Matrix.1999.1080p.mp4`\n"
                "or\n"
                "`/add The.Matrix.1999.1080p.BluRay.x264.mkv`",
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    first_arg = args[0].strip()
    extra_text = " ".join(args[1:]).strip() if len(args) > 1 else ""

    # Determine filename from URL or input
    if "://" in first_arg:
        share_url = first_arg
        resolved_filename = await resolve_filename_from_url(share_url)
        # If extra_text is provided, use it to augment or override
        if extra_text.isdigit() and len(extra_text) == 4:
            # User provided just a year, e.g. /add <url> 2024
            filename = f"{resolved_filename.rsplit('.', 1)[0]}.{extra_text}.mp4"
        elif extra_text:
            # User provided a custom title/year, e.g. /add <url> My Movie 2024
            filename = f"{extra_text}.mp4"
        else:
            filename = resolved_filename
    else:
        raw_input = " ".join(args).strip()
        filename = raw_input
        settings = get_settings()
        share_url = f"{settings.local_storage_base_url or 'https://storage.example.com'}/{filename}"

    if update.effective_message:
        await update.effective_message.reply_text(
            f"🔍 Fetching metadata for: `{filename}`...",
            parse_mode=ParseMode.MARKDOWN,
        )

    # 1. Parse filename
    parsed = parse_media_filename(filename)

    # If extra_text was just a year, ensure parsed.year is explicitly set
    if extra_text.isdigit() and len(extra_text) == 4:
        parsed.year = int(extra_text)

    # 2. Enrich metadata
    processor = MetadataProcessor()
    metadata = await processor.process(parsed)

    # 3. Create staging session
    staging_token = str(uuid.uuid4())[:8]
    STAGED_ADD_ITEMS[staging_token] = {
        "metadata": metadata,
        "share_url": share_url,
        "filename": filename,
    }

    # 4. Render preview
    preview_text = TelegramPublisher.format_post_text(metadata)

    keyboard = [
        [
            InlineKeyboardButton("✅ Publish Now", callback_data=f"staged_pub:{staging_token}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"staged_cancel:{staging_token}"),
        ]
    ]

    header = "📋 **Post Preview (Admin Review):**\n" + ("=" * 28) + "\n\n"

    if update.effective_message:
        if metadata.poster_url:
            try:
                caption_text = header + preview_text
                if len(caption_text) > 1020:
                    caption_text = caption_text[:1017] + "..."
                try:
                    await update.effective_message.reply_photo(
                        photo=metadata.poster_url,
                        caption=caption_text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    return
                except Exception:
                    await update.effective_message.reply_photo(
                        photo=metadata.poster_url,
                        caption=caption_text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                    )
                    return
            except Exception as e:
                logger.warning(f"Could not send preview photo: {e}")

        await update.effective_message.reply_text(
            header + preview_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


@admin_required
async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /delete <message_id> to remove a published post from channel."""
    args = context.args
    if not args or not args[0].isdigit():
        if update.effective_message:
            await update.effective_message.reply_text(
                "🗑 **Delete Post Command**\n\n"
                "Provide the channel message ID to remove.\n"
                "**Usage:** `/delete 1234`",
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    msg_id = int(args[0])
    publisher = TelegramPublisher(bot=context.bot)
    deleted = await publisher.delete_channel_post(msg_id)

    async with get_db() as session:
        item = await get_media_by_message_id(session, msg_id)
        if item:
            await mark_as_deleted(session, item.id)

    if deleted:
        msg = f"✅ Message `{msg_id}` deleted from channel successfully."
    else:
        msg = f"⚠️ Post record updated in database, but could not delete message `{msg_id}` from channel (may already be removed)."

    if update.effective_message:
        await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
