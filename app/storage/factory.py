"""Factory to dynamically instantiate the configured StorageProvider."""

from typing import Optional
from app.config import Settings, get_settings
from app.logger import logger
from app.storage.base import StorageProvider
from app.storage.local_provider import LocalStorageProvider
from app.storage.s3_provider import S3StorageProvider
from app.storage.terabox_provider import TeraBoxProvider

_cached_provider: Optional[StorageProvider] = None


def get_storage_provider(
    provider_name: Optional[str] = None, settings: Optional[Settings] = None
) -> StorageProvider:
    """Return an instance of the configured storage provider."""
    global _cached_provider

    curr_settings = settings or get_settings()
    name = (provider_name or curr_settings.storage_provider).lower()

    if _cached_provider and _cached_provider.provider_name == name and settings is None:
        return _cached_provider

    if name == "terabox":
        logger.info("Initializing official TeraBox Open Platform storage provider.")
        provider = TeraBoxProvider(settings=curr_settings)
    elif name == "s3":
        logger.info("Initializing S3-compatible cloud storage provider.")
        provider = S3StorageProvider(settings=curr_settings)
    elif name == "local":
        logger.info("Initializing Local filesystem storage provider.")
        provider = LocalStorageProvider(settings=curr_settings)
    else:
        logger.warning(
            f"Unknown storage provider '{name}'. Falling back to local storage provider."
        )
        provider = LocalStorageProvider(settings=curr_settings)

    if settings is None:
        _cached_provider = provider
    return provider
