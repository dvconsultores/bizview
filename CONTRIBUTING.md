# Contributing to Bizview

🇬🇧 English · 🇪🇸 [Español](CONTRIBUTING.es.md)

Thanks for helping! Bizview is open source under the [GNU AGPL-3.0-or-later](LICENSE). By
contributing you agree that your contribution is licensed under the same terms — there is no CLA
and no copyright assignment: your work stays yours, published under the same licence as the rest.

## Ground rules

- **One product for every customer.** Never add customer names, logos, addresses or credentials to
  the repository. Anything that differs per customer is a setting (see
  [`docs/INSTALL.md`](./docs/INSTALL.md)).
- **Bizview does not author.** The product validates, imports, runs and shares projects written
  outside it. A change that makes the product write a project, a spec or a query is out of scope by
  design (see the constitution, principle IX).
- **The contract has one source.** The JSON Schemas and SQL rules in `cli/bizview_cli/schemas/` are
  read by the CLI, the backend and the authoring pack. Never validate the same thing twice in two
  places.
- **The database is always external.** Do not add database containers; tests run in a temporary
  `app_test_*` schema of the database in `DATABASE_URL_BI` and drop it afterwards.
- **AI is optional and private.** A feature that calls a provider must work with AI off, send only
  aggregates or metadata, and document exactly what it sends. Inside 0.2.0 that is the read-only
  help page.
- **Mobile first.** Every screen works at 320 px without horizontal scrolling, meets WCAG 2.2 AA and
  runs on iOS/Safari 14+.
- The project's rules live in [`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## Run it locally

Requirements: Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node.js 20+, and a PostgreSQL
database you can write to.

```bash
cp .env.example .env        # set DATABASE_URL_BI, SUPER_USER_EMAIL, SUPER_USER_PASSWORD
python starter.py           # installs dependencies, migrates, runs backend + frontend
# open http://localhost:5173
```

## Tests and checks

```bash
sh scripts/gates/all.sh                                   # vocabulary, dead code, dependencies, routes, version, markdown
sh scripts/gates/05-migration.sh                          # needs DATABASE_URL_BI: rescue verified, tables gone
cd backend  && uv run ruff check app tests alembic && uv run pytest
cd cli      && uv run ruff check . && uv run pytest       # bizview CLI, schemas, SQL rules
cd frontend && npx tsc --noEmit -p . && npm test && npm run build && npm run check:compat
cd frontend && npx playwright install && npm run e2e      # Chromium/Firefox/WebKit, 320/375 px
bash deploy/tests/test_install.sh                         # installer (REAL_DOCKER=1 for compose check)
```

Run these before proposing a change — they are the checks the maintainers run, and CI runs the same
commands. Backend tests use the PostgreSQL database in `DATABASE_URL_BI` and create and drop
temporary `app_test_*` schemas there.

## Specification workflow

Product features are specified before they are built, with
[Spec Kit](https://github.com/github/spec-kit):

```text
/speckit.specify    → specs/NNN-name/spec.md (user stories, requirements, success criteria)
/speckit.clarify    → the underspecified parts, answered in the spec
/speckit.plan       → plan.md, research.md, data-model.md, contracts/, quickstart.md
/speckit.tasks      → tasks.md (ordered, one checkbox each)
/speckit.implement  → the code, the tests, the tasks ticked
/speckit.converge   → what the tree still lacks, appended as tasks
```

These are the **repository's** skills (`.claude/skills/`); they are not the product's. A
specification is part of the change: a pull request that changes behaviour without its spec (or
without updating the existing one) is asked for it. `/speckit.all` runs the whole sequence for
a single feature.

Every specification that adds a reader-facing surface carries a `## Docs` section: which document
under `docs/` describes it, and which help topic (see below) the user finds in the app.

## Documentation and help topics

- **Every document ships in both languages.** English lives at the canonical path and Spanish
  beside it: `docs/es/<name>.md` in `docs/`, `<NAME>.es.md` at the repository root, `es/` and `en/`
  in the guide and in the starter pack. A translation keeps the shape of its original — the same
  headings in the same order, the same code blocks and tables, the same links — and the prose is
  translated, never summarised. `python3 scripts/check_docs_parity.py`, run by `make check` and by
  CI, fails on a missing or drifted pair and prints what differs.
- Reader documents live in `docs/`: [`AUTHORING.md`](./docs/AUTHORING.md) (the contract and the
  worked example), [`IMPORT.md`](./docs/IMPORT.md) (the way in),
  [`REPORTS.md`](./docs/REPORTS.md) (the field-by-field reference),
  [`RENDERING.md`](./docs/RENDERING.md) (what the engine does with a `report.yaml`),
  [`INSTALL.md`](./docs/INSTALL.md) (installations).
- The in-app help is `backend/app/guide/`: `index.yaml` holds the topics' metadata (`id`, `section`,
  `title`, `summary`, `roles`, `routes`, `tiles`, `commands`, `aliases`, `related`) and
  `es/<topic>.md` + `en/<topic>.md` hold the bodies. **A new topic needs both languages**, the same
  five headings in each (`Para qué sirve` / `Quién puede usarlo` / `Cómo se hace` / `Opciones` /
  `Problemas frecuentes`), and an entry in `index.yaml`. `backend/tests/test_guide.py` enforces the
  parity, the ids, the roles and that a topic's bold words are real UI labels.
- A page that the help links to must exist (`routes:`), and a route that a user can reach should have
  a topic: `frontend/tests/unit/guide-drift.test.ts` checks both directions.

## Proposing a schema change

The artifact schemas are versioned with the product:

1. Change the schema in `cli/bizview_cli/schemas/` and bump its `format_version` when the change is
   not backward compatible.
2. Update the validator in `cli/bizview_cli/validate.py` and the rules it applies, plus the CLI
   tests and [`docs/REPORTS.md`](./docs/REPORTS.md) (the field reference).
3. If existing projects would stop validating, add a migration note to the specification and say in
   the changelog what an author has to change.
4. Regenerate the authoring pack so new workspaces get the new schema
   (`cli/bizview_cli/workspace_template/`) and re-run `bizview validate` over the example project.
5. Update the golden example (`backend/tests/fixtures/projects/coinmarketcap/`) if the change makes
   it invalid; the backend suite renders it on every run.

## Pull requests

1. Open an issue first for anything larger than a small fix, so we can agree on the approach.
2. Keep changes focused; include tests for behaviour changes.
3. Update `CHANGELOG.md` under *Unreleased*.
4. Sign off your commits (`git commit -s`) to certify the
   [Developer Certificate of Origin](https://developercertificate.org/).
5. Interface text is Spanish and lives in `frontend/src/i18n/es.ts` and
   `backend/app/i18n/es.py`; code, comments and docs are English.
6. Run `sh scripts/gates/all.sh` before pushing; the same gates run in CI.

## Releases (maintainers)

`VERSION` at the repository root is the single source of truth: bump it, align
`backend/pyproject.toml`, `frontend/package.json`, `cli/pyproject.toml` and
`cli/bizview_cli/__init__.py`, and `sh scripts/gates/07-version.sh` proves they agree. Move the
*Unreleased* notes in `CHANGELOG.md` under the new version, then tag `v<VERSION>` — the tag must equal
the file. The images are built and pushed from a maintainer's machine with `./deploy.sh` (Docker Hub:
`bizview-backend` and `bizview-web`). A GitHub release carries the notes, not build artifacts.

## Code of conduct

Everyone taking part must follow the [Code of Conduct](CODE_OF_CONDUCT.md).
