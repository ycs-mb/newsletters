# Newsletter Portal v2 — Design Spec

**Date:** 2026-03-22
**Status:** Approved

---

## Context

The newsletter portal serves three automated daily briefings (Claude Digest, US–Iran Conflict, Google AI) as a static site. The repository layout has already been refactored: topics live under `topics/<slug>/`, shared infrastructure under `shared/`, and `shared/build.py` is the active build script. The server is currently `python3 -m http.server 8787`. Each topic has a monolithic `prompt.md`. There is no dynamic capability.

This spec adds: FastAPI backend, NotebookLM integration (infographic, slides, on-demand podcast/video), prompt architecture split (topic / design / ops), and a web form for creating new topic briefings end-to-end.

---

## Prerequisites / Existing State

- `shared/build.py` — active build script, pure stdlib, invoked as `uv run shared/build.py`; never imported by other modules — always run as a standalone script
- `topics/{claude-digest,google-ai,us-iran-war}/` — each has `prompt.md` and `site/`
- `topics.toml` — **already migrated**: all three topics use `folder = "topics/<slug>"` (e.g. `folder = "topics/claude-digest"`). No root-relative paths remain. No topics.toml migration is needed.
- `newsletter-create` skill at `~/.claude/skills/newsletter-create/SKILL.md` — generates newsletter prompt files
- No `pyproject.toml` yet
- No `.gitignore` yet

---

## Architecture

### Folder Structure (final state)

```
~/newsletters/
  shared/
    build.py                        # Extended (see build.py changes)
    assemble_prompt.py              # NEW
    notebooklm_runner.py            # NEW — single canonical location
    prompts/
      design-guide.md               # NEW (locked)
      ops-guide.md                  # NEW (locked)
    portal.css                      # Extended
    templates/
      landing.html                  # Extended with Create Briefing form
      nav.html
    assets/
      style.css                     # Locked — never modified
  topics/
    <slug>/
      topic.md                      # NEW — topic-centric research only
      prompt.md                     # AUTO-ASSEMBLED (gitignored via .gitignore)
      site/
        template.html               # Updated: adds {{MEDIA_SECTION}} and data- attrs
        index.html
        YYYY-MM-DD.html
      YYYY-MM-DD.md
      media/                        # NEW
        YYYY-MM-DD-infographic.png
        YYYY-MM-DD-slides.pdf
        YYYY-MM-DD-notebook-id.txt  # per-issue, one per date
  server/
    __init__.py
    main.py
    jobs.py
    pipeline.py
    routers/
      __init__.py
      generate.py
      topics.py
      jobs_router.py
  dist/
  topics.toml
  run.sh                            # Updated (full script in Run Script section)
  pyproject.toml                    # NEW
  .gitignore                        # NEW
  CLAUDE.md
```

### Runtime Flow

**Daily run:**
```
1. assemble × 3                 (topic.md + guides → prompt.md per topic)
2. claude --task × 3            (web search → site/index.html + YYYY-MM-DD.md)
3. notebooklm_runner × 3        (infographic + slides → media/; non-fatal)
4. shared/build.py              (media copy + nav inject + media section inject → dist/)
5. kill :8787, start uvicorn    (with drain step — see run.sh)
```

**On-demand media:**
```
click → POST /api/generate/{slug}/{date}/{type} → {job_id}
→ ThreadPoolExecutor task: notebooklm generate → artifact wait → download → copy to dist/
→ poll GET /api/jobs/{job_id} every 5s
  done:    player replaces button
  failed:  "Failed — retry?" (error in button.title)
  404:     "Session expired, please retry"
```

**New topic creation:**
```
form → POST /api/topics → {job_id, slug}
→ ThreadPoolExecutor task (pipeline.py):
  1. scaffold topics/<slug>/site/ and media/
  2. copy shared template
  3. run claude with newsletter-create skill → writes topics/<slug>/topic.md
  4. append to topics.toml
  5. assemble_prompt.assemble(slug)
  6. run full newsletter pipeline (assemble → claude → notebooklm → build)
  7. job done
→ poll /api/jobs/{job_id} → progress stepper → page reload on done
```

---

## Prompt Split Architecture

### Three Layers

| File | Owner | Contents | Editable |
|------|-------|----------|---------|
| `topics/<slug>/topic.md` | Topic author | Role, audience, signal label, sources, sections | Yes |
| `shared/prompts/design-guide.md` | Infrastructure | Template path, placeholder map, CSS class reference | No |
| `shared/prompts/ops-guide.md` | Infrastructure | Build steps, archive copy, Telegram chat ID, delivery | No |

### `topic.md` Content Contract

```markdown
# <Topic Name> — Topic Brief

## Identity
- Role: <curator role description>
- Audience: <target reader>
- Signal label: <label> (1–5)

## Sources
<source list by category>

## Sections
### <Section N name> (<time window>)
  Sub-categories: ...
```

No HTML, no build steps, no placeholder references — those belong to the other layers.

### `assemble_prompt.py`

**CLI:**
```bash
uv run shared/assemble_prompt.py <slug>
# Writes to: topics/<slug>/prompt.md   ← explicit output path
# Exit 0: success, prints assembled path
# Exit 1: FileNotFoundError, prints which file is missing to stderr
```

**Python interface** (imported by `server/pipeline.py`):
```python
# shared/assemble_prompt.py
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).parent.parent
SHARED_PROMPTS = Path(__file__).parent / "prompts"

def assemble(slug: str) -> Path:
    """Assemble prompt.md from three layers. Returns output path.
    Raises FileNotFoundError if any layer file is missing."""
    layers = {
        "topic":  REPO_ROOT / "topics" / slug / "topic.md",
        "design": SHARED_PROMPTS / "design-guide.md",
        "ops":    SHARED_PROMPTS / "ops-guide.md",
    }
    for name, path in layers.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing {name} layer: {path}")
    prompt = "\n\n---\n\n".join(p.read_text() for p in layers.values())
    out = REPO_ROOT / "topics" / slug / "prompt.md"
    out.write_text(prompt)
    return out

if __name__ == "__main__":
    slug = sys.argv[1]
    try:
        print(f"Assembled: {assemble(slug)}")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
```

### Migration of Existing `prompt.md` Files

For each of the three existing topics:
1. Read current `topics/<slug>/prompt.md`
2. Extract research identity + sources + sections → write `topics/<slug>/topic.md`
3. Extract HTML design instructions → incorporate into `shared/prompts/design-guide.md`
4. Extract build + Telegram steps → incorporate into `shared/prompts/ops-guide.md`
5. Delete the old `topics/<slug>/prompt.md`

`shared/prompts/design-guide.md` and `shared/prompts/ops-guide.md` are written once from the three existing prompt.md files (content is identical across topics, only slug/template path varies — parameterised with `{{SLUG}}`).

### `.gitignore`

```
# Auto-assembled build artifact — do not commit
topics/*/prompt.md
```

### `newsletter-create` Skill Update

The skill at `~/.claude/skills/newsletter-create/SKILL.md` is updated to:
- Output `topic.md` only (not `prompt.md`)
- Write to `topics/<slug>/topic.md` (not the root)
- Content follows the `topic.md` content contract above: Identity, Sources, Sections — no HTML, no ops

When invoked by `pipeline.py`, the Claude task description is:
```
Use the newsletter-create skill to generate a topic.md file for a new newsletter briefing.
Topic name: {name}
Description: {description}
Focus areas: {focus_areas}
Output path: topics/{slug}/topic.md
Format: Identity section (role, audience, signal label) + Sources + Sections only.
Do NOT include HTML output instructions, build steps, or Telegram delivery steps.
Do NOT generate prompt.md. Write topic.md only.
```

`pipeline.py` validates that `topics/{slug}/topic.md` exists after the Claude task completes before proceeding to assemble.

---

## NotebookLM Integration

### Dependency

```toml
# pyproject.toml
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "notebooklm-py>=0.3",   # pip install notebooklm-py — published on PyPI
]
```

One-time setup per machine: `notebooklm login` (browser OAuth). Credentials persist in `~/.notebooklm/`. The `notebooklm status` command verifies auth before any runner invocation.

### `shared/notebooklm_runner.py`

**Implementation note:** `notebooklm_runner.py` wraps the `notebooklm` CLI via `subprocess.run()`. It does NOT use a Python API — the `notebooklm-py` package installs a CLI tool (`notebooklm`) which is what the runner invokes. This makes the wrapper independent of the package's internal Python API surface.

**CLI:**
```bash
uv run shared/notebooklm_runner.py <slug> [--date YYYY-MM-DD]
# Default date: today. Generates infographic + slides. Exits 0 on success, 1 on failure.
```

**Python interface** (imported by `server/pipeline.py`):
```python
def generate_issue_media(slug: str, date: str) -> dict[str, Path | str | None]:
    """Generate infographic + slides for one issue.
    Returns:
      {"infographic": Path|None, "slides": Path|None, "notebook_id": str|None}
    Never raises — failures are logged and returned as None values.
    Wraps notebooklm CLI via subprocess.run().
    """

def generate_on_demand(slug: str, date: str, media_type: str,
                       progress_cb: Callable[[str], None]) -> Path:
    """Generate podcast ('podcast') or video ('video') on demand.
    Calls progress_cb(step_label) as generation progresses.
    Returns path to downloaded file in topics/<slug>/media/.
    Raises RuntimeError on failure or timeout.
    Timeouts: podcast=1200s, video=2700s.
    """
```

**Auto-generation steps** (each wraps a `notebooklm` CLI call via subprocess):
1. `notebooklm status` — verify auth; raise `RuntimeError("NotebookLM not authenticated")` if not
2. `notebooklm list --json` → find existing notebook named `{slug}/{date}`, or `notebooklm create "{slug}/{date}"` → parse notebook_id
3. `notebooklm source add topics/{slug}/{date}.md --notebook {notebook_id} --json` → parse source_id
4. `notebooklm source wait {source_id} -n {notebook_id}` (timeout: 600s)
5. `notebooklm generate infographic --style editorial --orientation landscape --notebook {notebook_id} --json` → parse task_id
6. `notebooklm generate slide-deck --format detailed --notebook {notebook_id} --json` → parse task_id
7. `notebooklm artifact wait {task_id} -n {notebook_id}` × 2 (timeout: 900s each)
8. `notebooklm download infographic topics/{slug}/media/{date}-infographic.png -a {task_id} -n {notebook_id}`
9. `notebooklm download slide-deck topics/{slug}/media/{date}-slides.pdf -a {task_id} -n {notebook_id}`
10. Write notebook_id to `topics/{slug}/media/{date}-notebook-id.txt`

**notebook-id.txt location:** `topics/<slug>/media/<date>-notebook-id.txt` — one file per issue date.

**Failure policy:** If any step fails (network, quota, timeout), log to stderr, return `None` for that artifact. `run.sh` continues with `|| echo "NotebookLM: {slug} skipped"`. Newsletter publishes without media for that issue. `build.py` checks file existence before injecting media blocks.

### `build.py` Changes

Three new functions added to `shared/build.py`:

```python
def discover_media(topic_dir: Path, date: str) -> dict:
    """Returns {infographic: Path|None, slides: Path|None, notebook_id: str|None}."""
    media_dir = topic_dir / "media"
    def maybe(name): p = media_dir / f"{date}-{name}"; return p if p.exists() else None
    nb_file = media_dir / f"{date}-notebook-id.txt"
    return {
        "infographic": maybe("infographic.png"),
        "slides":      maybe("slides.pdf"),
        "notebook_id": nb_file.read_text().strip() if nb_file.exists() else None,
    }

def copy_media(topic_dir: Path, date: str, topic_dist: Path) -> None:
    """Copy media files from topics/<slug>/media/ to dist/<slug>/media/."""
    src_dir  = topic_dir / "media"
    dest_dir = topic_dist / "media"
    dest_dir.mkdir(exist_ok=True)
    for name in [f"{date}-infographic.png", f"{date}-slides.pdf",
                 f"{date}-podcast.mp3", f"{date}-video.mp4"]:
        src = src_dir / name
        if src.exists():
            shutil.copy2(src, dest_dir / name)

def render_media_section(slug: str, date: str, media: dict) -> str:
    """Render {{MEDIA_SECTION}} HTML. Returns empty string if no media available."""
    if not any([media["infographic"], media["slides"]]):
        return ""
    # ... renders Section 06 HTML with conditional infographic img, PDF embed, buttons
```

In the main `build()` loop, after `inject_nav()`:
1. Call `copy_media(topic_dir, date, topic_dist)`
2. Call `render_media_section(slug, date, media)` → replace `{{MEDIA_SECTION}}`
3. Inject `data-slug="{slug}"` and `data-date="{date}"` into `<body>` tag via regex

### Template Changes

All three `topics/<slug>/site/template.html` files are updated as part of implementation Step 2 (before any other changes):
- Add `{{MEDIA_SECTION}}` as a new `<section>` block after Section 05
- `build.py` injects `data-slug` and `data-date` into `<body>` (no change needed in template itself)

```html
<!-- Added to all three templates, after Section 05 -->
{{MEDIA_SECTION}}
```

`build.py` handles the `<body>` attribute injection via the existing `inject_nav()` function (extended):
```python
# In inject_nav(), extend the body tag regex:
html = re.sub(
    r'<body([^>]*)>',
    rf'<body\1 class="has-portal-nav" data-slug="{slug}" data-date="{date}">',
    html, count=1
)
```

`inject_nav()` signature changes to accept `slug` and `date` parameters.

---

## FastAPI Server

### `pyproject.toml`

```toml
[project]
name = "newsletter-portal"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "notebooklm-py>=0.3",
]
```

`shared/build.py` retains its inline uv script metadata (`# requires-python = ">=3.11"`) — `pyproject.toml` is additive and does not break `uv run shared/build.py`. `build.py` is **never imported** by the FastAPI server or any other module — it is always invoked via `subprocess.run(["uv", "run", "shared/build.py"])` or directly from `run.sh`. The pure-stdlib guarantee is preserved; only `server/` uses FastAPI/uvicorn.

### `server/main.py`

```python
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from server.routers import generate, topics, jobs_router

DIST_DIR = Path(__file__).parent.parent / "dist"

app = FastAPI(title="Newsletter Portal API")

# /api/* routes registered BEFORE static mount — order is critical
app.include_router(generate.router,    prefix="/api/generate", tags=["generate"])
app.include_router(topics.router,      prefix="/api/topics",   tags=["topics"])
app.include_router(jobs_router.router, prefix="/api/jobs",     tags=["jobs"])

# Static mount catches all remaining paths (including /{slug}/, /{slug}/{date}.html)
app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("server.main:app", host="0.0.0.0", port=8787, reload=False)
```

### Route Map

| Method | Path | Handler | Returns |
|--------|------|---------|---------|
| `POST` | `/api/generate/{slug}/{date}/podcast` | `generate.start_podcast` | `{job_id}` |
| `POST` | `/api/generate/{slug}/{date}/video` | `generate.start_video` | `{job_id}` |
| `POST` | `/api/generate/{slug}/{date}/infographic` | `generate.start_infographic` | `{job_id}` |
| `GET` | `/api/jobs/{job_id}` | `jobs_router.get_job` | Job state or 404 |
| `POST` | `/api/topics` | `topics.create_topic` | `{job_id, slug}` |
| `GET` | `/api/topics` | `topics.list_topics` | Topics + metadata |

All other paths (e.g. `/claude-digest/`, `/us-iran-war/2026-03-22.html`, `/dist/media/...`) are served by the StaticFiles mount from `dist/`.

### `server/pipeline.py`

Central orchestration module for all background jobs. Role: (1) thread pool for all async operations, (2) topic creation flow, (3) subprocess wrapper for Claude invocations.

```python
# server/pipeline.py
import subprocess, tomllib, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from server import jobs
from shared.assemble_prompt import assemble
from shared.notebooklm_runner import generate_issue_media

REPO_ROOT = Path(__file__).parent.parent
_executor = ThreadPoolExecutor(max_workers=4)
_toml_lock = threading.Lock()   # Protects concurrent topics.toml writes

def submit(fn, *args, **kwargs) -> str:
    """Create a job, submit fn to thread pool, return job_id."""
    job_id = jobs.create()
    _executor.submit(_run, job_id, fn, *args, **kwargs)
    return job_id

def _run(job_id, fn, *args, **kwargs):
    jobs.update(job_id, status=jobs.JobStatus.running)
    try:
        fn(job_id, *args, **kwargs)
        jobs.update(job_id, status=jobs.JobStatus.done)
    except Exception as e:
        jobs.update(job_id, status=jobs.JobStatus.failed, error=str(e))

def _run_claude(task: str, max_turns: int = 10) -> None:
    """Invoke claude CLI via subprocess.run(). Raises on non-zero exit."""
    result = subprocess.run(
        ["claude", "--task", task, "--dangerously-skip-permissions",
         "--max-turns", str(max_turns)],
        capture_output=True, text=True, timeout=600
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude exited {result.returncode}: {result.stderr[:500]}")

def _append_topic_toml(slug: str, name: str, description: str,
                        accent: str, signal_label: str) -> None:
    """Safely append new topic entry to topics.toml. Thread-safe via _toml_lock."""
    toml_path = REPO_ROOT / "topics.toml"
    entry = (
        f'\n[{slug}]\n'
        f'name = "{name}"\n'
        f'description = "{description}"\n'
        f'accent = "{accent}"\n'
        f'signal_label = "{signal_label}"\n'
        f'folder = "topics/{slug}"\n'
        f'eyebrow = "Daily Intelligence Brief"\n'
    )
    with _toml_lock:
        with open(toml_path, "a") as f:
            f.write(entry)

def create_topic_job(job_id: str, slug: str, name: str, description: str,
                     focus_areas: str, accent: str, signal_label: str) -> None:
    """Full new-topic creation pipeline. Called in thread pool."""
    today = datetime.now().strftime("%Y-%m-%d")

    jobs.update(job_id, step="Scaffolding topic folder…")
    (REPO_ROOT / "topics" / slug / "site").mkdir(parents=True, exist_ok=True)
    (REPO_ROOT / "topics" / slug / "media").mkdir(exist_ok=True)
    # Copy shared template
    shutil.copy2(REPO_ROOT / "shared" / "templates" / "topic-template.html",
                 REPO_ROOT / "topics" / slug / "site" / "template.html")
    shutil.copy2(REPO_ROOT / "shared" / "assets" / "style.css",
                 REPO_ROOT / "topics" / slug / "site" / "style.css")

    jobs.update(job_id, step="Generating research prompt…")
    _run_claude(
        f"Use the newsletter-create skill to generate a topic.md file. "
        f"Topic name: {name}. Description: {description}. Focus areas: {focus_areas}. "
        f"Output path: topics/{slug}/topic.md. "
        f"Format: Identity section (role, audience, signal label) + Sources + Sections only. "
        f"Do NOT include HTML output instructions, build steps, or Telegram delivery. "
        f"Do NOT generate prompt.md. Write topic.md only.",
        max_turns=10
    )
    topic_md = REPO_ROOT / "topics" / slug / "topic.md"
    if not topic_md.exists():
        raise RuntimeError(f"newsletter-create did not produce topics/{slug}/topic.md")

    _append_topic_toml(slug, name, description, accent, signal_label)
    assemble(slug)

    jobs.update(job_id, step="Running first newsletter issue…")
    prompt = (REPO_ROOT / "topics" / slug / "prompt.md").read_text()
    _run_claude(prompt, max_turns=25)

    jobs.update(job_id, step="Generating media…")
    generate_issue_media(slug, today)   # non-fatal if fails

    jobs.update(job_id, step="Building portal…")
    subprocess.run(["uv", "run", "shared/build.py"], cwd=REPO_ROOT, check=True)

    jobs.update(job_id, step="Done ✓")
```

### Background Job Concurrency

`ThreadPoolExecutor(max_workers=4)` in `server/pipeline.py`. All on-demand generation jobs and topic-creation jobs share this pool. At most 4 long-running operations run concurrently; additional requests queue.

### `server/jobs.py` — In-Memory Job Store

```python
import uuid, threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    done    = "done"
    failed  = "failed"

@dataclass
class Job:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: JobStatus = JobStatus.pending
    step: str = ""          # Human-readable current step label
    artifact_url: str = ""  # Set on done
    error: str = ""         # Set on failed

_store: dict[str, Job] = {}
_lock  = threading.Lock()

def create() -> str:
    job = Job()
    with _lock: _store[job.id] = job
    return job.id

def update(job_id: str, **kwargs) -> None:
    with _lock:
        for k, v in kwargs.items():
            setattr(_store[job_id], k, v)

def get(job_id: str) -> Optional[Job]:
    """Returns None if job_id not found (server restarted, job expired)."""
    return _store.get(job_id)
```

`GET /api/jobs/{job_id}` returns HTTP 404 if `get()` returns `None`. Frontend shows "Session expired, please retry" for 404.

**Known behavior:** Jobs are lost on server restart. Daily `run.sh` kills the server after all newsletters complete and before any on-demand jobs can be active (daily run is scheduled at a fixed time, not during the day). This is acceptable — on-demand generation is a daytime feature, daily run is an overnight batch job.

---

## Frontend Changes

### Section 06: Media (Newsletter Pages)

`build.py` renders `{{MEDIA_SECTION}}` (empty string if no media exists for the date):

```html
<section class="media-section">
  <div class="section-header reveal">
    <span class="section-num">06</span>
    <h2>Media</h2>
    <span class="section-sub">Infographic · Slides · Audio · Video</span>
  </div>

  <!-- Conditional: only if infographic exists -->
  <div class="media-block reveal">
    <div class="media-label">Infographic</div>
    <img src="../media/{date}-infographic.png" class="media-infographic" alt="Issue infographic">
  </div>

  <!-- Conditional: only if slides exist -->
  <div class="media-block reveal">
    <div class="media-label">Slide Deck</div>
    <embed src="../media/{date}-slides.pdf" class="media-slides" type="application/pdf">
  </div>

  <!-- Always shown -->
  <div class="media-block reveal" id="media-podcast">
    <div class="media-label">Audio Overview</div>
    <button class="media-btn" onclick="generateMedia('podcast')">Generate Podcast</button>
  </div>

  <div class="media-block reveal" id="media-video">
    <div class="media-label">Video Overview</div>
    <button class="media-btn" onclick="generateMedia('video')">Generate Video</button>
  </div>
</section>

<script>
async function generateMedia(type) {
  const slug = document.body.dataset.slug;
  const date = document.body.dataset.date;
  const container = document.getElementById('media-' + type);
  const btn = container.querySelector('.media-btn');
  btn.textContent = 'Starting\u2026'; btn.disabled = true;

  const res = await fetch('/api/generate/' + slug + '/' + date + '/' + type,
    { method: 'POST' });
  if (!res.ok) { btn.textContent = 'Failed \u2014 retry?'; btn.disabled = false; return; }
  const { job_id } = await res.json();

  const iv = setInterval(async () => {
    const r = await fetch('/api/jobs/' + job_id);
    if (!r.ok) {
      clearInterval(iv);
      btn.textContent = 'Session expired \u2014 retry'; btn.disabled = false; return;
    }
    const job = await r.json();
    btn.textContent = job.step || 'Generating\u2026';
    if (job.status === 'done') {
      clearInterval(iv);
      const tag = type === 'podcast' ? 'audio' : 'video';
      container.innerHTML = '<div class="media-label">'
        + (type === 'podcast' ? 'Audio Overview' : 'Video Overview') + '</div>'
        + '<' + tag + ' controls src="' + job.artifact_url + '" class="media-player"></' + tag + '>';
    }
    if (job.status === 'failed') {
      clearInterval(iv);
      btn.textContent = 'Failed \u2014 retry?'; btn.disabled = false; btn.title = job.error;
    }
  }, 5000);
}
</script>
```

### Create Briefing Form (Landing Page)

Added below `.portal-grid` in `templates/landing.html`:

```html
<section class="create-section reveal">
  <div class="section-header">
    <h2>Add Briefing</h2>
  </div>
  <form class="create-form" id="create-form" onsubmit="createTopic(event)">
    <div class="create-row">
      <label class="create-label">Topic name</label>
      <input class="create-input" name="name" required placeholder="e.g. AI Regulation">
    </div>
    <div class="create-row">
      <label class="create-label">Description</label>
      <input class="create-input" name="description" placeholder="One-line summary">
    </div>
    <div class="create-row">
      <label class="create-label">Focus areas</label>
      <input class="create-input" name="focus_areas" placeholder="e.g. policy, enforcement, EU AI Act">
    </div>
    <div class="create-row">
      <label class="create-label">Accent</label>
      <div class="accent-picker">
        <label><input type="radio" name="accent" value="terracotta" checked> Terracotta</label>
        <label><input type="radio" name="accent" value="sage"> Sage</label>
        <label><input type="radio" name="accent" value="prussian"> Prussian</label>
        <label><input type="radio" name="accent" value="gold"> Gold</label>
      </div>
    </div>
    <div class="create-row">
      <label class="create-label">Signal label</label>
      <input class="create-input" name="signal_label" value="Signal" placeholder="Signal">
    </div>
    <button class="create-btn" type="submit">Create Briefing &rarr;</button>
  </form>

  <div class="create-progress" id="create-progress" hidden>
    <div class="progress-steps" id="progress-steps"></div>
  </div>
</section>
```

**Progress stepper steps (6):**
1. `Scaffolding topic folder…`
2. `Generating research prompt…`
3. `Running first newsletter issue…`
4. `Generating media…`
5. `Building portal…`
6. `Done ✓`

On completion: `window.location.reload()` — new topic card appears on landing page.

### `portal.css` Additions

All new selectors use existing CSS vars only (`--paper`, `--paper-tint`, `--paper-dark`, `--ink`, `--ink-mid`, `--ink-light`, `--ink-faint`, `--rule`, `--font-mono`, `--font-body`). No modifications to `style.css`.

New classes:
```css
/* Media section */
.media-section          { /* standard section spacing */ }
.media-block            { margin: 24px 0; }
.media-label            { font-family: var(--font-mono); font-size: 10px;
                          text-transform: uppercase; letter-spacing: 0.1em;
                          color: var(--ink-faint); margin-bottom: 8px; }
.media-infographic      { width: 100%; border: 1px solid var(--rule); border-radius: 2px; }
.media-slides           { width: 100%; height: 480px; border: 1px solid var(--rule); display: block; }
.media-player           { width: 100%; margin-top: 8px; }
.media-btn              { font-family: var(--font-mono); font-size: 11px; text-transform: uppercase;
                          letter-spacing: 0.08em; padding: 10px 20px; cursor: pointer;
                          background: var(--paper-dark); border: 1px solid var(--rule);
                          color: var(--ink-mid); }
.media-btn:hover        { border-color: var(--ink-mid); color: var(--ink); }
.media-btn:disabled     { opacity: 0.5; cursor: not-allowed; }

/* Create form */
.create-section         { margin-top: 64px; }
.create-form            { display: flex; flex-direction: column; gap: 16px; max-width: 560px; }
.create-row             { display: flex; flex-direction: column; gap: 4px; }
.create-label           { font-family: var(--font-mono); font-size: 10px; text-transform: uppercase;
                          letter-spacing: 0.08em; color: var(--ink-light); }
.create-input           { font-family: var(--font-body); font-size: 14px; padding: 8px 12px;
                          border: 1px solid var(--rule); background: var(--paper-tint);
                          color: var(--ink); width: 100%; }
.create-input:focus     { outline: none; border-color: var(--ink-mid); }
.create-btn             { font-family: var(--font-mono); font-size: 11px; text-transform: uppercase;
                          letter-spacing: 0.08em; padding: 12px 24px; cursor: pointer;
                          background: var(--ink); border: none; color: var(--paper);
                          align-self: flex-start; }
.create-btn:hover       { opacity: 0.85; }
.accent-picker          { display: flex; gap: 20px; flex-wrap: wrap; }
.accent-picker label    { font-family: var(--font-mono); font-size: 11px; color: var(--ink-mid);
                          cursor: pointer; }

/* Progress stepper */
.create-progress        { margin-top: 24px; }
.progress-steps         { display: flex; flex-direction: column; gap: 6px; }
.progress-step          { font-family: var(--font-mono); font-size: 11px; color: var(--ink-faint); }
.progress-step.active   { color: var(--ink-mid); }
.progress-step.done     { color: var(--ink-light); }
.progress-step.done::before { content: '\2713  '; color: var(--sage); }
```

---

## `run.sh` — Updated Full Script

```bash
#!/bin/bash
# ============================================================
# Daily Digest Portal — Runner Script (v2)
# ============================================================
source ~/.zshrc 2>/dev/null || source ~/.bash_profile 2>/dev/null
REPO="$HOME/newsletters"

# --- Assemble prompts ---
uv run "$REPO/shared/assemble_prompt.py" claude-digest
uv run "$REPO/shared/assemble_prompt.py" google-ai
uv run "$REPO/shared/assemble_prompt.py" us-iran-war

# --- Run newsletter generators ---
claude --task "$(cat $REPO/topics/claude-digest/prompt.md)" \
  --channels plugin:telegram@claude-plugins-official \
  --dangerously-skip-permissions --max-turns 25

claude --task "$(cat $REPO/topics/google-ai/prompt.md)" \
  --channels plugin:telegram@claude-plugins-official \
  --dangerously-skip-permissions --max-turns 25

claude --task "$(cat $REPO/topics/us-iran-war/prompt.md)" \
  --channels plugin:telegram@claude-plugins-official \
  --dangerously-skip-permissions --max-turns 25

# --- Generate NotebookLM media (non-fatal) ---
uv run "$REPO/shared/notebooklm_runner.py" claude-digest || echo "NotebookLM: claude-digest skipped"
uv run "$REPO/shared/notebooklm_runner.py" google-ai     || echo "NotebookLM: google-ai skipped"
uv run "$REPO/shared/notebooklm_runner.py" us-iran-war   || echo "NotebookLM: us-iran-war skipped"

# --- Build portal ---
cd "$REPO" && uv run shared/build.py

# --- Serve ---
lsof -ti:8787 | xargs kill 2>/dev/null
sleep 1
nohup uv run "$REPO/server/main.py" > /tmp/newsletter-server.log 2>&1 &

# --- On-demand Telegram listener (restart to pick up new prompt) ---
pkill -f "on-demand-listener" 2>/dev/null || true
sleep 1
nohup claude \
  --task "$(cat $REPO/shared/prompts/on-demand-listener.md)" \
  --channels plugin:telegram@claude-plugins-official \
  --dangerously-skip-permissions \
  --max-turns 200 \
  > /tmp/newsletter-listener.log 2>&1 &

echo "$(date): portal built, server + listener started" >> "$REPO/log.txt"
```

---

## On-Demand Telegram Briefings

A separate delivery mode: user-triggered, single-use HTML pages, no `topics.toml` entry, shared via Telegram link.

### Flow

```
User → Telegram: "brief: AI regulation EU crackdown"
  → Claude Code listener session receives message via plugin:telegram
  → web search + compile content for the query
  → generate HTML using editorial design system
  → save to dist/on-demand/YYYY-MM-DD-HHMM-{slug}/index.html
  → FastAPI serves it (no change — already serves all of dist/)
  → reply to Telegram: http://100.110.249.12:8787/on-demand/{slug}/
```

### Trigger Format

Claude Code listener interprets Telegram messages as on-demand briefing requests if they start with:
- `brief:` — short intelligence brief on a topic
- `research:` — deeper research dive
- `on-demand:` — explicit trigger

Any other message is treated as normal conversation with the listener session.

### Listener Process

A persistent Claude Code session started by `run.sh` alongside the server:

```bash
# In run.sh, after starting uvicorn:
lsof -ti:8790 2>/dev/null | xargs kill 2>/dev/null   # kill old listener
nohup claude \
  --task "$(cat $REPO/shared/prompts/on-demand-listener.md)" \
  --channels plugin:telegram@claude-plugins-official \
  --dangerously-skip-permissions \
  --max-turns 200 \
  > /tmp/newsletter-listener.log 2>&1 &
```

The listener session runs indefinitely (high `--max-turns`), waiting for Telegram messages.

### `shared/prompts/on-demand-listener.md`

The task prompt for the listener session:

```markdown
# On-Demand Briefing Listener

You are a research assistant listening for Telegram briefing requests.

## Trigger Detection
When you receive a Telegram message starting with "brief:", "research:", or "on-demand:",
extract the topic query and generate a briefing. All other messages: respond conversationally.

## Briefing Generation Steps
1. Determine today's date from system clock
2. Create slug: YYYY-MM-DD-HHMM-{kebab-case-topic} (e.g. 2026-03-22-1430-eu-ai-regulation)
3. Search the web thoroughly for the topic (use multiple queries, multiple sources)
4. Generate HTML to: ~/newsletters/dist/on-demand/{slug}/index.html
   - Use template: ~/newsletters/shared/templates/on-demand-template.html
   - Fill {{PLACEHOLDERS}} with your research (see template comments)
   - DO NOT modify the design — use the locked style.css via href="../../../style.css"
5. Reply to Telegram with: http://100.110.249.12:8787/on-demand/{slug}/

## Behavior
- After sending the link, continue listening for new requests
- Do not exit — keep the session alive for further requests
- One briefing per message — do not batch
```

### `shared/templates/on-demand-template.html`

A flexible editorial template — sections are determined by Claude based on what it finds, not fixed. Shares the same masthead/typography/CSS as topic templates but with an open-ended `{{CONTENT_SECTIONS}}` block instead of numbered fixed sections.

Key differences from topic templates:
- CSS path: `href="../../../style.css"` (three levels up: `on-demand/{slug}/index.html` → `dist/`)
- No signal dots / escalation rating
- No `{{MEDIA_SECTION}}` — on-demand pages are text-only
- No nav injection — standalone pages, no archive

### Storage

```
dist/
  on-demand/
    2026-03-22-1430-eu-ai-regulation/
      index.html
    2026-03-22-1615-quantum-computing-ibm/
      index.html
```

`dist/on-demand/` is served by FastAPI's existing StaticFiles mount — no configuration change needed.

### Landing Page

On-demand briefings do **not** appear on the portal landing page. They are accessible only via the Tailscale link shared in Telegram. This is intentional — they are ephemeral research snapshots, not curated daily topics.

### No-Goals for On-Demand

- No `topics.toml` registration
- No dated archive copies
- No NotebookLM media generation
- No nav bar injection
- No listing on portal landing page

---

## Non-Goals

- No authentication (Tailscale network provides isolation)
- No database (jobs lost on restart — explicit behavior: 404 → "Session expired, retry")
- No WebSocket (5s polling is sufficient for 10–45 min jobs)
- No modification to `shared/assets/style.css`
- No change to `dist/` URL structure or topic slugs

---

## Verification

1. **Prompt assembly:** `uv run shared/assemble_prompt.py claude-digest` → writes `topics/claude-digest/prompt.md` containing all three layers separated by `---`; exits 1 if `topic.md` missing
2. **Build:** `uv run shared/build.py` completes; `dist/` has landing page, 3 topic dirs, each with `index.html` + dated pages; `dist/<slug>/media/` exists for dates with media; `dist/on-demand/` directory exists
3. **Server start:** `uv run server/main.py` starts on :8787; `curl localhost:8787/` → 200; `curl localhost:8787/claude-digest/` → 200; `curl localhost:8787/api/topics` → 200 with JSON
4. **API routes:** `curl -X POST localhost:8787/api/topics -H 'Content-Type: application/json' -d '{"name":"Test","description":"test","focus_areas":"test","accent":"sage","signal_label":"Signal"}'` → `{job_id, slug}`; polling `GET /api/jobs/{id}` shows status progression; unknown job_id → 404
5. **On-demand generation:** `POST /api/generate/claude-digest/2026-03-22/podcast` → job_id; polling shows pending→running→done; `dist/claude-digest/media/2026-03-22-podcast.mp3` exists on completion
6. **Media rendering:** Newsletter page with media shows infographic `<img>` and PDF embed; page without media has no Section 06; `data-slug` and `data-date` on `<body>` present
7. **Telegram on-demand:** Send "brief: quantum computing IBM" via Telegram → listener session generates `dist/on-demand/YYYY-MM-DD-HHMM-quantum-computing-ibm/index.html` → Tailscale link reply received → page loads with editorial styling
8. **Full pipeline:** `bash run.sh` completes without error; all three topics updated; Telegram messages sent; server + listener both running
