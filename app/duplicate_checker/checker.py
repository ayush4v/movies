"""Duplicate detection engine based on storage file IDs and SHA-256 content hashes."""

from dataclasses import dataclass
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.crud import is_duplicate_media
from app.logger import logger


@dataclass
class DuplicateCheckResult:
    """Outcome of duplicate evaluation."""

    is_duplicate: bool
    reason: str
    existing_item_id: Optional[int] = None
    existing_file_id: Optional[str] = None


class DuplicateChecker:
    """Prevents duplicate posts across storage file IDs and content checksums."""

    async def check(
        self,
        session: AsyncSession,
        storage_file_id: str,
        content_hash: Optional[str] = None,
    ) -> DuplicateCheckResult:
        """Evaluate whether a file has already been ingested or published."""
        is_dup, existing, reason = await is_duplicate_media(
            session=session,
            storage_file_id=storage_file_id,
            content_hash=content_hash,
        )

        if is_dup and existing:
            logger.info(
                f"Duplicate detected for file '{storage_file_id}': {reason} (Existing ID: {existing.id})"
            )
            return DuplicateCheckResult(
                is_duplicate=True,
                reason=reason,
                existing_item_id=existing.id,
                existing_file_id=existing.storage_file_id,
            )

        return DuplicateCheckResult(
            is_duplicate=False,
            reason="File is unique",
        )
