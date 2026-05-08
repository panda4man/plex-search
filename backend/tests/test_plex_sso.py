from unittest.mock import AsyncMock, MagicMock, patch

from urllib.parse import unquote

from app.auth.plex_sso import build_auth_url, create_pin, get_plex_username, poll_pin


# ── build_auth_url ───────────────────────────────────────────────────────────

def test_build_auth_url_starts_with_plex_domain():
    assert build_auth_url("code", 1).startswith("https://app.plex.tv/auth")


def test_build_auth_url_contains_code():
    assert "mycode123" in build_auth_url("mycode123", 1)


def test_build_auth_url_contains_pin_id_in_forward_url():
    # forwardUrl is URL-encoded in the outer query string — decode before asserting
    assert "pinId=99" in unquote(build_auth_url("code", 99))


def test_build_auth_url_contains_client_id():
    assert "test-client-id-fixed" in build_auth_url("code", 1)


def test_build_auth_url_forward_url_points_to_callback():
    assert "/auth/callback" in unquote(build_auth_url("code", 1))


# ── create_pin ───────────────────────────────────────────────────────────────

async def test_create_pin_returns_id_and_code():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 123, "code": "abc123", "expires_in": 1800}
    mock_resp.raise_for_status = MagicMock()
    client = AsyncMock()
    client.post = AsyncMock(return_value=mock_resp)

    result = await create_pin(client)
    assert result["id"] == 123
    assert result["code"] == "abc123"


async def test_create_pin_calls_correct_endpoint():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 1, "code": "x"}
    mock_resp.raise_for_status = MagicMock()
    client = AsyncMock()
    client.post = AsyncMock(return_value=mock_resp)

    await create_pin(client)
    call_url = client.post.call_args[0][0]
    assert "plex.tv/api/v2/pins" in call_url


async def test_create_pin_raises_on_http_error():
    client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("401 Unauthorized")
    client.post = AsyncMock(return_value=mock_resp)

    import pytest
    with pytest.raises(Exception):
        await create_pin(client)


# ── poll_pin ─────────────────────────────────────────────────────────────────

async def test_poll_pin_returns_token_immediately():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"authToken": "user-token-xyz"}
    mock_resp.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp)

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await poll_pin(client, pin_id=42, retries=3, delay=0)
    assert result == "user-token-xyz"


async def test_poll_pin_retries_until_token_appears():
    no_token = MagicMock()
    no_token.json.return_value = {"authToken": None}
    no_token.raise_for_status = MagicMock()
    has_token = MagicMock()
    has_token.json.return_value = {"authToken": "got-it"}
    has_token.raise_for_status = MagicMock()

    client = AsyncMock()
    client.get = AsyncMock(side_effect=[no_token, no_token, has_token])

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await poll_pin(client, pin_id=1, retries=5, delay=0)
    assert result == "got-it"
    assert client.get.call_count == 3


async def test_poll_pin_returns_none_when_retries_exhausted():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"authToken": None}
    mock_resp.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp)

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await poll_pin(client, pin_id=1, retries=3, delay=0)
    assert result is None
    assert client.get.call_count == 3


async def test_poll_pin_stops_polling_once_token_found():
    has_token = MagicMock()
    has_token.json.return_value = {"authToken": "early-token"}
    has_token.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=has_token)

    with patch("asyncio.sleep", new=AsyncMock()):
        await poll_pin(client, pin_id=1, retries=10, delay=0)
    assert client.get.call_count == 1


# ── get_plex_username ────────────────────────────────────────────────────────

async def test_get_plex_username_returns_username_field():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"username": "JohnDoe", "title": "John"}
    mock_resp.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp)

    assert await get_plex_username(client, "token") == "JohnDoe"


async def test_get_plex_username_falls_back_to_title():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"username": None, "title": "Fallback"}
    mock_resp.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp)

    assert await get_plex_username(client, "token") == "Fallback"


async def test_get_plex_username_falls_back_to_unknown():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {}
    mock_resp.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp)

    assert await get_plex_username(client, "token") == "Unknown"


async def test_get_plex_username_attaches_token_header():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"username": "u"}
    mock_resp.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp)

    await get_plex_username(client, "my-secret-token")
    headers_used = client.get.call_args[1]["headers"]
    assert headers_used["X-Plex-Token"] == "my-secret-token"
