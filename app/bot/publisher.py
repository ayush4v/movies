"""Telegram post formatter and channel publisher with rate-limiting and retry logic."""

import asyncio
from typing import Optional, Tuple
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter, TelegramError
from app.config import Settings, get_settings
from app.logger import logger
from app.metadata.base import EnrichedMetadata


class TelegramPublisher:
    """Formats and publishes media release announcements to Telegram channels and chats."""

    def __init__(self, bot: Bot, settings: Optional[Settings] = None):
        self.bot = bot
        self.settings = settings or get_settings()
        self.channel_id = self.settings.telegram_channel_id
        self.rate_limit_delay = self.settings.post_rate_limit_delay
        self.max_retries = self.settings.max_publish_retries

    @staticmethod
    def format_post_text(metadata: EnrichedMetadata) -> str:
        """Format post text according to exact specification:

        🎬 {TITLE}

        📅 Year: {YEAR}
        🎭 Genre: {GENRE}
        ⭐ Rating: {RATING}
        🎞 Quality: {QUALITY}

        📝 {DESCRIPTION}
        """
        date_str = metadata.release_date or (str(metadata.year) if metadata.year else "N/A")
        date_label = f"📅 Release Date: {date_str}" if metadata.release_date else f"📅 Year: {date_str}"
        genre_str = metadata.genre or "Cinema"
        rating_str = metadata.rating or "N/A"
        quality_str = metadata.quality or "HD"
        desc_str = metadata.description or "No description provided."

        return (
            f"🎬 {metadata.title}\n\n"
            f"{date_label}\n"
            f"🎭 Genre: {genre_str}\n"
            f"⭐ Rating: {rating_str}\n"
            f"🎞 Quality: {quality_str}\n\n"
            f"📝 {desc_str}"
        )

    @staticmethod
    def build_inline_keyboard(share_url: str) -> InlineKeyboardMarkup:
        """Construct the required inline keyboard with the [▶ WATCH VIDEO] button."""
        keyboard = [
            [
                InlineKeyboardButton(
                    text="▶ WATCH VIDEO",
                    url=share_url,
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def publish_to_channel(
        self,
        metadata: EnrichedMetadata,
        share_url: str,
        channel_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """Publish post to configured Telegram channel with retries and rate limiting.

        Returns:
            (success, telegram_message_id, error_message)
        """
        target_channel = channel_id or self.channel_id
        if not target_channel:
            return False, None, "No target channel configured (TELEGRAM_CHANNEL_ID is empty)"

        post_text = self.format_post_text(metadata)
        reply_markup = self.build_inline_keyboard(share_url)

        # Rate limiting pause before dispatch
        if self.rate_limit_delay > 0:
            await asyncio.sleep(self.rate_limit_delay)

        for attempt in range(1, self.max_retries + 1):
            try:
                # 1. Attempt sending with photo if poster URL is available
                if metadata.poster_url:
                    try:
                        photo_caption = post_text if len(post_text) <= 1020 else post_text[:1017] + "..."
                        msg = await self.bot.send_photo(
                            chat_id=target_channel,
                            photo=metadata.poster_url,
                            caption=photo_caption,
                            reply_markup=reply_markup,
                        )
                        logger.info(
                            f"Published '{metadata.title}' with poster to channel {target_channel} (Msg ID: {msg.message_id})"
                        )
                        return True, msg.message_id, None
                    except TelegramError as te:
                        logger.warning(
                            f"Failed to send poster via photo URL ({te}), falling back to text message."
                        )

                # 2. Fallback to standard text message
                msg = await self.bot.send_message(
                    chat_id=target_channel,
                    text=post_text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=False,
                )
                logger.info(
                    f"Published '{metadata.title}' as text to channel {target_channel} (Msg ID: {msg.message_id})"
                )
                return True, msg.message_id, None

            except RetryAfter as e:
                wait_time = int(e.retry_after) + 1
                logger.warning(
                    f"Telegram Flood Control triggered. Backing off for {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            except TelegramError as e:
                logger.error(
                    f"Telegram error publishing post (attempt {attempt}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return False, None, str(e)
            except Exception as e:
                logger.error(f"Unexpected error publishing to channel: {e}")
                return False, None, str(e)

        return False, None, "Exceeded maximum retry attempts"

    async def delete_channel_post(
        self, message_id: int, channel_id: Optional[str] = None
    ) -> bool:
        """Delete an existing post from the channel."""
        target_channel = channel_id or self.channel_id
        try:
            return await self.bot.delete_message(
                chat_id=target_channel, message_id=message_id
            )
        except Exception as e:
            logger.error(f"Failed to delete message {message_id} from {target_channel}: {e}")
            return False
