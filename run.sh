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
nohup uv run --directory "$REPO" -m server.main > /tmp/newsletter-server.log 2>&1 &

# --- On-demand Telegram listener (stub file exists; full behavior in Plan B) ---
# Kills any existing listener and starts a new one
lsof -ti:0 -c claude 2>/dev/null | xargs kill 2>/dev/null || true
nohup claude --task "$(cat $REPO/shared/prompts/on-demand-listener.md)" \
  --channels plugin:telegram@claude-plugins-official \
  --dangerously-skip-permissions --max-turns 200 \
  > /tmp/newsletter-listener.log 2>&1 &

echo "$(date): portal built and served" >> "$REPO/log.txt"
