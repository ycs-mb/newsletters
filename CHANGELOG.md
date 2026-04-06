# Changelog

## 2026-04-06

- Added `docs/Project_Architecture_Blueprint.md` — comprehensive architecture reference generated from the architecture-blueprint-generator skill, covering all layers, data flows, ADRs, extension patterns, and a new-development blueprint.
- Updated `skill/newsletter-create/SKILL.md` to use `topics.json` (via `shared/topic_registry.py`) instead of the legacy `topics.toml`, and to document the manage UI agent selector buttons.

## 2026-04-04

- Added agent selection to newsletter generation in the manage UI.
- Added `topic.md` viewing and copy support from the manage UI.
- Added agent-aware newsletter dispatch through `POST /api/topics/{slug}/newsletter`.
- Added CLI newsletter generation support in `shared/cli_newsletter_generation.py`.
- Refreshed portal build output dates in `dist/`.


