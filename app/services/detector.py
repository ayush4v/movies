"""New file detector inspecting configured storage providers for newly arrived media."""

from datetime import datetime, timezone
from typing import List, Optional
from app.logger import logger
from app.storage.base import StorageFileInfo, StorageProvider


class NewFileDetector:
    """Monitors cloud or local storage provider and surfaces new video files."""

    def __init__(self, provider: StorageProvider):
        self.provider = provider
        self.last_detection_watermark: Optional[datetime] = None

    async def detect_new_files(self) -> List[StorageFileInfo]:
        """Query storage provider for newly added files since last watermark."""
        logger.debug(
            f"Scanning for new files via {self.provider.provider_name} (since={self.last_detection_watermark})..."
        )

        try:
            files = await self.provider.list_new_files(since=self.last_detection_watermark)
            # Update watermark to current scan start
            self.last_detection_watermark = datetime.now(timezone.utc)
            logger.info(f"Detector found {len(files)} candidate media file(s).")
            return files
        except Exception as e:
            logger.error(f"Detector encountered an error while scanning storage: {e}")
            return []
