#!/bin/bash
# ============================================================
# Daily Digest Portal — Runner Script (v3)
# Discovers topics dynamically from topics.json.
# Only assembles prompts and generates newsletters for topics
# that have topic.md on disk.
# ============================================================
source ~/.zshrc 2>/dev/null || source ~/.bash_profile 2>/dev/null
REPO="$HOME/newsletters"

# --- Ensure topics.json exists (migrate from topics.toml if needed) ---
if [ ! -f "$REPO/topics.json" ]; then
  echo "Migrating topics.toml → topics.json..."
  uv run python -c "from shared.topic_registry import migrate_from_toml; migrate_from_toml()"
fi

# --- Discover slugs from topics.json ---
SLUGS=$(uv run python -c "
import json
from pathlib import Path
registry = json.loads((Path('$REPO') / 'topics.json').read_text())
for slug in registry:
    print(slug)
")

# --- Assemble prompts + generate newsletters for topics with topic.md ---
for slug in $SLUGS; do
  topic_md="$REPO/topics/$slug/topic.md"
  if [ ! -f "$topic_md" ]; then
    echo "SKIP $slug: no topic.md"
    continue
  fi

  echo "--- Assembling prompt for $slug ---"
  uv run "$REPO/shared/assemble_prompt.py" "$slug" || { echo "ERROR: assemble $slug failed"; continue; }

  echo "--- Generating newsletter for $slug ---"
  claude --task "$(cat $REPO/topics/$slug/prompt.md)" \
    --channels plugin:telegram@claude-plugins-official \
    --dangerously-skip-permissions --max-turns 25
done

# --- Generate NotebookLM media (non-fatal) ---
uv run python -c "
from shared.notebooklm_runner import generate_issue_media
from shared.topic_registry import list_all, topic_md_exists
from datetime import datetime
today = datetime.now().strftime('%Y-%m-%d')
for slug in list_all():
    if topic_md_exists(slug):
        generate_issue_media(slug, today)
" || echo "NotebookLM media: skipped"

# --- Build portal ---
cd "$REPO" && uv run shared/build.py

# --- Serve (FastAPI) ---
lsof -ti:8787 | xargs kill 2>/dev/null
sleep 1
nohup uv run --directory "$REPO" -m server.main > /tmp/newsletter-server.log 2>&1 &

# --- On-demand Telegram listener ---
lsof -ti:0 -c claude 2>/dev/null | xargs kill 2>/dev/null || true
nohup claude --task "$(cat $REPO/shared/prompts/on-demand-listener.md)" \
  --channels plugin:telegram@claude-plugins-official \
  --dangerously-skip-permissions --max-turns 200 \
  > /tmp/newsletter-listener.log 2>&1 &

echo "$(date): portal built and served" >> "$REPO/log.txt"
