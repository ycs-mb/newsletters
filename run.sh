#!/bin/bash

# ============================================================
# Daily Digest Portal — Runner Script
# Runs all newsletter generators, builds portal, serves on :8787
# ============================================================

source ~/.zshrc 2>/dev/null || source ~/.bash_profile 2>/dev/null

NEWSLETTERS_DIR=~/newsletters

# --- Run each newsletter generator ---

# Claude Digest
claude --task "$(cat $NEWSLETTERS_DIR/topics/claude-digest/prompt.md)" \
  --channels plugin:telegram@claude-plugins-official \
  --dangerously-skip-permissions \
  --max-turns 25

# Google AI Digest
claude --task "$(cat $NEWSLETTERS_DIR/topics/google-ai/prompt.md)" \
  --channels plugin:telegram@claude-plugins-official \
  --dangerously-skip-permissions \
  --max-turns 25

# US-Iran Conflict Briefing
claude --task "$(cat $NEWSLETTERS_DIR/topics/us-iran-war/prompt.md)" \
  --channels plugin:telegram@claude-plugins-official \
  --dangerously-skip-permissions \
  --max-turns 25

# --- Build the portal ---
cd $NEWSLETTERS_DIR && uv run shared/build.py

# --- Serve on single port ---
lsof -ti:8787 | xargs kill 2>/dev/null
lsof -ti:8788 | xargs kill 2>/dev/null
lsof -ti:8789 | xargs kill 2>/dev/null
cd $NEWSLETTERS_DIR/dist && nohup python3 -m http.server 8787 > /dev/null 2>&1 &

# Log it
echo "$(date): portal built and served" >> $NEWSLETTERS_DIR/log.txt
