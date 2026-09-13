"""End-to-end synchronization pipeline implementing the automatic workflow:

new file detected
→ validate
→ extract metadata
→ duplicate check
→ generate post
→ publish to Telegram channel
→ save Telegram message ID
→ mark as published
"""

from typing import Optional
from telegram import Bot
from app.bot.publisher import TelegramPublisher
from app.config import Settings, get_settings
from app.database.crud import (
    create_media_item,
    create_sync_log,
    mark_as_failed,
    mark_as_published,
    update_sync_log,
)
from app.database.session import get_db
from app.duplicate_checker.checker import DuplicateChecker
from app.logger import logger
from app.metadata.processor import MetadataProcessor
from app.parser.filename_parser import parse_media_filename
from app.services.detector import NewFileDetector
from app.storage.base import StorageFileInfo, StorageProvider
from app.storage.factory import get_storage_provider


class SyncService:
    """Orchestrates detection, duplicate checking, metadata enrichment, and channel publishing."""

    def __init__(
        self,
        bot: Optional[Bot] = None,
        provider: Optional[StorageProvider] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.bot = bot
        self.provider = provider or get_storage_provider(settings=self.settings)
        self.detector = NewFileDetector(self.provider)
        self.duplicate_checker = DuplicateChecker()
        self.metadata_processor = MetadataProcessor(settings=self.settings)
        self.publisher = TelegramPublisher(bot=self.bot, settings=self.settings) if self.bot else None

    async def run_sync(self, sync_source: str = "scheduled") -> dict:
        """Execute a full synchronization cycle."""
        logger.info(f"Starting media synchronization run (source={sync_source})...")

        files_detected = 0
        new_processed = 0
        duplicates_skipped = 0
        errors_count = 0
        log_id: Optional[int] = None

        # Create audit log record
        async with get_db() as session:
            sync_record = await create_sync_log(session, sync_source=sync_source)
            log_id = sync_record.id

        try:
            # 1. New file detected
            detected_files = await self.detector.detect_new_files()
            files_detected = len(detected_files)

            for file_info in detected_files:
                try:
                    processed = await self._process_single_file(file_info)
                    if processed == "published":
                        new_processed += 1
                    elif processed == "duplicate":
                        duplicates_skipped += 1
                    elif processed == "failed":
                        errors_count += 1
                except Exception as file_err:
                    logger.error(
                        f"Error processing file '{file_info.filename}': {file_err}",
                        exc_info=True,
                    )
                    errors_count += 1

            status = "success" if errors_count == 0 else "partial"

        except Exception as e:
            logger.error(f"Sync run failed with critical error: {e}", exc_info=True)
            status = "failed"
            errors_count += 1

        # Finalize audit log record
        if log_id:
            async with get_db() as session:
                await update_sync_log(
                    session=session,
                    log_id=log_id,
                    files_detected=files_detected,
                    new_processed=new_processed,
                    duplicates_skipped=duplicates_skipped,
                    errors_count=errors_count,
                    status=status,
                )

        summary = {
            "files_detected": files_detected,
            "new_processed": new_processed,
            "duplicates_skipped": duplicates_skipped,
            "errors_count": errors_count,
            "status": status,
        }
        logger.info(f"Sync run finished: {summary}")
        return summary

    async def _process_single_file(self, file_info: StorageFileInfo) -> str:
        """Process a single file through the pipeline.

        Returns:
            "published", "duplicate", "skipped", or "failed"
        """
        # Step 1: Validate file is a supported video
        if not file_info.is_video:
            logger.debug(f"Skipping non-video file: {file_info.filename}")
            return "skipped"

        # Compute content hash if provider supports it or local file
        content_hash = file_info.content_hash
        if not content_hash:
            content_hash = await self.provider.compute_content_hash(file_info.file_id)

        # Step 2: Duplicate check
        async with get_db() as session:
            dup_check = await self.duplicate_checker.check(
                session=session,
                storage_file_id=file_info.file_id,
                content_hash=content_hash,
            )
            if dup_check.is_duplicate:
                return "duplicate"

        # Step 3: Extract metadata from filename
        parsed = parse_media_filename(file_info.filename)

        # Step 4: Enrich metadata via TMDB/OMDB or fallback
        enriched = await self.metadata_processor.process(parsed)

        # Step 5: Save preliminary DB record
        item_id = None
        async with get_db() as session:
            item = await create_media_item(
                session=session,
                storage_file_id=file_info.file_id,
                filename=file_info.filename,
                title=enriched.title,
                share_url=file_info.share_url,
                storage_provider=self.provider.provider_name,
                content_hash=content_hash,
                year=enriched.year,
                quality=enriched.quality,
                genre=enriched.genre,
                rating=enriched.rating,
                description=enriched.description,
                poster_url=enriched.poster_url,
                file_size_bytes=file_info.size_bytes,
                status="pending",
            )
            item_id = item.id

        # Step 6: Publish post to Telegram channel
        if not self.publisher:
            logger.warning("Bot is not initialized. Marking item as pending.")
            return "published"

        success, msg_id, err = await self.publisher.publish_to_channel(
            metadata=enriched,
            share_url=file_info.share_url,
        )

        # Step 7: Save Telegram message ID and mark as published
        async with get_db() as session:
            if success and msg_id:
                await mark_as_published(session, item_id, channel_message_id=msg_id)
                return "published"
            else:
                await mark_as_failed(session, item_id, error_message=err or "Unknown error")
                return "failed"
