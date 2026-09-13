"""Metadata enrichment package."""

from app.metadata.base import EnrichedMetadata, MetadataProvider
from app.metadata.processor import MetadataProcessor

__all__ = ["EnrichedMetadata", "MetadataProvider", "MetadataProcessor"]
