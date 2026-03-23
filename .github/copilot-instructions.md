# Copilot instructions for newsletter-portal

## Build, test, and run commands

- Install dependencies: `uv sync`
- Build static portal output: `uv run shared/build.py`
- Run full daily pipeline (assemble prompts, generate topics via Claude, build, start server/listener): `bash run.sh`
- Run API/static server only: `uv run --directory . -m server.main`
- Serve built `dist/` directly for quick preview: `cd dist && python3 -m http.server 8787`

### Tests

- Run full test suite: `uv run pytest`
- Run a single test file: `uv run pytest tests/test_build.py`
- Run a single test case: `uv run pytest tests/test_jobs.py::JobStoreTest::test_new_job_is_pending`

## High-level architecture

The project has two cooperating paths:

1. **Content generation path**
   - Topic research prompt source lives at `topics/<slug>/topic.md`.
   - `shared/assemble_prompt.py` composes `topic.md` + `shared/prompts/design-guide.md` + `shared/prompts/ops-guide.md` into `topics/<slug>/prompt.md`.
   - Claude CLI executes that prompt and writes issue artifacts into `topics/<slug>/site/` (`index.html` + dated `YYYY-MM-DD.html`) and dated markdown in topic root.

2. **Portal build and serving path**
   - `shared/build.py` reads `topics.toml`, discovers per-topic dated files, injects portal nav/media UI into topic HTML, and writes unified output to `dist/`.
   - `server/main.py` serves `/api/*` routers (generation, topics, jobs) and mounts `dist/` static files at `/`.
   - On-demand media generation uses `/api/generate/*` + `/api/jobs/*` with background work coordinated in `server/pipeline.py` and in-memory status in `server/jobs.py`.

`topics.toml` is the canonical registry for topics (slug → folder/name/accent/labels). Build and API behavior both depend on it.

## Key repository conventions

- `shared/assets/style.css` is a **locked editorial design system**; do not edit it. Put portal-level styling in `shared/portal.css`.
- Topic templates/pages rely on `{{PLACEHOLDER}}` markers (including `{{MEDIA_SECTION}}`) that builders/generators fill; preserve these markers.
- Topic folder contract is strict: `topics/<slug>/` contains `topic.md`, generated `prompt.md`, `site/index.html`, optional `site/YYYY-MM-DD.html`, and optional `media/` assets.
- Build discovery is date-driven: dated issue files use exact `YYYY-MM-DD` naming for both markdown (`topic root`) and archived HTML (`site/`).
- In FastAPI startup, API routers must be registered before mounting static files (see `server/main.py`), otherwise static routing can shadow API paths.
- Job IDs are short UUID prefixes with thread-safe updates in an in-memory store (`server/jobs.py`); jobs are intentionally ephemeral across restarts.
- Pipeline concurrency assumptions are explicit: `ThreadPoolExecutor(max_workers=4)` and a lock for appending `topics.toml` entries.
- Slug creation for new topics is centralized in `server/routers/topics.py::_slugify`; reuse it instead of introducing alternate slug rules.
