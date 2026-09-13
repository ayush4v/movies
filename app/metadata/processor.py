"""Unified metadata processor orchestrating external APIs and local fallback synthesis."""

from typing import List, Optional
from app.config import Settings, get_settings
from app.logger import logger
from app.metadata.base import EnrichedMetadata, MetadataProvider
from app.metadata.omdb_provider import OMDBMetadataProvider
from app.metadata.public_provider import PublicMetadataProvider
from app.metadata.tmdb_provider import TMDBMetadataProvider
from app.parser.filename_parser import ParsedMediaInfo


class MetadataProcessor:
    """Coordinates metadata lookup across multiple providers with seamless fallback."""

    def __init__(
        self,
        providers: Optional[List[MetadataProvider]] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        if providers is not None:
            self.providers = providers
        else:
            self.providers = [
                TMDBMetadataProvider(self.settings),
                OMDBMetadataProvider(self.settings),
                PublicMetadataProvider(),
            ]

    async def process(self, parsed: ParsedMediaInfo) -> EnrichedMetadata:
        """Enrich parsed media file attributes using available metadata APIs."""
        for provider in self.providers:
            try:
                enriched = await provider.fetch_metadata(parsed.title, parsed.year)
                if enriched:
                    # Overlay detected video quality and technical specs from filename
                    enriched.quality = parsed.display_quality()
                    # Truncate description to ensure it complies with Telegram caption limits (max 800 chars for safety)
                    if len(enriched.description) > 750:
                        enriched.description = enriched.description[:747] + "..."
                    logger.info(
                        f"Successfully enriched metadata for '{parsed.title}' via {provider.name}"
                    )
                    return enriched
            except Exception as e:
                logger.warning(
                    f"Provider {provider.name} failed while processing '{parsed.title}': {e}"
                )

        # Fallback when no external provider found data or keys not configured
        logger.info(
            f"Using local fallback metadata for '{parsed.title}' (Year: {parsed.year})"
        )
        return self._create_fallback_metadata(parsed)

    def _create_fallback_metadata(self, parsed: ParsedMediaInfo) -> EnrichedMetadata:
        """Create fallback metadata record when online lookup is unavailable."""
        return EnrichedMetadata(
            title=parsed.title,
            year=parsed.year,
            genre="Cinema / Media",
            rating="Unrated",
            quality=parsed.display_quality(),
            description=f"Authorized media release: {parsed.title}"
            + (f" ({parsed.year})" if parsed.year else "")
            + ". High-definition authorized stream available via storage share.",
            poster_url=None,
            raw_details={"source": "filename_parser"},
        )
