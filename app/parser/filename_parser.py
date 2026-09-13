"""Robust regex-based media filename parser for extracting title, year, quality, and technical tags."""

import os
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedMediaInfo:
    """Extracted attributes from a media file name."""

    raw_filename: str
    title: str
    year: Optional[int] = None
    quality: Optional[str] = None
    source: Optional[str] = None
    codec: Optional[str] = None
    audio: Optional[str] = None

    def display_quality(self) -> str:
        """Formatted quality string for display in Telegram post."""
        parts = []
        if self.quality:
            parts.append(self.quality)
        if self.source:
            parts.append(self.source)
        if self.codec:
            parts.append(self.codec)
        return " ".join(parts) if parts else (self.quality or "HD")


# Common technical tags regex patterns
YEAR_PATTERN = re.compile(r"[\s._\(\[\{-](19\d\d|20\d\d)[\s._\)\]\}]?", re.IGNORECASE)

QUALITY_PATTERNS = [
    (re.compile(r"\b(2160p|4k|uhd)\b", re.IGNORECASE), "4K UHD"),
    (re.compile(r"\b(1080p|1080i|fhd)\b", re.IGNORECASE), "1080p Full HD"),
    (re.compile(r"\b(720p|hd)\b", re.IGNORECASE), "720p HD"),
    (re.compile(r"\b(480p|576p|sd)\b", re.IGNORECASE), "480p SD"),
]

SOURCE_PATTERNS = [
    (re.compile(r"\b(bluray|bdrip|brrip)\b", re.IGNORECASE), "BluRay"),
    (re.compile(r"\b(web[-._]?dl|webrip|web)\b", re.IGNORECASE), "WEBRip"),
    (re.compile(r"\b(hdtv|pdtv|dsr)\b", re.IGNORECASE), "HDTV"),
    (re.compile(r"\b(dvdrip|dvd)\b", re.IGNORECASE), "DVDRip"),
    (re.compile(r"\b(cam|camrip|ts|telesync)\b", re.IGNORECASE), "CAM/TS"),
]

CODEC_PATTERNS = [
    (re.compile(r"\b(x265|h[-._]?265|hevc)\b", re.IGNORECASE), "x265/HEVC"),
    (re.compile(r"\b(x264|h[-._]?264|avc)\b", re.IGNORECASE), "x264"),
    (re.compile(r"\b(av1)\b", re.IGNORECASE), "AV1"),
    (re.compile(r"\b(xvid|divx)\b", re.IGNORECASE), "XviD"),
]

AUDIO_PATTERNS = [
    (re.compile(r"\b(atmos)\b", re.IGNORECASE), "Atmos"),
    (re.compile(r"\b(dts[-._]hd|dts)\b", re.IGNORECASE), "DTS"),
    (re.compile(r"\b(truehd)\b", re.IGNORECASE), "TrueHD"),
    (re.compile(r"\b(eac3|ddp|dd\+|ac3|5\.1|7\.1)\b", re.IGNORECASE), "5.1 Surround"),
    (re.compile(r"\b(aac|mp3)\b", re.IGNORECASE), "Stereo"),
]

# Scene groups and common release watermarks to strip
NOISE_WORDS = re.compile(
    r"\b(yts|yify|rarbg|psa|galaxy|tgx|vxt|ettv|pahe|sparks|amiable|d3g|repack|proper|unrated|extended|directors[-._]?cut|remastered)\b",
    re.IGNORECASE,
)


def parse_media_filename(filename: str) -> ParsedMediaInfo:
    """Parse media filename to extract title, release year, video quality, and codec information.

    Examples:
        "The.Matrix.1999.1080p.BluRay.x264-SPARKS.mkv"
        -> title: "The Matrix", year: 1999, quality: "1080p Full HD", source: "BluRay", codec: "x264"
    """
    # Strip directory path and file extension
    base_name = os.path.basename(filename)
    name_without_ext, _ = os.path.splitext(base_name)

    # 1. Detect Quality
    detected_quality = None
    for pattern, label in QUALITY_PATTERNS:
        if pattern.search(name_without_ext):
            detected_quality = label
            break

    # 2. Detect Source
    detected_source = None
    for pattern, label in SOURCE_PATTERNS:
        if pattern.search(name_without_ext):
            detected_source = label
            break

    # 3. Detect Codec
    detected_codec = None
    for pattern, label in CODEC_PATTERNS:
        if pattern.search(name_without_ext):
            detected_codec = label
            break

    # 4. Detect Audio
    detected_audio = None
    for pattern, label in AUDIO_PATTERNS:
        if pattern.search(name_without_ext):
            detected_audio = label
            break

    # 5. Detect Year
    year_match = YEAR_PATTERN.search(name_without_ext)
    detected_year = None
    title_raw = name_without_ext

    if year_match:
        detected_year = int(year_match.group(1))
        # Everything before the year is typically the title
        title_raw = name_without_ext[: year_match.start()]
    else:
        # If no year found, find the earliest appearance of quality/source/codec
        earliest_idx = len(name_without_ext)
        for pattern, _ in QUALITY_PATTERNS + SOURCE_PATTERNS + CODEC_PATTERNS:
            m = pattern.search(name_without_ext)
            if m and m.start() < earliest_idx:
                earliest_idx = m.start()
        if earliest_idx < len(name_without_ext):
            title_raw = name_without_ext[:earliest_idx]

    # Clean up the extracted title
    # Replace dots, underscores, dashes with spaces
    clean_title = re.sub(r"[\._\-\+]+", " ", title_raw)
    # Remove brackets, parentheses, curly braces
    clean_title = re.sub(r"[\(\)\[\]\{\}]", " ", clean_title)
    # Remove noise words
    clean_title = NOISE_WORDS.sub("", clean_title)
    # Collapse multiple spaces and strip
    clean_title = re.sub(r"\s+", " ", clean_title).strip()

    # Fallback if title became empty
    if not clean_title:
        clean_title = os.path.splitext(base_name)[0]

    return ParsedMediaInfo(
        raw_filename=filename,
        title=clean_title,
        year=detected_year,
        quality=detected_quality or "1080p Full HD",
        source=detected_source,
        codec=detected_codec,
        audio=detected_audio,
    )
