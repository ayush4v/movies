"""S3-compatible cloud storage provider (AWS S3, MinIO, Cloudflare R2)."""

import hashlib
from datetime import datetime, timezone
from typing import List, Optional
from app.config import Settings, get_settings
from app.logger import logger
from app.storage.base import StorageFileInfo, StorageProvider


class S3StorageProvider(StorageProvider):
    """Storage provider for S3/MinIO compatible object stores."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.bucket = self.settings.s3_bucket_name
        self.endpoint = self.settings.s3_endpoint_url
        self.access_key = self.settings.s3_access_key
        self.secret_key = self.settings.s3_secret_key

    @property
    def provider_name(self) -> str:
        return "s3"

    async def validate_connection(self) -> bool:
        """Validate S3 configuration."""
        if not self.bucket or not self.access_key:
            logger.debug("S3 provider not configured.")
            return False
        return True

    async def list_new_files(
        self, since: Optional[datetime] = None
    ) -> List[StorageFileInfo]:
        """List media objects in the S3 bucket."""
        # Stub for S3 provider
        return []

    async def get_file_info(self, file_id: str) -> Optional[StorageFileInfo]:
        return None

    async def get_share_url(self, file_id: str) -> str:
        if self.endpoint:
            return f"{self.endpoint.rstrip('/')}/{self.bucket}/{file_id}"
        return f"https://{self.bucket}.s3.amazonaws.com/{file_id}"

    async def compute_content_hash(self, file_id: str) -> Optional[str]:
        return None
