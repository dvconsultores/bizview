#!/bin/sh
# 045 / SC-002: the in-app authoring agent cannot come back by accident.
#
# The gates live in scripts/gates/, one per concern, each naming what it refuses:
#   01-vocabulary    the words the removed agent used (delegates to 043 WS-A's script)
#   02-dead-code     modules and exports nothing reads
#   03-dependencies  packages installed that nothing imports
#   04-routes        no /assistant, /commands, /runs or /contracts endpoint, no assistant page
#   05-migration     a seeded database upgrades, its applied specs survive, the tables are gone
#   06-settings      no AI_CHAT_*, AI_AGENT_*, AI_AUTO_* or fake-provider switch left behind
#   07-version       one version in VERSION, every copy equal, /api/health agreeing (046)
#   08-markdown      fences, tables, relative links, headings and README parity (046)
#
# `all.sh` runs every gate that needs no database; 05 needs DATABASE_URL_BI and runs alone.
# CI runs them all: .github/workflows/gates.yml.
set -eu
cd "$(dirname "$0")/../.."

failed=0
for gate in scripts/gates/[0-9][0-9]-*.sh; do
  case "$gate" in
    *05-migration*) continue ;;   # needs DATABASE_URL_BI: `sh scripts/gates/05-migration.sh`
  esac
  printf '\n== %s\n' "$gate"
  sh "$gate" || failed=$((failed + 1))
done

if [ "$failed" -ne 0 ]; then
  printf '\n%d gate(s) failed\n' "$failed" >&2
  exit 1
fi
printf '\nall gates passed\n'
