"""Abstract StorageProvider interface for cloud and local storage systems."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class StorageFileInfo:
    """Standardized representation of a detected video/media file."""

    file_id: str
    filename: str
    size_bytes: int
    share_url: str
    created_at: Optional[datetime] = None
    content_hash: Optional[str] = None
    extra_meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_video(self) -> bool:
        """Check if file has a supported video extension."""
        video_extensions = (
            ".mp4",
            ".mkv",
            ".avi",
            ".mov",
            ".wmv",
            ".flv",
            ".webm",
            ".m4v",
            ".ts",
        )
        return any(self.filename.lower().endswith(ext) for ext in video_extensions)


class StorageProvider(ABC):
    """Abstract interface defining required storage operations for media detection."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifying name of the storage provider (e.g. 'local', 'terabox', 's3')."""
        pass

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate credentials and reachability of the storage source."""
        pass

    @abstractmethod
    async def list_new_files(
        self, since: Optional[datetime] = None
    ) -> List[StorageFileInfo]:
        """List files added or modified in the monitored storage location."""
        pass

    @abstractmethod
    async def get_file_info(self, file_id: str) -> Optional[StorageFileInfo]:
        """Fetch metadata details for a specific file by its storage identifier."""
        pass

    @abstractmethod
    async def get_share_url(self, file_id: str) -> str:
        """Generate or retrieve the authorized public/authenticated share URL."""
        pass

    @abstractmethod
    async def compute_content_hash(self, file_id: str) -> Optional[str]:
        """Compute or retrieve SHA-256 hash of the file content for duplicate prevention."""
        pass
