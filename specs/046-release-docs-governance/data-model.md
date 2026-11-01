# Data model — 046 release, documentation and governance

No database change. The entities are the values and documents the release has to keep consistent.

## VersionRecord (the single source of truth)

| Field | Value | Rules |
|---|---|---|
| `version` | `0.2.0` | SemVer, read from `VERSION` at the repository root |
| `copies` | `backend/pyproject.toml`, `frontend/package.json`, `cli/pyproject.toml`, `cli/bizview_cli/__init__.py` (`__version__`) | each MUST equal `version` |
| `runtime` | `/api/health.version`, the footer | MUST equal `version` when the backend runs from this tree |

Transitions: a release bumps `version` **and** every copy in one commit; `scripts/gates/07-version.sh`
refuses a tree where any copy disagrees. Image tags (`deploy.sh`) and the container labels are
derived from `VERSION` at build time and are not separate copies.

## DocumentSet (what a reader finds)

| Document | Reader | Must contain | Retires |
|---|---|---|---|
| `README.md` / `README.es.md` | newcomer | hero + 3 actions, one-screen install, the eight authoring steps, capabilities table, configuration groups, architecture, links to security/contributing/licence | every assistant reference, "AI Powered" |
| `SECURITY.md` | reporter | private channel, ack/fix targets, supported versions, scope in/out, built-in protections, structure-pack statement | the assistant data boundary |
| `CODE_OF_CONDUCT.md` | community | Contributor Covenant 2.1, contact address | — (already correct) |
| `CONTRIBUTING.md` | contributor | dev stack, spec workflow, tests/lints, how to add a help topic and a `## Docs` section, schema-change procedure, commit/PR conventions, AGPL note | — (rewritten) |
| `.specify/memory/constitution.md` | maintainer | preamble, folders, AI boundary, principle IX, import limits, schemas as single source, Sync Impact Report | `backend/app/assistant/` in the folder list |
| `docs/INSTALL.md` | operator | install, upgrade, backup, hardening | assistant settings and mounts |
| `docs/AUTHORING.md` | author | folder layout, `PROMPT.md`/`REQUEST.md`, schemas, rules, lite specs, `validate` and `problems.json`, images, one worked example | `docs/VIBE-REPORTING.md`'s agent workflow |
| `docs/IMPORT.md` | author | upload → map → collisions → validate → preview → apply, with CLI equivalents | — |
| `docs/VIBE-REPORTING.md` | anyone with an old link | a redirect note to AUTHORING | its agent sections |
| `backend/app/guide/{es,en}/*.md` | product user | the same behaviour as the documents above, in-app | assistant topics |
| `CHANGELOG.md` | anyone | 0.2.0 Added / Changed / Removed (by spec number) / Security | — |

Relationships: the help topics and `docs/AUTHORING.md` describe the same contract; `README`'s
capabilities table links each capability to the specification that owns it; `CONTRIBUTING.md` names
the gates that must pass before a pull request.

## GateRun

| Field | Value |
|---|---|
| `gates` | `01-vocabulary`, `02-dead-code`, `03-dependencies`, `04-routes`, `05-migration`, `06-settings`, `07-version`, `08-markdown` |
| `entry point` | `sh scripts/gates/all.sh` (skips 05, which needs a disposable database) |
| `ci` | `.github/workflows/gates.yml`, which runs `all.sh` and `05-migration.sh` |
| `evidence` | each gate is proved to fail on a deliberately reintroduced offence and to pass on the clean tree |

Validation rules:
- A gate MUST exit non-zero on its offence and print the offending path, line and reason.
- A gate MUST be runnable alone (`sh scripts/gates/07-version.sh`).
- The allowlist (`CHANGELOG.md`, `specs/_deprecated/`, `backend/alembic/versions/`) MUST be written
  in the gate that needs it, with the reason, never as a global exclusion.
