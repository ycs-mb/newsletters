# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## What This Is

Automated newsletter portal for dynamic daily briefings. Topics are registered
in `topics.json`, each topic keeps its research brief in `topics/<slug>/topic.md`,
and the portal builds static issue pages into `dist/`.

The current system supports two newsletter generation paths:

- the default OpenRouter-backed helper in `shared/newsletter_generation.py`
- CLI-backed runs through the manage UI via `shared/cli_newsletter_generation.py`

## Commands

```bash
# Build the portal (generates dist/ from topic HTML files)
uv run shared/build.py

# Run all newsletters + build + serve (full daily pipeline)
bash run.sh

# Serve the portal locally
cd dist && python3 -m http.server 8787

# Run the API server
uv run --directory . -m server.main

# Generate one newsletter issue directly with the default OpenRouter path
uv run python -c "from shared.newsletter_generation import generate_newsletter_issue; generate_newsletter_issue('google-ai')"

# Run tests
uv run pytest
```

## Architecture

### Generation Flow

`topics/<slug>/topic.md` -> `shared/assemble_prompt.py` -> `topics/<slug>/prompt.md` -> generator -> `topics/<slug>/site/index.html` + `topics/<slug>/site/YYYY-MM-DD.html` -> `shared/build.py` -> `dist/`

Each topic has a `topic.md` research brief that gets assembled with the shared
design and ops guides into `prompt.md`. That prompt is then used by the
newsletter generator to write the issue artifacts. The build script assembles
everything into `dist/` with navigation.

Newsletter generation is gated on `topic.md` existence. A topic must be
registered in `topics.json` and have `topic.md` on disk before newsletters can
be generated.

### Topic Registry

Topics are managed through `shared/topic_registry.py`, backed by `topics.json`
at the repo root. The registry provides thread-safe CRUD (`list_all`, `save`,
`delete`) and readiness checks (`is_ready`, `topic_md_exists`, `get_status`).

All consumers (`build.py`, server routers, `run.sh`) read through this module.
It is the single source of truth for topic metadata.

### Topic Structure

Each topic folder under `topics/<slug>/` contains:

- `topic.md` - required research brief
- `prompt.md` - assembled runtime prompt
- `site/template.html` - newsletter template
- `site/index.html` - latest generated issue
- `site/YYYY-MM-DD.html` - dated archive
- `YYYY-MM-DD.md` - raw markdown issue text

### API Endpoints

- `GET /api/topics` - list all topics with readiness status
- `GET /api/topics/{slug}` - get one topic with full status
- `POST /api/topics` - create a new topic
- `PUT /api/topics/{slug}/topic-md` - upload or replace `topic.md`
- `GET /api/topics/{slug}/topic-md` - read `topic.md`
- `POST /api/topics/{slug}/newsletter?agent=openrouter|claude|gemini|copilot|opencode` - request newsletter generation
- `POST /api/generate/{slug}/{date}/{type}` - on-demand media generation
- `GET /api/jobs/{job_id}` - check background job status

### Shared Infrastructure (`shared/`)

- `shared/topic_registry.py` - JSON-backed topic CRUD
- `shared/build.py` - static site generator
- `shared/assemble_prompt.py` - composes `topic.md` + design guide + ops guide -> `prompt.md`
- `shared/newsletter_generation.py` - OpenRouter-backed newsletter generator
- `shared/cli_newsletter_generation.py` - CLI agent runner for manual generation
- `shared/portal.css` - portal navigation and landing page styles
- `shared/templates/` - nav and landing page templates
- `shared/assets/style.css` - locked editorial design system copied into `dist/style.css`

### Build System (`shared/build.py`)

Pure stdlib Python (no deps, uses `tomllib`). Reads topic metadata, discovers
dated HTML archives in each topic's `site/` folder, injects a navigation bar
into each page, rewrites CSS paths, and generates a landing page.

Key functions:

- `inject_nav()` inserts nav HTML after the `<body>` tag
- `extract_metadata()` regex-parses signal ratings from generated HTML
- `discover_html_archives()` finds `site/YYYY-MM-DD.html` files

### Adding a New Topic

1. Create `topics/<slug>/` with `topic.md` and `site/template.html`.
2. Add dated markdown and generated HTML under `topics/<slug>/`.
3. Add an entry to `topics.toml` with name, description, accent, and folder.
4. Run `uv run shared/build.py` - the new topic is discovered automatically.

## Design System Rules

- `shared/assets/style.css` is locked - never modify it.
- `shared/portal.css` supplements the nav bar, landing page, and archive styles.
- Templates use `{{PLACEHOLDER}}` markers - generators fill them, never alter the structure.
- Accent colors: `terracotta` (`#c44b1a`), `sage` (`#2d6b42`), `prussian` (`#1a3552`), `gold` (`#9a7b1a`)
- Highlight card categories: CSS classes `voice`, `model`, `company`, `promo`
- Typography: Cormorant Garamond (display), Literata (body), Fira Code (mono)

## Serving

The FastAPI app serves `dist/` on port `9000` by default when `server.main`
is run directly. The static portal still lives at port `8787` when served via
`python3 -m http.server 8787`.

The manage page is available at `/manage.html` and now exposes an agent
selector plus a `topic.md` viewer.

## Telegram Integration

Newsletters send completion messages via the `plugin:telegram` channel.
Chat ID: `1538018072`. Links point to the Tailscale URL plus the topic path.
