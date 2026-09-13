"""SQLAlchemy ORM models for media items and audit synchronization logs."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MediaItem(Base):
    """Represents an indexed media file, its extracted metadata, and Telegram post state."""

    __tablename__ = "media_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    storage_file_id = Column(String(255), unique=True, nullable=False, index=True)
    content_hash = Column(String(64), index=True, nullable=True)  # SHA-256
    filename = Column(String(512), nullable=False)
    title = Column(String(255), nullable=False, index=True)
    year = Column(Integer, nullable=True, index=True)
    quality = Column(String(64), nullable=True)
    genre = Column(String(255), nullable=True)
    rating = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    poster_url = Column(String(1024), nullable=True)
    share_url = Column(String(2048), nullable=False)
    storage_provider = Column(String(64), nullable=False, default="local")
    file_size_bytes = Column(BigInteger, nullable=True)

    # Telegram Publishing Info
    channel_message_id = Column(Integer, nullable=True, index=True)
    status = Column(String(32), default="pending", nullable=False, index=True)  # pending, published, failed, deleted
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self) -> dict:
        """Convert model to dictionary representation."""
        return {
            "id": self.id,
            "storage_file_id": self.storage_file_id,
            "content_hash": self.content_hash,
            "filename": self.filename,
            "title": self.title,
            "year": self.year,
            "quality": self.quality,
            "genre": self.genre,
            "rating": self.rating,
            "description": self.description,
            "poster_url": self.poster_url,
            "share_url": self.share_url,
            "storage_provider": self.storage_provider,
            "file_size_bytes": self.file_size_bytes,
            "channel_message_id": self.channel_message_id,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


class SyncLog(Base):
    """Audit log record for storage synchronization runs."""

    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_source = Column(String(64), nullable=False, default="scheduled")  # scheduled, manual, webhook
    files_detected = Column(Integer, default=0, nullable=False)
    new_files_processed = Column(Integer, default=0, nullable=False)
    duplicates_skipped = Column(Integer, default=0, nullable=False)
    errors_count = Column(Integer, default=0, nullable=False)
    status = Column(String(32), default="in_progress", nullable=False)  # in_progress, success, partial, failed
    error_details = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
