# Live Log Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream Claude CLI step transitions into a persistent bottom drawer in the Newsroom UI, differentiated for topic.md vs newsletter generation.

**Architecture:** Switch `_run_claude` from `subprocess.run` to `Popen` with `--output-format stream-json`. Parse each JSON line for `tool_use` events, format them as human-readable step lines, and append to a per-job `log_lines` list in the job store. A new `GET /api/jobs/{id}/log?from=N` endpoint serves buffered lines with an offset. The frontend polls this endpoint every 2 seconds when a job is active and renders lines into a fixed bottom drawer that auto-scrolls.

**Tech Stack:** Python 3.11 stdlib (`subprocess.Popen`, `json`), FastAPI, vanilla JS (no new deps)

---

## File Map

| Status | Path | Change |
|--------|------|--------|
| MODIFY | `server/jobs.py` | Add `log_lines: list[str]` field; add `append_log(job_id, line)` |
| MODIFY | `server/pipeline.py` | Switch `_run_claude` to Popen + stream-json; add `context` + `job_id` params |
| MODIFY | `server/routers/jobs_router.py` | Add `GET /{job_id}/log` endpoint |
| MODIFY | `shared/templates/manage.html` | Add log drawer HTML + CSS + JS |
| MODIFY | `tests/test_jobs.py` | Add tests for `append_log` and `log_lines` |

---

## Task 1: Extend Job store with log_lines

**Files:**
- Modify: `server/jobs.py`
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_jobs.py`:

```python
def test_job_has_empty_log_lines(self):
    job_id = jobs.create()
    job = jobs.get(job_id)
    self.assertEqual(job.log_lines, [])

def test_append_log_adds_lines(self):
    job_id = jobs.create()
    jobs.append_log(job_id, "🔍 Searching: quantum")
    jobs.append_log(job_id, "✍ Writing: topic.md")
    job = jobs.get(job_id)
    self.assertEqual(job.log_lines, ["🔍 Searching: quantum", "✍ Writing: topic.md"])

def test_append_log_concurrent(self):
    import threading
    job_id = jobs.create()
    threads = [threading.Thread(target=jobs.append_log, args=(job_id, f"line-{i}")) for i in range(50)]
    for t in threads: t.start()
    for t in threads: t.join()
    self.assertEqual(len(jobs.get(job_id).log_lines), 50)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_jobs.py -v -k "log"
```
Expected: FAIL — `Job` has no `log_lines`, `jobs` has no `append_log`.

- [ ] **Step 3: Implement**

In `server/jobs.py`, add to `Job` dataclass:
```python
log_lines: list = field(default_factory=list)
```

Add function after `get()`:
```python
def append_log(job_id: str, line: str) -> None:
    """Append a log line to the job. Thread-safe."""
    with _lock:
        job = _store.get(job_id)
        if job:
            job.log_lines.append(line)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_jobs.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add server/jobs.py tests/test_jobs.py
git commit -m "feat: add log_lines and append_log to job store"
```

---

## Task 2: Stream-json parsing in _run_claude

**Files:**
- Modify: `server/pipeline.py`

The goal: replace `subprocess.run` with `Popen`, add `--output-format stream-json`,
parse each JSON line for `tool_use` events, format per context.

**Formatting rules:**

For context `"newsletter"`:
| tool_name | input key | formatted line |
|-----------|-----------|----------------|
| `WebSearch` | `query` | `🔍 Searching: {query}` |
| `Write` | `file_path` | `✍ Writing: {basename}` |
| `Bash` | `command` | `⚡ Bash: {command[:80]}` |
| `Read` | `file_path` | `📖 Reading: {basename}` |
| `Edit` | `file_path` | `✏️ Editing: {basename}` |
| anything else | — | `🔧 {tool_name}` |

For context `"topic_md"`:
Only emit lines for `Write` events where `file_path` ends with `topic.md`:
`✍ Writing: topics/{slug}/topic.md`
All other tool calls: silent (no line appended).

- [ ] **Step 1: Replace `_run_claude` in `server/pipeline.py`**

Replace the existing function:

```python
def _format_log_line(tool_name: str, tool_input: dict, context: str) -> str | None:
    """Return a human-readable log line for a tool_use event, or None to skip."""
    if context == "topic_md":
        if tool_name == "Write":
            fp = tool_input.get("file_path", "")
            if fp.endswith("topic.md"):
                return f"✍ Writing: {fp}"
        return None  # suppress everything else for topic_md

    # newsletter context — full trail
    if tool_name == "WebSearch":
        q = tool_input.get("query", "")
        return f"🔍 Searching: {q}"
    if tool_name in ("Write", "NotebookEdit"):
        fp = tool_input.get("file_path", "")
        return f"✍ Writing: {fp.split('/')[-1] if '/' in fp else fp}"
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        return f"⚡ Bash: {cmd[:80]}"
    if tool_name == "Read":
        fp = tool_input.get("file_path", "")
        return f"📖 Reading: {fp.split('/')[-1] if '/' in fp else fp}"
    if tool_name in ("Edit", "MultiEdit"):
        fp = tool_input.get("file_path", "")
        return f"✏️ Editing: {fp.split('/')[-1] if '/' in fp else fp}"
    return f"🔧 {tool_name}"


def _run_claude(task: str, max_turns: int = 10,
                job_id: str | None = None,
                context: str | None = None) -> None:
    """Invoke claude CLI via subprocess. Raises RuntimeError on non-zero exit.

    If job_id is given, tool_use events are parsed from --output-format stream-json
    and appended to the job log as human-readable step lines.
    context: 'newsletter' | 'topic_md' | None  — controls which events are logged.
    """
    cmd = [
        "claude", "-p", task,
        "--dangerously-skip-permissions",
        "--max-turns", str(max_turns),
    ]
    if job_id:
        cmd += ["--output-format", "stream-json"]

    # stderr=STDOUT merges stderr into stdout so the stdout loop drains both,
    # preventing the pipe-buffer deadlock that occurs when reading stderr after wait().
    proc = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    stdout_lines: list[str] = []
    try:
        for raw in proc.stdout:
            raw = raw.strip()
            if not raw:
                continue
            stdout_lines.append(raw)
            if job_id:
                try:
                    event = json.loads(raw)
                    # Handle both batched (message.content[]) and streaming
                    # (content_block_start) forms of the stream-json output.
                    blocks = (event.get("message", {}) or {}).get("content", [])
                    # streaming form: content_block_start carries tool_use directly
                    cb = event.get("content_block", {})
                    if event.get("type") == "content_block_start" and cb.get("type") == "tool_use":
                        blocks = [cb]
                    for block in blocks:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            line = _format_log_line(
                                block.get("name", ""),
                                block.get("input", {}),
                                context or "newsletter",
                            )
                            if line:
                                jobs.append_log(job_id, line)
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
    finally:
        proc.wait(timeout=600)

    if proc.returncode != 0:
        raise RuntimeError(
            f"claude exited {proc.returncode}: {chr(10).join(stdout_lines[-20:])[:500]}"
        )
```

Also add `import json` at the top of `pipeline.py`.

- [ ] **Step 2: Update callers to pass job_id and context**

In `_create_topic_job`:
- First `_run_claude` call (generate topic.md): add `job_id=job_id, context="topic_md"`
- Second `_run_claude` call (first newsletter): add `job_id=job_id, context="newsletter"`

In `_newsletter_generation_job`:
- `_run_claude` call: add `job_id=job_id, context="newsletter"`

In `_topic_md_generation_job`:
- `_run_claude` call: add `job_id=job_id, context="topic_md"`

In `_media_generation_job`: no change (no `_run_claude` call here).

- [ ] **Step 3: Smoke test manually**

```bash
# restart server
lsof -ti:8787 | xargs kill -9 2>/dev/null; sleep 1
uv run -m server.main &
sleep 2

# trigger a topic.md generation (needs a topic with description but no topic.md)
curl -s -X POST http://localhost:8787/api/topics \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Log","description":"test","focus_areas":"testing"}' | python3 -m json.tool

# poll the log endpoint (use job_id from above)
curl -s "http://localhost:8787/api/jobs/<JOB_ID>/log"
```

Expected: `{"lines": ["✍ Writing: topic.md"], "total": 1}`

- [ ] **Step 4: Commit**

```bash
git add server/pipeline.py
git commit -m "feat: stream-json parsing in _run_claude with per-context log lines"
```

---

## Task 3: /log endpoint

**Files:**
- Modify: `server/routers/jobs_router.py`
- Test: `tests/test_jobs.py` (API-level — just verify shape, no router test needed)

- [ ] **Step 1: Add endpoint to `jobs_router.py`**

```python
@router.get("/{job_id}/log")
async def get_job_log(job_id: str, from_: int = Query(0, alias="from")) -> dict:
    job = get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    lines = job.log_lines[from_:]
    return {"lines": lines, "total": len(job.log_lines)}
```

Add import at top:
```python
from fastapi import APIRouter, HTTPException, Query
```

- [ ] **Step 2: Verify manually**

```bash
curl -s "http://localhost:8787/api/jobs/<JOB_ID>/log?from=0"
# → {"lines": [...], "total": N}
curl -s "http://localhost:8787/api/jobs/<JOB_ID>/log?from=5"
# → only lines after index 5
```

- [ ] **Step 3: Commit**

```bash
git add server/routers/jobs_router.py
git commit -m "feat: add GET /api/jobs/{id}/log endpoint with offset support"
```

---

## Task 4: Log drawer in manage.html

**Files:**
- Modify: `shared/templates/manage.html`

The drawer is a fixed bottom panel. Add:
1. HTML structure (after `</div><!-- toast-container -->`)
2. CSS (in the `<style>` block)
3. JS functions: `openDrawer(jobId, title, context)`, `closeDrawer()`, `startLogPoll(jobId)`

**HTML to add before `</body>`:**

```html
<!-- ═══════════ Log Drawer ═══════════ -->
<div class="log-drawer" id="log-drawer" style="display:none">
  <div class="log-drawer-header">
    <div class="log-drawer-title">
      <span class="log-drawer-dot"></span>
      <span id="log-drawer-title-text">Job</span>
    </div>
    <button class="log-drawer-close" onclick="closeDrawer()">✕</button>
  </div>
  <div class="log-drawer-body" id="log-drawer-body"></div>
</div>
```

**CSS to add inside `<style>`:**

```css
/* ── Log Drawer ──────────────────────────────────────────────── */
.log-drawer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 220px;
  background: var(--ink);
  color: var(--paper);
  z-index: 4000;
  display: flex;
  flex-direction: column;
  box-shadow: 0 -8px 40px rgba(32,26,18,0.3);
  animation: drawerIn 0.25s cubic-bezier(0.16,1,0.3,1);
}

@keyframes drawerIn {
  from { transform: translateY(100%); }
  to   { transform: translateY(0); }
}

.log-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 38px;
  border-bottom: 1px solid rgba(247,243,236,0.1);
  flex-shrink: 0;
}

.log-drawer-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(247,243,236,0.7);
}

.log-drawer-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--sage);
  animation: pulse 1.4s ease-in-out infinite;
}

.log-drawer-dot.done  { background: var(--sage);      animation: none; }
.log-drawer-dot.error { background: var(--terracotta); animation: none; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.35; }
}

.log-drawer-close {
  background: none;
  border: none;
  color: rgba(247,243,236,0.4);
  font-size: 12px;
  cursor: pointer;
  padding: 4px 8px;
  transition: color 0.2s;
}
.log-drawer-close:hover { color: var(--paper); }

.log-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 20px;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.8;
  color: rgba(247,243,236,0.8);
}

.log-line { white-space: pre-wrap; word-break: break-all; }
.log-line.done  { color: var(--sage); }
.log-line.error { color: var(--terracotta); }

.log-cursor {
  display: inline-block;
  width: 7px;
  height: 12px;
  background: rgba(247,243,236,0.6);
  margin-left: 2px;
  vertical-align: middle;
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}
```

**JS to add (inside `<script>`, before the closing `</script>`):**

```javascript
// ── Log Drawer ──
let _logJobId = null;
let _logInterval = null;
let _logOffset = 0;

function openDrawer(jobId, title) {
  _logJobId = jobId;
  _logOffset = 0;
  document.getElementById('log-drawer-title-text').textContent = title;
  document.getElementById('log-drawer-body').innerHTML = '';
  document.getElementById('log-drawer').style.display = 'flex';
  document.querySelector('.log-drawer-dot').className = 'log-drawer-dot';
  startLogPoll(jobId);
}

function closeDrawer() {
  document.getElementById('log-drawer').style.display = 'none';
  if (_logInterval) { clearInterval(_logInterval); _logInterval = null; }
  _logJobId = null;
}

function appendLogLine(text, cls) {
  const body = document.getElementById('log-drawer-body');
  // Remove blinking cursor if present
  const cursor = body.querySelector('.log-cursor');
  if (cursor) cursor.remove();

  const line = document.createElement('div');
  line.className = 'log-line' + (cls ? ' ' + cls : '');
  line.textContent = text;
  body.appendChild(line);

  if (!cls) {
    // Add blinking cursor after last active line
    const cur = document.createElement('span');
    cur.className = 'log-cursor';
    body.appendChild(cur);
  }
  body.scrollTop = body.scrollHeight;
}

function startLogPoll(jobId) {
  if (_logInterval) clearInterval(_logInterval);
  _logInterval = setInterval(async () => {
    try {
      const res = await fetch(`${API}/jobs/${jobId}/log?from=${_logOffset}`);
      if (!res.ok) return;
      const data = await res.json();
      data.lines.forEach(line => appendLogLine(line));
      _logOffset = data.total;

      // Also check job status to know when to stop
      const jres = await fetch(`${API}/jobs/${jobId}`);
      const jdata = await jres.json();
      if (jdata.status === 'done') {
        clearInterval(_logInterval); _logInterval = null;
        document.querySelector('.log-drawer-dot').className = 'log-drawer-dot done';
        const body = document.getElementById('log-drawer-body');
        const cursor = body.querySelector('.log-cursor');
        if (cursor) cursor.remove();
        appendLogLine('✓ Done', 'done');
      } else if (jdata.status === 'failed') {
        clearInterval(_logInterval); _logInterval = null;
        document.querySelector('.log-drawer-dot').className = 'log-drawer-dot error';
        const body = document.getElementById('log-drawer-body');
        const cursor = body.querySelector('.log-cursor');
        if (cursor) cursor.remove();
        appendLogLine('✗ ' + (jdata.error || 'failed'), 'error');
      }
    } catch (_) {}
  }, 2000);
}
```

**Wire up `openDrawer` calls:**

In `generateNewsletter(slug)` — after `toast('Job started...')`:
```javascript
openDrawer(data.job_id, `${slug} — Generating newsletter`);
```

In `pollTopicMdJob(jobId, slug, name)` — at the top of the function:
```javascript
openDrawer(jobId, `${name} — Generating topic.md`);
```

- [ ] **Step 1: Add HTML, CSS, JS to manage.html**

Apply all the additions described above.

- [ ] **Step 2: Rebuild portal**

```bash
uv run shared/build.py
```

- [ ] **Step 3: Smoke test in browser**

Open http://localhost:8787/manage.html
- Create a new topic with description/focus_areas
- Drawer should slide up showing "⚙ Generating topic brief…" dot and then "✍ Writing: topic.md"
- Once done: dot turns green, "✓ Done" appears

- [ ] **Step 4: Commit**

```bash
git add shared/templates/manage.html
git commit -m "feat: add live log drawer to Newsroom UI"
```

---

## Task 5: Rebuild dist and restart server

- [ ] **Step 1: Full rebuild and restart**

```bash
uv run shared/build.py
lsof -ti:8787 | xargs kill -9 2>/dev/null
sleep 1
nohup uv run -m server.main > /tmp/newsletter-server.log 2>&1 &
sleep 2
echo "ready"
```

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 3: Final commit if anything changed**

```bash
git add -p
git commit -m "chore: rebuild dist with log drawer"
```
