"""Unit tests for TeraBoxDL client and URL detection."""

import pytest
from app.services.teraboxdl_client import TeraBoxDLClient


def test_is_terabox_url_detection():
    assert TeraBoxDLClient.is_terabox_url("https://terabox.com/s/1xxxx") is True
    assert TeraBoxDLClient.is_terabox_url("https://1024tera.com/s/1yyyy") is True
    assert TeraBoxDLClient.is_terabox_url("https://teraboxapp.com/s/1zzzz") is True
    assert TeraBoxDLClient.is_terabox_url("https://terabox.app/s/1aaaa") is True
    assert TeraBoxDLClient.is_terabox_url("https://google.com") is False
    assert TeraBoxDLClient.is_terabox_url("") is False


def test_signature_generation():
    client = TeraBoxDLClient()
    body_json = '{"url":"https://terabox.com/s/test","dir_path":"","page":1}'
    ts = "1744212345"
    sig = client._generate_signature(body_json, ts)
    assert len(sig) == 64  # SHA-256 hex digest length
    assert isinstance(sig, str)
