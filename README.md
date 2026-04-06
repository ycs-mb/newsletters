# Newsletter Portal

Automated portal for daily intelligence briefings.

The repository stores a dynamic set of newsletter topics in `topics.json`,
keeps each topic's research brief in `topics/<slug>/topic.md`, assembles a
runtime prompt in `topics/<slug>/prompt.md`, and then generates the issue
artifacts that are published into `dist/`.

## What It Does

- Tracks newsletter topics in a JSON registry.
- Scaffolds per-topic folders with templates and archives.
- Assembles `topic.md` plus shared design and ops guides into `prompt.md`.
- Generates newsletter issues through the API, the manage UI, or the daily
  runner.
- Builds a static portal with topic archives and a landing page.

## Recent Changes

- Newsletter generation now accepts an `agent` selector.
- The manage page adds buttons for `Claude`, `Gemini`, `Copilot`,
  `OpenCode`, and `OpenRouter`.
- Each topic now has a `topic.md` viewer modal in the manage UI.
- The API returns the selected agent from `POST /api/topics/{slug}/newsletter`.
- `shared/cli_newsletter_generation.py` adds CLI-backed newsletter runs.

## Layout

- `server/` - FastAPI app, topic routes, and pipeline jobs.
- `shared/` - prompt assembly, build scripts, generation helpers, and assets.
- `topics/` - topic-specific source material and generated outputs.
- `dist/` - built static site served to readers.
- `docs/` - planning notes and design specs.

## Running Locally

Build the portal:

```bash
uv run shared/build.py
```

Run the full daily pipeline:

```bash
bash run.sh
```

Serve the static output:

```bash
cd dist && python3 -m http.server 8787
```

Run the API server:

```bash
uv run --directory . -m server.main
```

Generate one issue directly with the OpenRouter-backed helper:

```bash
uv run python -c "from shared.newsletter_generation import generate_newsletter_issue; generate_newsletter_issue('google-ai')"
```

Open the manage page at:

```text
http://localhost:9000/manage.html
```

## GitHub Hosting and CI/CD

This repository now includes two GitHub Actions workflows:

- `.github/workflows/ci.yml` runs the test suite and rebuilds the static portal on pull requests and pushes to `main`.
- `.github/workflows/pages.yml` runs the same checks on `main`, builds `dist/`, and deploys the static site to GitHub Pages.

### What GitHub Pages Hosts

GitHub Pages can publish the reader-facing static portal from `dist/`, including:

- the landing page
- topic issue pages
- archive pages

The FastAPI API is **not** hosted on GitHub Pages. Newsroom actions such as creating topics, generating newsletters, polling jobs, and on-demand media generation still require a live backend.

### GitHub Pages Setup

1. In GitHub, enable **Pages** and set the source to **GitHub Actions**.
2. Let the `Deploy GitHub Pages` workflow publish `dist/` from `main`.
3. If you only want a public read-only portal, no extra configuration is required.
4. If you also deploy the API elsewhere, add a repository variable named `PORTAL_API_BASE_URL` with the full API base URL, for example:

   ```text
   https://your-api.example.com/api
   ```

   When that variable is present, the deployed site points newsroom and media actions at that backend. Without it, the GitHub Pages site stays in read-only mode.

## Topic Flow

1. Register the topic in `topics.json`.
2. Write `topics/<slug>/topic.md`.
3. Run `uv run shared/assemble_prompt.py <slug>` to create `prompt.md`.
4. Generate the issue via the manage UI or the newsletter API.
5. Build `dist/` with `uv run shared/build.py`.
