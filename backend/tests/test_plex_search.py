from unittest.mock import MagicMock

from app.llm.query_parser import SearchFilters
from app.plex.search import _build_plex_filters, _build_plex_kwargs, _serialize_item


# ── _build_plex_filters ──────────────────────────────────────────────────────

def test_filters_empty_on_no_constraints():
    assert _build_plex_filters(SearchFilters()) == {}


def test_filters_year_range():
    f = SearchFilters(year_from=1990, year_to=1999)
    result = _build_plex_filters(f)
    assert result["year>>"] == 1990
    assert result["year<<"] == 1999


def test_filters_year_from_only():
    result = _build_plex_filters(SearchFilters(year_from=2000))
    assert "year>>" in result
    assert "year<<" not in result


def test_filters_year_to_only():
    result = _build_plex_filters(SearchFilters(year_to=1985))
    assert "year<<" in result
    assert "year>>" not in result


def test_filters_min_rating():
    result = _build_plex_filters(SearchFilters(min_rating=7.5))
    assert result["audienceRating>>"] == 7.5


def test_filters_all_combined():
    f = SearchFilters(year_from=1990, year_to=1999, min_rating=8.0)
    result = _build_plex_filters(f)
    assert result["year>>"] == 1990
    assert result["year<<"] == 1999
    assert result["audienceRating>>"] == 8.0


# ── _build_plex_kwargs ───────────────────────────────────────────────────────

def test_kwargs_empty_on_no_constraints():
    assert _build_plex_kwargs(SearchFilters()) == {}


def test_kwargs_genre_uses_first_only():
    result = _build_plex_kwargs(SearchFilters(genres=["Action", "Comedy"]))
    assert result["genre"] == "Action"
    assert len([k for k in result if k == "genre"]) == 1


def test_kwargs_actor():
    result = _build_plex_kwargs(SearchFilters(actors=["Keanu Reeves"]))
    assert result["actor"] == "Keanu Reeves"


def test_kwargs_actor_uses_first_only():
    result = _build_plex_kwargs(SearchFilters(actors=["Actor A", "Actor B"]))
    assert result["actor"] == "Actor A"


def test_kwargs_director():
    result = _build_plex_kwargs(SearchFilters(directors=["Christopher Nolan"]))
    assert result["director"] == "Christopher Nolan"


def test_kwargs_title_keywords_joined():
    result = _build_plex_kwargs(SearchFilters(title_keywords=["dark", "knight"]))
    assert result["title"] == "dark knight"


def test_kwargs_title_single_keyword():
    result = _build_plex_kwargs(SearchFilters(title_keywords=["inception"]))
    assert result["title"] == "inception"


# ── _serialize_item ──────────────────────────────────────────────────────────

def _movie():
    item = MagicMock()
    item.ratingKey = 123
    item.title = "The Matrix"
    item.year = 1999
    item.type = "movie"
    item.genres = [MagicMock(tag="Action"), MagicMock(tag="Sci-Fi")]
    item.summary = "A computer hacker learns the truth."
    item.audienceRating = 8.7
    item.duration = 8160000  # 136 min in ms
    item.thumb = "/library/metadata/123/thumb"
    item.studio = "Warner Bros."
    return item


def _server():
    s = MagicMock()
    s.machineIdentifier = "machine-abc"
    return s


def test_serialize_movie_basic_fields():
    result = _serialize_item(_movie(), _server())
    assert result["plex_key"] == "123"
    assert result["title"] == "The Matrix"
    assert result["year"] == 1999
    assert result["media_type"] == "movie"
    assert result["machine_id"] == "machine-abc"


def test_serialize_movie_plex_key_is_string():
    item = _movie()
    item.ratingKey = 999
    assert isinstance(_serialize_item(item, _server())["plex_key"], str)


def test_serialize_movie_genres_list():
    result = _serialize_item(_movie(), _server())
    assert result["genres"] == ["Action", "Sci-Fi"]


def test_serialize_movie_rating():
    result = _serialize_item(_movie(), _server())
    assert result["rating"] == 8.7


def test_serialize_movie_duration_converted_to_minutes():
    result = _serialize_item(_movie(), _server())
    assert result["duration_minutes"] == 136


def test_serialize_movie_no_duration_is_none():
    item = _movie()
    item.duration = None
    assert _serialize_item(item, _server())["duration_minutes"] is None


def test_serialize_movie_thumb_url_constructed():
    result = _serialize_item(_movie(), _server())
    assert result["thumb_url"] == "http://plex-test:32400/library/metadata/123/thumb"


def test_serialize_movie_no_thumb_is_none():
    item = _movie()
    item.thumb = None
    assert _serialize_item(item, _server())["thumb_url"] is None


def test_serialize_movie_studio():
    assert _serialize_item(_movie(), _server())["studio"] == "Warner Bros."


def test_serialize_movie_seasons_is_none():
    assert _serialize_item(_movie(), _server())["seasons"] is None


def test_serialize_summary_truncated_at_500():
    item = _movie()
    item.summary = "x" * 600
    assert len(_serialize_item(item, _server())["summary"]) == 500


def test_serialize_show_seasons_count():
    item = MagicMock()
    item.ratingKey = 456
    item.title = "Breaking Bad"
    item.year = 2008
    item.type = "show"
    item.genres = [MagicMock(tag="Drama")]
    item.summary = "Chemistry teacher."
    item.audienceRating = 9.5
    item.duration = None
    item.thumb = "/thumb/456"
    item.seasons.return_value = [MagicMock()] * 5

    result = _serialize_item(item, _server())
    assert result["seasons"] == 5
    assert result["studio"] is None
    assert result["media_type"] == "show"
