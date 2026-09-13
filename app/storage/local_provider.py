"""Local disk storage provider for self-hosted or public domain media collections."""

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote
from app.config import Settings, get_settings
from app.logger import logger
from app.storage.base import StorageFileInfo, StorageProvider


class LocalStorageProvider(StorageProvider):
    """Monitors a local filesystem directory for public-domain or authorized user media files."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.root_path = Path(self.settings.local_storage_path).resolve()
        os.makedirs(self.root_path, exist_ok=True)

    @property
    def provider_name(self) -> str:
        return "local"

    async def validate_connection(self) -> bool:
        """Verify the local storage directory exists and is accessible."""
        try:
            return self.root_path.exists() and os.access(self.root_path, os.R_OK)
        except Exception as e:
            logger.error(f"Failed to access local storage directory {self.root_path}: {e}")
            return False

    async def list_new_files(
        self, since: Optional[datetime] = None
    ) -> List[StorageFileInfo]:
        """Scan local folder recursively for video files modified since timestamp."""
        results: List[StorageFileInfo] = []

        if not await self.validate_connection():
            return results

        try:
            for root, _, files in os.walk(self.root_path):
                for filename in files:
                    file_path = Path(root) / filename
                    # Relative path acts as our stable storage_file_id
                    rel_path = file_path.relative_to(self.root_path).as_posix()

                    stat = file_path.stat()
                    file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

                    if since and file_mtime <= since:
                        continue

                    file_info = StorageFileInfo(
                        file_id=rel_path,
                        filename=filename,
                        size_bytes=stat.st_size,
                        share_url=await self.get_share_url(rel_path),
                        created_at=file_mtime,
                        content_hash=None,  # Computed on demand during pipeline
                        extra_meta={"absolute_path": str(file_path)},
                    )

                    if file_info.is_video:
                        results.append(file_info)

        except Exception as e:
            logger.error(f"Error scanning local storage directory: {e}")

        return results

    async def get_file_info(self, file_id: str) -> Optional[StorageFileInfo]:
        """Retrieve file information for a given relative path."""
        file_path = self.root_path / file_id
        if not file_path.exists() or not file_path.is_file():
            return None

        stat = file_path.stat()
        file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        return StorageFileInfo(
            file_id=file_id,
            filename=file_path.name,
            size_bytes=stat.st_size,
            share_url=await self.get_share_url(file_id),
            created_at=file_mtime,
            content_hash=await self.compute_content_hash(file_id),
            extra_meta={"absolute_path": str(file_path)},
        )

    async def get_share_url(self, file_id: str) -> str:
        """Generate web access URL or local file URL."""
        if self.settings.local_storage_base_url:
            base = self.settings.local_storage_base_url.rstrip("/")
            return f"{base}/{quote(file_id)}"
        return f"file://{self.root_path / file_id}"

    async def compute_content_hash(self, file_id: str) -> Optional[str]:
        """Compute SHA-256 hash using streamed chunks to maintain low memory usage."""
        file_path = self.root_path / file_id
        if not file_path.exists():
            return None

        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Read in 64KB chunks
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate SHA-256 hash for {file_id}: {e}")
            return None
