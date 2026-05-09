import asyncio
import logging
from typing import TypedDict

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"
_COMPOSER_JOBS = {"Original Music Composer", "Music", "Composer", "Music Director"}


class TMDBEnrichment(TypedDict):
    composers: list[str]
    keywords: list[str]
    companies: list[str]
    collection: str | None


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


async def _fetch_enrichment(
    client: httpx.AsyncClient,
    tmdb_id: str,
    media_type: str,
    semaphore: asyncio.Semaphore,
) -> TMDBEnrichment:
    """
    Single TMDB call using append_to_response to get:
    - details (production_companies, belongs_to_collection)
    - keywords
    - credits (composers)
    """
    async with semaphore:
        try:
            r = await client.get(
                f"{TMDB_BASE}/{media_type}/{tmdb_id}",
                headers=_headers(),
                params={"append_to_response": "keywords,credits"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()

            # Composers from credits
            crew = data.get("credits", {}).get("crew", [])
            composers = [
                c["name"] for c in crew
                if c.get("job") in _COMPOSER_JOBS
                or (c.get("department") == "Sound" and "Composer" in c.get("job", ""))
            ]

            # Keywords (movies use 'keywords', TV uses 'results')
            kw_data = data.get("keywords", {})
            raw_kw = kw_data.get("keywords") or kw_data.get("results") or []
            keywords = [k["name"] for k in raw_kw[:20]]

            # Production companies
            companies = [c["name"] for c in data.get("production_companies", [])[:5]]

            # Collection / franchise
            col = data.get("belongs_to_collection")
            collection = col["name"] if col else None

            return TMDBEnrichment(
                composers=composers,
                keywords=keywords,
                companies=companies,
                collection=collection,
            )
        except Exception as e:
            logger.debug("TMDB enrichment failed for %s/%s: %s", media_type, tmdb_id, e)
            return TMDBEnrichment(composers=[], keywords=[], companies=[], collection=None)


async def fetch_enrichment_batch(items: list) -> dict[str, TMDBEnrichment]:
    """Fetch full TMDB enrichment for a batch of Plex items.
    Returns {plex_key: TMDBEnrichment}."""
    token = get_settings().tmdb_read_access_token
    if not token:
        return {}

    semaphore = asyncio.Semaphore(10)
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks: dict[str, asyncio.Task] = {}
        for item in items:
            result = get_tmdb_id(item)
            if result:
                tmdb_id, media_type = result
                tasks[str(item.ratingKey)] = asyncio.create_task(
                    _fetch_enrichment(client, tmdb_id, media_type, semaphore)
                )

        if not tasks:
            return {}

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return {
            key: (val if isinstance(val, dict) else TMDBEnrichment(composers=[], keywords=[], companies=[], collection=None))
            for key, val in zip(tasks.keys(), results)
        }


# Keep for backwards compat
async def fetch_composers_batch(items: list) -> dict[str, list[str]]:
    enrichment = await fetch_enrichment_batch(items)
    return {k: v["composers"] for k, v in enrichment.items()}
