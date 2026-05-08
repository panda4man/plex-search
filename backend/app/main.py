import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.llm import ai_client
from app.routers import auth, search

logger = logging.getLogger(__name__)
settings = get_settings()

_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    return _http_client


async def _check_ai_ready() -> None:
    if await ai_client.is_ready():
        logger.info("AI backend is ready (provider: %s/%s).",
                    settings.llm_provider, settings.embed_provider)
    else:
        logger.warning("AI backend not ready at startup (will retry on first request).")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client
    _http_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))

    await _check_ai_ready()

    from app.search.indexer import start_indexing_task
    asyncio.create_task(start_indexing_task())

    yield

    await _http_client.aclose()


app = FastAPI(title="PlexSearch", lifespan=lifespan)

# Middleware order: add CORS first in code (LIFO → Session wraps outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.session_https_only,
    same_site="lax",
    max_age=86400 * 7,
)

app.include_router(auth.router, prefix="/api/auth")
app.include_router(search.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
