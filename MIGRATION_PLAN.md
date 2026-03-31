# OpenRouter Migration Plan

Date: 2026-04-01

## Goal

Replace all Claude CLI and Anthropic-hosted AI invocation paths in this repository with explicit OpenRouter API calls, while preserving the current prompt content and newsletter outputs as closely as possible.

## Non-Goal

This document does not implement the migration. It defines the exact file-by-file work needed to do it safely.

## Key Constraint

The current system does not just "ask a model for text." It asks Claude Code to:

1. search the web
2. read local files
3. write `topic.md`, `YYYY-MM-DD.md`, `site/index.html`, and dated archives
4. build the portal
5. send a Telegram message

An OpenRouter chat completion is stateless and returns text only. The conservative migration is therefore:

1. keep the prompt content as the editorial source of truth
2. change prompts so they request structured text output instead of agent-side file writes
3. move all file writes and orchestration into local Python or shell code
4. call OpenRouter through one shared client, never through scattered inline HTTP logic

## Audit Summary

### Runtime AI invocation sites found

| File | Lines | Current behavior | Migration impact |
|---|---:|---|---|
| `run.sh` | 37-39 | Runs `claude -p "$(cat .../prompt.md)"` for each ready topic | Replace with a local runner that reads `prompt.md`, calls OpenRouter, and writes files locally |
| `run.sh` | 61-65 | Starts a long-lived `claude -p` listener with `shared/prompts/on-demand-listener.md` | Replace or remove; raw OpenRouter calls are not a drop-in persistent CLI listener |
| `server/pipeline.py` | 30-42 | `_run_claude()` shells out to `claude -p` | Replace with `_run_openrouter()` backed by a shared client |
| `server/pipeline.py` | 68-79 | Topic creation asks Claude to create `topics/{slug}/topic.md` | Change to prompt-for-content, then write `topic.md` in Python |
| `server/pipeline.py` | 98-100 | First newsletter generation shells prompt to Claude | Change to OpenRouter response parsing plus local writes |
| `server/pipeline.py` | 137-138 | Existing-topic newsletter generation shells prompt to Claude | Same replacement as above |
| `server/pipeline.py` | 192-203 | Background `topic.md` generation shells prompt to Claude | Same replacement as topic creation |
| `.github/workflows/claude-review.yml` | 20-22 | Uses `anthropics/claude-code-action@v1` with `ANTHROPIC_API_KEY` | Replace with a repo script that calls OpenRouter, or remove if this review path is not needed |

### Prompt and operator files that must change because they encode Claude-specific behavior

| File | Lines | Current behavior | Migration impact |
|---|---:|---|---|
| `shared/prompts/ops-guide.md` | 5-24 | Tells Claude to search, write files, build, and send Telegram | Rewrite to request structured output only; orchestration moves into code |
| `topics/google-ai/prompt.md` | assembled file | Bakes Claude-side actions into prompt | Will regenerate after `shared/prompts/ops-guide.md` changes |
| `topics/claude-digest/prompt.md` | assembled file | Same | Same |
| `topics/us-iran-war/prompt.md` | assembled file | Same | Same |
| `topics/indian-parliament-news/prompt.md` | assembled file | Same | Same |
| `shared/prompts/on-demand-listener.md` | 1-11 | Describes a persistent Claude Code session | Needs redesign or removal |
| `CLAUDE.md` | 21-35, 53 | Documents `claude -p` and Claude-driven generation flow | Update commands and architecture docs |
| `skill/newsletter-create/SKILL.md` | 102-108 | Tells operator to run `claude -p` on `prompt.md` | Update to the new runner entrypoint |
| `shared/templates/manage.html` | 706, 715 | UI copy explicitly says "Claude CLI" | Update to provider-neutral or OpenRouter-specific copy |

### Files explicitly audited with no direct AI invocation

| File | Result |
|---|---|
| `.collaborator/config.json` | No Claude or AI invocation; no migration code needed |
| `.claude/settings.local.json` | No runtime AI invocation; only local tool permissions |
| `shared/assemble_prompt.py` | No AI call itself, but its outputs change because prompt layers change |
| `shared/notebooklm_runner.py` | No Claude/OpenRouter call; unaffected except surrounding orchestration order |

## OpenRouter API Shape

Research source: official OpenRouter docs and model pages checked on 2026-04-01.

### Endpoint

`POST https://openrouter.ai/api/v1/chat/completions`

### Required auth

- Env var: `OPENROUTER_API_KEY`
- HTTP header: `Authorization: Bearer $OPENROUTER_API_KEY`
- Never hardcode keys in source, prompts, docs, or workflow files

### Recommended optional headers

- `HTTP-Referer: <repo or deployment URL>`
- `X-Title: newsletters`

These are optional but recommended by OpenRouter for app identification.

### Minimal request shape

```json
{
  "model": "anthropic/claude-sonnet-4.6",
  "messages": [
    {
      "role": "user",
      "content": "<full prompt text>"
    }
  ]
}
```

### Minimal response extraction

Read:

```json
choices[0].message.content
```

The migration should normalize both string and array-form content defensively, but the expected happy path is a text string.

### Example `curl`

```bash
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "HTTP-Referer: http://100.110.249.12:8787" \
  -H "X-Title: newsletters" \
  -d '{
    "model": "anthropic/claude-sonnet-4.6",
    "messages": [
      {"role": "user", "content": "'"$(python - <<'PY'
from pathlib import Path
print(Path("topics/google-ai/prompt.md").read_text())
PY
)"'"}
    ]
  }'
```

## Model Mapping

As of 2026-04-01, OpenRouter lists:

- `anthropic/claude-sonnet-4.6`
- `anthropic/claude-opus-4.6`
- older still-available variants including `anthropic/claude-sonnet-4.5` and `anthropic/claude-opus-4.5`

Recommended mapping:

| Use case | Recommended model | Reason |
|---|---|---|
| Default newsletter generation | `anthropic/claude-sonnet-4.6` | Best cost/performance default for recurring long prompts |
| Topic creation (`topic.md`) | `anthropic/claude-sonnet-4.6` | Enough quality, lower cost than Opus |
| Optional manual high-fidelity fallback | `anthropic/claude-opus-4.6` | Best quality for difficult or degraded runs |
| Conservative compatibility fallback | `anthropic/claude-sonnet-4.5` | Useful if output drift appears after 4.6 cutover |

Recommended env vars:

- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`
- `OPENROUTER_MODEL_NEWSLETTER=anthropic/claude-sonnet-4.6`
- `OPENROUTER_MODEL_TOPIC_MD=anthropic/claude-sonnet-4.6`
- `OPENROUTER_MODEL_FALLBACK=anthropic/claude-opus-4.6`
- `OPENROUTER_HTTP_REFERER=http://100.110.249.12:8787`
- `OPENROUTER_APP_TITLE=newsletters`

## Proposed Shared Helper Modules

### New file: `shared/openrouter_client.py`

Responsibility:

- load and validate env vars
- send chat completion requests
- normalize the returned assistant text
- centralize timeouts, headers, and error formatting

Proposed API:

```python
def chat_completion(prompt: str, *, model: str, timeout: int = 600) -> str: ...
```

Implementation notes:

- prefer stdlib `urllib.request` plus `json` to avoid adding a dependency just for one API client
- raise `RuntimeError` with HTTP status and short body excerpts
- do not silently retry in v1; keep behavior obvious

### New file: `shared/newsletter_generation.py`

Responsibility:

- read a topic's assembled `prompt.md`
- call `shared.openrouter_client`
- parse structured output
- write:
  - `topics/<slug>/YYYY-MM-DD.md`
  - `topics/<slug>/site/index.html`
  - `topics/<slug>/site/YYYY-MM-DD.html`

Proposed API:

```python
def generate_newsletter_issue(slug: str, *, date: str | None = None) -> dict[str, str]: ...
```

### New file: `shared/topic_md_generation.py`

Responsibility:

- build the topic-creation prompt
- call OpenRouter
- return `topic.md` text only

Proposed API:

```python
def generate_topic_md(name: str, description: str, focus_areas: str, slug: str) -> str: ...
```

## Required Prompt Contract Change

This is the most important migration step.

### Current contract

The prompt tells Claude Code to search, read files, write files, copy files, build the portal, and send Telegram.

### Proposed contract

The prompt should tell the model to return structured content only. Local code will perform all file writes and orchestration.

Recommended output shape for newsletter generation:

```json
{
  "raw_markdown": "...",
  "html": "...full rendered issue html...",
  "top_story_summary": "..."
}
```

Recommended output shape for topic generation:

```json
{
  "topic_md": "...markdown..."
}
```

Conservative prompt instruction:

- keep the editorial/research instructions
- remove instructions that imply filesystem access
- explicitly require valid JSON only
- tell the model not to wrap JSON in Markdown fences

## File-by-File Migration Plan

### 1. `shared/openrouter_client.py` (new)

Create the shared OpenRouter client first.

Before:

```python
# file does not exist
```

After:

```python
from __future__ import annotations

import json
import os
from urllib import request, error


def chat_completion(prompt: str, *, model: str, timeout: int = 600) -> str:
    api_key = os.environ["OPENROUTER_API_KEY"]
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if os.environ.get("OPENROUTER_HTTP_REFERER"):
        headers["HTTP-Referer"] = os.environ["OPENROUTER_HTTP_REFERER"]
    if os.environ.get("OPENROUTER_APP_TITLE"):
        headers["X-Title"] = os.environ["OPENROUTER_APP_TITLE"]
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    ...
```

### 2. `shared/topic_md_generation.py` (new)

Create a helper that asks OpenRouter for `topic.md` content and returns a string. Python writes the file after the call succeeds.

Before:

```python
# file does not exist
```

After:

```python
from shared.openrouter_client import chat_completion


def generate_topic_md(name: str, description: str, focus_areas: str, slug: str) -> str:
    prompt = (
        "Generate topic.md content only as valid JSON with key topic_md.\\n"
        f"Topic name: {name}\\n"
        f"Description: {description}\\n"
        f"Focus areas: {focus_areas}\\n"
        f"Slug: {slug}\\n"
        "Do not include code fences."
    )
    content = chat_completion(
        prompt,
        model=os.environ.get("OPENROUTER_MODEL_TOPIC_MD", "anthropic/claude-sonnet-4.6"),
    )
    ...
```

### 3. `shared/newsletter_generation.py` (new)

Centralize newsletter generation so both `run.sh` and `server/pipeline.py` use the same code path.

Before:

```python
# file does not exist
```

After:

```python
from shared.openrouter_client import chat_completion


def generate_newsletter_issue(slug: str, *, date: str | None = None) -> dict[str, str]:
    prompt = (REPO_ROOT / "topics" / slug / "prompt.md").read_text()
    content = chat_completion(
        prompt,
        model=os.environ.get("OPENROUTER_MODEL_NEWSLETTER", "anthropic/claude-sonnet-4.6"),
    )
    # parse JSON -> raw_markdown/html/top_story_summary
    # write markdown, index.html, dated archive
    ...
```

### 4. `shared/prompts/ops-guide.md`

Rewrite the prompt from "take actions in my repo" to "return structured content for local code to save."

Before:

```markdown
1. Search the web thoroughly for all sections in the topic brief above.
2. Compile newsletter content.
3. Save raw markdown to: `~/newsletters/topics/{SLUG}/YYYY-MM-DD.md`
...
8. Send one Telegram message to chat_id 1538018072:
```

After:

```markdown
1. Research the topic thoroughly using the context and sources above.
2. Compile the issue content.
3. Return valid JSON only with keys:
   - `raw_markdown`
   - `html`
   - `top_story_summary`
4. The `html` value must be the fully rendered newsletter HTML that fits the template contract.
5. Do not describe filesystem actions, shell commands, or Telegram actions.
6. Do not wrap the JSON in Markdown fences.
```

### 5. `shared/assemble_prompt.py`

The code can likely remain unchanged. The migration work here is to confirm no logic changes are needed once the prompt layers are updated.

Before:

```python
prompt = "\n\n---\n\n".join([topic_text, design_text, ops_text])
```

After:

```python
prompt = "\n\n---\n\n".join([topic_text, design_text, ops_text])
```

Decision:

- no functional change expected
- regenerate `topics/*/prompt.md` after changing `shared/prompts/ops-guide.md`

### 6. `server/pipeline.py`

Replace the generic Claude subprocess wrapper with explicit OpenRouter-backed helpers.

Before:

```python
def _run_claude(task: str, max_turns: int = 10) -> None:
    result = subprocess.run(
        ["claude", "-p", task, "--dangerously-skip-permissions"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
```

After:

```python
from shared.newsletter_generation import generate_newsletter_issue
from shared.topic_md_generation import generate_topic_md


def _generate_topic_md(slug: str, payload: "TopicCreate") -> Path:
    content = generate_topic_md(payload.name, payload.description, payload.focus_areas, slug)
    topic_md = REPO_ROOT / "topics" / slug / "topic.md"
    topic_md.write_text(content)
    return topic_md
```

Specific call-site changes:

- `_create_topic_job()`
  - replace `_run_claude(...topic.md...)` with `_generate_topic_md(...)`
  - replace `_run_claude(prompt_text, max_turns=25)` with `generate_newsletter_issue(slug)`
- `_newsletter_generation_job()`
  - replace `_run_claude(prompt_path.read_text(), max_turns=25)` with `generate_newsletter_issue(slug)`
- `_topic_md_generation_job()`
  - replace `_run_claude(...topic.md...)` with `_generate_topic_md(...)`

Also update user-facing step labels:

- `"Generating topic.md via Claude…"` -> `"Generating topic.md via OpenRouter…"`
- error messages should no longer mention `claude exited`

### 7. `run.sh`

Keep orchestration in shell, but move AI generation into a Python helper instead of inline `claude -p`.

Before:

```bash
echo "--- Generating newsletter for $slug ---"
claude -p "$(cat $REPO/topics/$slug/prompt.md)" \
  --dangerously-skip-permissions
```

After:

```bash
echo "--- Generating newsletter for $slug ---"
uv run python -c "
from shared.newsletter_generation import generate_newsletter_issue
generate_newsletter_issue('$slug')
"
```

Listener block:

Before:

```bash
lsof -ti:0 -c claude 2>/dev/null | xargs kill 2>/dev/null || true
nohup claude -p "$(cat $REPO/shared/prompts/on-demand-listener.md)" \
  --dangerously-skip-permissions \
  > /tmp/newsletter-listener.log 2>&1 &
```

After:

```bash
# Removed in Phase 1.
# OpenRouter chat completions are stateless and do not replace a long-lived Claude session.
```

Conservative decision:

- remove this block in the first migration PR unless a real server-backed listener replacement is implemented

### 8. `shared/prompts/on-demand-listener.md`

This file describes behavior that does not map to a raw OpenRouter completion.

Before:

```markdown
This prompt configures a persistent Claude Code session that listens for
Telegram messages and generates on-demand briefings.
```

After:

One of:

```markdown
# On-Demand Briefing Listener

Deprecated during OpenRouter migration.
Persistent Claude Code sessions are not replaced by stateless OpenRouter calls.
Use server-backed on-demand generation instead.
```

or delete the file if no replacement path remains.

Recommendation:

- deprecate first
- delete only after `run.sh` no longer references it

### 9. `.github/workflows/claude-review.yml`

This is not part of daily newsletter generation, but it is an active Anthropic AI invocation path in-repo and should be migrated or intentionally retired.

Before:

```yaml
- uses: anthropics/claude-code-action@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

After:

```yaml
- name: Run OpenRouter PR review
  env:
    OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
  run: uv run python .github/scripts/openrouter_pr_review.py
```

Recommendation:

- move this into a follow-up phase if daily-generation migration is the top priority
- still document it in the same migration plan because it is an AI invocation site

### 10. `CLAUDE.md`

Update operator docs and architecture language.

Before:

```markdown
claude -p "$(cat topics/google-ai/prompt.md)" \
  --dangerously-skip-permissions
```

After:

```markdown
OPENROUTER_API_KEY=... uv run python -c "
from shared.newsletter_generation import generate_newsletter_issue
generate_newsletter_issue('google-ai')
"
```

Architecture text changes:

- `prompt.md -> Claude Code` becomes `prompt.md -> OpenRouter API -> local file writer`
- `POST /api/topics` should say `generates topic.md via OpenRouter`

### 11. `skill/newsletter-create/SKILL.md`

Update the operator command it recommends after assembling `prompt.md`.

Before:

```bash
claude -p "$(cat ~/newsletters/topics/{TOPIC_SLUG}/prompt.md)" \
  --dangerously-skip-permissions
```

After:

```bash
cd ~/newsletters && OPENROUTER_API_KEY=... uv run python -c "
from shared.newsletter_generation import generate_newsletter_issue
generate_newsletter_issue('{TOPIC_SLUG}')
"
```

### 12. `shared/templates/manage.html`

UI copy only.

Before:

```html
<div class="form-hint">If provided without topic.md below, the AI will use this to generate topic.md (requires Claude CLI).</div>
...
<div class="form-hint">Providing this directly registers the topic as ready — no Claude CLI needed.</div>
```

After:

```html
<div class="form-hint">If provided without topic.md below, the server can generate topic.md via OpenRouter.</div>
...
<div class="form-hint">Providing this directly registers the topic as ready — no AI generation needed.</div>
```

### 13. `topics/*/prompt.md`

These are generated files, but they must be regenerated after updating `shared/prompts/ops-guide.md`.

Before:

- instruct the model to write files and send Telegram

After:

- instruct the model to return JSON only

Command after prompt-layer changes:

```bash
uv run shared/assemble_prompt.py claude-digest
uv run shared/assemble_prompt.py google-ai
uv run shared/assemble_prompt.py us-iran-war
uv run shared/assemble_prompt.py indian-parliament-news
```

## Testing Strategy

### Unit tests to add

#### New file: `tests/test_openrouter_client.py`

Verify:

- missing `OPENROUTER_API_KEY` raises clearly
- request headers include `Authorization`
- optional `HTTP-Referer` and `X-Title` are forwarded
- non-200 responses become useful exceptions
- string response extraction works

#### New file: `tests/test_topic_md_generation.py`

Verify:

- valid JSON response writes only `topic.md` content
- malformed JSON fails before writing partial output

#### New file: `tests/test_newsletter_generation.py`

Verify:

- generated JSON writes:
  - `topics/<slug>/YYYY-MM-DD.md`
  - `topics/<slug>/site/index.html`
  - `topics/<slug>/site/YYYY-MM-DD.html`
- archive copy matches `index.html`
- invalid JSON or missing keys fails cleanly

#### Update `tests/test_build.py`

Keep existing build assertions, but add one integration fixture where newsletter files are generated by the local writer path instead of assumed Claude side effects.

### Manual parity checks

1. Pick one existing topic, preferably `google-ai`.
2. Assemble the prompt without changing topic research content.
3. Run the current Claude path and save outputs in a temporary comparison folder.
4. Run the OpenRouter path with the same prompt.
5. Compare:
   - raw markdown length and section coverage
   - placeholder completeness in HTML
   - archive file creation
   - build success via `uv run shared/build.py`
6. Repeat for at least one second topic with different source mix, such as `us-iran-war`.

### Acceptance criteria

- no remaining `claude -p` or `anthropic_api_key` usage in active runtime paths
- `bash run.sh` still produces topic HTML and dated archives
- `POST /api/topics` can generate `topic.md` with only `focus_areas`
- `POST /api/topics/{slug}/newsletter` still works
- `uv run pytest` passes

## Rollout Order

1. Add `shared/openrouter_client.py`.
2. Add `shared/topic_md_generation.py`.
3. Add `shared/newsletter_generation.py`.
4. Rewrite `shared/prompts/ops-guide.md` to structured-output mode.
5. Regenerate `topics/*/prompt.md`.
6. Refactor `server/pipeline.py` to use the new helpers.
7. Refactor `run.sh` to use the new newsletter-generation helper.
8. Deprecate or remove the `run.sh` listener block and update `shared/prompts/on-demand-listener.md`.
9. Update `shared/templates/manage.html`.
10. Update `CLAUDE.md`.
11. Update `skill/newsletter-create/SKILL.md`.
12. Migrate or retire `.github/workflows/claude-review.yml`.
13. Add tests and run full verification.

## Risks and Conservative Decisions

### Risk 1: Web search parity

The current Claude Code flow explicitly says "search the web thoroughly." A plain OpenRouter chat completion does not guarantee an equivalent browsing/tooling layer.

Conservative decision:

- phase 1 should preserve prompt and output-writing architecture first
- if search freshness drops, add a separate explicit research-fetch stage later rather than hiding the gap

### Risk 2: Prompt drift from agent mode to API mode

Prompts that assume filesystem and shell access will degrade badly when sent to a plain API.

Conservative decision:

- change only `shared/prompts/ops-guide.md`
- keep topic briefs and design guide intact

### Risk 3: On-demand listener is not a drop-in migration

A background `claude` process is a stateful agent; OpenRouter chat completions are not.

Conservative decision:

- remove or deprecate listener behavior in the first migration PR
- rebuild it later as an explicit server process if it is still needed

### Risk 4: Workflow migration may not be worth coupling to daily generation

The PR-review action is independent from newsletter runtime.

Conservative decision:

- track it in this plan
- optionally land it in a follow-up PR if that keeps the main migration smaller

## Recommended Commit Breakdown For The Actual Migration

1. `feat: add shared OpenRouter client`
2. `feat: move topic generation to OpenRouter`
3. `feat: move newsletter generation to OpenRouter`
4. `refactor: convert prompt ops guide to structured output`
5. `chore: remove claude listener stub`
6. `docs: update operator instructions for OpenRouter`
7. `test: cover OpenRouter generation paths`
