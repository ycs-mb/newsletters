# Topic Folder Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all topic content under `topics/`, move shared infrastructure under `shared/`, and preserve the generated `dist/` output structure and behavior.

**Architecture:** Normalize repository layout so `topics.toml` points to explicit topic folders and `shared/build.py` resolves all shared assets from a single place. Protect the refactor with focused builder tests that verify discovery, asset copying, and `dist/` output for the normalized layout.

**Tech Stack:** Python 3.11 stdlib (`pathlib`, `unittest`, `tempfile`, `tomllib`), shell scripts, static HTML/CSS

---

### Task 1: Add Builder Regression Tests

**Files:**
- Create: `tests/test_build.py`
- Test: `tests/test_build.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_uses_explicit_topic_folders_and_writes_dist():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_build -v`
Expected: FAIL because `shared/build.py` and the normalized layout do not exist yet.

- [ ] **Step 3: Write minimal implementation support in the test fixture**

Create a temporary repo fixture that mirrors the intended structure:
- `topics/<slug>/...`
- `shared/templates/...`
- `shared/assets/style.css`
- `topics.toml`

- [ ] **Step 4: Run test to verify it still fails for the expected reason**

Run: `uv run python -m unittest tests.test_build -v`
Expected: FAIL on missing builder behavior rather than test setup issues.

- [ ] **Step 5: Commit**

```bash
git add tests/test_build.py
git commit -m "test: add builder regression coverage"
```

### Task 2: Move Source Files Into `topics/` And `shared/`

**Files:**
- Create: `topics/claude-digest/`
- Create: `topics/google-ai/`
- Create: `topics/us-iran-war/`
- Create: `shared/templates/`
- Create: `shared/assets/`
- Modify: `topics.toml`

- [ ] **Step 1: Move the root topic into `topics/claude-digest/`**

Move:
- `prompt.md`
- `2026-03-22.md`
- `site/`

- [ ] **Step 2: Move existing topic folders under `topics/`**

Move:
- `google-ai/`
- `us-iran-war/`

- [ ] **Step 3: Move shared files into `shared/`**

Move:
- `build.py` → `shared/build.py`
- `portal.css` → `shared/portal.css`
- `templates/` → `shared/templates/`
- `site/style.css` copy equivalent → `shared/assets/style.css`

- [ ] **Step 4: Update `topics.toml` to use explicit topic folders**

Example:

```toml
folder = "topics/claude-digest"
```

- [ ] **Step 5: Commit**

```bash
git add topics shared topics.toml
git commit -m "refactor: normalize topic and shared folders"
```

### Task 3: Refactor The Builder For The New Layout

**Files:**
- Modify: `shared/build.py`
- Test: `tests/test_build.py`

- [ ] **Step 1: Write the failing test assertion for shared path resolution**

Add assertions covering:
- loading `topics.toml` from repo root
- reading templates from `shared/templates/`
- copying `shared/assets/style.css`

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_build -v`
Expected: FAIL because the moved builder still resolves old paths.

- [ ] **Step 3: Write minimal implementation**

Update constants and helper logic so `shared/build.py` resolves:
- `REPO_ROOT`
- `DIST_DIR`
- `TEMPLATES_DIR`
- shared stylesheet path
- topic directories directly from `topics.toml`

Remove the `folder = "."` special case.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_build -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/build.py tests/test_build.py
git commit -m "refactor: update builder for normalized layout"
```

### Task 4: Update Runner And Docs

**Files:**
- Modify: `run.sh`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write the failing test or verification note**

Document expected command paths:
- `uv run shared/build.py`
- `topics/<slug>/prompt.md`

- [ ] **Step 2: Update `run.sh`**

Change prompt paths and build invocation to the normalized layout while keeping `dist/` serving behavior unchanged.

- [ ] **Step 3: Update `CLAUDE.md`**

Refresh:
- commands
- architecture notes
- topic structure
- add-a-topic instructions

- [ ] **Step 4: Run verification**

Run:
- `uv run python -m unittest tests.test_build -v`
- `uv run shared/build.py`

Expected:
- tests pass
- `dist/index.html` exists
- each topic has `dist/<slug>/index.html`

- [ ] **Step 5: Commit**

```bash
git add run.sh CLAUDE.md dist
git commit -m "docs: update runner and repo structure"
```
