"""Unit tests for metadata enrichment and fallback logic."""

import pytest
from app.metadata.base import EnrichedMetadata, MetadataProvider
from app.metadata.processor import MetadataProcessor
from app.parser.filename_parser import ParsedMediaInfo


class MockMetadataProvider(MetadataProvider):
    """Mock external metadata provider returning simulated movie details."""

    def __init__(self, should_find: bool = True):
        self.should_find = should_find

    @property
    def name(self) -> str:
        return "mock_provider"

    async def fetch_metadata(self, title: str, year: int | None = None) -> EnrichedMetadata | None:
        if not self.should_find:
            return None
        return EnrichedMetadata(
            title="The Matrix",
            year=1999,
            genre="Action, Sci-Fi",
            rating="8.7/10",
            quality="1080p",
            description="A computer hacker learns from mysterious rebels about the true nature of his reality.",
            poster_url="https://image.tmdb.org/t/p/w780/matrix_poster.jpg",
        )


@pytest.mark.asyncio
async def test_metadata_enrichment_success():
    parsed = ParsedMediaInfo(
        raw_filename="The.Matrix.1999.1080p.mkv",
        title="The Matrix",
        year=1999,
        quality="1080p Full HD",
    )
    processor = MetadataProcessor(providers=[MockMetadataProvider(should_find=True)])
    enriched = await processor.process(parsed)

    assert enriched.title == "The Matrix"
    assert enriched.year == 1999
    assert enriched.genre == "Action, Sci-Fi"
    assert enriched.poster_url == "https://image.tmdb.org/t/p/w780/matrix_poster.jpg"
    assert enriched.quality == "1080p Full HD"


@pytest.mark.asyncio
async def test_metadata_fallback():
    parsed = ParsedMediaInfo(
        raw_filename="MyIndependentDocumentary.2024.4K.mp4",
        title="MyIndependentDocumentary",
        year=2024,
        quality="4K UHD",
    )
    processor = MetadataProcessor(providers=[MockMetadataProvider(should_find=False)])
    enriched = await processor.process(parsed)

    assert enriched.title == "MyIndependentDocumentary"
    assert enriched.year == 2024
    assert enriched.quality == "4K UHD"
    assert "Authorized media release" in enriched.description
    assert enriched.poster_url is None
