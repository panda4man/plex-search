from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # e.g. LLM_PROVIDER=openai, LLM_API_BASE=http://vllm:8000, LLM_MODEL=openai/mistral
    llm_api_base: str = ""
    embed_api_base: str = ""

    # Cloud API keys (only required for respective cloud provider)
    together_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    session_secret: str
    # Set to true when serving over HTTPS (e.g. behind Cloudflare Tunnel)
    # Adds Secure flag to session cookie — required for HTTPS, breaks plain HTTP
    session_https_only: bool = False
    frontend_url: str = "http://localhost"
    backend_cors_origins: list[str] = ["http://localhost"]

    chroma_persist_dir: str = "/data/chroma"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
