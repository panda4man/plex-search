def merge_results(plex_results: list[dict], vector_results: list[dict],
                  limit: int) -> list[dict]:
    """Hybrid merge: intersection first (scored), then union, dedup by plex_key."""
    plex_keys = {r["plex_key"]: r for r in plex_results}
    vector_keys = {r["plex_key"]: r for r in vector_results}
    merged: dict[str, dict] = {}

    for key in set(plex_keys) & set(vector_keys):
        item = dict(plex_keys[key])
        vec_score = vector_keys[key].get("_vector_score", 0.5)
        plex_rating = float(item.get("rating") or 0) / 10.0
        item["_score"] = 0.6 * vec_score + 0.4 * plex_rating
        merged[key] = item

    for key in set(plex_keys) - set(vector_keys):
        item = dict(plex_keys[key])
        item["_score"] = 0.4 * (float(item.get("rating") or 0) / 10.0)
        merged[key] = item

    for key in set(vector_keys) - set(plex_keys):
        item = dict(vector_keys[key])
        item["_score"] = 0.6 * item.get("_vector_score", 0.5)
        merged[key] = item

    sorted_results = sorted(merged.values(), key=lambda x: x["_score"], reverse=True)
    for r in sorted_results:
        r.pop("_score", None)
        r.pop("_vector_score", None)
    return sorted_results[:limit]
