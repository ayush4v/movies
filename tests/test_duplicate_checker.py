"""Unit tests for duplicate detection mechanisms."""

import pytest
from app.database.crud import create_media_item
from app.duplicate_checker.checker import DuplicateChecker


@pytest.mark.asyncio
async def test_duplicate_detection(db_session):
    checker = DuplicateChecker()

    # Initially empty - unique
    res = await checker.check(
        session=db_session,
        storage_file_id="storage_file_001",
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert res.is_duplicate is False

    # Ingest the item
    await create_media_item(
        session=db_session,
        storage_file_id="storage_file_001",
        filename="TestVideo.mp4",
        title="Test Video",
        share_url="https://storage.example.com/TestVideo.mp4",
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    await db_session.commit()

    # 1. Primary check: Storage File ID duplicate
    res_file_id = await checker.check(
        session=db_session,
        storage_file_id="storage_file_001",
        content_hash="different_hash_value",
    )
    assert res_file_id.is_duplicate is True
    assert "Storage File ID" in res_file_id.reason

    # 2. Secondary check: Content hash collision
    res_hash = await checker.check(
        session=db_session,
        storage_file_id="different_storage_file_002",
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert res_hash.is_duplicate is True
    assert "Identical content hash" in res_hash.reason
