"""The Movie Database (TMDB) metadata provider client."""

from typing import Optional
import aiohttp
from app.config import Settings, get_settings
from app.logger import logger
from app.metadata.base import EnrichedMetadata, MetadataProvider


class TMDBMetadataProvider(MetadataProvider):
    """Fetches movie metadata and official high-resolution posters from TMDB API."""

    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w780"

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.api_key = self.settings.tmdb_api_key
        self.language = self.settings.metadata_language or "en-US"

    @property
    def name(self) -> str:
        return "tmdb"

    async def fetch_metadata(
        self, title: str, year: Optional[int] = None
    ) -> Optional[EnrichedMetadata]:
        """Search TMDB for movie by title and optional release year."""
        if not self.api_key:
            logger.debug("TMDB API key not configured, skipping TMDB lookup.")
            return None

        params = {
            "api_key": self.api_key,
            "query": title,
            "language": self.language,
            "include_adult": "false",
        }
        if year:
            params["year"] = str(year)

        search_url = f"{self.BASE_URL}/search/movie"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    search_url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"TMDB search returned HTTP {resp.status} for '{title}'")
                        return None

                    data = await resp.json()
                    results = data.get("results", [])
                    if not results:
                        # If searching with year failed, try once more without year
                        if year:
                            params.pop("year")
                            async with session.get(
                                search_url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                            ) as retry_resp:
                                if retry_resp.status == 200:
                                    retry_data = await retry_resp.json()
                                    results = retry_data.get("results", [])

                    if not results:
                        logger.info(f"No TMDB matches found for title '{title}' (year={year})")
                        return None

                    best_match = results[0]
                    movie_id = best_match.get("id")

                    # Fetch full details including genres
                    details_url = f"{self.BASE_URL}/movie/{movie_id}"
                    async with session.get(
                        details_url,
                        params={"api_key": self.api_key, "language": self.language},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as detail_resp:
                        if detail_resp.status == 200:
                            details = await detail_resp.json()
                        else:
                            details = best_match

                    # Extract genres
                    genres = [g["name"] for g in details.get("genres", [])]
                    genre_str = ", ".join(genres) if genres else "Cinema"

                    # Format rating
                    vote_avg = details.get("vote_average", 0)
                    rating_str = f"{vote_avg:.1f}/10" if vote_avg else "N/A"

                    # Poster URL
                    poster_path = details.get("poster_path")
                    poster_url = f"{self.IMAGE_BASE_URL}{poster_path}" if poster_path else None

                    # Year
                    release_date = details.get("release_date", "")
                    matched_year = int(release_date.split("-")[0]) if release_date and release_date[:4].isdigit() else year

                    return EnrichedMetadata(
                        title=details.get("title") or title,
                        year=matched_year,
                        genre=genre_str,
                        rating=rating_str,
                        quality="1080p Full HD",  # Will be merged with parser quality
                        description=details.get("overview") or "No description available.",
                        poster_url=poster_url,
                        tmdb_id=movie_id,
                        raw_details=details,
                    )

        except Exception as e:
            logger.error(f"Error querying TMDB for '{title}': {e}")
            return None
