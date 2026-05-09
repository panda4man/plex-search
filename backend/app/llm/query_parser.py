import json
import logging
import re
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.llm import ai_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a movie and TV show search filter extractor. Extract search filters from
the user's natural language query and return ONLY a valid JSON object.

Output format:
{
  "media_type": "movie" | "show" | null,
  "genres": ["string"] | null,
  "year_from": integer | null,
  "year_to": integer | null,
  "min_rating": float | null,
  "actors": ["string"] | null,
  "directors": ["string"] | null,
  "title_keywords": ["string"] | null,
  "exclude_titles": ["string"] | null,
  "sort_by": "rating" | "year" | "title" | "added" | null
}

Rules:
- media_type: "movie" for films, "show" for TV series, null if ambiguous
  IMPORTANT: "show me", "show me some", "find me", "give me", "I want" are
  request phrases — NOT indicators of media_type. Only set media_type="show"
  when the user explicitly says "TV show", "series", "episodes", or a show name.
- Always extract genres when the query describes a type of content with a clear
  Plex genre match:
  "zombie movies" → genres=["Horror"]
  "alien movies" → genres=["Science Fiction"]
  "romantic films" → genres=["Romance"]
  "superhero movies" → genres=["Action"]
- Leave genres null when no standard Plex genre maps to the query theme:
  "christian content", "faith-based movies", "religious films", "inspiring movies",
  "feel-good films", "tearjerkers" → genres=null (let semantic search handle it)
- exclude_titles: only use for franchise/series exclusions explicitly stated by the
  user. Do NOT exclude well-known titles that are examples of the genre requested.
- For decades: "90s" or "1990s" means year_from=1990, year_to=1999
- min_rating: scale 0-10 (e.g. "highly rated"=7.5, "great"=8.0, "masterpiece"=9.0)
- genres: use EXACT Plex genre names — Science Fiction (NOT Sci-Fi), Action,
  Comedy, Drama, Horror, Thriller, Fantasy, Romance, Documentary, Animation,
  Crime, Mystery, Adventure, Family, Western, Music, Biography, History
- If the query mentions an actor or director by name, include in actors/directors
- sort_by: "rating" if user wants best/top; "year" if newest/oldest; null otherwise
- exclude_titles: keywords to exclude from results — use when user says "not X",
  "except X", "but not X franchise" (e.g. "alien movies not from alien franchise"
  → exclude_titles=["Alien", "Aliens", "Prometheus", "Covenant"])
- title_keywords: ONLY use when user is searching by a specific movie/show name
  (e.g. "show me the matrix" → title_keywords=["matrix"])
  Do NOT use for content descriptions like "zombie", "space", "romantic" — those are
  handled by genres or left for semantic search. Leave title_keywords null for
  queries like "zombie movies", "films about space", "scary movies".
- Return ONLY the JSON object. No explanation, no markdown, no code blocks.
""".strip()

_FENCE_RE = re.compile(r"```(?:json)?(.*?)```", re.DOTALL)

# Validated Plex genre names — anything outside this is silently dropped
_PLEX_GENRES = {
    "Action", "Adventure", "Animation", "Biography", "Comedy", "Crime",
    "Documentary", "Drama", "Family", "Fantasy", "History", "Horror",
    "Music", "Mystery", "Romance", "Science Fiction", "Thriller", "Western",
    "Sport", "Reality", "Anime",
}


class SearchFilters(BaseModel):
    media_type: Literal["movie", "show"] | None = None
    genres: list[str] | None = None
    year_from: int | None = None
    year_to: int | None = None
    min_rating: float | None = None
    actors: list[str] | None = None
    directors: list[str] | None = None
    title_keywords: list[str] | None = None
    exclude_titles: list[str] | None = None
    sort_by: Literal["rating", "year", "title", "added"] | None = None


async def parse_query(natural_query: str) -> SearchFilters:
    """Parse natural language query into structured search filters."""
    try:
        raw = await ai_client.chat(SYSTEM_PROMPT, natural_query)
    except Exception as e:
        logger.warning("LLM unavailable, returning empty filters: %s", e)
        return SearchFilters()

    # Strip markdown code fences if present
    match = _FENCE_RE.search(raw)
    if match:
        raw = match.group(1)

    try:
        data = json.loads(raw.strip())
        filters = SearchFilters.model_validate(data)
        # Drop any genres the LLM hallucinated that don't exist in Plex
        if filters.genres:
            valid = [g for g in filters.genres if g in _PLEX_GENRES]
            filters = filters.model_copy(update={"genres": valid or None})
        return filters
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning("Failed to parse LLM output (returning empty filters): %s | raw=%r", e, raw)
        return SearchFilters()
