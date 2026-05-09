import logging
from typing import Any

import chromadb

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_collection = None
_client = None


def get_collection() -> chromadb.Collection:
    global _collection, _client
    if _collection is None:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        _collection = _client.get_or_create_collection(
            "plex_media",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB collection loaded: %d items", _collection.count())
    return _collection


def upsert(items: list[dict], embeddings: list[list[float]]) -> None:
    col = get_collection()
    col.upsert(
        ids=[str(item["plex_key"]) for item in items],
        embeddings=embeddings,
        documents=[item["text"] for item in items],
        metadatas=[{k: v for k, v in item.items() if k != "text"} for item in items],
    )


def clear_collection() -> None:
    """Wipe all vectors — call before reindex when schema changes."""
    global _collection, _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    try:
        _client.delete_collection("plex_media")
    except Exception:
        pass
    _collection = _client.get_or_create_collection(
        "plex_media",
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("ChromaDB collection cleared.")


def query_with_filters(
    embedding: list[float],
    media_type: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    min_rating: float | None = None,
    genres: list[str] | None = None,
    actors: list[str] | None = None,
    directors: list[str] | None = None,
    content_rating: str | None = None,
    composers: list[str] | None = None,
    n_results: int = 50,
    score_threshold: float = 0.50,
) -> list[dict]:
    col = get_collection()
    count = col.count()
    if count == 0:
        return []

    # Metadata where clause (exact / range filters)
    conditions: list[dict[str, Any]] = []
    if media_type:
        conditions.append({"media_type": {"$eq": media_type}})
    if year_from:
        conditions.append({"year": {"$gte": year_from}})
    if year_to:
        conditions.append({"year": {"$lte": year_to}})
    if min_rating:
        conditions.append({"rating": {"$gte": min_rating}})

    where: dict | None = None
    if len(conditions) == 1:
        where = conditions[0]
    elif len(conditions) > 1:
        where = {"$and": conditions}

    # Document where clause (text containment — uses indexed document text)
    doc_conditions: list[dict] = []
    if content_rating:
        doc_conditions.append({"$contains": f"Rated: {content_rating}"})
    if genres:
        for genre in genres[:2]:
            doc_conditions.append({"$contains": f"Genres: {genre}"})
    if actors:
        for actor in actors[:2]:
            doc_conditions.append({"$contains": actor})
    if directors:
        for director in directors[:1]:
            doc_conditions.append({"$contains": director})
    if composers:
        for composer in composers[:2]:
            doc_conditions.append({"$contains": composer})

    where_document: dict | None = None
    if len(doc_conditions) == 1:
        where_document = doc_conditions[0]
    elif len(doc_conditions) > 1:
        where_document = {"$and": doc_conditions}

    try:
        results = col.query(
            query_embeddings=[embedding],
            where=where,
            where_document=where_document,
            n_results=min(n_results, count),
            include=["metadatas", "distances"],
        )
    except Exception as e:
        logger.warning("ChromaDB query failed, falling back to unfiltered: %s", e)
        results = col.query(
            query_embeddings=[embedding],
            n_results=min(n_results, count),
            include=["metadatas", "distances"],
        )

    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    out = []
    for meta, dist in zip(metadatas, distances):
        score = float(1.0 - dist)
        if score >= score_threshold:
            meta["_vector_score"] = score
            out.append(meta)
    return out


def query_similar(embedding: list[float], n_results: int = 50) -> list[dict]:
    return query_with_filters(embedding, n_results=n_results)


def get_indexed_ids() -> set[str]:
    col = get_collection()
    if col.count() == 0:
        return set()
    result = col.get(include=[])
    return set(result["ids"])


def collection_count() -> int:
    return get_collection().count()
