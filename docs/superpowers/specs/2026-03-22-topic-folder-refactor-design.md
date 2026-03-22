# Topic Folder Refactor Design

## Goal

Refactor the newsletter repository so every topic lives in its own folder under `topics/`, while shared infrastructure lives under `shared/`. Preserve the generated site structure in `dist/` and avoid behavior changes to rendering, archive discovery, or topic URLs.

## Current Problems

- `claude-digest` is a root-level special case while other topics already live in their own folders.
- Shared infrastructure is mixed with topic content at the repository root.
- The build system depends on special-case path handling for `folder = "."`.
- The root directory does not clearly separate source content from system code.

## Approved Direction

Use a `topics/ + shared/` layout:

```text
newsletters/
  topics/
    claude-digest/
    google-ai/
    us-iran-war/
  shared/
    build.py
    portal.css
    templates/
    assets/
      style.css
  dist/
  topics.toml
  run.sh
  CLAUDE.md
```

## Repository Boundaries

### `topics/`

Each topic folder owns:

- `prompt.md`
- raw dated markdown source files like `YYYY-MM-DD.md`
- generated topic HTML files in `site/`
- topic-specific `site/template.html`

Each topic keeps the same internal shape so the build script can treat all topics uniformly.

### `shared/`

`shared/` owns only infrastructure:

- `shared/build.py`
- `shared/portal.css`
- `shared/templates/nav.html`
- `shared/templates/landing.html`
- `shared/assets/style.css`

No topic-owned prompts, content, or topic templates move into `shared/`.

## Configuration Changes

Update `topics.toml` so every topic uses an explicit path under `topics/`.

Example:

```toml
[claude-digest]
folder = "topics/claude-digest"
```

This removes the `folder = "."` special case and makes every topic resolve the same way.

## Build Script Changes

Move `build.py` to `shared/build.py` and update its path constants so it resolves:

- repository root
- `dist/` at the repository root
- shared templates in `shared/templates/`
- shared CSS in `shared/assets/style.css`
- topic paths from `topics.toml`

Behavior must stay the same:

- discover dated source files per topic
- discover archived HTML files in `<topic>/site/`
- use `<topic>/site/index.html` as the latest HTML
- inject navigation into each output page
- build the landing page in `dist/index.html`
- emit topic pages to `dist/<slug>/`

## Runner Changes

Update `run.sh` to:

- read prompts from `topics/<slug>/prompt.md`
- invoke `uv run shared/build.py`

The script should keep serving `dist/` from the repository root and should not change the served URL layout.

## Documentation Changes

Update `CLAUDE.md` to reflect:

- new topic locations under `topics/`
- shared infrastructure under `shared/`
- updated build command
- updated add-a-topic instructions

## Migration Steps

1. Create `topics/` and `shared/`.
2. Move the current root topic files into `topics/claude-digest/`.
3. Move `google-ai/` and `us-iran-war/` into `topics/`.
4. Move shared files into `shared/`.
5. Update `topics.toml`.
6. Update `shared/build.py` path resolution.
7. Update `run.sh`.
8. Update `CLAUDE.md`.
9. Rebuild `dist/` and verify output.

## Non-Goals

- Do not change topic slugs or generated URL paths.
- Do not redesign newsletter HTML or CSS behavior.
- Do not introduce shared prompt inheritance or topic templating abstractions.
- Do not move `dist/` out of the repository root.

## Verification

Verification should confirm:

- `uv run shared/build.py` completes successfully
- `dist/index.html` is generated
- each topic still generates `dist/<slug>/index.html`
- archived dated pages are still emitted
- shared CSS is copied from `shared/assets/style.css`
- navigation links still resolve correctly from topic pages

## Notes

This refactor is intended to normalize layout and reduce special cases, not to change output behavior. The main success criterion is cleaner source organization with identical site behavior after rebuild.
