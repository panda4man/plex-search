import asyncio
import logging
from typing import Any

from plexapi.server import PlexServer

from app.config import get_settings
from app.llm.query_parser import SearchFilters
from app.plex.client import get_executor

logger = logging.getLogger(__name__)
settings = get_settings()


def _build_plex_filters(filters: SearchFilters) -> dict[str, Any]:
    plex_filters: dict[str, Any] = {}
    if filters.year_from:
        plex_filters["year>>"] = filters.year_from
    if filters.year_to:
        plex_filters["year<<"] = filters.year_to
    if filters.min_rating:
        plex_filters["audienceRating>>"] = filters.min_rating
    return plex_filters


def _build_plex_kwargs(filters: SearchFilters) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if filters.genres:
        kwargs["genre"] = filters.genres[0]
    if filters.directors:
        kwargs["director"] = filters.directors[0]
    if filters.actors:
        kwargs["actor"] = filters.actors[0]
    # title_keywords only used for Plex title search when no other filters set
    # (avoids over-restricting genre queries like "zombie movies")
    if filters.title_keywords and not filters.genres and not filters.actors and not filters.directors:
        kwargs["title"] = " ".join(filters.title_keywords)
    return kwargs


_SORT_MAP = {
    "rating": "audienceRating:desc",
    "year": "year:desc",
    "title": "titleSort:asc",
    "added": "addedAt:desc",
}


def _serialize_item(item, server: PlexServer) -> dict:
    genres = [g.tag for g in getattr(item, "genres", [])]
    thumb = getattr(item, "thumb", None)
    thumb_url = f"{settings.plex_server_url}{thumb}" if thumb else None
    duration_ms = getattr(item, "duration", None)
    return {
        "plex_key": str(item.ratingKey),
        "title": item.title,
        "year": getattr(item, "year", None),
        "genres": genres,
        "summary": (getattr(item, "summary", "") or "")[:500],
        "rating": getattr(item, "audienceRating", None),
        "duration_minutes": (duration_ms // 60000) if duration_ms else None,
        "thumb_url": thumb_url,
        "media_type": item.type,
        "machine_id": server.machineIdentifier,
        "plex_web_url": (
            f"{settings.plex_server_url}/web/index.html#!/server/"
            f"{server.machineIdentifier}/details?key=/library/metadata/{item.ratingKey}"
        ),
        "plex_app_url": (
            f"plex://preplay/?metadataKey=/library/metadata/{item.ratingKey}"
            f"&server={server.machineIdentifier}"
        ),
        "seasons": len(item.seasons()) if item.type == "show" else None,
        "studio": getattr(item, "studio", None) if item.type == "movie" else None,
    }


def _execute_search(server: PlexServer, filters: SearchFilters,
                    limit: int) -> list[dict]:
    plex_filters = _build_plex_filters(filters)
    plex_kwargs = _build_plex_kwargs(filters)
    sort = _SORT_MAP.get(filters.sort_by or "", "titleSort:asc")

    results: list = []
    sections = server.library.sections()

    for section in sections:
        if filters.media_type and section.type != filters.media_type:
            continue
        if section.type not in ("movie", "show"):
            continue
        try:
            items = section.search(
                filters=plex_filters if plex_filters else None,
                sort=sort,
                maxresults=limit,
                **plex_kwargs,
            )
            results.extend(items)
        except Exception as e:
            logger.warning("Plex section search failed for %s: %s", section.title, e)

    return [_serialize_item(item, server) for item in results[:limit]]


async def search_plex(server: PlexServer, filters: SearchFilters,
                      limit: int = 50) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        get_executor(),
        _execute_search,
        server, filters, limit,
    )


def _get_recently_added(server: PlexServer, limit: int) -> list[dict]:
    results = []
    for section in server.library.sections():
        if section.type in ("movie", "show"):
            results.extend(section.recentlyAdded(maxresults=limit))
    results.sort(key=lambda x: getattr(x, "addedAt", None) or 0, reverse=True)
    return [_serialize_item(item, server) for item in results[:limit]]


async def recently_added(server: PlexServer, limit: int = 20) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(get_executor(), _get_recently_added, server, limit)
