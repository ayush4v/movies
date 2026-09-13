"""Unit tests for the filename parsing engine."""

import pytest
from app.parser.filename_parser import parse_media_filename


def test_parse_standard_scene_release():
    filename = "The.Matrix.1999.1080p.BluRay.x264-SPARKS.mkv"
    parsed = parse_media_filename(filename)

    assert parsed.title == "The Matrix"
    assert parsed.year == 1999
    assert "1080p" in parsed.quality
    assert parsed.source == "BluRay"
    assert parsed.codec == "x264"


def test_parse_4k_hdr_release():
    filename = "Interstellar.2014.2160p.UHD.BluRay.x265.10bit.Atmos.mkv"
    parsed = parse_media_filename(filename)

    assert parsed.title == "Interstellar"
    assert parsed.year == 2014
    assert "4K UHD" in parsed.quality
    assert parsed.codec == "x265/HEVC"
    assert parsed.audio == "Atmos"


def test_parse_webrip_with_brackets():
    filename = "[YTS] Inception (2010) [720p] [WEBRip] [AAC].mp4"
    parsed = parse_media_filename(filename)

    assert parsed.title == "Inception"
    assert parsed.year == 2010
    assert "720p" in parsed.quality
    assert parsed.source == "WEBRip"


def test_parse_movie_without_year():
    filename = "Casablanca.1080p.BluRay.mkv"
    parsed = parse_media_filename(filename)

    assert parsed.title == "Casablanca"
    assert parsed.year is None
    assert "1080p" in parsed.quality


def test_display_quality_formatting():
    filename = "Dune.Part.Two.2024.2160p.WEB-DL.x265.mp4"
    parsed = parse_media_filename(filename)

    display = parsed.display_quality()
    assert "4K UHD" in display
    assert "WEBRip" in display or "x265" in display
