# Contract — the documentation gates

## 01-vocabulary (extended)

Refuses, in `README.md`, `README.es.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
`docs/`, `backend/app/guide/` and the code paths 045 already covered:

`asistente|speckit-|run_contract|token_budget|AI Powered`

Allowlist, each with its reason inside the script: `CHANGELOG.md` (it records the removals),
`specs/` (historical documents; `specs/_deprecated/` is where the removed features live),
`backend/alembic/versions/` (a migration names what it drops).

## 07-version (new)

Refuses a tree where any copy of the version disagrees with `VERSION`, and where a reachable
backend's `/api/health.version` disagrees. See [version-contract.md](./version-contract.md).

## 08-markdown (new)

Refuses, over `README*.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`,
`docs/**/*.md` and `backend/app/guide/**/*.md`:

1. an unclosed fenced code block;
2. a table row whose cell count differs from its header's;
3. a relative link or image whose target does not exist;
4. a heading starting with `#` and no space, or duplicated verbatim in the same file;
5. trailing whitespace after a heading;
6. a section count mismatch between `README.md` and `README.es.md` (same number of `##` headings).

Exit code 0 when clean, 1 with `path:line: reason` lines otherwise.

## all.sh

Runs 01–04, 06, 07, 08 (05 needs a disposable database and runs alone). CI runs `all.sh` plus 05.
