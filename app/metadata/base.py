"""Abstract base class and data containers for movie metadata providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class EnrichedMetadata:
    """Standardized metadata ready for database storage and Telegram formatting."""

    title: str
    year: Optional[int]
    genre: str
    rating: str
    quality: str
    description: str
    release_date: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    imdb_id: Optional[str] = None
    tmdb_id: Optional[int] = None
    raw_details: Dict[str, Any] = field(default_factory=dict)


class MetadataProvider(ABC):
    """Abstract interface for movie metadata sources (TMDB, OMDB, etc.)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @abstractmethod
    async def fetch_metadata(
        self, title: str, year: Optional[int] = None
    ) -> Optional[EnrichedMetadata]:
        """Query external movie database for matching film/show details."""
        pass
