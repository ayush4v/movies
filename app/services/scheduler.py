"""Background scheduler executing periodic storage synchronization runs."""

from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from app.config import Settings, get_settings
from app.logger import logger
from app.services.sync_service import SyncService


class PeriodicSyncScheduler:
    """Manages periodic background execution of media synchronization."""

    def __init__(self, bot: Optional[Bot] = None, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.sync_service = SyncService(bot=self.bot, settings=self.settings)

    def start(self) -> None:
        """Start background scheduler."""
        interval = self.settings.sync_interval_seconds
        logger.info(
            f"Scheduling periodic storage sync every {interval} seconds."
        )

        self.scheduler.add_job(
            self._execute_sync_job,
            trigger="interval",
            seconds=interval,
            id="periodic_storage_sync",
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()

    async def _execute_sync_job(self) -> None:
        """Internal callback invoked periodically by APScheduler."""
        try:
            await self.sync_service.run_sync(sync_source="scheduled")
        except Exception as e:
            logger.error(f"Scheduled sync execution encountered an error: {e}", exc_info=True)

    def shutdown(self) -> None:
        """Gracefully stop background scheduler."""
        if self.scheduler.running:
            logger.info("Stopping background scheduler...")
            self.scheduler.shutdown(wait=False)
