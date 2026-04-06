# Newsletter Portal — Project Architecture Blueprint

> Generated: 2026-04-06  
> Architecture Pattern: Layered Pipeline with Background Job Processing  
> Technology Stack: Python / FastAPI / stdlib HTML+CSS static output  
> Detail Level: Comprehensive / Implementation-Ready

---

## 1. Architectural Overview

The Newsletter Portal is a **layered pipeline system** that converts research briefs (`topic.md`) into styled, dated newsletter issues served as static HTML. It combines a FastAPI application server with a static site builder, backed by a JSON registry for topic metadata.

### Guiding Principles

- **Single source of truth per concern.** Topic metadata lives in `topics.json` only. Build artifacts live in `dist/` only. Research briefs live in `topics/<slug>/topic.md` only.
- **Registry-first operations.** Every API endpoint, the build script, and the daily runner all read topic metadata through `shared/topic_registry.py`. No code reads `topics.json` or `topics.toml` directly.
- **Separation between generation and serving.** Content generation (AI calls) happens in background threads; serving is always instant from pre-built static files.
- **API routes registered before static mounts.** FastAPI's static file handler shadows everything below it; all `/api/*` routers must be registered first (enforced in `server/main.py`).
- **Atomic file writes.** Both registry writes and build output writes use temp-file-then-rename patterns to prevent corruption on crash.

### Architectural Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                    External Clients                          │
│   Browsers (manage.html / portal) · Telegram · CLI         │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP / webhooks
┌──────────────────▼──────────────────────────────────────────┐
│                 FastAPI Server (port 9000)                   │
│  /api/topics  /api/generate  /api/jobs  + static StaticFiles│
└──────────────────┬──────────────────────────────────────────┘
                   │ background threads (ThreadPoolExecutor)
┌──────────────────▼──────────────────────────────────────────┐
│                  Pipeline Layer (server/pipeline.py)         │
│  Topic creation · Newsletter generation · Media generation   │
└──────────────────┬──────────────────────────────────────────┘
                   │ function calls
┌──────────────────▼──────────────────────────────────────────┐
│                  Shared Infrastructure (shared/)             │
│  topic_registry · assemble_prompt · newsletter_generation   │
│  cli_newsletter_generation · build · openrouter_client      │
└──────────────────┬──────────────────────────────────────────┘
                   │ reads / writes
┌──────────────────▼──────────────────────────────────────────┐
│                  File System                                  │
│  topics.json · topics/<slug>/ · dist/ · shared/assets/      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Visualization — Component Diagram

```
topics.json (registry)
      │ read/write via topic_registry.py
      ▼
┌─────────────────────┐     assemble_prompt.py      ┌─────────────────────┐
│  topics/<slug>/     │ ──────────────────────────► │  topics/<slug>/     │
│  topic.md           │                             │  prompt.md          │
│  (research brief)   │                             │  (assembled)        │
└─────────────────────┘                             └──────────┬──────────┘
                                                               │
                                              newsletter_generation.py
                                              cli_newsletter_generation.py
                                                               │
                                                               ▼
                                              ┌─────────────────────────┐
                                              │  topics/<slug>/site/    │
                                              │  index.html             │
                                              │  YYYY-MM-DD.html        │
                                              │  YYYY-MM-DD.md          │
                                              └──────────┬──────────────┘
                                                         │
                                                    build.py
                                                         │
                                                         ▼
                                              ┌─────────────────────────┐
                                              │  dist/                  │
                                              │  index.html (portal)    │
                                              │  <slug>/index.html      │
                                              │  <slug>/YYYY-MM-DD.html │
                                              │  style.css              │
                                              └──────────┬──────────────┘
                                                         │
                                              server.main (StaticFiles mount)
                                                         │
                                                         ▼
                                              Browser (port 9000 or 8787)
```

---

## 3. Core Architectural Components

### 3.1 Topic Registry (`shared/topic_registry.py`)

**Purpose:** Single, thread-safe gateway to `topics.json`. Provides CRUD, existence checks, and readiness detection.

**Key operations:**
- `list_all()` — returns full registry dict
- `save(slug, data)` — create/update with atomic write (temp → rename)
- `delete(slug)` — remove with atomic write
- `is_ready(slug)` — `True` only if registered AND `topic.md` exists on disk
- `get_status(slug)` — returns `{registered, has_topic_md, has_prompt_md, has_site, ready, issue_count}`

**Thread safety:** A `threading.Lock` protects all writes; reads are unprotected (idempotent JSON parse).

**Migration:** `migrate_from_toml()` performs a one-time import from legacy `topics.toml` if `topics.json` is absent.

---

### 3.2 Prompt Assembler (`shared/assemble_prompt.py`)

**Purpose:** Composes `topics/<slug>/prompt.md` from three ordered layers:

1. `topics/<slug>/topic.md` — topic-specific identity, sources, and sections
2. `shared/prompts/design-guide.md` — locked editorial design rules (with `{SLUG}` substitution)
3. `shared/prompts/ops-guide.md` — output format and delivery steps (with `{SLUG}` substitution)

**Key constraint:** `prompt.md` is always assembled — never hand-authored. All shared conventions live in the guide files, not in individual topic briefs.

---

### 3.3 Newsletter Generators

Two generation paths exist in parallel:

| Module | Trigger | How it works |
|---|---|---|
| `shared/newsletter_generation.py` | API (`agent=openrouter`) | Reads `prompt.md` + template, calls OpenRouter synchronously, parses structured JSON `{raw_markdown, html, top_story_summary}`, writes files |
| `shared/cli_newsletter_generation.py` | API (`agent=claude\|gemini\|copilot\|opencode`) | Reads `prompt.md`, calls the selected CLI agent (`claude`, `gemini`, `gh copilot`, `opencode`) via `subprocess.run`, agent writes files directly |

**Agent validation:** `POST /api/topics/{slug}/newsletter?agent=<name>` validates against `{"openrouter","claude","gemini","copilot","opencode"}` and returns HTTP 400 for unknown agents.

---

### 3.4 Build System (`shared/build.py`)

**Purpose:** Produces `dist/` from per-topic generated HTML archives. Pure Python stdlib — no external dependencies.

**Process:**
1. Reads all topics from `shared/topic_registry.list_all()`
2. For each topic, discovers dated `site/YYYY-MM-DD.html` archives
3. Injects a nav bar into each page (`inject_nav()`)
4. Rewrites CSS paths to point to `dist/style.css`
5. Generates a landing page from `shared/templates/landing.html`
6. Copies `shared/assets/style.css` → `dist/style.css` and `shared/portal.css` → `dist/portal.css`

**Key functions:**
- `inject_nav(html, slug, topic_name, archives)` — inserts nav HTML after `<body>`
- `extract_metadata(html)` — regex-parses signal ratings from generated HTML
- `discover_html_archives(topic_dir)` — finds `site/YYYY-MM-DD.html` files, sorted descending

---

### 3.5 FastAPI Server (`server/main.py`, `server/routers/`)

**Routers:**

| Router | Prefix | Key endpoints |
|---|---|---|
| `topics.py` | `/api/topics` | CRUD + topic-md upload/read + newsletter trigger + SSE topic-md generation |
| `generate.py` | `/api/generate` | On-demand NotebookLM media (podcast, video, infographic) |
| `jobs_router.py` | `/api/jobs` | Job status polling + incremental log tailing |

**Mount order constraint:** All `/api/*` routers must be registered **before** `StaticFiles` is mounted on `/`; otherwise FastAPI's catch-all static handler swallows API requests.

---

### 3.6 Job Store (`server/jobs.py`)

**Purpose:** Thread-safe in-memory store for background job lifecycle.

**Job states:** `pending → running → done | failed`

**Fields per job:** `id`, `status`, `step` (human label), `artifact_url`, `error`, `log_lines` (incremental)

**Design intent:** Ephemeral across restarts. The `GET /api/jobs/{id}/log?from=N` endpoint supports incremental log polling without resending already-seen lines.

---

### 3.7 Pipeline (`server/pipeline.py`)

**Purpose:** Background job orchestration. All long-running operations run in a `ThreadPoolExecutor(max_workers=4)`.

**Jobs:**
- `submit_topic_creation(job_id, slug, payload)` — scaffold folder, generate `topic.md` via OpenRouter, register in registry, assemble prompt, generate first issue, trigger media, build portal
- `submit_newsletter_generation(job_id, slug, agent, model)` — assemble prompt, generate via selected agent, build portal
- `submit_topic_md_generation(job_id, slug, payload)` — generate `topic.md` only via OpenRouter
- `submit_media_generation(job_id, slug, date, type)` — NotebookLM podcast/video/infographic

---

## 4. Architectural Layers and Dependencies

```
Layer 4: Presentation
  dist/           static HTML+CSS portal files (never edited directly)
  manage.html     management UI — served from dist/, calls /api/*

Layer 3: Application (HTTP)
  server/main.py         FastAPI app bootstrap
  server/routers/        Request handling, validation, background task dispatch
  server/jobs.py         Job lifecycle management

Layer 2: Pipeline / Business Logic
  server/pipeline.py     Background job orchestration
  shared/newsletter_generation.py    OpenRouter content generation
  shared/cli_newsletter_generation.py  CLI agent content generation
  shared/topic_md_generation.py      OpenRouter topic.md generation
  shared/assemble_prompt.py          Prompt composition

Layer 1: Infrastructure / Data
  shared/topic_registry.py     JSON-backed topic CRUD + readiness checks
  shared/openrouter_client.py  OpenRouter API (stdlib urllib, no SDK)
  shared/build.py              Static site builder (stdlib only)
  topics.json                  Topic metadata registry
  topics/<slug>/               Topic source files and generated output
```

**Dependency rules:**
- Layer N can import from Layer N-1 or below only
- `shared/topic_registry.py` imports only stdlib — no upward dependencies
- `server/routers/` may import from `server/jobs`, `server/pipeline`, and all of `shared/`
- `server/pipeline.py` imports from `shared/` and `server/jobs` only — never from routers
- `shared/build.py` imports only stdlib and `shared/topic_registry`

---

## 5. Data Architecture

### 5.1 Topic Registry Schema (`topics.json`)

```json
{
  "<slug>": {
    "name": "Human-readable name",
    "description": "One-line brief",
    "accent": "terracotta|sage|prussian|gold",
    "signal_label": "Signal|Escalation|Activity|…",
    "eyebrow": "Daily Intelligence Brief",
    "folder": "topics/<slug>"
  }
}
```

`folder` is always derived from `slug` — the registry module enforces this on every write.

### 5.2 Topic Folder Contract

```
topics/<slug>/
  topic.md            ← required for generation (readiness gate)
  prompt.md           ← assembled at generation time, never hand-authored
  YYYY-MM-DD.md       ← raw markdown output per issue
  site/
    template.html     ← HTML scaffolding with {{PLACEHOLDER}} markers
    index.html        ← latest generated issue
    YYYY-MM-DD.html   ← dated HTML archive
    style.css         ← copy of shared/assets/style.css
  media/
    YYYY-MM-DD/       ← NotebookLM-generated podcast/video/infographic
```

### 5.3 Build Output (`dist/`)

```
dist/
  index.html          ← portal landing page
  style.css           ← editorial design system (locked)
  portal.css          ← portal nav and landing styles
  <slug>/
    index.html        ← latest issue with injected nav
    YYYY-MM-DD.html   ← dated archive with injected nav
```

### 5.4 Data Flow for Newsletter Generation

```
topics.json
    │ topic_registry.is_ready(slug)
    ▼
topics/<slug>/topic.md     ──► assemble_prompt.py ──► topics/<slug>/prompt.md
                                                              │
                                          ┌───────────────────┤
                               agent=openrouter    agent=claude|gemini|…
                                    │                         │
                          openrouter_client.py      subprocess (CLI)
                                    │                         │
                                    ▼                         ▼
                         {raw_markdown, html}    writes files directly
                                    │
                          topics/<slug>/YYYY-MM-DD.md
                          topics/<slug>/site/index.html
                          topics/<slug>/site/YYYY-MM-DD.html
                                    │
                               build.py
                                    │
                               dist/<slug>/
```

---

## 6. Cross-Cutting Concerns

### 6.1 Error Handling and Resilience

- **Background jobs:** All pipeline steps are wrapped in try/except; failures call `jobs.update(job_id, status=JobStatus.failed, error=str(e))`. Individual optional steps (NotebookLM, Telegram) catch and log instead of failing the job.
- **File write atomicity:** Both `topic_registry.py` writes and build output writes use `write(tmp) → rename(tmp, final)` to prevent partial-write corruption.
- **OpenRouter errors:** `openrouter_client.py` raises `RuntimeError` with the HTTP status and first 300 chars of the body for upstream debugging.
- **CLI agent errors:** `cli_newsletter_generation.py` raises `RuntimeError` with exit code and first 600 chars of stderr/stdout.

### 6.2 Thread Safety

- `server/jobs.py` protects all `_store` mutations with a `threading.Lock`.
- `shared/topic_registry.py` protects all `topics.json` writes with a `threading.Lock`. Reads are unprotected since Python's GIL and JSON parse are safe for read-only access.
- `server/pipeline.py` uses `ThreadPoolExecutor(max_workers=4)` to bound concurrency.

### 6.3 Configuration Management

All configuration is via environment variables with sensible defaults:

| Variable | Default | Used in |
|---|---|---|
| `OPENROUTER_API_KEY` | macOS keychain fallback | `openrouter_client.py` |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | `openrouter_client.py` |
| `OPENROUTER_MODEL_NEWSLETTER` | `stepfun/step-3.5-flash:free` | `openrouter_client.py` |
| `OPENROUTER_HTTP_REFERER` | `http://localhost:8787` | `openrouter_client.py` |
| `OPENROUTER_APP_TITLE` | `newsletters` | `openrouter_client.py` |
| `PORT` | `9000` | `server/main.py` |

### 6.4 Logging and Observability

- **Job logs:** All pipeline steps emit log lines to `jobs.append_log(job_id, ...)` with emoji prefixes for readability.
- **Server logs:** Uvicorn standard access logs via stdout.
- **File log:** `log.txt` at repo root — `run.sh` appends timestamps on each daily run.
- **External notifications:** Completed newsletters send Telegram messages via `plugin:telegram@claude-plugins-official` in the Claude CLI path.

### 6.5 Input Validation

- **Slug creation:** `_slugify()` in `server/routers/topics.py` lowercases, removes non-word characters, and truncates to 40 characters. All new topic creation must go through this function.
- **Agent validation:** `POST /api/topics/{slug}/newsletter` validates `agent` against the explicit set `{"openrouter","claude","gemini","copilot","opencode"}`.
- **Duplicate detection:** `POST /api/topics` returns HTTP 409 if the slug already exists.
- **Readiness gate:** Newsletter generation returns HTTP 409 if `topic.md` does not exist.

---

## 7. Service Communication Patterns

### 7.1 Client → Server (Synchronous REST)

All management operations are synchronous REST calls to `/api/*`. Responses are JSON.

### 7.2 Server → Background Worker (Async via BackgroundTasks)

Long-running operations are dispatched via FastAPI's `BackgroundTasks`, which runs them in a thread from the `ThreadPoolExecutor`. The endpoint returns a `job_id` immediately.

### 7.3 Client → Job Status (Polling)

```
POST /api/topics/{slug}/newsletter
  → { job_id: "abc12345", slug: "...", agent: "..." }

GET /api/jobs/{job_id}
  → { id, status, step, artifact_url, error }

GET /api/jobs/{job_id}/log?from=0
  → { lines: [...], total: N, status: "..." }
  (incremental: pass from=<last total> to get only new lines)
```

### 7.4 Server → OpenRouter (Outbound HTTP)

All OpenRouter calls use Python stdlib `urllib.request`. No SDK or third-party HTTP library is used. Two modes:

- `chat_completion(prompt)` — blocking, returns full response text
- `chat_completion_stream(prompt)` — SSE streaming generator, yields string tokens

### 7.5 Server → CLI Agents (Subprocess)

The CLI-backed generation path (`shared/cli_newsletter_generation.py`) uses `subprocess.run` with `capture_output=True, text=True, timeout=600`. The agent reads `prompt.md` from disk and writes output files directly.

### 7.6 Topic-md SSE Streaming

`POST /api/topics/generate-topic-md` returns `StreamingResponse` with `media_type="text/event-stream"`. Tokens from OpenRouter are forwarded as `data: <token>` events. The final event is `data: [DONE]` after the file is written. Errors emit `data: [ERROR] <msg>`.

---

## 8. Technology-Specific Architectural Patterns (Python)

### 8.1 Module Organisation

```
newsletter-portal/
├── server/                 FastAPI application
│   ├── main.py             App bootstrap and router registration
│   ├── jobs.py             In-memory job store
│   ├── pipeline.py         Background job orchestration
│   └── routers/
│       ├── topics.py       Topic CRUD and newsletter dispatch
│       ├── generate.py     On-demand media generation
│       └── jobs_router.py  Job status and log endpoints
├── shared/                 Reusable backend utilities
│   ├── topic_registry.py   JSON-backed topic CRUD
│   ├── assemble_prompt.py  Prompt composition
│   ├── build.py            Static site builder
│   ├── newsletter_generation.py     OpenRouter generation
│   ├── cli_newsletter_generation.py CLI agent generation
│   ├── topic_md_generation.py       OpenRouter topic.md generation
│   ├── openrouter_client.py         HTTP client for OpenRouter
│   ├── notebooklm_runner.py         NotebookLM media generation
│   ├── prompts/            Shared prompt layer files (locked)
│   ├── templates/          HTML templates for nav, landing page
│   ├── assets/             Locked editorial CSS
│   └── portal.css          Portal nav and landing styles
├── tests/                  Unit and integration tests
└── topics/                 Per-topic source and generated output
```

### 8.2 Dependency Injection (FastAPI)

FastAPI's `BackgroundTasks` is the primary DI mechanism for background work. No custom DI container is used. Shared state (job store, registry path) is module-level.

### 8.3 Asynchronous Programming

- FastAPI route handlers are `async def` for I/O-bound handlers.
- CPU/I/O-bound background tasks use `ThreadPoolExecutor` via `BackgroundTasks.add_task()`.
- SSE streaming uses synchronous generators wrapped in `StreamingResponse`.

### 8.4 Pydantic Models

Request body validation uses Pydantic `BaseModel` in all routers:

- `TopicCreate` — new topic payload with optional `topic_md` field
- `TopicMdUpdate` — content field for `PUT /api/topics/{slug}/topic-md`
- `TopicMdGenerateRequest` — name/description/focus_areas/slug for SSE generation

---

## 9. Implementation Patterns

### 9.1 Registry Write Pattern (Atomic)

```python
def save(slug: str, data: dict) -> dict:
    entry = {**_DEFAULTS, **data, "folder": _ensure_folder(slug)}
    with _lock:
        registry = _read_registry()
        registry[slug] = entry
        tmp_path = _REGISTRY_PATH.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n")
        tmp_path.replace(_REGISTRY_PATH)  # atomic rename
    return entry
```

### 9.2 Background Job Pattern

```python
# Router: dispatch immediately, return job_id
@router.post("/{slug}/newsletter")
async def generate_newsletter(slug: str, background_tasks: BackgroundTasks, agent: str = "openrouter"):
    job_id = jobs.create()
    background_tasks.add_task(submit_newsletter_generation, job_id, slug, agent, None)
    return {"job_id": job_id, "slug": slug, "agent": agent}

# Pipeline: update job state at each step
def _newsletter_job(job_id: str, slug: str, agent: str) -> None:
    try:
        _update(job_id, "Assembling prompt…")
        assemble(slug)
        _update(job_id, "Generating newsletter…")
        generate_newsletter_issue(slug) if agent == "openrouter" else generate_with_cli(slug, agent)
        jobs.update(job_id, status=JobStatus.done, step="Complete")
    except Exception as e:
        jobs.update(job_id, status=JobStatus.failed, error=str(e))
```

### 9.3 SSE Streaming Pattern

```python
@router.post("/generate-topic-md")
async def stream_generate_topic_md(payload: TopicMdGenerateRequest) -> StreamingResponse:
    def event_stream():
        for token in chat_completion_stream(prompt):
            safe = token.replace("\n", "\\n")
            yield f"data: {safe}\n\n"
        # Write file, emit DONE
        (topic_dir / "topic.md").write_text("".join(accumulated))
        yield "data: [DONE]\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

### 9.4 Readiness Gate Pattern

```python
# Always check readiness before any AI generation
if not is_ready(slug):
    raise HTTPException(status_code=409,
        detail=f"Topic '{slug}' is not ready: topics/{slug}/topic.md must exist")
```

### 9.5 Slug Normalization

```python
def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:40]
```

All new topic creation must use this function. Never introduce an alternate slug rule.

---

## 10. Testing Architecture

Tests live in `tests/` and use Python's stdlib `unittest`. The test suite can be run with:

```bash
uv run pytest
```

### Test Coverage by Module

| Test file | Coverage |
|---|---|
| `test_assemble_prompt.py` | `shared/assemble_prompt.py` — all 3 layers, substitution, missing-file errors |
| `test_build.py` | `shared/build.py` — full build run, expected dist output file layout |
| `test_jobs.py` | `server/jobs.py` — create, update, get, append_log, JobStatus enum |
| `test_jobs_router.py` | `server/routers/jobs_router.py` — 200/404 for status and log endpoints |
| `test_topic_registry.py` | `shared/topic_registry.py` — CRUD, atomic writes, is_ready, get_status |
| `test_topics_router.py` | `server/routers/topics.py` — create, get, list, delete, topic-md upload |

### Test Strategy

- **Unit tests** use `tempfile.TemporaryDirectory` for isolated file system operations; no external services.
- **Integration tests** (`test_build.py`) run the real build script against the repository's own `topics/` directory.
- **HTTP tests** use FastAPI's `TestClient` (backed by `httpx`) without starting an actual server.

---

## 11. Deployment Architecture

### Local Development

```bash
# Terminal 1: API server
uv run --directory . -m server.main          # FastAPI on port 9000

# Terminal 2: Static portal preview
cd dist && python3 -m http.server 8787       # Plain HTTP on 8787

# Terminal 3: Full daily pipeline (assemble + generate + build + serve)
bash run.sh
```

### Production (Tailscale network)

- FastAPI server runs on port `9000` on a Tailscale-connected host.
- Completed newsletter links point to `http://100.110.249.12:8787/<slug>/`.
- Telegram completion notifications are sent via `plugin:telegram@claude-plugins-official` (chat ID `1538018072`).

### Environment Requirements

| Requirement | Notes |
|---|---|
| Python ≥ 3.11 | `tomllib` stdlib (used in build.py) requires 3.11+ |
| `uv` | Package manager and script runner |
| `OPENROUTER_API_KEY` | Required for OpenRouter generation path |
| `claude` CLI | Required for `agent=claude` newsletter generation |
| `gemini` CLI | Required for `agent=gemini` newsletter generation |
| `gh` CLI with Copilot extension | Required for `agent=copilot` newsletter generation |
| `opencode` CLI | Required for `agent=opencode` newsletter generation |

### Dependency Summary (`pyproject.toml`)

```toml
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "notebooklm-py>=0.3",
]
dev = [
    "httpx>=0.28.1",   # TestClient for API tests
]
```

---

## 12. Extension and Evolution Patterns

### 12.1 Adding a New Newsletter Topic

**Via API (recommended):**
```bash
curl -X POST http://localhost:9000/api/topics \
  -H "Content-Type: application/json" \
  -d '{"name": "Rust Weekly", "description": "...", "accent": "prussian"}'
```

**Manual:**
1. Create `topics/<slug>/topic.md` with the Identity/Sources/Sections structure.
2. Create `topics/<slug>/site/template.html` (copy from an existing topic, update accent).
3. Run `uv run shared/assemble_prompt.py <slug>`.
4. `topics.json` is updated automatically when topic is created via the API. For manual creation, add an entry with `shared.topic_registry.save()`.

### 12.2 Adding a New Generation Agent

1. Add the agent name to `VALID_AGENTS` in `server/routers/topics.py` and `_AGENT_LABELS` in `shared/cli_newsletter_generation.py`.
2. Add a branch in `generate_with_cli()` with the CLI command.
3. Add a button in `dist/manage.html` (or regenerate from template).
4. No changes needed to the pipeline or job store.

### 12.3 Adding a New API Endpoint

1. Create or extend a router in `server/routers/`.
2. Register the router in `server/main.py` **before** the `StaticFiles` mount.
3. Add Pydantic request/response models in the same router file.
4. Add a test in `tests/test_<router_name>.py`.

### 12.4 Modifying the Build Output

Edit `shared/build.py`. Key extension points:
- `inject_nav()` — change the nav HTML structure
- `extract_metadata()` — parse additional metadata from generated HTML
- `_build_landing_page()` — change the portal landing page layout

Do **not** modify `shared/assets/style.css`. Put all new styles in `shared/portal.css`.

### 12.5 Changing Topic Metadata Schema

1. Update `_DEFAULTS` in `shared/topic_registry.py` with new fields and defaults.
2. The `save()` function merges with `_DEFAULTS` on every write — old registry entries will receive the default value on their next write.
3. Update `TopicCreate` Pydantic model in `server/routers/topics.py`.
4. Update `list_topics()` response in the same file.

---

## 13. Architectural Decision Records

### ADR-001: JSON Registry over TOML

**Context:** The original system stored topic metadata in `topics.toml`. TOML has no atomic write semantics and the Python `tomllib` module is read-only (no write support in stdlib).

**Decision:** Replace `topics.toml` with `topics.json`, managed exclusively through `shared/topic_registry.py`.

**Consequences:**
- (+) Atomic writes with temp-file rename pattern.
- (+) Thread-safe updates from the FastAPI pipeline.
- (+) Full CRUD available programmatically.
- (-) `topics.toml` must be kept in sync manually until fully deprecated.
- (-) Migration helper (`migrate_from_toml`) adds maintenance surface.

### ADR-002: Static File Build over Server-Side Rendering

**Context:** Newsletter issues are generated infrequently (daily or on-demand) but read frequently.

**Decision:** Pre-build all issue HTML to `dist/` and serve as static files.

**Consequences:**
- (+) Zero latency for readers; no per-request rendering.
- (+) `dist/` can be served from any static host with no Python runtime.
- (-) `dist/` must be rebuilt after every generation — the pipeline always ends with `build.py`.
- (-) `dist/` content is stale until next build; no live updates.

### ADR-003: Stdlib HTTP Client for OpenRouter

**Context:** The `openai` Python SDK is a natural fit for OpenRouter (which has an OpenAI-compatible API), but adds a large dependency.

**Decision:** Use Python stdlib `urllib.request` with manual JSON serialization.

**Consequences:**
- (+) Zero additional runtime dependencies.
- (+) Full control over timeout, headers, streaming.
- (-) More verbose than SDK calls.
- (-) SSE streaming requires manual line parsing.

### ADR-004: Multi-Agent Architecture

**Context:** Different users prefer different AI CLI tools (Claude, Gemini, Copilot, OpenCode). The OpenRouter path requires no local CLI installation.

**Decision:** Support both a stateless OpenRouter path and a CLI-delegation path via a single `agent` query parameter.

**Consequences:**
- (+) Users can choose the tool they have installed.
- (+) OpenRouter path is always available regardless of CLI installations.
- (-) CLI agent path depends on local tool availability.
- (-) CLI agents write files directly — output format is not validated by the server.

### ADR-005: API Routes Before Static Mount

**Context:** FastAPI's `StaticFiles` mounted on `/` acts as a catch-all. If registered before API routers, it swallows all `/api/*` requests.

**Decision:** All routers are registered in `_register_routers()` which is called before the `StaticFiles` mount.

**Consequences:**
- (+) Clear convention enforced by code structure.
- (-) Must be documented carefully; a new developer adding a router after the mount line would silently break the endpoint.

---

## 14. Architecture Governance

### Enforced Conventions

| Convention | Enforcement |
|---|---|
| All topic registry reads/writes go through `topic_registry.py` | Code review; no other module imports `topics.json` directly |
| API routes registered before static mount | `server/main.py` structure; enforced by ordering in `_register_routers()` |
| Slugs always created via `_slugify()` | Single function in `server/routers/topics.py`; documented in CLAUDE.md |
| `shared/assets/style.css` never modified | Repository convention; portal styles go in `shared/portal.css` |
| `prompt.md` never hand-authored | Enforced by convention: `assemble_prompt.py` is the only writer |
| Atomic file writes for registry | `save()` and `delete()` always use temp-then-rename pattern |

### Test-Driven Stability

The test suite covers all core modules. Running `uv run pytest` before merging is required. Tests use `tempfile.TemporaryDirectory` so they do not touch production `topics/` or `dist/` content.

---

## 15. Blueprint for New Development

### Starting a New Feature: Typical Workflow

1. **Identify the layer.** Is this a new API endpoint (routers layer), a new generation strategy (shared layer), or a build output change (build layer)?

2. **Register in the registry.** If the feature touches topic metadata, update `_DEFAULTS` in `topic_registry.py` and the `TopicCreate` Pydantic model.

3. **Write the implementation.** Follow the patterns in Section 9 (atomic writes, readiness gates, job lifecycle).

4. **Add a background job if long-running.** Use `jobs.create()` → `background_tasks.add_task(pipeline_fn, job_id, ...)` → return `{job_id}`. Update `jobs.update()` at each step.

5. **Register API routes before static mount.** Any new router must be included in `_register_routers()` in `server/main.py`.

6. **Write tests.** Add a test file in `tests/`. Use `tempfile.TemporaryDirectory` for isolation. Use FastAPI `TestClient` for HTTP tests.

7. **Run the full suite.** `uv run pytest`

### Common Pitfalls

| Pitfall | Avoidance |
|---|---|
| Importing `topics.json` directly | Always use `shared.topic_registry` |
| Registering a router after `StaticFiles` | Always add to `_register_routers()` |
| Hand-authoring `prompt.md` | Always call `assemble_prompt.assemble(slug)` |
| Non-atomic topic registry writes | Always use `topic_registry.save()` or `delete()` |
| Starting a slow operation in a sync handler | Dispatch to `BackgroundTasks` + return `job_id` |
| Using a slug not created by `_slugify()` | Call `_slugify(name)` for every new topic |
| Editing `shared/assets/style.css` | Add styles to `shared/portal.css` instead |
| Forgetting to rebuild `dist/` after generation | End every pipeline path with `_build_portal()` |

### File Organisation for a New Topic Type

```
topics/<new-slug>/
  topic.md                    ← author this: Identity + Sources + Sections
  site/
    template.html             ← copy from shared/templates/topic-template.html
                                  then update data-accent="<accent>"
```

Then register via API:
```bash
curl -X POST http://localhost:9000/api/topics \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Topic",
    "description": "Brief description",
    "accent": "prussian",
    "signal_label": "Signal",
    "topic_md": "<contents of topic.md>"
  }'
```

---

*This blueprint was generated on 2026-04-06. Recommend reviewing after any major architecture change, especially changes to the topic registry schema, generation agent list, or build output format.*
