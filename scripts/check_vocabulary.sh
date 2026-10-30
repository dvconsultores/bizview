#!/bin/sh
# 043 WS-A / SC-002: the product no longer speaks the authoring agent's vocabulary.
#
# Fails when one of these words appears in shipped code or shipped docs:
#   asistente      the in-app chat (removed: specs 014/017/021/024/028/039/040)
#   speckit-       the in-app slash commands (the CLI's own are spelled /speckit.<stage>)
#   run_contract   the Auto-mode contract
#   token_budget   the retired conversation budget
#
# Excluded on purpose: cli/bizview_cli/workspace_template/ (the external authoring contract),
# specs/ (historical feature documents), CHANGELOG.md (it records what was removed) and
# alembic/versions/ (a migration has to name the tables it drops).
set -eu
cd "$(dirname "$0")/.."

PATHS=${*:-"backend/app frontend/src docs README.md README.es.md"}

hits=$(grep -rInE 'asistente|speckit-|run_contract|token_budget' $PATHS \
         --exclude-dir=workspace_template --exclude-dir=node_modules 2>/dev/null || true)

if [ -n "$hits" ]; then
  printf '%s\n' "$hits"
  printf '\nSC-002: %s hit(s). The product no longer speaks this vocabulary (043 WS-A).\n' \
    "$(printf '%s\n' "$hits" | wc -l)" >&2
  exit 1
fi
