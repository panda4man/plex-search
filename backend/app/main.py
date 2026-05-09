import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.http_client import get_http_client, set_http_client  # noqa: F401 — re-exported
from app.llm import ai_client
from app.routers import auth, search

logger = logging.getLogger(__name__)
settings = get_settings()


async def _check_ai_ready() -> None:
    if await ai_client.is_ready():
        logger.info("AI backend is ready (provider: %s/%s).",
                    settings.llm_provider, settings.embed_provider)
    else:
        logger.warning("AI backend not ready at startup (will retry on first request).")


async def _warmup_models() -> None:
    """Load LLM and embed model into VRAM before first user request."""
    try:
        logger.info("Warming up embed model...")
        await ai_client.embed("warmup")
        logger.info("Embed model warm.")
    except Exception as e:
        logger.warning("Embed warmup failed (non-fatal): %s", e)

    try:
        logger.info("Warming up LLM...")
        await ai_client.chat("You are helpful.", "hi")
        logger.info("LLM warm.")
    except Exception as e:
        logger.warning("LLM warmup failed (non-fatal): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
    set_http_client(client)

    await _check_ai_ready()
    asyncio.create_task(_warmup_models())

    from app.search.indexer import start_indexing_task
    asyncio.create_task(start_indexing_task())

    yield

    await client.aclose()


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
