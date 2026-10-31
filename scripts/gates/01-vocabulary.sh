#!/bin/sh
# Gate 1/6 (045): the product no longer speaks the removed agent's vocabulary.
#
# 043 WS-A wrote the check; 045 keeps it in the gate suite so it cannot be dropped silently.
set -eu
cd "$(dirname "$0")/../.."
sh scripts/check_vocabulary.sh "$@"
