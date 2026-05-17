# PlexSearch — Agent Guide

Natural language search interface for Plex Media Server. Vue 3 + FastAPI + Ollama + ChromaDB, all Docker Compose. Plex SSO auth. Hybrid search: LLM extracts structured filters + embedding similarity.

---

## Architecture

```
[Browser] → [nginx :80] → [FastAPI :8000] → [Ollama :11434]
                                           → [Plex Server (LAN :32400)]
[Browser] ↔ [plex.tv] (SSO PIN flow)
```

Docker services: `frontend` (nginx + Vue build), `backend` (FastAPI + ChromaDB embedded), `ollama` (LLM + embed model).

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
| `frontend/src/llm/ai_client.py` | — |
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
docker compose down -v   # destroys chroma + ollama volumes
docker compose up        # cold start, reindexes after first login
```

Do NOT change `EMBED_PROVIDER` without running the above or the backend will crash on query.

### Cloud cost estimates (100 queries/day, ~1,100 item library)

| Scenario | Index (one-time) | Monthly |
|----------|-----------------|---------|
| Full local (default) | $0 | $0 |
| Together LLM + OpenAI embed | $0.002 | ~$0.25 |
| Full OpenAI | $0.002 | ~$0.34 |
| Full Anthropic | $0.002 | ~$0.64 |

---

## Deployment: LAN vs Cloudflare Tunnel (Unraid)

### LAN only
```bash
FRONTEND_URL=http://192.168.1.x
BACKEND_CORS_ORIGINS=http://192.168.1.x
SESSION_HTTPS_ONLY=false
```
Open port 80 on host firewall: `sudo ufw allow 80/tcp`

### Cloudflare Tunnel (public HTTPS)
```bash
FRONTEND_URL=https://plexsearch.yourdomain.com
BACKEND_CORS_ORIGINS=https://plexsearch.yourdomain.com
SESSION_HTTPS_ONLY=true   # adds Secure flag to session cookie
```
Point the tunnel at `http://localhost:80`. Cloudflare handles SSL — nginx needs no certs.
Plex SSO `forwardUrl` is built from `FRONTEND_URL`, so the HTTPS callback URL works automatically.

**`SESSION_HTTPS_ONLY`**: controlled by `settings.session_https_only` → `SessionMiddleware(https_only=...)` in `main.py`.
Do NOT set `true` on plain HTTP — browser will never send the cookie and all requests return 401.

---

## Adding a local OpenAI-compatible provider (vLLM, LocalAI, llama.cpp)

1. Add service to `docker-compose.yml`
2. Set in `.env`:
   ```
   LLM_PROVIDER=openai
   LLM_API_BASE=http://<service>:<port>
   LLM_MODEL=openai/<model-name>
   ```
3. For custom embed server:
   ```
   EMBED_PROVIDER=openai
   EMBED_API_BASE=http://<service>:<port>
   EMBED_MODEL=openai/<model-name>
   ```
4. `LLM_API_BASE` / `EMBED_API_BASE` override all other `api_base` logic in `ai_client.py`

---

## Hardware (GPU)

- **Current**: GTX 1660 Super — 6GB VRAM
  - `qwen2.5:7b` ≈ 4.5GB + `nomic-embed-text` ≈ 274MB = ~4.8GB total ✓
- **Upgrade path** (RTX 3060, 12GB): set `OLLAMA_MODEL=qwen2.5:14b` in `.env`
- GPU passthrough in `docker-compose.yml` requires `nvidia-container-toolkit` on host
- Ollama unloads idle models automatically if VRAM is tight

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
# Fill in: PLEX_SERVER_URL, PLEX_CLIENT_ID, SESSION_SECRET
# Generate PLEX_CLIENT_ID: python -c "import uuid; print(uuid.uuid4())"
# Generate SESSION_SECRET: openssl rand -hex 32

docker compose up --build          # production stack
# OR
docker compose -f docker-compose.yml -f docker-compose.dev.yml up  # hot reload
```

Frontend dev server: `http://localhost:5173` (proxies `/api` to backend on :8000).
Production: `http://localhost` (nginx on :80 proxies `/api` to backend).

## Reindex Plex library

```bash
# Via API (requires active session cookie):
curl -X POST http://localhost/api/admin/reindex \
  -H "Cookie: session=<value>"

# Check status:
curl http://localhost/api/admin/index-status \
  -H "Cookie: session=<value>"
```

---

## Mobile (future)

Vue + Capacitor wraps this web app natively — no React rewrite needed.
When adding Capacitor: session cookies may not work in native webview.
`require_auth` in `backend/app/auth/session.py` already accepts `Authorization: Bearer <token>` as fallback.
Switch frontend to send JWT bearer token instead of relying on cookies.

## Code Exploration Policy

Always use jCodemunch-MCP tools for code navigation. Never fall back to Read, Grep, Glob, or Bash for code exploration.
**Exception:** Use `Read` when you need to edit a file — the agent harness requires a `Read` before `Edit`/`Write` will succeed. Use jCodemunch tools to *find and understand* code, then `Read` only the specific file you're about to modify.

**Start any session:**
1. `resolve_repo { "path": "." }` — confirm the project is indexed. If not: `index_folder { "path": "." }`
2. `suggest_queries` — when the repo is unfamiliar

**Finding code:**
- symbol by name → `search_symbols` (add `kind=`, `language=`, `file_pattern=`, `decorator=` to narrow)
- decorator-aware queries → `search_symbols(decorator="X")` to find symbols with a specific decorator (e.g. `@property`, `@route`); combine with set-difference to find symbols *lacking* a decorator (e.g. "which endpoints lack CSRF protection?")
- string, comment, config value → `search_text` (supports regex, `context_lines`)
- database columns (dbt/SQLMesh) → `search_columns`

**Reading code:**
- before opening any file → `get_file_outline` first
- one or more symbols → `get_symbol_source` (single ID → flat object; array → batch)
- symbol + its imports → `get_context_bundle`
- specific line range only → `get_file_content` (last resort)

**Repo structure:**
- `get_repo_outline` → dirs, languages, symbol counts
- `get_file_tree` → file layout, filter with `path_prefix`

**Relationships & impact:**
- what imports this file → `find_importers`
- where is this name used → `find_references`
- is this identifier used anywhere → `check_references`
- file dependency graph → `get_dependency_graph`
- what breaks if I change X → `get_blast_radius`
- what symbols actually changed since last commit → `get_changed_symbols`
- find unreachable/dead code → `find_dead_code`
- class hierarchy → `get_class_hierarchy`

## Session-Aware Routing

**Opening move for any task:**
1. `plan_turn { "repo": "...", "query": "your task description", "model": "<your-model-id>" }` — get confidence + recommended files; the `model` parameter narrows the exposed tool list to match your capabilities at zero extra requests.
2. Obey the confidence level:
   - `high` → go directly to recommended symbols, max 2 supplementary reads
   - `medium` → explore recommended files, max 5 supplementary reads
   - `low` → the feature likely doesn't exist. Report the gap to the user. Do NOT search further hoping to find it.

**Interpreting search results:**
- If `search_symbols` returns `negative_evidence` with `verdict: "no_implementation_found"`:
  - Do NOT re-search with different terms hoping to find it
  - Do NOT assume a related file (e.g. auth middleware) implements the missing feature (e.g. CSRF)
  - DO report: "No existing implementation found for X. This would need to be created."
  - DO check `related_existing` files — they show what's nearby, not what exists
- If `verdict: "low_confidence_matches"`: examine the matches critically before assuming they implement the feature

**After editing files:**
- If PostToolUse hooks are installed (Claude Code only), edited files are auto-reindexed
- Otherwise, call `register_edit` with edited file paths to invalidate caches and keep the index fresh
- For bulk edits (5+ files), always use `register_edit` with all paths to batch-invalidate

**Token efficiency:**
- If `_meta` contains `budget_warning`: stop exploring and work with what you have
- If `auto_compacted: true` appears: results were automatically compressed due to turn budget
- Use `get_session_context` to check what you've already read — avoid re-reading the same files

## Model-Driven Tool Tiering

Your jcodemunch-mcp server narrows the exposed tool list based on the model you are running as. To avoid wasting requests on primitives when a composite would do, always include `model="<your-model-id>"` in your opening `plan_turn` call.

Replace `<your-model-id>` with your active model:
- Claude Opus variants → `claude-opus-4-7` (or any `claude-opus-*`)
- Claude Sonnet variants → `claude-sonnet-4-6`
- Claude Haiku variants → `claude-haiku-4-5`
- GPT-4o / GPT-5 / o1 / Llama → use the model id as printed by your runner

The `model=` parameter rides on the existing `plan_turn` call — it does **not** add a separate tool invocation. If `plan_turn` is not appropriate for a non-code task, call `announce_model(model="...")` once instead.

