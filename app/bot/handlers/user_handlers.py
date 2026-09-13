"""User-facing command handlers for general audience and subscribers."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from app.database.crud import get_latest_media, search_media
from app.database.session import get_db
from app.logger import logger


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command with an introduction and navigation menu."""
    user = update.effective_user
    greeting = f"Hello {user.first_name if user else 'there'}! 👋\n\n"

    text = (
        f"{greeting}"
        "Welcome to the **Media Automation Hub**!\n\n"
        "Here you can explore newly added, authorized and public-domain media releases. "
        "Every release includes complete metadata and direct access links.\n\n"
        "**Available Commands:**\n"
        "• `/latest` - View the most recently published videos\n"
        "• `/search <title>` - Search our catalog by title or keyword\n"
        "• `/help` - View command assistance and tips\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("🔥 Latest Releases", callback_data="cmd:latest"),
            InlineKeyboardButton("ℹ️ Help & Info", callback_data="cmd:help"),
        ]
    ]

    if update.effective_message:
        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command with instructions and guidelines."""
    text = (
        "📖 **Help & Guidance**\n\n"
        "**User Commands:**\n"
        "• `/start` - Start the bot and display main menu\n"
        "• `/latest` - Show the 5 latest authorized video releases\n"
        "• `/search <keyword>` - Search through indexed titles\n"
        "  _Example:_ `/search Matrix` or `/search 2024`\n\n"
        "**Admin Commands:** (Authorized administrators only)\n"
        "• `/admin` - Open Admin Control Panel\n"
        "• `/stats` - View system, storage, and publishing statistics\n"
        "• `/resync` - Trigger an immediate manual scan of cloud storage\n"
        "• `/add <url or file>` - Manually stage, preview, and publish a video\n"
        "• `/delete <message_id>` - Remove a post from the channel\n\n"
        "🛡️ _Notice: This bot exclusively indexes public domain, user-owned, or authorized media._"
    )

    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def latest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /latest command showing the 5 most recently published media items."""
    async with get_db() as session:
        items = await get_latest_media(session, limit=5)

    if not items:
        if update.effective_message:
            await update.effective_message.reply_text(
                "📭 No media items have been published yet. Check back soon!"
            )
        return

    text = "🔥 **Latest 5 Releases:**\n\n"
    keyboard = []

    for idx, item in enumerate(items, 1):
        year_str = f" ({item.year})" if item.year else ""
        quality_str = f" [{item.quality}]" if item.quality else ""
        text += f"{idx}. **{item.title}**{year_str}{quality_str}\n"
        keyboard.append(
            [InlineKeyboardButton(f"▶ Watch: {item.title[:25]}", url=item.share_url)]
        )

    if update.effective_message:
        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search command with query matching."""
    args = context.args
    if not args:
        if update.effective_message:
            await update.effective_message.reply_text(
                "🔎 Please specify a search query.\n\n"
                "_Example:_ `/search Inception` or `/search 1080p`",
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    query = " ".join(args).strip()

    async with get_db() as session:
        items, total = await search_media(session, query, limit=5, offset=0)

    if not items:
        if update.effective_message:
            await update.effective_message.reply_text(
                f"🔍 No results found matching **'{query}'**.",
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    text = f"🔎 **Found {total} result(s) for '{query}':**\n\n"
    keyboard = []

    for idx, item in enumerate(items, 1):
        year_str = f" ({item.year})" if item.year else ""
        quality_str = f" • {item.quality}" if item.quality else ""
        text += f"{idx}. **{item.title}**{year_str}{quality_str}\n"
        keyboard.append(
            [InlineKeyboardButton(f"▶ Watch: {item.title[:25]}", url=item.share_url)]
        )

    if update.effective_message:
        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
