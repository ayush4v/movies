"""CRUD repository functions for media items, search, and audit logs."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import MediaItem, SyncLog


async def get_media_by_storage_id(
    session: AsyncSession, storage_file_id: str
) -> Optional[MediaItem]:
    """Find media item by storage file ID."""
    stmt = select(MediaItem).where(MediaItem.storage_file_id == storage_file_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_media_by_content_hash(
    session: AsyncSession, content_hash: str
) -> Optional[MediaItem]:
    """Find media item by content hash."""
    if not content_hash:
        return None
    stmt = select(MediaItem).where(MediaItem.content_hash == content_hash)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_media_by_id(session: AsyncSession, item_id: int) -> Optional[MediaItem]:
    """Find media item by internal primary key."""
    stmt = select(MediaItem).where(MediaItem.id == item_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_media_by_message_id(
    session: AsyncSession, channel_message_id: int
) -> Optional[MediaItem]:
    """Find media item by Telegram channel message ID."""
    stmt = select(MediaItem).where(MediaItem.channel_message_id == channel_message_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def is_duplicate_media(
    session: AsyncSession,
    storage_file_id: str,
    content_hash: Optional[str] = None,
) -> Tuple[bool, Optional[MediaItem], str]:
    """Check if file already exists in database by file ID or SHA-256 hash.

    Returns:
        (is_dup, existing_item, reason)
    """
    # 1. Primary check: Storage File ID
    existing = await get_media_by_storage_id(session, storage_file_id)
    if existing:
        return True, existing, f"Storage File ID already indexed (ID: {existing.id})"

    # 2. Secondary check: Content Hash
    if content_hash:
        existing_hash = await get_media_by_content_hash(session, content_hash)
        if existing_hash:
            return True, existing_hash, f"Identical content hash detected (matches ID: {existing_hash.id})"

    return False, None, ""


async def create_media_item(
    session: AsyncSession,
    storage_file_id: str,
    filename: str,
    title: str,
    share_url: str,
    storage_provider: str = "local",
    content_hash: Optional[str] = None,
    year: Optional[int] = None,
    quality: Optional[str] = None,
    genre: Optional[str] = None,
    rating: Optional[str] = None,
    description: Optional[str] = None,
    poster_url: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
    status: str = "pending",
) -> MediaItem:
    """Create and persist a new media item."""
    item = MediaItem(
        storage_file_id=storage_file_id,
        filename=filename,
        title=title,
        share_url=share_url,
        storage_provider=storage_provider,
        content_hash=content_hash,
        year=year,
        quality=quality,
        genre=genre,
        rating=rating,
        description=description,
        poster_url=poster_url,
        file_size_bytes=file_size_bytes,
        status=status,
    )
    session.add(item)
    await session.flush()
    return item


async def mark_as_published(
    session: AsyncSession, item_id: int, channel_message_id: int
) -> Optional[MediaItem]:
    """Mark media item as published and record Telegram channel message ID."""
    item = await get_media_by_id(session, item_id)
    if item:
        item.status = "published"
        item.channel_message_id = channel_message_id
        item.published_at = datetime.now(timezone.utc)
        item.error_message = None
        await session.flush()
    return item


async def mark_as_failed(
    session: AsyncSession, item_id: int, error_message: str
) -> Optional[MediaItem]:
    """Mark media item as failed with error details."""
    item = await get_media_by_id(session, item_id)
    if item:
        item.status = "failed"
        item.error_message = error_message
        await session.flush()
    return item


async def mark_as_deleted(session: AsyncSession, item_id: int) -> Optional[MediaItem]:
    """Mark media item as deleted."""
    item = await get_media_by_id(session, item_id)
    if item:
        item.status = "deleted"
        await session.flush()
    return item


async def get_latest_media(
    session: AsyncSession, limit: int = 5
) -> List[MediaItem]:
    """Retrieve the most recently published media items."""
    stmt = (
        select(MediaItem)
        .where(MediaItem.status == "published")
        .order_by(MediaItem.published_at.desc(), MediaItem.id.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_media(
    session: AsyncSession, query: str, limit: int = 10, offset: int = 0
) -> Tuple[List[MediaItem], int]:
    """Search published media items by title, genre, or description.

    Returns:
        (items, total_count)
    """
    clean_query = query.strip()
    pattern = f"%{clean_query}%"
    filter_clause = or_(
        MediaItem.title.ilike(pattern),
        MediaItem.genre.ilike(pattern),
        MediaItem.filename.ilike(pattern),
    )

    count_stmt = select(func.count(MediaItem.id)).where(
        MediaItem.status == "published", filter_clause
    )
    total = (await session.execute(count_stmt)).scalar() or 0

    items_stmt = (
        select(MediaItem)
        .where(MediaItem.status == "published", filter_clause)
        .order_by(MediaItem.year.desc().nullslast(), MediaItem.title.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(items_stmt)
    items = list(result.scalars().all())

    return items, total


async def get_system_stats(session: AsyncSession) -> dict:
    """Retrieve statistical counters for admin dashboard."""
    total_stmt = select(func.count(MediaItem.id))
    total_count = (await session.execute(total_stmt)).scalar() or 0

    published_stmt = select(func.count(MediaItem.id)).where(MediaItem.status == "published")
    published_count = (await session.execute(published_stmt)).scalar() or 0

    failed_stmt = select(func.count(MediaItem.id)).where(MediaItem.status == "failed")
    failed_count = (await session.execute(failed_stmt)).scalar() or 0

    pending_stmt = select(func.count(MediaItem.id)).where(MediaItem.status == "pending")
    pending_count = (await session.execute(pending_stmt)).scalar() or 0

    size_stmt = select(func.coalesce(func.sum(MediaItem.file_size_bytes), 0))
    total_bytes = (await session.execute(size_stmt)).scalar() or 0

    last_sync_stmt = select(SyncLog).order_by(SyncLog.id.desc()).limit(1)
    last_sync = (await session.execute(last_sync_stmt)).scalar_one_or_none()

    return {
        "total_items": total_count,
        "published_items": published_count,
        "failed_items": failed_count,
        "pending_items": pending_count,
        "total_bytes": total_bytes,
        "last_sync_time": last_sync.completed_at.isoformat() if last_sync and last_sync.completed_at else "Never",
        "last_sync_status": last_sync.status if last_sync else "N/A",
    }


async def create_sync_log(session: AsyncSession, sync_source: str = "scheduled") -> SyncLog:
    """Create a new sync log entry."""
    log_entry = SyncLog(
        sync_source=sync_source,
        status="in_progress",
        started_at=datetime.now(timezone.utc),
    )
    session.add(log_entry)
    await session.flush()
    return log_entry


async def update_sync_log(
    session: AsyncSession,
    log_id: int,
    files_detected: int,
    new_processed: int,
    duplicates_skipped: int,
    errors_count: int,
    status: str,
    error_details: Optional[str] = None,
) -> None:
    """Update sync log entry with execution summary."""
    stmt = (
        update(SyncLog)
        .where(SyncLog.id == log_id)
        .values(
            files_detected=files_detected,
            new_files_processed=new_processed,
            duplicates_skipped=duplicates_skipped,
            errors_count=errors_count,
            status=status,
            error_details=error_details,
            completed_at=datetime.now(timezone.utc),
        )
    )
    await session.execute(stmt)
