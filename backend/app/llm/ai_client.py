"""
Provider-agnostic AI client via LiteLLM.

LLM providers:   ollama | together | openai | anthropic
Embed providers: ollama | openai   | together

Set LLM_PROVIDER / EMBED_PROVIDER in .env. API keys only needed for cloud providers.
"""

import logging
from typing import Any

import litellm

from app.config import get_settings

logger = logging.getLogger(__name__)
litellm.suppress_debug_info = True

_LLM_DEFAULTS: dict[str, str] = {
    "together": "together_ai/Qwen/Qwen2.5-7B-Instruct-Turbo",
    "openai":   "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}

_EMBED_DEFAULTS: dict[str, str] = {
    "openai":   "text-embedding-3-small",
    "together": "together_ai/togethercomputer/m2-bert-80M-8k-retrieval",
}


def _llm_model() -> str:
    s = get_settings()
    if s.llm_model:
        return s.llm_model
    if s.llm_provider == "ollama":
        return f"ollama_chat/{s.ollama_model}"
    return _LLM_DEFAULTS[s.llm_provider]


def _embed_model() -> str:
    s = get_settings()
    if s.embed_model:
        return s.embed_model
    if s.embed_provider == "ollama":
        return f"ollama/{s.ollama_embed_model}"
    return _EMBED_DEFAULTS[s.embed_provider]


def _llm_kwargs() -> dict[str, Any]:
    s = get_settings()
    kwargs: dict[str, Any] = {"timeout": 120}
    # llm_api_base overrides everything — use for local OpenAI-compat servers
    if s.llm_api_base:
        kwargs["api_base"] = s.llm_api_base
    elif s.llm_provider == "ollama":
        kwargs["api_base"] = s.ollama_base_url
    if s.llm_provider == "together" and s.together_api_key:
        kwargs["api_key"] = s.together_api_key
    elif s.llm_provider == "openai" and s.openai_api_key:
        kwargs["api_key"] = s.openai_api_key
    elif s.llm_provider == "anthropic" and s.anthropic_api_key:
        kwargs["api_key"] = s.anthropic_api_key
    return kwargs


def _embed_kwargs() -> dict[str, Any]:
    s = get_settings()
    kwargs: dict[str, Any] = {"timeout": 60}
    # embed_api_base overrides everything — use for local OpenAI-compat embed servers
    if s.embed_api_base:
        kwargs["api_base"] = s.embed_api_base
    elif s.embed_provider == "ollama":
        kwargs["api_base"] = s.ollama_base_url
    if s.embed_provider == "openai" and s.openai_api_key:
        kwargs["api_key"] = s.openai_api_key
        # Normalize to 768 dims for ChromaDB consistency with nomic-embed-text
        kwargs["dimensions"] = 768
    elif s.embed_provider == "together" and s.together_api_key:
        kwargs["api_key"] = s.together_api_key
    return kwargs


async def chat(system_prompt: str, user_message: str) -> str:
    s = get_settings()
    # Anthropic has no JSON mode — rely on prompt + fence-stripping in query_parser
    use_json_mode = s.llm_provider != "anthropic"

    response = await litellm.acompletion(
        model=_llm_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        **({"response_format": {"type": "json_object"}} if use_json_mode else {}),
        **_llm_kwargs(),
    )
    return response.choices[0].message.content


async def embed(text: str) -> list[float]:
    response = await litellm.aembedding(
        model=_embed_model(),
        input=[text],
        **_embed_kwargs(),
    )
    return response.data[0]["embedding"]


async def is_ready() -> bool:
    s = get_settings()
    if s.llm_provider != "ollama" and s.embed_provider != "ollama":
        return True  # cloud providers assumed available if keys are set
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{s.ollama_base_url}/api/tags")
            return r.status_code == 200
    except Exception:
        return False
