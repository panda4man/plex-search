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
  "sort_by": "rating" | "year" | "title" | "added" | null
}

Rules:
- media_type: "movie" for films, "show" for TV series, null if ambiguous
- For decades: "90s" or "1990s" means year_from=1990, year_to=1999
- min_rating: scale 0-10 (e.g. "highly rated"=7.5, "great"=8.0, "masterpiece"=9.0)
- genres: use standard names: Action, Comedy, Drama, Horror, Thriller, Sci-Fi,
  Fantasy, Romance, Documentary, Animation, Crime, Mystery, Adventure, Family
- If the query mentions an actor or director by name, include in actors/directors
- sort_by: "rating" if user wants best/top; "year" if newest/oldest; null otherwise
- Return ONLY the JSON object. No explanation, no markdown, no code blocks.
""".strip()

_FENCE_RE = re.compile(r"```(?:json)?(.*?)```", re.DOTALL)


class SearchFilters(BaseModel):
    media_type: Literal["movie", "show"] | None = None
    genres: list[str] | None = None
    year_from: int | None = None
    year_to: int | None = None
    min_rating: float | None = None
    actors: list[str] | None = None
    directors: list[str] | None = None
    title_keywords: list[str] | None = None
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
        return SearchFilters.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning("Failed to parse LLM output (returning empty filters): %s | raw=%r", e, raw)
        return SearchFilters()
