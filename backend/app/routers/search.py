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

    plex_results = await plex_search.search_plex(server, filters, limit=200)

    # Vector search
    try:
        embedding = await ai_client.embed(body.query)
        vector_results = vector_store.query_similar(embedding, n_results=50)
    except Exception as e:
        logger.warning("Vector search unavailable: %s", e)
        vector_results = []

    results = merge_results(plex_results, vector_results, limit=body.limit)

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
    from app.main import get_http_client
    client = get_http_client()
    try:
        r = await client.get(url, params={"X-Plex-Token": token}, timeout=10.0)
        return Response(content=r.content, media_type=r.headers.get("content-type", "image/jpeg"))
    except Exception:
        return Response(status_code=404)


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
