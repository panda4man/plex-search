import json
from functools import lru_cache
from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, EnvSettingsSource, SettingsConfigDict


class _FlexibleEnvSource(EnvSettingsSource):
    """Env source that accepts comma-separated strings for list fields."""

    def decode_complex_value(self, field_name: str, field: FieldInfo, value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [s.strip() for s in value.split(",") if s.strip()]
        return super().decode_complex_value(field_name, field, value)


class Settings(BaseSettings):
    plex_server_url: str
    plex_app_name: str = "PlexSearch"
    plex_client_id: str

    # Ollama (used when llm_provider or embed_provider is "ollama")
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_embed_model: str = "nomic-embed-text"

    # AI providers: ollama | together | openai | anthropic
    llm_provider: str = "ollama"
    # Embed providers: ollama | openai | together
    # WARNING: switching embed_provider invalidates existing ChromaDB vectors.
    # Delete the chroma volume and reindex after changing: docker compose down -v
    embed_provider: str = "ollama"

    # Optional model overrides — leave empty to use provider defaults
    llm_model: str = ""
    embed_model: str = ""

    # Optional API base overrides — use for local OpenAI-compat servers (vLLM, LocalAI, etc.)
    llm_api_base: str = ""
    embed_api_base: str = ""

    # Cloud API keys (only required for respective cloud provider)
    together_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # TMDB — composer augmentation during indexing (optional)
    # Get Read Access Token at: https://www.themoviedb.org/settings/api
    tmdb_read_access_token: str = ""

    session_secret: str
    # Set to true when serving over HTTPS (e.g. behind Cloudflare Tunnel)
    # Adds Secure flag to session cookie — required for HTTPS, breaks plain HTTP
    session_https_only: bool = False
    frontend_url: str = "http://localhost"
    # Accepts comma-separated: http://localhost,http://localhost:5173
    backend_cors_origins: list[str] = ["http://localhost"]

    chroma_persist_dir: str = "/data/chroma"

    @classmethod
    def settings_customise_sources(cls, settings_cls, env_settings, **kwargs):
        return (_FlexibleEnvSource(settings_cls), *kwargs.values())

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
