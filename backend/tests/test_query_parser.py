from unittest.mock import AsyncMock, patch

import pytest

from app.llm.query_parser import SearchFilters, _FENCE_RE, parse_query


# ── Fence stripping ──────────────────────────────────────────────────────────

def test_fence_regex_matches_json_fenced():
    text = '```json\n{"media_type": "movie"}\n```'
    m = _FENCE_RE.search(text)
    assert m is not None
    assert '"media_type"' in m.group(1)


def test_fence_regex_matches_plain_fenced():
    text = '```\n{"media_type": "show"}\n```'
    assert _FENCE_RE.search(text) is not None


def test_fence_regex_no_match_on_bare_json():
    assert _FENCE_RE.search('{"media_type": "movie"}') is None


# ── SearchFilters model ──────────────────────────────────────────────────────

def test_search_filters_all_defaults_none():
    f = SearchFilters()
    assert f.media_type is None
    assert f.genres is None
    assert f.year_from is None
    assert f.year_to is None
    assert f.min_rating is None
    assert f.actors is None
    assert f.directors is None
    assert f.title_keywords is None
    assert f.sort_by is None


def test_search_filters_valid_construction():
    f = SearchFilters(
        media_type="movie",
        genres=["Action", "Sci-Fi"],
        year_from=1990,
        year_to=1999,
        min_rating=7.5,
        sort_by="rating",
    )
    assert f.media_type == "movie"
    assert f.genres == ["Action", "Sci-Fi"]
    assert f.year_from == 1990
    assert f.year_to == 1999
    assert f.min_rating == 7.5
    assert f.sort_by == "rating"


def test_search_filters_equality():
    assert SearchFilters() == SearchFilters()
    assert SearchFilters(media_type="movie") != SearchFilters(media_type="show")


# ── parse_query ──────────────────────────────────────────────────────────────

async def test_parse_query_returns_structured_filters():
    payload = '{"media_type": "movie", "genres": ["Action"], "year_from": 1990, "year_to": 1999}'
    with patch("app.llm.query_parser.ai_client.chat", new=AsyncMock(return_value=payload)):
        result = await parse_query("action movies from the 90s")
    assert result.media_type == "movie"
    assert result.genres == ["Action"]
    assert result.year_from == 1990
    assert result.year_to == 1999


async def test_parse_query_strips_json_fences():
    payload = '```json\n{"media_type": "show", "genres": ["Drama"]}\n```'
    with patch("app.llm.query_parser.ai_client.chat", new=AsyncMock(return_value=payload)):
        result = await parse_query("drama shows")
    assert result.media_type == "show"
    assert result.genres == ["Drama"]


async def test_parse_query_strips_plain_fences():
    payload = '```\n{"min_rating": 8.0}\n```'
    with patch("app.llm.query_parser.ai_client.chat", new=AsyncMock(return_value=payload)):
        result = await parse_query("highly rated movies")
    assert result.min_rating == 8.0


async def test_parse_query_invalid_json_returns_empty_filters():
    with patch("app.llm.query_parser.ai_client.chat", new=AsyncMock(return_value="not json at all")):
        result = await parse_query("something")
    assert result == SearchFilters()


async def test_parse_query_invalid_literal_returns_empty_filters():
    # "film" is not a valid Literal["movie", "show"]
    payload = '{"media_type": "film"}'
    with patch("app.llm.query_parser.ai_client.chat", new=AsyncMock(return_value=payload)):
        result = await parse_query("something")
    assert result == SearchFilters()


async def test_parse_query_invalid_sort_by_returns_empty_filters():
    payload = '{"sort_by": "popularity"}'  # not in Literal
    with patch("app.llm.query_parser.ai_client.chat", new=AsyncMock(return_value=payload)):
        result = await parse_query("popular movies")
    assert result == SearchFilters()


async def test_parse_query_ai_unavailable_returns_empty_filters():
    with patch("app.llm.query_parser.ai_client.chat",
               new=AsyncMock(side_effect=Exception("Connection refused"))):
        result = await parse_query("action movies")
    assert result == SearchFilters()


async def test_parse_query_null_fields_accepted():
    payload = '{"media_type": null, "genres": null, "year_from": null}'
    with patch("app.llm.query_parser.ai_client.chat", new=AsyncMock(return_value=payload)):
        result = await parse_query("movies")
    assert result.media_type is None
    assert result.genres is None


async def test_parse_query_extra_fields_ignored():
    payload = '{"media_type": "movie", "unknown_field": "ignored"}'
    with patch("app.llm.query_parser.ai_client.chat", new=AsyncMock(return_value=payload)):
        result = await parse_query("movies")
    assert result.media_type == "movie"
    assert not hasattr(result, "unknown_field")
