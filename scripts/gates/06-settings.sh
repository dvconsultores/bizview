#!/bin/sh
# Gate 6/6 (045): the removed agent's switches are gone from code, settings and documentation.
#
# `AI_CHAT_*` (rounds, timeouts, previews, budgets), `AI_AGENT_*` (concurrency, discovery),
# `AI_AUTO_*` (run contracts), `AI_COMMAND_TOKEN_CEILING`, `AI_CONTEXT_COMPACT_CHARS`,
# `AI_STAGE_TOKEN_BUDGET`, `AI_VISION`, `ATTACHMENTS_*` and the `fake` provider switch.
#
# $1: an optional path to check instead of the whole tree (used by the proof that the gate fails).
set -eu
cd "$(dirname "$0")/../.."

PATHS=${1:-"backend/app backend/alembic frontend/src deploy .env.example docs README.md README.es.md"}
PATTERN='AI_CHAT_|AI_AGENT_|AI_AUTO_|AI_COMMAND_TOKEN_CEILING|AI_CONTEXT_COMPACT_CHARS|AI_STAGE_TOKEN_BUDGET|AI_VISION|ATTACHMENTS_DIR|ATTACHMENTS_MAX|AI_TOOL_TIMEOUT_SECONDS|ai_provider=[\"'"'"']fake'

hits=$(grep -rInE "$PATTERN" $PATHS \
         --exclude-dir=node_modules --exclude-dir=workspace_template 2>/dev/null || true)

# A migration has to name what it removes; the deprecation note says what is no longer read.
hits=$(printf '%s\n' "$hits" | grep -vE 'alembic/versions/|CHANGELOG.md' || true)

if [ -n "$hits" ]; then
  printf '%s\n' "$hits"
  printf '\nthe removed authoring agent left %s switch(es) behind (045)\n' \
    "$(printf '%s\n' "$hits" | grep -c .)" >&2
  exit 1
fi
printf 'ok\n'
