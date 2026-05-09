import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from app.config import get_settings
from app.llm import ai_client
from app.search import vector_store

logger = logging.getLogger(__name__)
settings = get_settings()

_executor = ThreadPoolExecutor(max_workers=2)

_status = {
    "state": "idle",   # idle | running | done | error
    "total": 0,
    "indexed": 0,
    "last_run": None,
    "error": None,
}

BATCH_SIZE = 100


def get_status() -> dict:
    return dict(_status)


def _build_index_text(item) -> str:
    genres = ", ".join(g.tag for g in getattr(item, "genres", [])[:5])
    actors = ", ".join(r.tag for r in getattr(item, "roles", [])[:5])
    directors = ", ".join(d.tag for d in getattr(item, "directors", [])[:3])
    year = getattr(item, "year", "") or ""
    summary = (getattr(item, "summary", "") or "")[:300]
    media_type = "Movie" if item.type == "movie" else "TV Show"
    content_rating = getattr(item, "contentRating", "") or ""
    rated = f" Rated: {content_rating}." if content_rating else ""
    return (
        f"{item.title} ({year}). {media_type}. "
        f"Genres: {genres}.{rated} {summary} "
        f"Starring: {actors}. Directed by: {directors}."
    ).strip()


def _get_all_plex_items(token: str) -> tuple[list, str]:
    from plexapi.server import PlexServer
    server = PlexServer(settings.plex_server_url, token)
    items = []
    for section in server.library.sections():
        if section.type in ("movie", "show"):
            items.extend(section.all())
    return items, server.machineIdentifier


async def run_indexing(token: str) -> None:
    global _status
    _status.update({"state": "running", "total": 0, "indexed": 0, "error": None})

    try:
        loop = asyncio.get_event_loop()
        items, machine_id = await loop.run_in_executor(_executor, _get_all_plex_items, token)

        existing_ids = vector_store.get_indexed_ids()
        to_index = [i for i in items if str(i.ratingKey) not in existing_ids]

        _status["total"] = len(items)
        logger.info("Indexing %d new items (%d already indexed)", len(to_index), len(existing_ids))

        for batch_start in range(0, len(to_index), BATCH_SIZE):
            batch = to_index[batch_start: batch_start + BATCH_SIZE]
            texts = [_build_index_text(item) for item in batch]
            metas = []
            embeddings = await ai_client.embed_batch(texts)

            for item, text, vec in zip(batch, texts, embeddings):
                metas.append({
                    "plex_key": str(item.ratingKey),
                    "machine_id": machine_id,
                    "title": item.title,
                    "year": getattr(item, "year", None) or 0,
                    "media_type": item.type,
                    "genres": ", ".join(g.tag for g in getattr(item, "genres", [])[:5]),
                    "content_rating": getattr(item, "contentRating", "") or "",
                    "rating": float(getattr(item, "audienceRating", None) or 0),
                    "thumb": getattr(item, "thumb", "") or "",
                    "summary": (getattr(item, "summary", "") or "")[:500],
                    "text": text,
                })

            vector_store.upsert(metas, embeddings)
            _status["indexed"] += len(batch)
            logger.info("Indexed %d/%d", _status["indexed"], len(to_index))

        import datetime
        _status.update({"state": "done", "last_run": datetime.datetime.utcnow().isoformat()})
        logger.info("Indexing complete. Total in store: %d", vector_store.collection_count())

    except Exception as e:
        logger.error("Indexing failed: %s", e)
        _status.update({"state": "error", "error": str(e)})


# Bootstrap token for initial indexing — stored after first successful auth
_bootstrap_token: str | None = None


def set_bootstrap_token(token: str) -> None:
    global _bootstrap_token
    _bootstrap_token = token


async def start_indexing_task() -> None:
    """Called from lifespan. Waits for Ollama then indexes if token available."""
    # Wait up to 10 min for Ollama to be ready (model pull in progress)
    for attempt in range(60):
        if await ai_client.is_ready():
            break
        await asyncio.sleep(10)
    else:
        logger.warning("AI backend not ready after 10 min; skipping auto-index")
        return

    if _bootstrap_token:
        await run_indexing(_bootstrap_token)
    else:
        logger.info("No Plex token yet; indexing will run after first login")
