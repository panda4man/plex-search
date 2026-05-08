# PlexSearch

Natural language search for your Plex library. Ask for *"sci-fi movies from the 80s"* or *"that show about meth in the desert"* and get results — powered by a local LLM and semantic vector search, all running on your own hardware.

![Stack](https://img.shields.io/badge/Vue_3-4FC08D?style=flat&logo=vuedotjs&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white) ![Ollama](https://img.shields.io/badge/Ollama-local_LLM-black?style=flat) ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)

---

## How it works

Every search runs two paths in parallel and merges the results:

1. **LLM filter extraction** — `qwen2.5:7b` converts your query into structured Plex filters (genre, year range, rating, actors). Fast, precise for structured queries.
2. **Semantic vector search** — `nomic-embed-text` embeds your query and finds similar content by meaning. Handles fuzzy queries that keywords can't.

Everything runs locally. No data leaves your network.

---

## Features

- Natural language search across movies and TV shows
- Hybrid scoring: structured filters + semantic similarity
- Plex SSO — login with your existing Plex account
- Recently added view on home page
- Poster thumbnails, ratings, genre badges
- Click any result to open directly in Plex Web
- Swappable AI providers via environment variables (Ollama, Together AI, Anthropic)
- Cloudflare Tunnel / public HTTPS ready

---

## Requirements

- Docker + Docker Compose v2
- NVIDIA GPU recommended (GTX 1660 Super 6GB or better)
  - `nvidia-container-toolkit` installed on host for GPU passthrough
  - CPU inference works but is slow (~30–120s per query)
- Plex Media Server on the same network

---

## Quick start

```bash
git clone <repo-url>
cd plex-search

cp .env.example .env
```

Edit `.env` — three required values:

```bash
PLEX_SERVER_URL=http://192.168.1.x:32400        # your Plex server LAN address
PLEX_CLIENT_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
SESSION_SECRET=$(openssl rand -hex 32)
```

```bash
docker compose up --build
```

On first boot Ollama pulls both models (~5GB total). Open `http://localhost` once the logs show *"All models ready."*

Sign in with your Plex account. The library indexes automatically in the background after first login.

---

## Configuration

All settings live in `.env`. Full reference in `.env.example`.

### Key variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PLEX_SERVER_URL` | — | LAN address of your Plex server |
| `PLEX_CLIENT_ID` | — | Stable UUID for this app (generate once) |
| `SESSION_SECRET` | — | 32-byte hex secret for session signing |
| `OLLAMA_MODEL` | `qwen2.5:7b` | LLM for query parsing |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `FRONTEND_URL` | `http://localhost` | Public URL (update for LAN/Cloudflare access) |
| `SESSION_HTTPS_ONLY` | `false` | Set `true` behind HTTPS (Cloudflare Tunnel etc.) |

### GPU upgrade

RTX 3060 (12GB VRAM) or better — upgrade the LLM for better query parsing:

```bash
OLLAMA_MODEL=qwen2.5:14b
```

### LAN access

```bash
FRONTEND_URL=http://192.168.1.x
BACKEND_CORS_ORIGINS=http://192.168.1.x
```

Open port 80 on host: `sudo ufw allow 80/tcp`

### Cloudflare Tunnel (Unraid / public access)

```bash
FRONTEND_URL=https://plexsearch.yourdomain.com
BACKEND_CORS_ORIGINS=https://plexsearch.yourdomain.com
SESSION_HTTPS_ONLY=true
```

Point the tunnel at `http://localhost:80`. No SSL config needed — Cloudflare handles it.

### Cloud AI providers

The LLM and embedding model can be swapped without code changes:

```bash
# Use Together AI for LLM (cheap, fast)
LLM_PROVIDER=together
TOGETHER_API_KEY=sk-...

# Keep embeddings local
EMBED_PROVIDER=ollama
```

See `.env.example` for all provider options.

> ⚠️ **Switching `EMBED_PROVIDER` wipes your index.** Run `docker compose down -v && docker compose up` after changing it.

---

## Development

```bash
# Hot reload for both frontend and backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

- Frontend dev server: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

### Run backend tests

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-test.txt
.venv/bin/python -m pytest tests/ -v
```

### Reindex Plex library manually

```bash
curl -X POST http://localhost/api/admin/reindex \
  -H "Cookie: session=<your-session-cookie>"

# Check status
curl http://localhost/api/admin/index-status \
  -H "Cookie: session=<your-session-cookie>"
```

---

## Project structure

```
plex-search/
├── backend/
│   ├── app/
│   │   ├── auth/          # Plex SSO PIN flow, session middleware
│   │   ├── llm/           # LiteLLM abstraction, query parser
│   │   ├── plex/          # PlexServer client, search + filter translation
│   │   ├── search/        # ChromaDB vector store, indexer, merge logic
│   │   └── routers/       # FastAPI route handlers
│   └── tests/             # 69 unit tests
├── frontend/
│   └── src/
│       ├── api/           # Axios client
│       ├── stores/        # Pinia: auth, search
│       ├── components/    # SearchBar, ResultsGrid, MediaCard
│       └── views/         # Home, Login, AuthCallback
├── ollama/                # Docker image + model pull entrypoint
├── docker-compose.yml
└── docker-compose.dev.yml
```

---

## Mobile

The frontend is built with [Capacitor](https://capacitorjs.com/) in mind — wrap it in a native iOS/Android shell without a React rewrite. With Cloudflare Tunnel providing a public HTTPS URL the app works from anywhere, not just your home network.

---

## License

MIT
