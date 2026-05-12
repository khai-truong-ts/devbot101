#!/bin/sh
set -e

if [ -n "$CLAUDE_CREDENTIALS_B64" ]; then
  mkdir -p "$HOME/.claude"
  printf '%s' "$CLAUDE_CREDENTIALS_B64" | base64 -d > "$HOME/.claude/.credentials.json"
  chmod 600 "$HOME/.claude/.credentials.json"
fi

exec python -m bot.main
