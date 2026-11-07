#!/bin/sh
# 043 WS-A / SC-002 and 046: the product no longer speaks the authoring agent's vocabulary, and it
# is no longer "AI Powered".
#
# Fails when one of these words appears in shipped code, shipped docs or the community documents:
#   asistente      the in-app chat (removed: specs 014/017/021/024/028/039/040)
#   speckit-       the in-app slash commands (the CLI's own are spelled /speckit.<stage>)
#   run_contract   the Auto-mode contract
#   token_budget   the retired conversation budget
#   AI Powered     the name the product dropped in 0.2.0 (046)
#   source_chat    the structure chat 052 shipped and then removed (one generator button instead)
#   MAX_RECIPIENTS / SENDS_PER_HOUR   the volume ceilings 058 removed: the product has no quota, the
#                   mail provider governs the volume (spec 058 FR-004, SC-003)
#
# Excluded on purpose: cli/bizview_cli/workspace_template/ (the external authoring contract),
# specs/ (historical feature documents, and specs/_deprecated/ is where the removed features live),
# CHANGELOG.md (it records what was removed) and alembic/versions/ (a migration has to name the
# tables it drops). A line that must name a retired term anyway — the audit history it left behind,
# a label for that history — says so with `vocab-allow` and is skipped.
set -eu
cd "$(dirname "$0")/.."

PATHS=${*:-"backend/app frontend/src docs README.md README.es.md SECURITY.md CONTRIBUTING.md CODE_OF_CONDUCT.md"}

hits=$(grep -rInE 'asistente|speckit-|run_contract|token_budget|AI Powered|source_chat|MAX_RECIPIENTS|SENDS_PER_HOUR' $PATHS \
         --exclude-dir=workspace_template --exclude-dir=node_modules 2>/dev/null \
         | grep -v 'vocab-allow' || true)

if [ -n "$hits" ]; then
  printf '%s\n' "$hits"
  printf '\nSC-002: %s hit(s). The product no longer speaks this vocabulary (043 WS-A).\n' \
    "$(printf '%s\n' "$hits" | wc -l)" >&2
  exit 1
fi
