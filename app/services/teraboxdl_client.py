"""TeraBoxDL API extraction client.

Provides high-throughput extraction of file metadata, direct download links,
HLS/m3u8 streaming links, and thumbnails from TeraBox share URLs using HMAC-SHA256 authentication.
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import List, Optional
import aiohttp
from app.config import Settings, get_settings
from app.logger import logger

TERABOX_DOMAINS = (
    "terabox.com",
    "1024tera.com",
    "teraboxapp.com",
    "teraboxshare.com",
    "terabox.app",
    "mirrobox.com",
    "nephobox.com",
    "4funbox.com",
    "momerybox.com",
    "tibibox.com",
)


@dataclass
class TeraBoxExtractedItem:
    """Represents a file or stream extracted from a TeraBox share link."""

    filename: str
    size_bytes: int
    formatted_size: str
    direct_link: Optional[str] = None
    stream_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    fs_id: Optional[str] = None
    share_url: str = ""


class TeraBoxDLClient:
    """Async client for TeraBoxDL API with automatic HMAC-SHA256 request signing."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.api_key = self.settings.teraboxdl_api_key
        self.api_secret = self.settings.teraboxdl_api_secret
        self.endpoint = self.settings.teraboxdl_endpoint or "https://api.teraboxdl.site/v1/api"

    @classmethod
    def is_terabox_url(cls, url: str) -> bool:
        """Check if a given string contains a known TeraBox domain."""
        if not url:
            return False
        clean = url.lower().strip()
        return any(domain in clean for domain in TERABOX_DOMAINS)

    def _generate_signature(self, body_json: str, timestamp: str) -> str:
        """Calculate HMAC-SHA256 signature according to TeraBoxDL specification:
        message = 'POST/v1/api' + timestamp + body
        signature = hmac_sha256(api_secret, message)
        """
        message = f"POST/v1/api{timestamp}{body_json}"
        secret_bytes = (self.api_secret or "").encode("utf-8")
        return hmac.new(secret_bytes, message.encode("utf-8"), hashlib.sha256).hexdigest()

    async def extract(self, share_url: str) -> Optional[TeraBoxExtractedItem]:
        """Extract primary video metadata, title, size, and download/stream links from TeraBox URL."""
        if not self.api_key or not self.api_secret:
            logger.warning("TeraBoxDL extraction skipped: API Key or Secret not configured.")
            return None

        payload = {
            "url": share_url.strip(),
            "dir_path": "",
            "page": 1,
        }

        # Compact JSON encoding without whitespace as required for signature verification
        body_json = json.dumps(payload, separators=(",", ":"))
        timestamp = str(int(time.time()))
        signature = self._generate_signature(body_json, timestamp)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "X-API-Key": self.api_key,
            "X-Timestamp": timestamp,
            "X-Signature": signature,
        }

        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(self.endpoint, data=body_json, timeout=timeout) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        logger.error(
                            f"TeraBoxDL extraction API returned HTTP {resp.status}: {err_text}"
                        )
                        return None

                    data = await resp.json()

                    if data.get("errno") != 0:
                        errmsg = data.get("errmsg", "Unknown error from TeraBox")
                        logger.warning(
                            f"TeraBoxDL extraction error (errno {data.get('errno')}): {errmsg}"
                        )
                        # Even if errno != 0, check if title or file info exists
                        title = data.get("title")
                        if title and len(title) > 3:
                            return TeraBoxExtractedItem(
                                filename=title,
                                size_bytes=0,
                                formatted_size="Unknown",
                                share_url=share_url,
                            )
                        return None

                    file_list: List[dict] = data.get("list", [])
                    if not file_list:
                        title = data.get("title", "unknown_video.mp4")
                        return TeraBoxExtractedItem(
                            filename=title,
                            size_bytes=data.get("total_size_bytes", 0),
                            formatted_size=data.get("formatted_size", "Unknown"),
                            share_url=share_url,
                        )

                    # Find best video file in list (or first item)
                    primary_item = file_list[0]
                    for item in file_list:
                        name = item.get("server_filename", "").lower()
                        if any(name.endswith(ext) for ext in (".mp4", ".mkv", ".avi", ".mov", ".webm")):
                            primary_item = item
                            break

                    thumbs = primary_item.get("thumbs", {})
                    thumb_url = thumbs.get("url3") or thumbs.get("url2") or thumbs.get("url1")

                    return TeraBoxExtractedItem(
                        filename=primary_item.get("server_filename", "unknown_video.mp4"),
                        size_bytes=primary_item.get("size", 0),
                        formatted_size=primary_item.get("formatted_size", "Unknown"),
                        direct_link=primary_item.get("direct_link"),
                        stream_url=primary_item.get("stream_url"),
                        thumbnail_url=thumb_url,
                        fs_id=str(primary_item.get("fs_id", "")),
                        share_url=share_url,
                    )

        except Exception as exc:
            logger.error(f"TeraBoxDL extraction failed for URL '{share_url}': {exc}", exc_info=True)
            return None
