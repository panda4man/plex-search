import logging

import chromadb

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_collection: chromadb.Collection | None = None


def get_collection() -> chromadb.Collection:
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        _collection = client.get_or_create_collection(
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


def query_similar(embedding: list[float], n_results: int = 50) -> list[dict]:
    col = get_collection()
    count = col.count()
    if count == 0:
        return []
    results = col.query(
        query_embeddings=[embedding],
        n_results=min(n_results, count),
        include=["metadatas", "distances"],
    )
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    # Attach similarity score (cosine distance → similarity: 1 - distance)
    for meta, dist in zip(metadatas, distances):
        meta["_vector_score"] = float(1.0 - dist)
    return metadatas


def get_indexed_ids() -> set[str]:
    col = get_collection()
    if col.count() == 0:
        return set()
    result = col.get(include=[])
    return set(result["ids"])


def collection_count() -> int:
    return get_collection().count()
