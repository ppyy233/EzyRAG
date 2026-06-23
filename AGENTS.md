# AGENTS.md — Ezy-RAG

RAG knowledge base system. Python 3.11+ / FastAPI / ChromaDB / Vue 3 frontend.
**Windows-only** (win32 + AMD64 required by pyproject.toml).

## Commands

```bash
# First-time setup (interactive: installs deps, writes config/.env, starts services)
python quickstart.py

# CLI menu
python ezyrag.py                 # interactive menu
python ezyrag.py service         # service management
python ezyrag.py db              # document management
python ezyrag.py config          # config management
python ezyrag.py health          # health check

# Start individual services (each is a separate process)
python -m servers.chroma         # ChromaDB on :9898
python -m servers.web            # Web API on :9767
python -m servers.mcp            # MCP server on :9766
python -m servers.embedding      # local embedding on :1234 (optional)
python -m servers.rerank         # local rerank on :5001 (optional)

# Frontend build (optional, quickstart.py does this automatically)
cd frontend && npm install && npm run build

# Package manager: uv (NOT pip)
uv sync                          # install deps
uv sync --extra local            # + local embedding/rerank (needs torch + CUDA)
```

**Startup order matters**: ChromaDB must be running before Web API or MCP server.

## Architecture (4 layers)

```
config/     → settings.py loads .env + config.json; pointer.py manages collection pointer
core/       → api.py (EmbeddingAPI/RerankAPI), database.py (DocumentDatabase), chunking.py, scheduler.py
servers/    → each is a standalone FastAPI app started via `python -m servers.X`
cli/        → ezyrag.py entrypoint, ui.py terminal components
frontend/   → Vue 3 + Element Plus + Vite, builds to frontend/dist/, served by web.py
```

## Config (two files, both required)

- `config/.env` — secrets + ports. Copy from `config/.env.example`. **Loaded at import time** by `config/settings.py`; missing file = crash.
- `config/config.json` — chunk templates, HNSW params, retrieval params. Created by quickstart.py.

Key env vars: `EMBEDDING_MODE` (cloud/local), `EMBEDDING_CLOUD_API_KEY`, `RERANK_ENABLED`, `CHROMA_SERVER_PORT`, `MCP_SERVER_PORT`, `WEB_API_PORT`, `CHUNK_TEMPLATE`.

## Data directories (all gitignored except .gitkeep)

- `data/docs/` — local documents (PDF, DOCX, TXT, MD)
- `data/web/` — crawled web pages
- `data/chroma_db/` — ChromaDB persistent storage
- `data/models/` — local model files
- `runtime/logs/` — service logs
- `runtime/state/collection_pointer.json` — active collection pointer (atomic writes)

## Key patterns

- **Every Python module** uses `ROOT = Path(__file__).resolve().parent.parent` + `sys.path.insert(0, str(ROOT))` for imports.
- **Config access**: always via `config.settings` functions (`get_embedding_config()`, `get_chunk_config()`, etc.), never raw `.env` reads.
- **Collection pointer**: `config/pointer.py` maps config keys to active ChromaDB collection names. Used during rebuild (shadow collection swap). File: `runtime/state/collection_pointer.json`.
- **Scheduler**: `core/scheduler.py` — priority queue. `priority=0` for search queries (VIP), `priority=100` for indexing. Singleton via `get_scheduler()`.
- **Embedding batch size**: controlled by `EMBED_BATCH_SIZE` env var (default 50). Cloud APIs typically limit to 64.
- **HNSW repair**: `connect_chroma()` in `servers/web.py` detects corrupted HNSW indexes and deletes the segment dir to force rebuild.
- **Shadow collection**: `database.py` uses shadow collection strategy for `update`/`sync`/`rebuild` to guarantee atomicity. `add` and `delete` are direct operations.
- **Document processing**: `core/document.py` reads files, prepends `[文件名: ...]` to text before chunking.
- **MCP tool**: single tool `search_knowledge_base` exposed at `/mcp` endpoint. Tool description includes trigger phrases for LLM to know when to call it.

## Frontend

- Vue 3 + Element Plus + Vite
- Dev server proxies `/api` and `/ws` to `http://127.0.0.1:9767`
- Build output: `frontend/dist/` (served as static files by web.py)
- `quickstart.py` auto-detects source changes and rebuilds

## What NOT to do

- Don't use `pip` — use `uv`
- Don't import `config.settings` without `config/.env` existing (it crashes at import time)
- Don't start Web API or MCP without ChromaDB running first
- Don't edit `config/.env` directly for config changes — use the Web API `PUT /api/config` or CLI
- Don't assume ChromaDB collection UUIDs are stable — they change on rebuild. The pointer system handles this.
