"""Unit tests for storage providers."""

import os
import tempfile
import pytest
from app.config import Settings
from app.storage.base import StorageFileInfo
from app.storage.factory import get_storage_provider
from app.storage.local_provider import LocalStorageProvider
from app.storage.terabox_provider import TeraBoxProvider


@pytest.mark.asyncio
async def test_local_storage_provider():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a sample video file
        sample_video = os.path.join(tmp_dir, "MyMovie.2023.1080p.mp4")
        with open(sample_video, "wb") as f:
            f.write(b"SAMPLE_VIDEO_CONTENT_BINARY_DATA_FOR_TESTING")

        # Create a non-video file (should be ignored)
        text_file = os.path.join(tmp_dir, "readme.txt")
        with open(text_file, "w") as f:
            f.write("text content")

        settings = Settings(
            LOCAL_STORAGE_PATH=tmp_dir,
            LOCAL_STORAGE_BASE_URL="https://cdn.example.com/videos",
        )
        provider = LocalStorageProvider(settings=settings)

        assert await provider.validate_connection() is True

        files = await provider.list_new_files()
        assert len(files) == 1
        assert files[0].filename == "MyMovie.2023.1080p.mp4"
        assert files[0].is_video is True
        assert files[0].share_url == "https://cdn.example.com/videos/MyMovie.2023.1080p.mp4"

        # Check content hash computation
        content_hash = await provider.compute_content_hash(files[0].file_id)
        assert content_hash is not None
        assert len(content_hash) == 64  # SHA-256


def test_terabox_provider_initialization():
    settings = Settings(
        TERABOX_APP_ID="test_app_id",
        TERABOX_ACCESS_TOKEN="test_access_token",
        TERABOX_ROOT_FOLDER="/PublicDomainVideos",
    )
    provider = TeraBoxProvider(settings=settings)
    assert provider.provider_name == "terabox"
    assert provider._headers()["Authorization"] == "Bearer test_access_token"


def test_storage_factory():
    settings = Settings(STORAGE_PROVIDER="local")
    provider = get_storage_provider(settings=settings)
    assert provider.provider_name == "local"
