# PlexSearch — Agent Guide

Natural language search interface for Plex Media Server. Vue 3 + FastAPI + Ollama + ChromaDB, all Docker Compose. Plex SSO auth. Hybrid search: LLM extracts structured filters + embedding similarity.

---

## Architecture

```
[Browser] → [nginx :80] → [FastAPI :8000] → [Ollama :11434 (external)]
                                           → [Plex Server (LAN :32400)]
[Browser] ↔ [plex.tv] (SSO PIN flow)
```

Docker services: `frontend` (nginx + Vue build), `backend` (FastAPI + ChromaDB embedded). Ollama runs externally — set `OLLAMA_BASE_URL` in `.env`.

---

## Key files

| File | Purpose |
|------|---------|
| `backend/app/llm/ai_client.py` | All AI calls — LiteLLM abstraction, provider dispatch |
| `backend/app/llm/query_parser.py` | NL → structured filters; **system prompt lives here** |
| `backend/app/search/indexer.py` | Plex library → ChromaDB embedding pipeline |
| `backend/app/search/vector_store.py` | ChromaDB client (cosine similarity, 768-dim) |
| `backend/app/plex/search.py` | Filter translation + Plex API calls |
| `backend/app/plex/client.py` | PlexServer factory, per-token cache, thread executor |
| `backend/app/auth/plex_sso.py` | Plex PIN OAuth flow (create PIN → poll → get token) |
| `backend/app/auth/session.py` | `require_auth` dependency (cookie + Bearer token) |
| `backend/app/config.py` | All settings via pydantic-settings; reads `.env` |
| `backend/app/main.py` | FastAPI app, lifespan, CORS+session middleware |
| `frontend/src/stores/auth.ts` | Pinia: session state, SSO flow |
| `frontend/src/stores/search.ts` | Pinia: query, results, loading |
| `frontend/src/views/AuthCallbackView.vue` | Handles plex.tv redirect, completes login |
| `frontend/nginx.conf` | Proxies `/api/` to backend, SPA fallback |
| `docker-compose.yml` | Production stack |
| `docker-compose.dev.yml` | Dev overrides (hot reload, Vite dev server) |
| `.env.example` | All configurable vars with documentation |

---

## AI providers

All AI calls go through `backend/app/llm/ai_client.py` (LiteLLM). Switch providers via `.env` — no code changes needed.

### LLM (query parsing)

| `LLM_PROVIDER` | Default model | Notes |
|----------------|---------------|-------|
| `ollama` (default) | `qwen2.5:7b` | Local, ~4.5GB VRAM |
| `together` | `Qwen/Qwen2.5-7B-Instruct-Turbo` | ~$0.24/mo at 100 q/day |
| `openai` | `gpt-4o-mini` | ~$0.33/mo at 100 q/day |
| `anthropic` | `claude-haiku-4-5-20251001` | ~$0.63/mo at 100 q/day; no JSON mode |

Override model: `LLM_MODEL=openai/gpt-4o` (or any LiteLLM model string).

### Embeddings

| `EMBED_PROVIDER` | Default model | Dimensions |
|-----------------|---------------|------------|
| `ollama` (default) | `nomic-embed-text` | 768 |
| `openai` | `text-embedding-3-small` (forced to 768-dim) | 768 |
| `together` | `togethercomputer/m2-bert-80M-8k-retrieval` | 768 |

Override model: `EMBED_MODEL=openai/text-embedding-3-large`.

### ⚠️ Embed provider switching — DESTRUCTIVE

ChromaDB stores vectors at fixed dimensions (768). Changing `EMBED_PROVIDER` produces incompatible vectors. **Must wipe and reindex:**

```bash
docker compose down -v   # destroys chroma volume
docker compose up        # cold start, reindexes after first login
```

Do NOT change `EMBED_PROVIDER` without running the above or the backend will crash on query.

---

## Plex API gotchas

- **Never hardcode section names** — enumerate by `.type == "movie"/"show"`, not by name
- **`PlexServer()` is synchronous and blocking** — always wrap in `loop.run_in_executor(executor, ...)`
- **Year range filters** require operator syntax: `filters={"year>>": 1990, "year<<": 1999}` (not kwargs)
- **Thumbnails** need token appended: `{PLEX_SERVER_URL}{item.thumb}?X-Plex-Token={token}`
- **PlexServer instantiation hits the network** — cached per token in `plex/client.py`

## Auth / CORS gotchas

- **Plex SSO** is PIN-based (not standard OAuth2): create PIN → redirect user → poll for completion
- **`forwardUrl`** in Plex auth URL must point to `{FRONTEND_URL}/auth/callback?pinId={pin_id}`
- **CORS + credentials**: `allow_origins` must be explicit list, never `["*"]` when `allow_credentials=True`
- **Middleware order** in `main.py` is LIFO: add CORSMiddleware first in code, SessionMiddleware second
- **Axios** must set `withCredentials: true` on every request or session cookie is never sent
- **nginx** must have `proxy_pass_header Set-Cookie` and `try_files $uri /index.html` (SPA fallback)

## Ollama gotchas

- **Cold start**: model pull takes 3–10 min on first boot — startup check is non-fatal
- **Timeout**: LLM inference on CPU can take 60–120s — `ai_client.py` uses `timeout=120`
- **JSON mode**: Anthropic has no `response_format` support — relies on prompt + fence-stripping fallback in `query_parser.py`

---

## Search flow

1. `POST /api/search` with `{query: "action movies from the 90s"}`
2. LLM extracts `SearchFilters` → Plex API query (structured path)
3. `nomic-embed-text` embeds query → ChromaDB cosine similarity (semantic path)
4. Hybrid merge: `score = 0.6 × vector_similarity + 0.4 × plex_rating_normalized`
5. Deduped, sorted results returned

---

## Dev workflow

```bash
cp .env.example .env
# Fill in: PLEX_SERVER_URL, PLEX_CLIENT_ID, SESSION_SECRET, OLLAMA_BASE_URL

docker compose up --build          # production stack
docker compose -f docker-compose.yml -f docker-compose.dev.yml up  # hot reload
```

Reindex Plex library: `curl -X POST http://localhost/api/admin/reindex -H "Cookie: session=<value>"`

---

## Code Exploration Policy

Always use jCodemunch-MCP tools for code navigation. Never fall back to Read, Grep, Glob, or Bash for code exploration.
**Exception:** Use `Read` when you need to edit a file — the agent harness requires a `Read` before `Edit`/`Write` will succeed.

**Opening move:** `plan_turn { "repo": ".", "query": "...", "model": "claude-sonnet-4-6" }`. Obey the confidence level — `low` means the feature doesn't exist, stop searching. If unsure which tool to use, call `jcodemunch_guide`.
