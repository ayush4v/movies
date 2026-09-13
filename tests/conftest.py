"""Pytest fixtures for unit and integration testing."""

import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import Settings
from app.database.models import Base

# Set testing environment variables
os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:TEST_BOT_TOKEN_MOCK_123456789"
os.environ["TELEGRAM_CHANNEL_ID"] = "@test_channel"
os.environ["ADMIN_USER_IDS"] = "12345,67890"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["STORAGE_PROVIDER"] = "local"


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Fixture providing test configuration settings."""
    return Settings(
        TELEGRAM_BOT_TOKEN="123456789:TEST_BOT_TOKEN_MOCK_123456789",
        TELEGRAM_CHANNEL_ID="@test_channel",
        ADMIN_USER_IDS=[12345, 67890],
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        STORAGE_PROVIDER="local",
        LOCAL_STORAGE_PATH="./test_storage",
    )


@pytest_asyncio.fixture
async def db_session():
    """Fixture providing an isolated in-memory async SQLite session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()
