# OpenRouter Migration Plan

> Historical planning doc. It records the migration analysis that led to the
> current implementation and may describe intermediate or superseded work.

## Executive Summary

At the time this plan was written, the repo did not use the Anthropic Python SDK directly. The live AI dependency was the `claude` CLI, plus one GitHub Action that used `ANTHROPIC_API_KEY`. That meant the migration was not a simple SDK transport swap.

The pipeline described here depended on Claude Code behaving like a local agent: it read prompt files, searched the web, wrote `topic.md` / `YYYY-MM-DD.md` / `site/index.html`, copied archive files, and may have triggered Telegram-oriented workflows. OpenRouter's OpenAI-compatible API can replace model inference, but it does not replace Claude Code's local tool execution by itself. The migration therefore needed two layers:

1. Replace direct Claude/Anthropic entry points with a shared OpenRouter client.
2. Move file I/O, build steps, and any Telegram delivery into explicit repo code instead of relying on agentic CLI behavior.

## Findings

- Direct runtime AI call sites: `run.sh`, `server/pipeline.py`
- Prompt files tightly coupled to Claude Code tool-use: `shared/prompts/ops-guide.md`, `shared/prompts/on-demand-listener.md`
- Operator/config references that must be updated: `CLAUDE.md`, `skill/newsletter-create/SKILL.md`, `.github/workflows/claude-review.yml`
- No Anthropic SDK imports were found in Python.
- No hard-coded `claude-*` model IDs were found in executable Python or shell code.
- `shared/assemble_prompt.py` and `shared/build.py` do not call Claude/Anthropic directly, but they sit on the hot path and their contracts will need to change or be validated during migration.

## Call-Site Inventory

| File | Lines | Current pattern | OpenRouter equivalent | Notes / risk |
|---|---:|---|---|---|
| `run.sh` | 34-39 | Assembles `prompt.md`, then runs `claude -p "$(cat .../prompt.md)" --dangerously-skip-permissions` | Replace with a host-side runner, e.g. `uv run python -m shared.openrouter_runner --prompt-file topics/$slug/prompt.md --model anthropic/claude-sonnet-4.5` that calls `OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY).chat.completions.create(...)` | High risk because current prompt expects web search + filesystem writes by the model |
| `run.sh` | 62-65 | Starts persistent listener with `nohup claude -p "$(cat shared/prompts/on-demand-listener.md)"` | No direct 1:1 replacement. Requires a new long-running Python listener that receives events and calls OpenRouter per request | Highest risk; current design assumes persistent Claude Code session semantics |
| `server/pipeline.py` | 30-42 | `_run_claude()` shells out to `claude -p task --dangerously-skip-permissions` | Replace with `_run_openrouter(task: str, model: str)` using the OpenAI SDK against `https://openrouter.ai/api/v1` | Medium risk helper swap, but output contract changes materially |
| `server/pipeline.py` | 68-79 | Topic creation job asks Claude Code to use the `newsletter-create` skill and write `topics/{slug}/topic.md` | Call OpenRouter with a structured prompt and return text/JSON; Python must write `topics/{slug}/topic.md` itself | High risk because skills/tooling disappear |
| `server/pipeline.py` | 98-100 | First issue generation reads `prompt.md` and lets Claude create markdown + HTML files implicitly | Call OpenRouter for structured output such as `{raw_markdown, html, summary}`; Python writes `YYYY-MM-DD.md`, `site/index.html`, `site/YYYY-MM-DD.html` | High risk; this is the core pipeline rewrite |
| `server/pipeline.py` | 137-138 | Existing-topic newsletter generation uses `_run_claude(prompt_path.read_text(), max_turns=25)` | Same OpenRouter structured generation path as above | High risk for same reason |
| `server/pipeline.py` | 192-203 | Best-effort `topic.md` generation again relies on Claude writing files | Same as topic creation path: OpenRouter returns content, Python persists it | High risk |
| `shared/prompts/ops-guide.md` | 3-31 | Imperative agent prompt: search web, save markdown/html, run build, send Telegram, exit | Replace with a generation spec that asks OpenRouter only for content artifacts, not tool execution; move side effects into Python | High risk because current prompt assumes agent tools |
| `shared/prompts/on-demand-listener.md` | 5-11 | Prompt assumes a persistent Claude Code session that listens for Telegram messages | Replace with app code plus an API request template, or remove until a real listener is implemented | Highest risk |
| `shared/assemble_prompt.py` | 16-38 | Builds `prompt.md` for Claude Code by concatenating topic + design + ops guides | Likely keep file assembly, but change the final prompt contract so it targets a stateless OpenRouter completion instead of CLI-agent behavior | Low risk; indirect dependency only |
| `shared/build.py` | 21-29, 189-256 | Builds the portal from generated files; no Claude/Anthropic call | No API change needed | Low risk; validate output format compatibility |
| `server/routers/topics.py` | 83-87, 112-116 | User-facing docs/comments say topic generation happens via Claude CLI; router dispatches pipeline jobs | Update text to provider-neutral or OpenRouter-specific wording; dispatch remains to pipeline | Low risk; no runtime model call here |
| `CLAUDE.md` | 7, 21-23, 33-35, 53, 98 | Operator docs instruct users to run `claude -p ...` and describe Claude-based generation | Update examples to the new runner and provider-neutral wording | Low risk documentation |
| `skill/newsletter-create/SKILL.md` | 102-108 | Tells operators to run `claude -p "$(cat .../prompt.md)"` | Update to invoke the new OpenRouter-backed runner | Low risk documentation / workflow |
| `.github/workflows/claude-review.yml` | 20-22 | Uses `anthropics/claude-code-action@v1` with `secrets.ANTHROPIC_API_KEY` | Either remove/disable, or replace with a different review workflow that explicitly calls OpenRouter through a script | Medium risk because there is no drop-in OpenRouter equivalent to this GitHub Action in-repo today |

## Equivalent OpenRouter Call Shape

Use one shared client shape everywhere:

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
)

response = client.chat.completions.create(
    model=os.environ.get("OPENROUTER_MODEL_NEWSLETTER", "anthropic/claude-sonnet-4.5"),
    messages=[
        {"role": "system", "content": "You generate newsletter artifacts in a strict schema."},
        {"role": "user", "content": prompt_text},
    ],
)

text = response.choices[0].message.content
```

For topic generation, use a separate model env such as `OPENROUTER_MODEL_TOPIC_MD`. For newsletter generation, prefer structured output so Python can deterministically write files.

## Environment Variable Changes

Required:

- `OPENROUTER_API_KEY` replaces `ANTHROPIC_API_KEY`
- `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`

Recommended additions:

- `OPENROUTER_MODEL_TOPIC_MD=anthropic/claude-sonnet-4.5`
- `OPENROUTER_MODEL_NEWSLETTER=anthropic/claude-sonnet-4.5`
- `OPENROUTER_MODEL_FALLBACK=anthropic/claude-3.5-sonnet`

Optional metadata headers if the client wrapper supports them:

- `OPENROUTER_HTTP_REFERER`
- `OPENROUTER_APP_TITLE`

Config/secret updates required:

- Any shell startup files or deployment environments currently exporting `ANTHROPIC_API_KEY`
- GitHub Actions secrets: replace `ANTHROPIC_API_KEY` with `OPENROUTER_API_KEY`
- Any local operator docs that assume `claude` CLI auth

## SDK / CLI Swap Strategy

### 1. Introduce a single provider wrapper

Create one shared Python module responsible for:

- constructing the OpenRouter client
- selecting models via env vars
- normalizing retries / timeouts / error handling
- returning plain text or structured JSON to callers

Do not let `run.sh` or `server/pipeline.py` talk to OpenRouter directly in multiple ways.

### 2. Stop depending on Claude Code side effects

Current prompts assume the model can:

- search the web
- read templates from disk
- write markdown files
- write HTML files
- copy archive files
- trigger Telegram delivery
- run the build

OpenRouter should only be used for content generation. The host application should own:

- reading prompt/template inputs
- writing `topic.md`
- writing `topics/{slug}/YYYY-MM-DD.md`
- writing `topics/{slug}/site/index.html`
- copying `site/YYYY-MM-DD.html`
- running `shared/build.py`
- sending Telegram messages, if still required

### 3. Change prompt contracts

Replace imperative "do these filesystem actions" prompts with prompts that return explicit artifacts, ideally JSON:

- topic generation: `{ "topic_md": "..." }`
- newsletter generation: `{ "raw_markdown": "...", "html": "...", "summary": "..." }`

This is the key design change that makes the migration reliable.

### 4. Keep model choice configurable

Even if the first migration still uses Anthropic models through OpenRouter, all runtime code should become provider-agnostic and model-configurable.

## Migration Steps Ordered By Risk

### Low Risk

1. Document the current dependency surface and add provider-neutral terminology in docs.
2. Add `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, and model env vars to deployment/local-env docs.
3. Add a shared OpenRouter client wrapper module and unit tests around request construction and response parsing.
4. Update `CLAUDE.md` and `skill/newsletter-create/SKILL.md` examples to call the new runner instead of `claude -p`.
5. Update `server/routers/topics.py` docstrings and messages to stop referring to "Claude CLI".

### Medium Risk

6. Replace `server/pipeline.py::_run_claude()` with an OpenRouter-backed helper behind the same high-level interface.
7. Replace `run.sh` newsletter generation call with a Python runner that reads `prompt.md`, calls OpenRouter, and writes outputs explicitly.
8. Decide the fate of `.github/workflows/claude-review.yml`: replace with an in-repo review script that calls OpenRouter, or disable the workflow until a real replacement exists.

### High Risk

9. Refactor `shared/prompts/ops-guide.md` from an agent-instructions document into a content-generation schema that does not assume local tools.
10. Refactor topic generation flows in `server/pipeline.py` so OpenRouter returns `topic.md` content and Python writes it.
11. Refactor newsletter generation flows so OpenRouter returns content artifacts and Python handles all file writes and archive copying.
12. Implement explicit Telegram delivery in app code if it is still a requirement; remove it from prompts otherwise.
13. Replace or remove the persistent `on-demand-listener` design, since a long-lived Claude Code session is not equivalent to OpenRouter inference calls.

## Testing Checklist

### Static audit

- Confirm there are no remaining executable `claude` invocations in `.sh`, `.py`, `.md` operator docs, or GitHub workflows.
- Confirm there are no remaining `ANTHROPIC_API_KEY` references outside historical newsletter content.
- Confirm no runtime path imports an Anthropic SDK.

### Unit tests

- Test shared OpenRouter client construction with `OPENROUTER_API_KEY` and `OPENROUTER_BASE_URL`.
- Test model selection from env vars.
- Test response parsing for both topic generation and newsletter generation.
- Test failure handling for non-200 responses, timeouts, and empty model outputs.

### Pipeline tests

- Topic creation path writes `topics/{slug}/topic.md` from returned model content.
- Newsletter generation path writes:
  - `topics/{slug}/YYYY-MM-DD.md`
  - `topics/{slug}/site/index.html`
  - `topics/{slug}/site/YYYY-MM-DD.html`
- `shared/build.py` still succeeds after generated output format changes.
- Existing API endpoints continue returning the same job lifecycle states.

### Manual verification

- Run the equivalent of the daily pipeline for one existing topic.
- Create one brand-new topic through the API and verify `topic.md` generation.
- Verify `dist/` pages render correctly after the build.
- Verify any Telegram notification path still works, or confirm it is intentionally disabled.
- Verify the on-demand media endpoints still work after newsletter generation changes.

## Rollback Procedure

1. Keep the first OpenRouter migration behind a feature flag or provider env switch, for example `LLM_PROVIDER=claude_cli|openrouter`.
2. Preserve the current `claude` execution path until one end-to-end topic run succeeds under OpenRouter.
3. If output quality, file generation, or job stability regresses:
   - switch `LLM_PROVIDER` back to `claude_cli`
   - restore `ANTHROPIC_API_KEY` in the affected environment
   - disable any new OpenRouter-specific workflow changes
4. Do not delete the old prompt files immediately; keep them until the new structured prompts are validated.
5. Roll back in this order:
   - runtime provider switch
   - CI/workflow changes
   - doc/env changes

## Recommended First Implementation Slice

The safest first slice is not "swap every call site at once." It is:

1. add a shared OpenRouter client,
2. convert one topic-generation path to structured output,
3. convert one newsletter-generation path to structured output,
4. verify generated files and portal build,
5. only then switch `run.sh` and background jobs over broadly.

That sequence minimizes blast radius and exposes the real migration risk early: replacing Claude Code tool-use with explicit application logic.
