import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.auth.session import require_auth
from app.config import get_settings
from app.http_client import get_http_client
from app.llm import ai_client, query_parser
from app.plex import client as plex_client
from app.plex import search as plex_search
from app.search import indexer, vector_store

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


class SearchRequest(BaseModel):
    query: str
    limit: int = 50
    offset: int = 0


def _build_urls(results: list[dict]) -> None:
    """Add plex_web_url and plex_app_url to every result in-place."""
    for r in results:
        key = r["plex_key"]
        mid = r.get("machine_id", "")
        r["plex_web_url"] = (
            f"{settings.plex_server_url}/web/index.html#!/server/{mid}"
            f"/details?key=/library/metadata/{key}"
        )
        r["plex_app_url"] = (
            f"plex://preplay/?metadataKey=/library/metadata/{key}&server={mid}"
        )


def _post_filter(results: list[dict], filters) -> list[dict]:
    results = [r for r in results if r.get("genres")]
    if filters.exclude_titles:
        excl = [t.lower() for t in filters.exclude_titles]
        results = [r for r in results if not any(e in r.get("title", "").lower() for e in excl)]
    return results


def _rank(results: list[dict]) -> list[dict]:
    """Re-rank by combining vector similarity with stored Plex rating."""
    for r in results:
        vec = r.get("_vector_score", 0.5)
        rating = float(r.get("rating") or 0) / 10.0
        r["_score"] = 0.7 * vec + 0.3 * rating
    results.sort(key=lambda x: x["_score"], reverse=True)
    for r in results:
        r.pop("_score", None)
        r.pop("_vector_score", None)
    return results


@router.post("/search")
async def search(body: SearchRequest, session: Annotated[dict, Depends(require_auth)]):
    filters = await query_parser.parse_query(body.query)

    try:
        embedding = await ai_client.embed(body.query)
        # When filtering by actor/director, structural filter does the precision work
        # — drop similarity threshold so all matches are returned regardless of score
        has_person_filter = bool(filters.actors or filters.directors or filters.composers)
        results = vector_store.query_with_filters(
            embedding=embedding,
            media_type=filters.media_type,
            year_from=filters.year_from,
            year_to=filters.year_to,
            min_rating=filters.min_rating,
            genres=filters.genres,
            actors=filters.actors,
            directors=filters.directors,
            content_rating=filters.content_rating,
            composers=filters.composers,
            n_results=min(body.limit + 50, 200),
            score_threshold=0.0 if has_person_filter else 0.50,
        )
    except Exception as e:
        logger.warning("Vector search failed: %s", e)
        results = []

    results = _post_filter(results, filters)
    results = _rank(results)
    _build_urls(results)

    return {
        "results": results[body.offset: body.offset + body.limit],
        "total": len(results),
        "filters_used": filters.model_dump(exclude_none=True),
    }


@router.get("/search/recent")
async def recent(session: Annotated[dict, Depends(require_auth)],
                 limit: int = Query(default=20, le=50)):
    token = session["plex_token"]
    server = await plex_client.get_server(token)
    results = await plex_search.recently_added(server, limit=limit)
    return {"results": results, "total": len(results)}


@router.get("/media/thumb/{plex_key:path}")
async def thumb(plex_key: str, session: Annotated[dict, Depends(require_auth)]):
    token = session["plex_token"]
    url = f"{settings.plex_server_url}/library/metadata/{plex_key}/thumb"
    client = get_http_client()
    try:
        r = await client.get(url, params={"X-Plex-Token": token}, timeout=10.0)
        return Response(content=r.content, media_type=r.headers.get("content-type", "image/jpeg"))
    except Exception:
        return Response(status_code=404)


@router.post("/debug/search")
async def debug_search(body: SearchRequest, session: Annotated[dict, Depends(require_auth)]):
    filters = await query_parser.parse_query(body.query)

    try:
        embedding = await ai_client.embed(body.query)
        results = vector_store.query_with_filters(
            embedding=embedding,
            media_type=filters.media_type,
            year_from=filters.year_from,
            year_to=filters.year_to,
            min_rating=filters.min_rating,
            genres=filters.genres,
            actors=filters.actors,
            directors=filters.directors,
            content_rating=filters.content_rating,
            n_results=100,
        )
    except Exception as e:
        results = []

    results = _post_filter(results, filters)
    ranked = _rank(list(results))

    return {
        "query": body.query,
        "llm_filters": filters.model_dump(exclude_none=True),
        "chroma_result_count": len(results),
        "top5": [{"title": r["title"], "year": r.get("year"), "genres": r.get("genres"), "score": round(r.get("_vector_score", 0), 3)} for r in results[:5]],
        "merged_top10": [{"title": r["title"], "year": r.get("year"), "genres": r.get("genres")} for r in ranked[:10]],
    }


@router.get("/admin/index-status")
async def index_status(session: Annotated[dict, Depends(require_auth)]):
    return indexer.get_status()


@router.post("/admin/reindex")
async def reindex(session: Annotated[dict, Depends(require_auth)]):
    token = session["plex_token"]
    if indexer.get_status()["state"] == "running":
        return {"message": "Indexing already in progress"}
    asyncio.create_task(indexer.run_indexing(token))
    return {"message": "Indexing started"}


@router.post("/admin/clear-reindex")
async def clear_reindex(session: Annotated[dict, Depends(require_auth)]):
    """Wipe ChromaDB and reindex — required after schema changes."""
    token = session["plex_token"]
    if indexer.get_status()["state"] == "running":
        return {"message": "Indexing already in progress"}
    vector_store.clear_collection()
    asyncio.create_task(indexer.run_indexing(token))
    return {"message": "Collection cleared, reindexing started"}
