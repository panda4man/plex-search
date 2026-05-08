from app.search.merge import merge_results as _merge_results


def _p(key, rating=None):
    return {"plex_key": key, "title": f"Title {key}", "rating": rating}


def _v(key, score=0.8):
    return {"plex_key": key, "title": f"Title {key}", "_vector_score": score}


# ── Basic inclusion ──────────────────────────────────────────────────────────

def test_merge_intersection_item_included():
    results = _merge_results([_p("1", rating=8.0)], [_v("1", score=0.9)], limit=10)
    assert len(results) == 1
    assert results[0]["plex_key"] == "1"


def test_merge_plex_only_included():
    results = _merge_results([_p("1")], [], limit=10)
    assert len(results) == 1


def test_merge_vector_only_included():
    results = _merge_results([], [_v("1")], limit=10)
    assert len(results) == 1


def test_merge_both_empty_returns_empty():
    assert _merge_results([], [], limit=10) == []


# ── Deduplication ────────────────────────────────────────────────────────────

def test_merge_no_duplicate_keys():
    plex = [_p("1"), _p("2")]
    vec = [_v("1"), _v("3")]
    results = _merge_results(plex, vec, limit=10)
    keys = [r["plex_key"] for r in results]
    assert len(keys) == len(set(keys))


def test_merge_correct_total_count():
    plex = [_p("1"), _p("2")]
    vec = [_v("1"), _v("3")]
    results = _merge_results(plex, vec, limit=10)
    assert len(results) == 3  # "1", "2", "3"


# ── Limit ────────────────────────────────────────────────────────────────────

def test_merge_limit_respected():
    plex = [_p(str(i)) for i in range(10)]
    vec = [_v(str(i), score=0.9) for i in range(10)]
    assert len(_merge_results(plex, vec, limit=5)) == 5


def test_merge_limit_larger_than_results():
    results = _merge_results([_p("1")], [_v("2")], limit=100)
    assert len(results) == 2


# ── Scoring ──────────────────────────────────────────────────────────────────

def test_merge_intersection_ranks_above_plex_only():
    # "both" in intersection, "plex_only" only in Plex with equal rating
    plex = [_p("both", rating=8.0), _p("plex_only", rating=8.0)]
    vec = [_v("both", score=1.0)]
    results = _merge_results(plex, vec, limit=10)
    assert results[0]["plex_key"] == "both"


def test_merge_high_vector_score_ranks_above_low():
    vec = [_v("low", score=0.1), _v("high", score=0.99)]
    results = _merge_results([], vec, limit=10)
    assert results[0]["plex_key"] == "high"


# ── Internal field cleanup ───────────────────────────────────────────────────

def test_merge_strips_score_field():
    results = _merge_results([_p("1", rating=8.0)], [_v("1", score=0.9)], limit=10)
    assert "_score" not in results[0]


def test_merge_strips_vector_score_field():
    results = _merge_results([], [_v("1", score=0.9)], limit=10)
    assert "_vector_score" not in results[0]


def test_merge_preserves_original_fields():
    plex = [{"plex_key": "1", "title": "Matrix", "rating": 8.7, "year": 1999}]
    results = _merge_results(plex, [], limit=10)
    assert results[0]["title"] == "Matrix"
    assert results[0]["year"] == 1999
    assert results[0]["rating"] == 8.7
