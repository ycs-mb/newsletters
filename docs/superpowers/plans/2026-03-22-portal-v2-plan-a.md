# Newsletter Portal v2 — Plan A: Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic `prompt.md` per topic with a 3-layer prompt assembly system, replace `python3 -m http.server` with a FastAPI server that serves `dist/` and exposes `/api/` routes for topic creation and background jobs.

**Architecture:** `assemble_prompt.py` concatenates `topic.md` + `shared/prompts/design-guide.md` + `shared/prompts/ops-guide.md` into a runtime `prompt.md` per topic. A FastAPI app in `server/` serves the static `dist/` directory and provides JSON API routes. Background jobs (topic creation) run in a `ThreadPoolExecutor` tracked by an in-memory job store. NotebookLM media generation and the Create Briefing web form are **Plan B** — stubs only here.

**Tech Stack:** Python 3.11+, FastAPI 0.111+, uvicorn, uv, unittest (existing test style)

**Spec:** `docs/superpowers/specs/2026-03-22-portal-v2-design.md`

---

## File Map

| Status | Path | Responsibility |
|--------|------|----------------|
| CREATE | `pyproject.toml` | uv project + FastAPI/uvicorn dependencies |
| CREATE | `.gitignore` | Exclude `topics/*/prompt.md` (assembled artifacts) |
| CREATE | `shared/prompts/design-guide.md` | Locked: template ref, CSS class reference, placeholder map |
| CREATE | `shared/prompts/ops-guide.md` | Locked: build steps, Telegram delivery (uses `{SLUG}`) |
| CREATE | `shared/assemble_prompt.py` | Assembles 3 layers into `topics/<slug>/prompt.md` |
| CREATE | `topics/claude-digest/topic.md` | Claude Digest research identity + sources + sections |
| CREATE | `topics/google-ai/topic.md` | Google AI research identity + sources + sections |
| CREATE | `topics/us-iran-war/topic.md` | US–Iran research identity + sources + sections |
| DELETE | `topics/*/prompt.md` | Replaced by assembled artifact (after topic.md created) |
| CREATE | `server/__init__.py` | Package marker |
| CREATE | `server/main.py` | FastAPI app: mounts routers, serves `dist/` |
| CREATE | `server/jobs.py` | Thread-safe in-memory job store |
| CREATE | `server/pipeline.py` | ThreadPoolExecutor, `_run_claude`, `_append_topic_toml`, `create_topic_job` |
| CREATE | `server/routers/__init__.py` | Package marker |
| CREATE | `server/routers/generate.py` | `/api/generate/{slug}/{date}/{type}` → 501 stub (Plan B) |
| CREATE | `server/routers/topics.py` | `GET /api/topics` + `POST /api/topics` |
| CREATE | `server/routers/jobs_router.py` | `GET /api/jobs/{job_id}` |
| CREATE | `shared/notebooklm_runner.py` | Stub: `generate_issue_media(slug, date)` — full impl in Plan B |
| MODIFY | `topics/claude-digest/site/template.html` | Add `{{MEDIA_SECTION}}` after Section 05 |
| MODIFY | `topics/google-ai/site/template.html` | Add `{{MEDIA_SECTION}}` after Section 05 |
| MODIFY | `topics/us-iran-war/site/template.html` | Add `{{MEDIA_SECTION}}` after Section 05 |
| MODIFY | `shared/build.py` | Update `inject_nav()` (slug/date params + body attrs); add `discover_media()`, `copy_media()`, `render_media_section()` stubs |
| CREATE | `shared/templates/topic-template.html` | Generic newsletter HTML template for new topics created via `POST /api/topics` |
| CREATE | `shared/prompts/on-demand-listener.md` | Stub listener prompt for on-demand Telegram briefings (Plan B content) |
| CREATE | `shared/templates/on-demand-template.html` | Stub HTML template for on-demand briefings |
| MODIFY | `~/.claude/skills/newsletter-create/SKILL.md` | Output `topic.md` format only (not `prompt.md`) |
| MODIFY | `run.sh` | Use `assemble_prompt.py` + `uvicorn` instead of static server |
| MODIFY | `tests/test_build.py` | Expect `topic.md` files; remove `prompt.md` expectations |
| CREATE | `tests/test_assemble_prompt.py` | Unit tests for `assemble_prompt.assemble()` |
| CREATE | `tests/test_jobs.py` | Unit tests for `server/jobs.py` |

---

## Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`

- [ ] **Step 1: Create `pyproject.toml`**

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

- [ ] **Step 2: Create `.gitignore`**

```
# Assembled prompt artifacts — never commit
topics/*/prompt.md

# Server logs
/tmp/newsletter-*.log
```

- [ ] **Step 3: Install dependencies**

```bash
cd ~/newsletters
uv sync
```

Expected: `uv.lock` created, packages installed.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "chore: add pyproject.toml and .gitignore"
```

---

## Task 2: `assemble_prompt.py`

**Files:**
- Create: `tests/test_assemble_prompt.py`
- Create: `shared/assemble_prompt.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_assemble_prompt.py
import sys
import unittest
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from shared.assemble_prompt import assemble


class AssemblePromptTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Create folder structure
        (self.root / "topics" / "test-slug").mkdir(parents=True)
        (self.root / "shared" / "prompts").mkdir(parents=True)
        (self.root / "topics" / "test-slug" / "topic.md").write_text("## Identity\nRole: test")
        (self.root / "shared" / "prompts" / "design-guide.md").write_text("## Design\nTemplate: {SLUG}")
        (self.root / "shared" / "prompts" / "ops-guide.md").write_text("## Ops\nSave to {SLUG}/YYYY-MM-DD.md")

    def tearDown(self):
        self.tmp.cleanup()

    def test_assemble_writes_prompt_md(self):
        result = assemble("test-slug", repo_root=self.root)
        out = self.root / "topics" / "test-slug" / "prompt.md"
        self.assertTrue(out.exists())
        self.assertEqual(result, out)

    def test_assemble_contains_all_three_layers(self):
        assemble("test-slug", repo_root=self.root)
        content = (self.root / "topics" / "test-slug" / "prompt.md").read_text()
        self.assertIn("Role: test", content)
        self.assertIn("## Design", content)
        self.assertIn("## Ops", content)

    def test_assemble_substitutes_slug(self):
        assemble("test-slug", repo_root=self.root)
        content = (self.root / "topics" / "test-slug" / "prompt.md").read_text()
        self.assertIn("test-slug", content)
        self.assertNotIn("{SLUG}", content)

    def test_assemble_raises_if_topic_md_missing(self):
        (self.root / "topics" / "test-slug" / "topic.md").unlink()
        with self.assertRaises(FileNotFoundError):
            assemble("test-slug", repo_root=self.root)

    def test_assemble_raises_if_design_guide_missing(self):
        (self.root / "shared" / "prompts" / "design-guide.md").unlink()
        with self.assertRaises(FileNotFoundError):
            assemble("test-slug", repo_root=self.root)

    def test_assemble_raises_if_ops_guide_missing(self):
        (self.root / "shared" / "prompts" / "ops-guide.md").unlink()
        with self.assertRaises(FileNotFoundError):
            assemble("test-slug", repo_root=self.root)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd ~/newsletters
uv run python -m pytest tests/test_assemble_prompt.py -v
```

Expected: `ModuleNotFoundError: No module named 'shared.assemble_prompt'`

- [ ] **Step 3: Create `shared/assemble_prompt.py`**

> **Note on spec divergence:** The spec's code sketch for `assemble()` does not show `{SLUG}` substitution, but the `ops-guide.md` and `design-guide.md` files use `{SLUG}` as a literal token (e.g., `~/newsletters/topics/{SLUG}/site/template.html`). The implementation below performs the substitution, which is the correct behavior. The spec's code was a sketch, not the authoritative implementation.

```python
# shared/assemble_prompt.py
"""
Assembles topics/<slug>/prompt.md from three layers:
  1. topics/<slug>/topic.md      — topic-specific research
  2. shared/prompts/design-guide.md — locked design conventions
  3. shared/prompts/ops-guide.md    — locked delivery steps

The string {SLUG} in design-guide.md and ops-guide.md is replaced with the slug.
"""
import sys
from pathlib import Path

_DEFAULT_REPO_ROOT = Path(__file__).parent.parent


def assemble(slug: str, repo_root: Path = _DEFAULT_REPO_ROOT) -> Path:
    """Assemble prompt.md from three layers. Returns path to written file.

    Raises FileNotFoundError if any layer file is missing.
    """
    shared_prompts = repo_root / "shared" / "prompts"
    layers = {
        "topic":  repo_root / "topics" / slug / "topic.md",
        "design": shared_prompts / "design-guide.md",
        "ops":    shared_prompts / "ops-guide.md",
    }
    for name, path in layers.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing {name} layer: {path}")

    topic_text  = layers["topic"].read_text()
    design_text = layers["design"].read_text().replace("{SLUG}", slug)
    ops_text    = layers["ops"].read_text().replace("{SLUG}", slug)

    prompt = "\n\n---\n\n".join([topic_text, design_text, ops_text])
    out = repo_root / "topics" / slug / "prompt.md"
    out.write_text(prompt)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: assemble_prompt.py <slug>", file=sys.stderr)
        sys.exit(1)
    slug = sys.argv[1]
    try:
        out = assemble(slug)
        print(f"Assembled: {out}")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run python -m pytest tests/test_assemble_prompt.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/assemble_prompt.py tests/test_assemble_prompt.py
git commit -m "feat: add assemble_prompt.py with 3-layer prompt assembly"
```

---

## Task 3: Shared Prompt Layer Files

**Files:**
- Create: `shared/prompts/design-guide.md`
- Create: `shared/prompts/ops-guide.md`

- [ ] **Step 1: Create `shared/prompts/design-guide.md`**

```markdown
# Design Guide — Newsletter HTML Generation

## Template

Read the template file before generating HTML:
`~/newsletters/topics/{SLUG}/site/template.html`

Also read the stylesheet for class reference:
`~/newsletters/shared/assets/style.css`

**DO NOT modify style.css or template.html structure. All styling is locked.**

## Placeholders to Replace

| Placeholder | Value |
|---|---|
| `{{DATE_TITLE}}` | e.g. `March 22, 2026` |
| `{{DATE_LONG}}` | e.g. `Saturday, March 22, 2026` |
| `{{SIGNAL_DOTS}}` | N filled dots + (5-N) empty dots using `.signal-dot.filled` / `.signal-dot` CSS classes |
| `{{SIGNAL_RATING}}` | e.g. `4 / 5` |
| `{{VERSION_RANGE}}` | Date or version range covered |
| `{{RELEASE_ITEMS}}` | One `.release-item` div per event |
| `{{HIGHLIGHT_CARDS}}` | One `.highlight-card` div per highlight |
| `{{REPO_COUNT}}` | Integer count of repos/tools |
| `{{REPO_CARDS}}` | One `<a class="repo-card">` per repo |
| `{{COMMUNITY_BLOCKS}}` | One `.community-block` per source |
| `{{TIP_CONTENT}}` | Tip or context briefing text |
| `{{FOOTER_COLOPHON}}` | One-line day summary |

## HTML Patterns

**Signal dots (4 of 5 filled):**
```html
<div class="signal-dot filled"></div>
<div class="signal-dot filled"></div>
<div class="signal-dot filled"></div>
<div class="signal-dot filled"></div>
<div class="signal-dot"></div>
```

**Release item:**
```html
<div class="release-item">
  <span class="release-version">v2.1.81</span>
  <span class="release-date">Mar 21</span>
  <span class="release-desc">Description. Wrap CLI in <code>--flag</code> tags.</span>
</div>
```

**Highlight card (category classes: `voice` `model` `company` `promo`):**
```html
<div class="highlight-card voice">
  <div class="highlight-label">Category</div>
  <div class="highlight-title">Title</div>
  <div class="highlight-desc">Description text.</div>
</div>
```

**Repo card (difficulty classes: `easy` `medium` `advanced`):**
```html
<a href="https://github.com/owner/repo" target="_blank" rel="noopener" class="repo-card">
  <div class="repo-top">
    <span class="repo-name">owner/repo</span>
    <div class="repo-badges">
      <span class="repo-stars">12k</span>
      <span class="repo-diff easy">Easy</span>
    </div>
  </div>
  <div class="repo-desc">One-line description.</div>
  <div class="repo-why">Why it's relevant — one sentence.</div>
</a>
```

**Community block:**
```html
<div class="community-block">
  <div class="source-name">
    <span class="source-icon">&#128172;</span> Reddit
    <span class="source-meta">r/ClaudeAI &middot; 612k members</span>
  </div>
  <div class="community-item">
    <div class="community-title">Post title <span class="upvote-badge">&#9650; 1.2k</span></div>
    <div class="community-detail">Summary. <a href="URL" target="_blank">Read &rarr;</a></div>
  </div>
</div>
```

If a section has no content, write "Nothing notable today" — do not pad with filler.
```

- [ ] **Step 2: Create `shared/prompts/ops-guide.md`**

```markdown
# Operations Guide — Newsletter Delivery

## ACTIONS (execute in order)

Today's date: determine from system clock (format YYYY-MM-DD).

1. Search the web thoroughly for all sections in the topic brief above.

2. Compile newsletter content.

3. Save raw markdown to:
   `~/newsletters/topics/{SLUG}/YYYY-MM-DD.md`
   (replace YYYY-MM-DD with today's date)

4. Read the template:
   `~/newsletters/topics/{SLUG}/site/template.html`

5. Fill all {{PLACEHOLDERS}} with compiled content following the design guide above.
   Save generated HTML to:
   `~/newsletters/topics/{SLUG}/site/index.html`

6. Save dated archive copy:
   `cp ~/newsletters/topics/{SLUG}/site/index.html ~/newsletters/topics/{SLUG}/site/YYYY-MM-DD.html`

7. Build portal:
   `cd ~/newsletters && uv run shared/build.py`

8. Send one Telegram message to chat_id 1538018072:
   Link: `http://100.110.249.12:8787/{SLUG}/`
   Include: today's date, 1-sentence summary of top story.

9. Exit — do not start or restart the HTTP server (handled by run.sh).
```

- [ ] **Step 3: Verify assemble works with real guides**

```bash
cd ~/newsletters
# This will fail until topic.md exists — that's expected
uv run shared/assemble_prompt.py claude-digest 2>&1
```

Expected: `Error: Missing topic layer: .../topics/claude-digest/topic.md`

- [ ] **Step 4: Commit**

```bash
git add shared/prompts/
git commit -m "feat: add shared design-guide.md and ops-guide.md prompt layers"
```

---

## Task 4: Migrate Existing `prompt.md` → `topic.md`

**Files:**
- Create: `topics/claude-digest/topic.md`
- Create: `topics/google-ai/topic.md`
- Create: `topics/us-iran-war/topic.md`
- Delete: `topics/*/prompt.md` (after topic.md confirmed working)

The existing `prompt.md` files contain the full monolith. Extract only the topic-specific content (role, audience, sources, sections) for `topic.md`. The design and ops sections are now in the shared guides.

- [ ] **Step 1: Create `topics/claude-digest/topic.md`**

Read `topics/claude-digest/prompt.md` — copy only the research/content sections (everything before "OUTPUT FORMAT"). Create `topic.md`:

```markdown
# Claude Digest — Topic Brief

## Identity
- Role: technical newsletter curator covering Anthropic, Claude Code, and the Claude ecosystem for developers and AI practitioners
- Audience: developers and AI practitioners
- Signal label: Signal (1–5, where 5 = major release or breaking change day)

## Sources

**Claude Code releases:**
- GitHub releases: github.com/anthropics/claude-code/releases
- npm changelog: npmjs.com/package/@anthropic-ai/claude-code
- Claude Code changelog: docs.anthropic.com/claude-code/changelog

**Anthropic official:**
- Anthropic blog: anthropic.com/news
- Anthropic research: anthropic.com/research
- Model releases: docs.anthropic.com/claude/models

**Community:**
- Hacker News: news.ycombinator.com (search "Claude", "Anthropic", "claude-code")
- Reddit: r/ClaudeAI, r/MachineLearning, r/LocalLLaMA
- X/Twitter: @AnthropicAI, @alexalbert__, @AmandaAskell, notable dev accounts

**GitHub ecosystem:**
- Trending repos tagged "claude", "anthropic", "mcp"
- MCP servers: github.com/modelcontextprotocol

**Research & papers:**
- arXiv (cs.AI, cs.CL): new Anthropic-affiliated papers
- Hugging Face: new Anthropic models, papers

## Sections

### Section 01: Claude Code (past 7 days)
Track all Claude Code CLI releases. Include version numbers, dates, key features/fixes.
Wrap CLI flags in `<code>` tags. If nothing new: "No releases this week."

### Section 02: Anthropic Official (past 7 days)
Major announcements, model releases, policy updates, blog posts.
Highlight card categories: `voice` (product/features), `model` (models/research), `company` (org news), `promo` (partnerships/enterprise).
Aim for 4–6 cards.

### Section 03: GitHub Picks (past 7 days)
Trending or newly notable repos related to Claude, Anthropic, MCP, or AI tooling.
Include: name, stars, 1-line description, why it's interesting, difficulty.
Aim for 5–8 repos.

### Section 04: Community & Research (past 24 hours)
Top posts from Reddit and HN. Notable tweets from key accounts. New arXiv papers.
Include: title, upvotes/engagement, 1-sentence summary, link.

### Section 05: Tip of the Day
One practical, actionable tip for Claude Code or Claude API users.
Include a code example if applicable. Prefer tips that are non-obvious or recently enabled.
```

- [ ] **Step 2: Create `topics/google-ai/topic.md`**

```markdown
# Google AI — Topic Brief

## Identity
- Role: technical newsletter curator covering Google's AI announcements, releases, and research for developers and AI practitioners
- Audience: developers and AI practitioners
- Signal label: Signal (1–5, where 5 = major model release or API breaking change)

## Sources

**Official Google sources:**
- Google AI Blog: blog.google/technology/ai/
- Google Developers Blog: developers.googleblog.com
- Gemini API Changelog: ai.google.dev/gemini-api/docs/changelog
- Vertex AI Release Notes: cloud.google.com/vertex-ai/docs/release-notes
- Google Cloud Blog: cloud.google.com/blog/

**Model & API:**
- Gemini Apps Release Notes: gemini.google/release-notes/
- Google AI Studio: aistudio.google.com
- Gemini CLI: github.com/google-gemini/gemini-cli

**Research:**
- Google Research: research.google
- DeepMind: deepmind.google/research/
- arXiv: papers authored by Google/DeepMind

**Community:**
- Reddit: r/GoogleGeminiAI, r/MachineLearning, r/artificial, r/LocalLLaMA
- X/Twitter: @Google, @GoogleAI, @GoogleDeepMind, @JeffDean, @DemisHassabis

## Sections

### Section 01: Model Releases & API Updates (past 7 days)
Gemini model family updates, new versions, deprecations, API changes, SDK updates.
Sub-categories: Model releases, API changes, SDK updates, Developer tools.

### Section 02: Strategic Highlights (past 7 days)
Major announcements, product launches, research breakthroughs, partnerships.
Highlight card categories: `voice` (product/consumer AI), `model` (models/research), `company` (DeepMind/org), `promo` (cloud/enterprise).
Aim for 4–6 cards.

### Section 03: GitHub Picks (past 7 days)
Official google-gemini/* repos, community Gemini ecosystem repos, fine-tuning tools, benchmarks.
Include: name, stars, 1-line description, why interesting, difficulty.
Aim for 5–8 repos.

### Section 04: Community & Research (past 24 hours)
Top Reddit posts, notable tweets, new arXiv papers from Google/DeepMind.
Include: title, engagement, 1-sentence summary, link.

### Section 05: Developer Tip of the Day
One practical, actionable tip for Gemini API, Vertex AI, or Gemini CLI.
Include a code example if applicable.
```

- [ ] **Step 3: Create `topics/us-iran-war/topic.md`**

```markdown
# US–Iran Conflict — Topic Brief

## Identity
- Role: geopolitical intelligence briefing curator covering the US–Iran conflict for an informed general audience
- Audience: informed general reader interested in geopolitics
- Signal label: Escalation (1–5, where 5 = active military exchange or imminent strike)

## Sources

**Breaking news:**
- Reuters, AP News, BBC News, Al Jazeera, CNN, NYT

**Official government:**
- Pentagon/DoD press releases: defense.gov
- US State Department briefings: state.gov
- Iranian state media: IRNA, Press TV, Fars News

**Regional:**
- Israeli media: Times of Israel, Haaretz
- Gulf media: Al Arabiya, The National (UAE)

**Analysis:**
- Think tanks: CSIS, Brookings, RAND, Atlantic Council, Crisis Group, Carnegie, IISS
- Defense outlets: War on the Rocks, The Drive/War Zone, Defense One, Janes
- Foreign policy: Foreign Affairs, Foreign Policy magazine

**Community & OSINT:**
- Reddit: r/geopolitics, r/worldnews, r/MiddleEastNews, r/iran, r/CredibleDefense
- X/Twitter: @AP, @Reuters, @Joyce_Karam, @ArmsControlWonk, @GeoConfirmed, @Bellingcat

## Sections

### Section 01: Breaking Developments (past 24 hours)
Military operations, diplomatic moves, political statements, regional spillover, civilian impact.
Include UTC timestamp and date for each event. Skip sub-categories with nothing new.

### Section 02: Analysis & Strategic Highlights
Expert analysis, think tank reports, strategic commentary.
Highlight card categories: `voice` (military/defense), `model` (diplomatic/political), `company` (humanitarian), `promo` (international response/sanctions).
Aim for 4–6 cards.

### Section 03: OSINT & Data Tools (past 7 days)
Satellite imagery tools, flight/ship tracking, conflict maps, sanctions trackers, media monitoring.
Include: name+link, stars (if GitHub), 1-line description, relevance to US–Iran, difficulty tag.
Aim for 4–6 tools.

### Section 04: Community & Social Media (past 24 hours)
Top Reddit posts (title, upvotes, top comment summary, link).
Notable tweets from journalists and analysts (text summary, engagement, link).

### Section 05: Context Briefing
Concise paragraph: key historical/political context behind today's top story.
Why it matters strategically. What to watch for next (escalation triggers or de-escalation signals).
```

- [ ] **Step 4: Verify assembly works for all three topics**

```bash
cd ~/newsletters
uv run shared/assemble_prompt.py claude-digest
uv run shared/assemble_prompt.py google-ai
uv run shared/assemble_prompt.py us-iran-war
```

Expected for each: `Assembled: .../topics/<slug>/prompt.md`

Check content of one:
```bash
head -5 topics/claude-digest/prompt.md
tail -20 topics/claude-digest/prompt.md
```

Expected: starts with `# Claude Digest — Topic Brief`, ends with Telegram delivery ops.

- [ ] **Step 5: Delete old prompt.md files (now replaced by assembled artifacts)**

The assembled `topics/*/prompt.md` files are now the correct output. The `.gitignore` entry `topics/*/prompt.md` will exclude them from version control.

```bash
# The assembled prompt.md files exist and are gitignored — nothing to delete manually.
# Verify gitignore is working:
git status topics/claude-digest/
```

Expected: `prompt.md` does NOT appear in `git status` output (it's gitignored).

- [ ] **Step 6: Update `tests/test_build.py`**

Remove the three `topics/*/prompt.md` entries from `expected_files` (they're now gitignored build artifacts). The build test should not expect them.

Find and remove these lines from `expected_files` list in `tests/test_build.py`:
```python
REPO_ROOT / "topics" / "claude-digest" / "prompt.md",   # REMOVE
REPO_ROOT / "topics" / "google-ai" / "prompt.md",        # REMOVE
REPO_ROOT / "topics" / "us-iran-war" / "prompt.md",      # REMOVE
```

Add verification that `topic.md` files exist:
```python
REPO_ROOT / "topics" / "claude-digest" / "topic.md",
REPO_ROOT / "topics" / "google-ai" / "topic.md",
REPO_ROOT / "topics" / "us-iran-war" / "topic.md",
REPO_ROOT / "shared" / "prompts" / "design-guide.md",
REPO_ROOT / "shared" / "prompts" / "ops-guide.md",
```

- [ ] **Step 7: Run existing tests**

```bash
uv run python -m pytest tests/ -v
```

Expected: All tests PASS including the updated `test_build.py`.

- [ ] **Step 8: Commit**

```bash
git add topics/claude-digest/topic.md topics/google-ai/topic.md topics/us-iran-war/topic.md
git add tests/test_build.py
git commit -m "feat: migrate monolithic prompt.md into topic.md per topic"
```

---

## Task 5: Templates, `notebooklm_runner.py` Stub, `build.py` Media Support

**Files:**
- Modify: `topics/claude-digest/site/template.html`
- Modify: `topics/google-ai/site/template.html`
- Modify: `topics/us-iran-war/site/template.html`
- Modify: `shared/build.py`
- Create: `shared/notebooklm_runner.py`
- Modify: `~/.claude/skills/newsletter-create/SKILL.md`

- [ ] **Step 1: Add `{{MEDIA_SECTION}}` to all three template.html files**

For each of `topics/claude-digest/site/template.html`, `topics/google-ai/site/template.html`, `topics/us-iran-war/site/template.html`:

Read the file, find the closing tag of Section 05 (`</section>` that ends the last section before the footer), and insert the placeholder on the next line:

```html
      {{MEDIA_SECTION}}
```

This must be placed after Section 05's closing `</section>` and before the `<footer>` element.

- [ ] **Step 2: Verify placeholder is present in each template**

```bash
grep -c "MEDIA_SECTION" topics/claude-digest/site/template.html
grep -c "MEDIA_SECTION" topics/google-ai/site/template.html
grep -c "MEDIA_SECTION" topics/us-iran-war/site/template.html
```

Expected: `1` for each file.

- [ ] **Step 3: Update `inject_nav()` and add media functions to `shared/build.py`**

Read `shared/build.py`. Make the following changes:

**3a. Update `inject_nav()` signature** to accept `slug` and `date`, and inject `data-slug`/`data-date` into `<body>`:

```python
def inject_nav(html: str, nav_html: str, slug: str = "", date: str = "") -> str:
    """Inject nav bar into existing HTML: add portal.css, body class, nav element."""
    # Rewrite style.css path to ../style.css (one level up from dist/<slug>/)
    html = re.sub(
        r'<link\s+rel="stylesheet"\s+href="style\.css"\s*/?>',
        '<link rel="stylesheet" href="../style.css">\n<link rel="stylesheet" href="../portal.css">',
        html,
    )

    # Add has-portal-nav class and data-slug/data-date to body
    data_attrs = f' data-slug="{slug}" data-date="{date}"' if slug else ""
    html = re.sub(r"<body([^>]*)>", rf'<body\1 class="has-portal-nav"{data_attrs}>', html, count=1)

    # Insert nav right after <body ...>
    html = re.sub(
        r'(<body[^>]*>)',
        rf'\1\n{nav_html}',
        html,
        count=1,
    )

    return html
```

**3b. Add stub media functions** after `inject_nav()`:

```python
def discover_media(topic_dir: Path, date: str) -> dict[str, Path | None]:
    """Find media files for a given date. Full impl in Plan B."""
    return {"infographic": None, "slides": None}


def copy_media(media: dict[str, Path | None], topic_dist: Path) -> dict[str, str]:
    """Copy media files to dist dir. Full impl in Plan B. Returns relative URLs."""
    return {}


def render_media_section(slug: str, date: str, media: dict[str, str]) -> str:
    """Render media section HTML from media URL dict.

    Plan A: renders placeholder stub regardless of media dict content.
    Plan B: renders infographic img, slides embed, and on-demand buttons.
    """
    return (
        f'<section class="portal-media-section" '
        f'data-slug="{slug}" data-date="{date}">'
        f'<!-- Media assets generated in Plan B -->'
        f'</section>'
    )
```

**3c. Update the call to `inject_nav()` in `build()`** to pass slug and date:

Find: `output_html = inject_nav(page_html, nav_html)`
Replace with:
```python
            output_html = inject_nav(page_html, nav_html, slug=slug, date=date)
```

**3d. Add media replacement after inject_nav call** in `build()`:

After the `inject_nav` call, add:
```python
            media = copy_media(discover_media(topic_dir, date), topic_dist)
            media_html = render_media_section(slug, date, media)
            output_html = output_html.replace("{{MEDIA_SECTION}}", media_html)
```

- [ ] **Step 4: Verify build still works**

```bash
cd ~/newsletters
uv run shared/build.py
```

Expected: `Built portal: 3 topics → dist/` (no `{{MEDIA_SECTION}}` literal in output)

```bash
grep -r "MEDIA_SECTION" dist/ | wc -l
```

Expected: `0` (placeholder replaced in all pages).

- [ ] **Step 5: Create `shared/notebooklm_runner.py`** (stub — full implementation in Plan B)

```python
# shared/notebooklm_runner.py
"""NotebookLM media generation runner.

This is a Plan A STUB. Full implementation in Plan B.
Interface is defined here so pipeline.py can import it without error.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent


def generate_issue_media(slug: str, date: str) -> dict[str, str]:
    """Generate infographic and slides for a newsletter issue.

    Plan A: logs a skip message and returns empty dict.
    Plan B: invokes notebooklm CLI to generate artifacts.

    Args:
        slug: Topic slug (e.g. 'claude-digest')
        date: Issue date in YYYY-MM-DD format

    Returns:
        dict with keys 'infographic', 'slides', 'podcast', 'video'
        (empty in Plan A stub; populated with relative URLs in Plan B)
    """
    logger.info("NotebookLM media generation: Plan A stub — skipping for %s/%s", slug, date)
    return {}
```

- [ ] **Step 6: Verify notebooklm_runner stub imports cleanly**

```bash
cd ~/newsletters
uv run python -c "from shared.notebooklm_runner import generate_issue_media; print(generate_issue_media('test', '2026-03-22'))"
```

Expected: `{}`

- [ ] **Step 7: Create `shared/templates/topic-template.html`**

This is copied by `pipeline.py` when creating new topics via `POST /api/topics`. It must use the same `{{PLACEHOLDER}}` conventions as existing templates.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{DATE_TITLE}} — {{TOPIC_NAME}}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="masthead">
    <div class="masthead-inner">
      <div class="masthead-eyebrow">Daily Intelligence Brief</div>
      <h1 class="masthead-title">{{TOPIC_NAME}}</h1>
      <div class="masthead-date">{{DATE_LONG}}</div>
      <div class="masthead-meta">
        <span class="signal-label">{{SIGNAL_LABEL}}</span>
        <span class="signal-rating">{{SIGNAL_RATING}}</span>
        <div class="signal-dots">{{SIGNAL_DOTS}}</div>
      </div>
    </div>
  </header>

  <main class="container">

    <section class="section" id="section-01">
      <h2 class="section-title">{{SECTION_01_TITLE}}</h2>
      <div class="release-list">{{RELEASE_ITEMS}}</div>
    </section>

    <section class="section" id="section-02">
      <h2 class="section-title">{{SECTION_02_TITLE}}</h2>
      <div class="highlight-grid">{{HIGHLIGHT_CARDS}}</div>
    </section>

    <section class="section" id="section-03">
      <h2 class="section-title">{{SECTION_03_TITLE}}</h2>
      <div class="repo-count">{{REPO_COUNT}} picks</div>
      <div class="repo-grid">{{REPO_CARDS}}</div>
    </section>

    <section class="section" id="section-04">
      <h2 class="section-title">{{SECTION_04_TITLE}}</h2>
      <div class="community-feed">{{COMMUNITY_BLOCKS}}</div>
    </section>

    <section class="section" id="section-05">
      <h2 class="section-title">{{SECTION_05_TITLE}}</h2>
      <div class="tip-content">{{TIP_CONTENT}}</div>
    </section>

    {{MEDIA_SECTION}}

  </main>

  <footer class="footer">
    <div class="footer-colophon">{{FOOTER_COLOPHON}}</div>
  </footer>
</body>
</html>
```

- [ ] **Step 8: Create on-demand stub files**  <!-- Step 8 correct -->

Create `shared/prompts/on-demand-listener.md` — a Plan B stub so `run.sh` can reference it without error:

```markdown
# On-Demand Briefing Listener

**Plan B stub.** Full implementation in Plan B.

This prompt configures a persistent Claude Code session that listens for
Telegram messages and generates on-demand briefings.

When a Telegram message arrives starting with `brief:`, `research:`, or
`on-demand:`, generate a briefing HTML and reply with the Tailscale link.

**Status:** Not yet implemented — run.sh includes this as a commented-out stub.
```

Create `shared/templates/on-demand-template.html` — a minimal HTML stub:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{BRIEFING_TITLE}}</title>
  <link rel="stylesheet" href="../../style.css">
</head>
<body>
  <main class="container">
    <h1>{{BRIEFING_TITLE}}</h1>
    <p class="date">{{DATE_LONG}}</p>
    <div class="briefing-content">{{BRIEFING_CONTENT}}</div>
  </main>
</body>
</html>
```

- [ ] **Step 9: Update `newsletter-create` skill to output `topic.md` format**  <!-- Step 9 correct -->

Read `~/.claude/skills/newsletter-create/SKILL.md`. Find the section that defines the output path and format. Update it so the skill:
- Writes output to `topics/<slug>/topic.md` (not `prompt.md`)
- Generates only: Identity section (role, audience, signal label) + Sources + Sections
- Explicitly does NOT include: HTML output instructions, build steps, Telegram delivery steps, or `{{PLACEHOLDER}}` references

Add this note at the top of the output format section:
```
## Output Contract (topic.md format)

Output ONLY `topics/<slug>/topic.md`. Do NOT create `prompt.md`.
The file must contain:
  1. ## Identity — role, audience, signal label
  2. ## Sources — categorized list of URLs/sources to monitor
  3. ## Sections — named sections with research instructions

Do NOT include: placeholder syntax, build commands, Telegram steps,
or HTML generation instructions. These are in the shared ops-guide.
```

- [ ] **Step 10: Commit**

```bash
git add topics/claude-digest/site/template.html topics/google-ai/site/template.html topics/us-iran-war/site/template.html
git add shared/build.py shared/notebooklm_runner.py
git add shared/templates/topic-template.html
git add shared/prompts/on-demand-listener.md shared/templates/on-demand-template.html
git commit -m "feat: MEDIA_SECTION placeholder, build.py media stubs, notebooklm_runner stub, topic-template, on-demand stubs"
```

---

## Task 6: FastAPI Server Skeleton  <!-- was Task 5 -->

**Files:**
- Create: `server/__init__.py`
- Create: `server/routers/__init__.py`
- Create: `server/main.py`

- [ ] **Step 1: Create package markers**

```bash
touch server/__init__.py
touch server/routers/__init__.py
```

- [ ] **Step 2: Create `server/main.py`**

```python
# server/main.py
"""Newsletter Portal FastAPI application.

Serves dist/ as static files and exposes /api/* routes.
API routes MUST be registered before the StaticFiles mount.
"""
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DIST_DIR  = REPO_ROOT / "dist"

app = FastAPI(title="Newsletter Portal", version="2.0.0")

# Import and register routers lazily to avoid circular imports
def _register_routers():
    from server.routers.generate   import router as generate_router
    from server.routers.topics     import router as topics_router
    from server.routers.jobs_router import router as jobs_router

    app.include_router(generate_router, prefix="/api/generate", tags=["generate"])
    app.include_router(topics_router,   prefix="/api/topics",   tags=["topics"])
    app.include_router(jobs_router,     prefix="/api/jobs",     tags=["jobs"])

_register_routers()

# Static files MUST be mounted after all /api/* routes
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("server.main:app", host="0.0.0.0", port=8787, reload=False)
```

- [ ] **Step 3: Verify syntax (routers don't exist yet — import will fail)**

```bash
cd ~/newsletters
uv run python -c "import ast; ast.parse(open('server/main.py').read()); print('Syntax OK')"
```

Expected: `Syntax OK`. (A full `from server.main import app` will raise `ModuleNotFoundError` for the routers until Task 8 — that is expected. The syntax check confirms the file is valid Python.)

- [ ] **Step 4: Commit skeleton**

```bash
git add server/__init__.py server/routers/__init__.py server/main.py
git commit -m "feat: add FastAPI server skeleton"
```

---

## Task 7: Job Store  <!-- was Task 6 -->

**Files:**
- Create: `tests/test_jobs.py`
- Create: `server/jobs.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_jobs.py
import sys
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from server.jobs import create, update, get, JobStatus


class JobStoreTest(unittest.TestCase):

    def test_create_returns_string_id(self):
        job_id = create()
        self.assertIsInstance(job_id, str)
        self.assertGreater(len(job_id), 0)

    def test_new_job_is_pending(self):
        job_id = create()
        job = get(job_id)
        self.assertEqual(job.status, JobStatus.pending)
        self.assertEqual(job.step, "")
        self.assertEqual(job.artifact_url, "")
        self.assertEqual(job.error, "")

    def test_get_returns_none_for_unknown_id(self):
        self.assertIsNone(get("does-not-exist"))

    def test_update_status(self):
        job_id = create()
        update(job_id, status=JobStatus.running, step="Doing something...")
        job = get(job_id)
        self.assertEqual(job.status, JobStatus.running)
        self.assertEqual(job.step, "Doing something...")

    def test_update_done_with_artifact_url(self):
        job_id = create()
        update(job_id, status=JobStatus.done, artifact_url="/dist/media/test.mp3")
        job = get(job_id)
        self.assertEqual(job.status, JobStatus.done)
        self.assertEqual(job.artifact_url, "/dist/media/test.mp3")

    def test_update_failed_with_error(self):
        job_id = create()
        update(job_id, status=JobStatus.failed, error="Timeout after 600s")
        job = get(job_id)
        self.assertEqual(job.status, JobStatus.failed)
        self.assertEqual(job.error, "Timeout after 600s")

    def test_concurrent_creates_are_unique(self):
        ids = []
        lock = threading.Lock()

        def make():
            jid = create()
            with lock:
                ids.append(jid)

        threads = [threading.Thread(target=make) for _ in range(50)]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertEqual(len(ids), len(set(ids)), "Duplicate job IDs created concurrently")

    def test_concurrent_updates_are_safe(self):
        job_id = create()
        errors = []

        def do_update(i):
            try:
                update(job_id, step=f"step-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_update, args=(i,)) for i in range(20)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run python -m pytest tests/test_jobs.py -v
```

Expected: `ModuleNotFoundError: No module named 'server.jobs'`

- [ ] **Step 3: Create `server/jobs.py`**

```python
# server/jobs.py
"""Thread-safe in-memory job store.

Jobs are lost on server restart — this is acceptable since daily runs happen
overnight and on-demand generation is a daytime activity with no overlap.
"""
import threading
import uuid
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
    step: str = ""           # Human-readable current step label
    artifact_url: str = ""   # Populated on done (relative URL to served file)
    error: str = ""          # Populated on failed


_store: dict[str, Job] = {}
_lock  = threading.Lock()


def create() -> str:
    """Create a new pending job. Returns the job ID."""
    job = Job()
    with _lock:
        _store[job.id] = job
    return job.id


def update(job_id: str, **kwargs) -> None:
    """Update job fields by keyword. Thread-safe."""
    with _lock:
        job = _store[job_id]
        for k, v in kwargs.items():
            setattr(job, k, v)


def get(job_id: str) -> Optional[Job]:
    """Return job or None if not found (server restarted, job expired)."""
    return _store.get(job_id)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run python -m pytest tests/test_jobs.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add server/jobs.py tests/test_jobs.py
git commit -m "feat: add thread-safe in-memory job store"
```

---

## Task 8: API Routers  <!-- was Task 7 -->

**Files:**
- Create: `server/routers/generate.py`
- Create: `server/routers/jobs_router.py`
- Create: `server/routers/topics.py`

- [ ] **Step 1: Create `server/routers/generate.py`** (Plan B stubs)

```python
# server/routers/generate.py
"""Generate router — on-demand NotebookLM media generation.

Endpoints return 501 Not Implemented in Plan A.
Full implementation in Plan B (notebooklm_runner.py).
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/{slug}/{date}/podcast")
async def start_podcast(slug: str, date: str):
    return JSONResponse({"error": "NotebookLM integration not yet available"}, status_code=501)


@router.post("/{slug}/{date}/video")
async def start_video(slug: str, date: str):
    return JSONResponse({"error": "NotebookLM integration not yet available"}, status_code=501)


@router.post("/{slug}/{date}/infographic")
async def start_infographic(slug: str, date: str):
    return JSONResponse({"error": "NotebookLM integration not yet available"}, status_code=501)
```

- [ ] **Step 2: Create `server/routers/jobs_router.py`**

```python
# server/routers/jobs_router.py
from fastapi import APIRouter, HTTPException
from server.jobs import get, Job

router = APIRouter()


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict:
    job = get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found — session may have expired")
    return {
        "id":           job.id,
        "status":       job.status.value,
        "step":         job.step,
        "artifact_url": job.artifact_url,
        "error":        job.error,
    }
```

- [ ] **Step 3: Create `server/routers/topics.py`**

```python
# server/routers/topics.py
import tomllib
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from server import jobs

router    = APIRouter()
REPO_ROOT = Path(__file__).parent.parent.parent


def _load_topics() -> dict:
    with open(REPO_ROOT / "topics.toml", "rb") as f:
        return tomllib.load(f)


class TopicCreate(BaseModel):
    name:         str
    description:  str = ""
    focus_areas:  str = ""
    accent:       str = "terracotta"
    signal_label: str = "Signal"


def _slugify(name: str) -> str:
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:40]


@router.get("")
async def list_topics() -> dict:
    config = _load_topics()
    topics = {
        slug: {
            "name":         t.get("name", slug),
            "description":  t.get("description", ""),
            "accent":       t.get("accent", "terracotta"),
            "signal_label": t.get("signal_label", "Signal"),
        }
        for slug, t in config.items()
    }
    return {"topics": topics, "count": len(config)}


@router.post("")
async def create_topic(payload: TopicCreate, background_tasks: BackgroundTasks) -> dict:
    from server.pipeline import submit_topic_creation
    slug   = _slugify(payload.name)
    job_id = jobs.create()
    background_tasks.add_task(submit_topic_creation, job_id, slug, payload)
    return {"job_id": job_id, "slug": slug}
```

- [ ] **Step 4: Verify server starts cleanly**

```bash
cd ~/newsletters
uv run python -c "
from server.main import app
print('Routes:')
for route in app.routes:
    if hasattr(route, 'methods'):
        print(f'  {list(route.methods)} {route.path}')
"
```

Expected: Lines showing all `/api/generate/*`, `/api/topics`, `/api/jobs/{job_id}` routes.

- [ ] **Step 5: Commit routers**

```bash
git add server/routers/
git commit -m "feat: add API routers (generate stubs, jobs, topics)"
```

---

## Task 9: Pipeline  <!-- was Task 8 -->

**Files:**
- Create: `server/pipeline.py`

- [ ] **Step 1: Create `server/pipeline.py`**

```python
# server/pipeline.py
"""Background job orchestration.

All long-running operations (topic creation) run in a shared ThreadPoolExecutor.
Claude is invoked via subprocess.run() — no Python SDK needed.
topics.toml writes are protected by a threading.Lock().
"""
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from server import jobs
from server.jobs import JobStatus

if TYPE_CHECKING:
    from server.routers.topics import TopicCreate

REPO_ROOT  = Path(__file__).parent.parent
_executor  = ThreadPoolExecutor(max_workers=4)
_toml_lock = threading.Lock()


def _update(job_id: str, step: str, status: JobStatus = JobStatus.running) -> None:
    jobs.update(job_id, step=step, status=status)


def _run_claude(task: str, max_turns: int = 10) -> None:
    """Invoke claude CLI via subprocess. Raises RuntimeError on non-zero exit."""
    result = subprocess.run(
        ["claude", "--task", task, "--dangerously-skip-permissions",
         "--max-turns", str(max_turns)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude exited {result.returncode}: {(result.stderr or result.stdout)[:500]}"
        )


def _append_topic_toml(slug: str, name: str, description: str,
                        accent: str, signal_label: str) -> None:
    """Append a new topic entry to topics.toml. Thread-safe via _toml_lock."""
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
        with open(REPO_ROOT / "topics.toml", "a") as f:
            f.write(entry)


def _create_topic_job(job_id: str, slug: str, payload: "TopicCreate") -> None:
    """Full new-topic creation pipeline. Runs in thread pool."""
    try:
        _update(job_id, "Scaffolding topic folder\u2026")
        topic_dir = REPO_ROOT / "topics" / slug
        (topic_dir / "site").mkdir(parents=True, exist_ok=True)
        (topic_dir / "media").mkdir(exist_ok=True)

        # Copy shared template
        tmpl_src = REPO_ROOT / "shared" / "templates" / "topic-template.html"
        css_src  = REPO_ROOT / "shared" / "assets" / "style.css"
        if tmpl_src.exists():
            shutil.copy2(tmpl_src, topic_dir / "site" / "template.html")
        if css_src.exists():
            shutil.copy2(css_src, topic_dir / "site" / "style.css")

        _update(job_id, "Generating research prompt\u2026")
        _run_claude(
            f"Use the newsletter-create skill to generate a topic.md file for a new newsletter.\n"
            f"Topic name: {payload.name}\n"
            f"Description: {payload.description}\n"
            f"Focus areas: {payload.focus_areas}\n"
            f"Output path: topics/{slug}/topic.md\n"
            f"Format: Identity section (role, audience, signal label) + Sources + Sections only.\n"
            f"Do NOT include HTML output instructions, build steps, or Telegram delivery steps.\n"
            f"Do NOT generate prompt.md. Write topic.md only.",
            max_turns=10,
        )
        topic_md = topic_dir / "topic.md"
        if not topic_md.exists():
            raise RuntimeError(
                f"newsletter-create did not produce topics/{slug}/topic.md"
            )

        _append_topic_toml(
            slug, payload.name, payload.description,
            payload.accent, payload.signal_label,
        )

        _update(job_id, "Assembling prompt\u2026")
        from shared.assemble_prompt import assemble
        assemble(slug)

        _update(job_id, "Running first newsletter issue\u2026")
        prompt_text = (topic_dir / "prompt.md").read_text()
        _run_claude(prompt_text, max_turns=25)

        _update(job_id, "Generating NotebookLM media\u2026")
        try:
            from shared.notebooklm_runner import generate_issue_media
            today = datetime.now().strftime("%Y-%m-%d")
            generate_issue_media(slug, today)
        except Exception as nlm_err:
            # Non-fatal: media generation failure does not abort topic creation
            import logging
            logging.getLogger(__name__).warning("NotebookLM skipped: %s", nlm_err)

        _update(job_id, "Building portal\u2026")
        subprocess.run(
            ["uv", "run", "shared/build.py"],
            cwd=REPO_ROOT,
            check=True,
        )

        jobs.update(job_id, step="Done \u2713", status=JobStatus.done)

    except Exception as e:
        jobs.update(job_id, status=JobStatus.failed, error=str(e))


def submit_topic_creation(job_id: str, slug: str, payload: "TopicCreate") -> None:
    """Submit topic creation to the thread pool. Called by FastAPI background task."""
    _executor.submit(_create_topic_job, job_id, slug, payload)
```

- [ ] **Step 2: Verify the full server starts**

```bash
cd ~/newsletters
# Start server in background, test routes, kill it
uv run server/main.py &
SERVER_PID=$!
sleep 2

curl -s http://localhost:8787/api/topics | python3 -m json.tool
curl -s http://localhost:8787/api/jobs/nonexistent | python3 -m json.tool
curl -s -o /dev/null -w "%{http_code}" http://localhost:8787/api/generate/claude-digest/2026-03-22/podcast

kill $SERVER_PID 2>/dev/null
```

Expected:
- `/api/topics` → `{"topics": {"claude-digest": {"name": "Claude Digest", ...}, ...}, "count": 3}`
- `/api/jobs/nonexistent` → 404 JSON with detail message
- `/api/generate/.../podcast` → `501`

- [ ] **Step 3: Commit**

```bash
git add server/pipeline.py
git commit -m "feat: add pipeline.py with ThreadPoolExecutor and topic creation flow"
```

---

## Task 10: Update `run.sh`  <!-- was Task 9 -->

**Files:**
- Modify: `run.sh`

- [ ] **Step 1: Replace `run.sh` with updated version**

```bash
#!/bin/bash
# ============================================================
# Daily Digest Portal — Runner Script (v2)
# Assembles prompts, runs newsletters, builds portal, serves.
# ============================================================
source ~/.zshrc 2>/dev/null || source ~/.bash_profile 2>/dev/null
REPO="$HOME/newsletters"

# --- Assemble prompts (topic.md + design-guide + ops-guide → prompt.md) ---
uv run "$REPO/shared/assemble_prompt.py" claude-digest || { echo "ERROR: assemble claude-digest failed"; exit 1; }
uv run "$REPO/shared/assemble_prompt.py" google-ai     || { echo "ERROR: assemble google-ai failed"; exit 1; }
uv run "$REPO/shared/assemble_prompt.py" us-iran-war   || { echo "ERROR: assemble us-iran-war failed"; exit 1; }

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

# --- Generate NotebookLM media (non-fatal; full impl in Plan B) ---
uv run python -c "
from shared.notebooklm_runner import generate_issue_media
from datetime import datetime
today = datetime.now().strftime('%Y-%m-%d')
for slug in ['claude-digest', 'google-ai', 'us-iran-war']:
    generate_issue_media(slug, today)
" || echo "NotebookLM media: skipped (Plan A stub)"

# --- Build portal ---
cd "$REPO" && uv run shared/build.py

# --- Serve (FastAPI replaces python3 -m http.server) ---
lsof -ti:8787 | xargs kill 2>/dev/null
sleep 1
nohup uv run "$REPO/server/main.py" > /tmp/newsletter-server.log 2>&1 &

# --- On-demand Telegram listener (stub file exists; full behavior in Plan B) ---
# Kills any existing listener and starts a new one
lsof -ti:0 -c claude 2>/dev/null | xargs kill 2>/dev/null || true
nohup claude --task "$(cat $REPO/shared/prompts/on-demand-listener.md)" \
  --channels plugin:telegram@claude-plugins-official \
  --dangerously-skip-permissions --max-turns 200 \
  > /tmp/newsletter-listener.log 2>&1 &

echo "$(date): portal built and served" >> "$REPO/log.txt"
```

- [ ] **Step 2: Verify assemble steps work**

```bash
cd ~/newsletters
bash -x run.sh 2>&1 | head -20
# Stop after assemble steps complete (ctrl+c before claude invocations)
```

Expected: Three `Assembled: ...` lines, no errors.

- [ ] **Step 3: Test server starts via run.sh**

Skip the claude invocations by commenting them out temporarily, then:

```bash
cd ~/newsletters && uv run shared/build.py && lsof -ti:8787 | xargs kill 2>/dev/null && nohup uv run server/main.py > /tmp/test-server.log 2>&1 &
sleep 2
curl -s http://localhost:8787/ | head -5
curl -s http://localhost:8787/api/topics
lsof -ti:8787 | xargs kill
```

Expected: HTML for the landing page, JSON for `/api/topics`.

- [ ] **Step 4: Commit**

```bash
git add run.sh
git commit -m "feat: update run.sh to use assemble_prompt + uvicorn"
```

---

## Task 11: Full Test Run  <!-- was Task 10 -->

- [ ] **Step 1: Run all tests**

```bash
cd ~/newsletters
uv run python -m pytest tests/ -v
```

Expected: All tests PASS — `test_build.py`, `test_assemble_prompt.py`, `test_jobs.py`.

- [ ] **Step 2: Smoke test the full API**

```bash
# Start server
cd ~/newsletters && uv run server/main.py &
sleep 2

# Landing page
curl -s -o /dev/null -w "Landing: %{http_code}\n" http://localhost:8787/

# Topic pages (require dist/ to exist — run build.py first)
uv run shared/build.py 2>/dev/null
curl -s -o /dev/null -w "Claude Digest: %{http_code}\n" http://localhost:8787/claude-digest/

# API routes
curl -s http://localhost:8787/api/topics | python3 -m json.tool
curl -s http://localhost:8787/api/jobs/badid
curl -s -X POST http://localhost:8787/api/generate/claude-digest/2026-03-22/podcast

kill %1
```

Expected output:
```
Landing: 200
Claude Digest: 200
{"topics": {"claude-digest": {"name": "Claude Digest", ...}, ...}, "count": 3}
{"detail": "Job not found — session may have expired"}
{"error": "NotebookLM integration not yet available"}
```

- [ ] **Step 3: Final commit**

```bash
git add -A
git status   # verify nothing unexpected is staged
git commit -m "feat: Plan A complete — prompt split + FastAPI server + job system"
```

---

## Plan A Complete

Plan A delivers (11 tasks):
- ✅ 3-layer prompt assembly (`topic.md` + shared guides, `{SLUG}` substitution)
- ✅ `{{MEDIA_SECTION}}` placeholder in all 3 templates
- ✅ `build.py`: updated `inject_nav()` with `data-slug`/`data-date` body attrs; stubs for `discover_media()`, `copy_media()`, `render_media_section(slug, date, media)`
- ✅ `shared/notebooklm_runner.py` stub (importable, returns `{}`)
- ✅ `shared/prompts/on-demand-listener.md` + `shared/templates/on-demand-template.html` stubs
- ✅ `newsletter-create` skill updated to output `topic.md` format only
- ✅ FastAPI server replacing `python3 -m http.server`
- ✅ Thread-safe in-memory job store
- ✅ `/api/topics` list (with full metadata) + create (topic creation runs full pipeline)
- ✅ `/api/jobs/{id}` polling
- ✅ `/api/generate/*` stubs (501, filled in Plan B)
- ✅ `run.sh`: non-fatal notebooklm step + on-demand listener started
- ✅ All existing tests pass

**Next:** Plan B — NotebookLM media generation + Create Briefing web form + On-demand Telegram listener
