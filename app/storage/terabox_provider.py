"""Official TeraBox Open Platform storage provider.

Strictly integrates via official developer REST APIs, OAuth2 tokens, and webhook notifications.
Does NOT use credential scraping, browser automation, or unofficial bypasses.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import aiohttp
from app.config import Settings, get_settings
from app.logger import logger
from app.storage.base import StorageFileInfo, StorageProvider


class TeraBoxProvider(StorageProvider):
    """Official API client for TeraBox Open Platform."""

    OPEN_API_BASE = "https://open.terabox.com/api"

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.access_token = self.settings.terabox_access_token
        self.app_id = self.settings.terabox_app_id
        self.root_folder = self.settings.terabox_root_folder or "/"

    @property
    def provider_name(self) -> str:
        return "terabox"

    def _headers(self) -> Dict[str, str]:
        """Generate official API authorization headers."""
        headers = {
            "User-Agent": "TeraBox-Official-Automation-Bot/1.0",
            "Accept": "application/json",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def validate_connection(self) -> bool:
        """Verify API token validity and connectivity against official endpoint."""
        if not self.access_token:
            logger.warning(
                "TeraBox access token is not configured. Set TERABOX_ACCESS_TOKEN in .env."
            )
            return False

        url = f"{self.OPEN_API_BASE}/user/info"
        try:
            async with aiohttp.ClientSession(headers=self._headers()) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("errno") == 0 or "user_id" in data:
                            logger.info("Successfully authenticated with TeraBox Open Platform.")
                            return True
                    logger.warning(f"TeraBox validation returned HTTP {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to connect to TeraBox Open API: {e}")
            return False

    async def list_new_files(
        self, since: Optional[datetime] = None
    ) -> List[StorageFileInfo]:
        """Fetch list of files from authorized TeraBox directory via official /file/list endpoint."""
        results: List[StorageFileInfo] = []
        if not self.access_token:
            logger.debug("Skipping TeraBox sync: No access token provided.")
            return results

        url = f"{self.OPEN_API_BASE}/file/list"
        params = {
            "dir": self.root_folder,
            "order": "time",
            "desc": "1",
        }

        retries = 3
        for attempt in range(retries):
            try:
                async with aiohttp.ClientSession(headers=self._headers()) as session:
                    async with session.get(
                        url, params=params, timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            file_list = data.get("list", [])

                            for item in file_list:
                                if item.get("isdir") == 1:
                                    continue

                                filename = item.get("server_filename", "")
                                file_id = str(item.get("fs_id", ""))
                                size = item.get("size", 0)
                                server_mtime = item.get("server_mtime", 0)
                                file_mtime = datetime.fromtimestamp(
                                    server_mtime, tz=timezone.utc
                                ) if server_mtime else None

                                if since and file_mtime and file_mtime <= since:
                                    continue

                                # Pre-existing share link or official share generation
                                share_url = item.get("share_url")
                                if not share_url:
                                    share_url = await self.get_share_url(file_id)

                                file_info = StorageFileInfo(
                                    file_id=file_id,
                                    filename=filename,
                                    size_bytes=size,
                                    share_url=share_url,
                                    created_at=file_mtime,
                                    content_hash=item.get("md5"),  # Official cloud hash
                                    extra_meta={
                                        "path": item.get("path"),
                                        "category": item.get("category"),
                                    },
                                )

                                if file_info.is_video:
                                    results.append(file_info)

                            return results
                        elif resp.status == 401:
                            logger.error(
                                "TeraBox API Token expired or unauthorized. Re-authentication required."
                            )
                            return results
                        else:
                            logger.warning(
                                f"TeraBox file/list HTTP {resp.status} (attempt {attempt + 1}/{retries})"
                            )

            except Exception as e:
                logger.warning(f"TeraBox file list attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)

        return results

    async def get_file_info(self, file_id: str) -> Optional[StorageFileInfo]:
        """Fetch metadata for a single file using /file/detail endpoint."""
        if not self.access_token:
            return None

        url = f"{self.OPEN_API_BASE}/file/detail"
        params = {"fs_id": file_id}

        try:
            async with aiohttp.ClientSession(headers=self._headers()) as session:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        item = data.get("detail", {})
                        if not item:
                            return None

                        server_mtime = item.get("server_mtime", 0)
                        file_mtime = datetime.fromtimestamp(
                            server_mtime, tz=timezone.utc
                        ) if server_mtime else None

                        return StorageFileInfo(
                            file_id=file_id,
                            filename=item.get("server_filename", ""),
                            size_bytes=item.get("size", 0),
                            share_url=await self.get_share_url(file_id),
                            created_at=file_mtime,
                            content_hash=item.get("md5"),
                            extra_meta={"path": item.get("path")},
                        )
        except Exception as e:
            logger.error(f"Failed to get TeraBox file detail for {file_id}: {e}")

        return None

    async def get_share_url(self, file_id: str) -> str:
        """Call official TeraBox share API to create an authorized share link."""
        if not self.access_token:
            return f"https://terabox.com/s/file_{file_id}"

        url = f"{self.OPEN_API_BASE}/share/create"
        payload = {
            "fs_id": file_id,
            "period": 0,  # Permanent share link
        }

        try:
            async with aiohttp.ClientSession(headers=self._headers()) as session:
                async with session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        link = data.get("link") or data.get("shorturl")
                        if link:
                            return link
        except Exception as e:
            logger.warning(f"Could not generate dynamic share link for {file_id}: {e}")

        return f"https://terabox.com/s/file_{file_id}"

    async def compute_content_hash(self, file_id: str) -> Optional[str]:
        """Retrieve the cloud-side content hash (MD5 or SHA256) provided by the official API."""
        info = await self.get_file_info(file_id)
        if info:
            return info.content_hash
        return None
