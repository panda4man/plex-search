import asyncio
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"
_COMPOSER_JOBS = {"Original Music Composer", "Music", "Composer", "Music Director"}


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_settings().tmdb_read_access_token}",
        "Accept": "application/json",
    }


def get_tmdb_id(item) -> tuple[str, str] | None:
    """Extract (tmdb_id, media_type) from Plex item GUIDs. Returns None if not found."""
    for guid in getattr(item, "guids", []):
        gid = guid.id if hasattr(guid, "id") else str(guid)
        if gid.startswith("tmdb://"):
            return gid.replace("tmdb://", ""), ("movie" if item.type == "movie" else "tv")
    return None


async def fetch_composers(
    client: httpx.AsyncClient,
    tmdb_id: str,
    media_type: str,
    semaphore: asyncio.Semaphore,
) -> list[str]:
    """Fetch Original Music Composers from TMDB credits."""
    async with semaphore:
        try:
            r = await client.get(
                f"{TMDB_BASE}/{media_type}/{tmdb_id}/credits",
                headers=_headers(),
                timeout=10.0,
            )
            r.raise_for_status()
            crew = r.json().get("crew", [])
            return [
                c["name"] for c in crew
                if c.get("job") in _COMPOSER_JOBS
                or (c.get("department") == "Sound" and "Composer" in c.get("job", ""))
            ]
        except Exception as e:
            logger.debug("TMDB fetch failed for %s/%s: %s", media_type, tmdb_id, e)
            return []


async def fetch_composers_batch(items: list) -> dict[str, list[str]]:
    """Fetch composers for a batch of Plex items. Returns {plex_key: [composer_names]}."""
    token = get_settings().tmdb_read_access_token
    if not token:
        return {}

    semaphore = asyncio.Semaphore(10)
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = {}
        for item in items:
            result = get_tmdb_id(item)
            if result:
                tmdb_id, media_type = result
                tasks[str(item.ratingKey)] = asyncio.create_task(
                    fetch_composers(client, tmdb_id, media_type, semaphore)
                )

        if not tasks:
            return {}

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return {
            key: (val if isinstance(val, list) else [])
            for key, val in zip(tasks.keys(), results)
        }
