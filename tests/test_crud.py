"""Unit tests for database CRUD operations."""

import pytest
from app.database.crud import (
    create_media_item,
    get_latest_media,
    get_media_by_id,
    get_system_stats,
    mark_as_published,
    search_media,
)


@pytest.mark.asyncio
async def test_crud_lifecycle(db_session):
    # 1. Create Media Item
    item = await create_media_item(
        session=db_session,
        storage_file_id="fs_test_101",
        filename="Gladiator.2000.1080p.mp4",
        title="Gladiator",
        share_url="https://storage.example.com/Gladiator.mp4",
        year=2000,
        quality="1080p Full HD",
        genre="Action, Adventure",
        rating="8.5/10",
        description="A former Roman General sets out to exact vengeance.",
        status="pending",
    )
    await db_session.commit()

    assert item.id is not None
    assert item.title == "Gladiator"
    assert item.status == "pending"

    # 2. Query Item by ID
    fetched = await get_media_by_id(db_session, item.id)
    assert fetched is not None
    assert fetched.storage_file_id == "fs_test_101"

    # 3. Mark as Published
    published = await mark_as_published(db_session, item.id, channel_message_id=999)
    await db_session.commit()
    assert published.status == "published"
    assert published.channel_message_id == 999

    # 4. Search Media
    results, count = await search_media(db_session, "Gladiator")
    assert count == 1
    assert len(results) == 1
    assert results[0].title == "Gladiator"

    # 5. Get Latest Media
    latest = await get_latest_media(db_session, limit=5)
    assert len(latest) >= 1
    assert latest[0].id == item.id

    # 6. System Stats
    stats = await get_system_stats(db_session)
    assert stats["total_items"] == 1
    assert stats["published_items"] == 1
