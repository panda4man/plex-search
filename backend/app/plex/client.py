import asyncio
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor

from plexapi.server import PlexServer

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_executor = ThreadPoolExecutor(max_workers=4)
_server_cache: dict[str, PlexServer] = {}


def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _connect(token: str) -> PlexServer:
    return PlexServer(settings.plex_server_url, token)


async def get_server(token: str) -> PlexServer:
    key = _token_key(token)
    if key not in _server_cache:
        loop = asyncio.get_event_loop()
        server = await loop.run_in_executor(_executor, _connect, token)
        _server_cache[key] = server
        logger.debug("PlexServer connected for token %s", key)
    return _server_cache[key]


def get_executor() -> ThreadPoolExecutor:
    return _executor
