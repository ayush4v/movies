"""Open Movie Database (OMDB) metadata provider client."""

from typing import Optional
import aiohttp
from app.config import Settings, get_settings
from app.logger import logger
from app.metadata.base import EnrichedMetadata, MetadataProvider


class OMDBMetadataProvider(MetadataProvider):
    """OMDB metadata provider fallback."""

    BASE_URL = "https://www.omdbapi.com/"

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.api_key = self.settings.omdb_api_key

    @property
    def name(self) -> str:
        return "omdb"

    async def fetch_metadata(
        self, title: str, year: Optional[int] = None
    ) -> Optional[EnrichedMetadata]:
        """Fetch movie details using OMDB API."""
        if not self.api_key:
            return None

        params = {"apikey": self.api_key, "t": title, "plot": "full"}
        if year:
            params["y"] = str(year)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.BASE_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    if data.get("Response") != "True":
                        return None

                    poster = data.get("Poster")
                    poster_url = poster if poster and poster.startswith("http") else None

                    year_str = data.get("Year", "")
                    clean_year = int(year_str[:4]) if year_str and year_str[:4].isdigit() else year

                    return EnrichedMetadata(
                        title=data.get("Title") or title,
                        year=clean_year,
                        genre=data.get("Genre") or "Cinema",
                        rating=f"{data.get('imdbRating', 'N/A')}/10",
                        quality="HD",
                        description=data.get("Plot") or "No description available.",
                        poster_url=poster_url,
                        imdb_id=data.get("imdbID"),
                        raw_details=data,
                    )
        except Exception as e:
            logger.error(f"Error querying OMDB for '{title}': {e}")
            return None
