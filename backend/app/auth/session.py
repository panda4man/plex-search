from fastapi import HTTPException, Request


async def require_auth(request: Request) -> dict:
    """FastAPI dependency. Accepts session cookie OR Authorization: Bearer token."""
    # Bearer token for future Capacitor mobile support
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
        if token:
            return {"plex_token": token, "authenticated": True,
                    "plex_username": request.session.get("plex_username", "Unknown")}

    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return dict(request.session)
