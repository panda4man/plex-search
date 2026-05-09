import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.auth.session import require_auth
from app.llm import ai_client, query_parser
from app.plex import client as plex_client
from app.plex import search as plex_search
from app.search import indexer, vector_store
from app.search.merge import merge_results

logger = logging.getLogger(__name__)
router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    limit: int = 50
    offset: int = 0




@router.post("/search")
async def search(body: SearchRequest, session: Annotated[dict, Depends(require_auth)]):
    token = session["plex_token"]
    server = await plex_client.get_server(token)
    filters = await query_parser.parse_query(body.query)

    # Only use Plex results when a meaningful filter was extracted —
    # unfiltered Plex returns hundreds of high-rated movies that pollute
    # thematic/semantic queries ("christian content", "inspiring movies", etc.)
    has_plex_filter = any([
        filters.genres, filters.year_from, filters.year_to,
        filters.min_rating, filters.actors, filters.directors,
        filters.media_type,
    ])

    if has_plex_filter:
        plex_results = await plex_search.search_plex(server, filters, limit=200)
        plex_results = [r for r in plex_results if r.get("genres")]
    else:
        plex_results = []

    # Vector search
    try:
        embedding = await ai_client.embed(body.query)
        vector_results = vector_store.query_similar(embedding, n_results=50)
    except Exception as e:
        logger.warning("Vector search unavailable: %s", e)
        vector_results = []

    # Post-filter both result sets
    # Filter untagged items from vector results too
    vector_results = [r for r in vector_results if r.get("genres")]
    if filters.media_type:
        vector_results = [r for r in vector_results if r.get("media_type") == filters.media_type]
    if filters.exclude_titles:
        excl = [t.lower() for t in filters.exclude_titles]
        def not_excluded(r: dict) -> bool:
            title = r.get("title", "").lower()
            return not any(e in title for e in excl)
        plex_results = [r for r in plex_results if not_excluded(r)]
        vector_results = [r for r in vector_results if not_excluded(r)]

    results = merge_results(plex_results, vector_results, limit=body.limit)

    # Ensure all results have plex_web_url (vector-only results won't have it)
    from app.config import get_settings as _gs
    _s = _gs()
    for r in results:
        if not r.get("plex_web_url"):
            r["plex_web_url"] = (
                f"{_s.plex_server_url}/web/index.html#!/server/"
                f"{r.get('machine_id','')}/details?key=/library/metadata/{r['plex_key']}"
            )
        if not r.get("plex_app_url"):
            r["plex_app_url"] = (
                f"plex://preplay/?metadataKey=/library/metadata/{r['plex_key']}"
                f"&server={r.get('machine_id','')}"
            )

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
    """Proxy thumbnail from Plex to avoid exposing token in frontend."""
    token = session["plex_token"]
    from app.config import get_settings
    settings = get_settings()
    url = f"{settings.plex_server_url}/library/metadata/{plex_key}/thumb"
    from app.http_client import get_http_client
    client = get_http_client()
    try:
        r = await client.get(url, params={"X-Plex-Token": token}, timeout=10.0)
        return Response(content=r.content, media_type=r.headers.get("content-type", "image/jpeg"))
    except Exception:
        return Response(status_code=404)


@router.post("/debug/search")
async def debug_search(body: SearchRequest, session: Annotated[dict, Depends(require_auth)]):
    """Returns parsed filters, top plex results, top vector results, and final merged — for tuning."""
    token = session["plex_token"]
    server = await plex_client.get_server(token)
    filters = await query_parser.parse_query(body.query)

    has_plex_filter = any([
        filters.genres, filters.year_from, filters.year_to,
        filters.min_rating, filters.actors, filters.directors,
        filters.media_type,
    ])
    if has_plex_filter:
        plex_results = await plex_search.search_plex(server, filters, limit=200)
        plex_results = [r for r in plex_results if r.get("genres")]
    else:
        plex_results = []

    try:
        embedding = await ai_client.embed(body.query)
        vector_results = vector_store.query_similar(embedding, n_results=50)
    except Exception as e:
        vector_results = []

    vector_results = [r for r in vector_results if r.get("genres")]
    if filters.media_type:
        vector_results = [r for r in vector_results if r.get("media_type") == filters.media_type]
    if filters.exclude_titles:
        excl = [t.lower() for t in filters.exclude_titles]
        plex_results = [r for r in plex_results if not any(e in r.get("title","").lower() for e in excl)]
        vector_results = [r for r in vector_results if not any(e in r.get("title","").lower() for e in excl)]

    merged = merge_results(plex_results, vector_results, limit=body.limit)

    return {
        "query": body.query,
        "llm_filters": filters.model_dump(exclude_none=True),
        "plex_result_count": len(plex_results),
        "plex_top5": [{"title": r["title"], "year": r.get("year"), "genres": r.get("genres")} for r in plex_results[:5]],
        "vector_top5": [{"title": r["title"], "year": r.get("year"), "score": round(r.get("_vector_score", 0), 3)} for r in vector_results[:5]],
        "merged_top10": [{"title": r["title"], "year": r.get("year"), "genres": r.get("genres")} for r in merged[:10]],
    }


@router.get("/admin/index-status")
async def index_status(session: Annotated[dict, Depends(require_auth)]):
    return indexer.get_status()


@router.post("/admin/reindex")
async def reindex(session: Annotated[dict, Depends(require_auth)]):
    import asyncio
    token = session["plex_token"]
    if indexer.get_status()["state"] == "running":
        return {"message": "Indexing already in progress"}
    asyncio.create_task(indexer.run_indexing(token))
    return {"message": "Indexing started"}
