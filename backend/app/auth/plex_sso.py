from urllib.parse import urlencode

import httpx

from app.config import get_settings

settings = get_settings()

PLEX_API_BASE = "https://plex.tv/api/v2"

_HEADERS = {
    "X-Plex-Client-Identifier": settings.plex_client_id,
    "X-Plex-Product": settings.plex_app_name,
    "X-Plex-Version": "1.0.0",
    "Accept": "application/json",
}


async def create_pin(client: httpx.AsyncClient) -> dict:
    """Returns {id, code, expires_in}."""
    r = await client.post(f"{PLEX_API_BASE}/pins", headers=_HEADERS,
                          params={"strong": "true"})
    r.raise_for_status()
    return r.json()


def build_auth_url(code: str, pin_id: int) -> str:
    forward_url = f"{settings.frontend_url}/auth/callback?pinId={pin_id}"
    params = {
        "clientID": settings.plex_client_id,
        "code": code,
        "context[device][product]": settings.plex_app_name,
        "forwardUrl": forward_url,
    }
    return "https://app.plex.tv/auth#?" + urlencode(params)


async def poll_pin(client: httpx.AsyncClient, pin_id: int,
                   retries: int = 10, delay: float = 2.0) -> str | None:
    """Polls plex.tv until authToken is available or retries exhausted."""
    import asyncio
    for _ in range(retries):
        r = await client.get(f"{PLEX_API_BASE}/pins/{pin_id}", headers=_HEADERS)
        r.raise_for_status()
        data = r.json()
        if data.get("authToken"):
            return data["authToken"]
        await asyncio.sleep(delay)
    return None


async def get_plex_username(client: httpx.AsyncClient, token: str) -> str:
    headers = {**_HEADERS, "X-Plex-Token": token}
    r = await client.get(f"{PLEX_API_BASE}/user", headers=headers)
    r.raise_for_status()
    data = r.json()
    return data.get("username") or data.get("title") or "Unknown"
