"""Asynchronous database session setup and lifecycle management."""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.config import get_settings
from app.database.models import Base
from app.logger import logger

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create singleton async database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.database_url

        # Ensure sqlite data directory exists if using local sqlite file
        if "sqlite" in db_url:
            path_part = db_url.split("sqlite+aiosqlite:///")[-1]
            if path_part and not path_part.startswith(":memory:"):
                # Handle leading slash if present
                clean_path = path_part.lstrip("/")
                directory = os.path.dirname(clean_path)
                if directory:
                    os.makedirs(directory, exist_ok=True)

        connect_args = {}
        if "sqlite" in db_url:
            connect_args["check_same_thread"] = False

        _engine = create_async_engine(
            db_url,
            echo=False,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def init_db() -> None:
    """Initialize database tables and enable SQLite WAL mode for performance."""
    engine = get_engine()
    async with engine.begin() as conn:
        # Enable WAL mode for SQLite to improve concurrent read/write throughput
        if "sqlite" in str(engine.url):
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            await conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialized successfully.")


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager yielding a database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
