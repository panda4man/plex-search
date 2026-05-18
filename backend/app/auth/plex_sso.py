from urllib.parse import urlencode

import httpx

from app.config import get_settings

PLEX_API_BASE = "https://plex.tv/api/v2"


def _headers() -> dict:
    s = get_settings()
    return {
        "X-Plex-Client-Identifier": s.plex_client_id,
        "X-Plex-Product": s.plex_app_name,
        "X-Plex-Version": "1.0.0",
        "Accept": "application/json",
    }


async def create_pin(client: httpx.AsyncClient) -> dict:
    """Returns {id, code, expires_in}."""
    r = await client.post(f"{PLEX_API_BASE}/pins", headers=_headers(),
                          params={"strong": "true"})
    r.raise_for_status()
    return r.json()


def build_auth_url(code: str, pin_id: int) -> str:
    s = get_settings()
    forward_url = f"{s.frontend_url}/auth/callback?pinId={pin_id}"
    params = {
        "clientID": s.plex_client_id,
        "code": code,
        "context[device][product]": s.plex_app_name,
        "forwardUrl": forward_url,
    }
    return "https://app.plex.tv/auth#?" + urlencode(params)


async def poll_pin(client: httpx.AsyncClient, pin_id: int,
                   retries: int = 10, delay: float = 2.0) -> str | None:
    """Polls plex.tv until authToken is available or retries exhausted."""
    import asyncio
    for _ in range(retries):
        r = await client.get(f"{PLEX_API_BASE}/pins/{pin_id}", headers=_headers())
        r.raise_for_status()
        data = r.json()
        if data.get("authToken"):
            return data["authToken"]
        await asyncio.sleep(delay)
    return None


async def get_plex_username(client: httpx.AsyncClient, token: str) -> str:
    headers = {**_headers(), "X-Plex-Token": token}
    r = await client.get(f"{PLEX_API_BASE}/user", headers=headers)
    r.raise_for_status()
    data = r.json()
    return data.get("username") or data.get("title") or "Unknown"
