import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.auth import plex_sso
from app.auth.session import require_auth
from app.main import get_http_client
from app.search import indexer

router = APIRouter()


@router.get("/plex/start")
async def plex_start(request: Request):
    client = get_http_client()
    pin = await plex_sso.create_pin(client)
    request.session["pending_pin_id"] = pin["id"]
    auth_url = plex_sso.build_auth_url(pin["code"], pin["id"])
    return {"auth_url": auth_url, "pin_id": pin["id"]}


@router.get("/plex/callback")
async def plex_callback(request: Request, pinId: int):
    client = get_http_client()

    # Validate pin_id matches what we set in session (CSRF guard)
    session_pin = request.session.get("pending_pin_id")
    if session_pin is None or int(session_pin) != pinId:
        raise HTTPException(status_code=400, detail="Invalid pin")

    token = await plex_sso.poll_pin(client, pinId)
    if not token:
        raise HTTPException(status_code=401, detail="Plex authorization not completed")

    username = await plex_sso.get_plex_username(client, token)

    request.session["authenticated"] = True
    request.session["plex_token"] = token
    request.session["plex_username"] = username
    request.session.pop("pending_pin_id", None)

    # Trigger library indexing on first login (non-blocking)
    indexer.set_bootstrap_token(token)
    if indexer.get_status()["state"] == "idle":
        asyncio.create_task(indexer.run_indexing(token))

    return {"success": True, "username": username}


@router.get("/me")
async def me(request: Request):
    if request.session.get("authenticated"):
        return {"authenticated": True, "username": request.session.get("plex_username")}
    return {"authenticated": False, "username": None}


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return JSONResponse(status_code=204, content=None)


@router.get("/protected-test")
async def protected_test(session: dict = Depends(require_auth)):
    return {"user": session.get("plex_username")}
