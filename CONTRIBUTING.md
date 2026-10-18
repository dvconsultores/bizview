# Contributing to Bizview AI Powered

Thanks for helping! This project is open source under the
[GNU AGPL-3.0-or-later](LICENSE). By contributing you agree that your contribution is licensed
under the same terms.

## Ground rules

- **One product for every customer.** Never add customer names, logos, addresses, or credentials
  to the repository. Anything that differs per customer is a setting (see `docs/INSTALL.md`).
- **The database is always external.** Do not add database containers; tests run in a temporary
  `app_test_*` schema of the database in `DATABASE_URL_BI` and drop it afterwards.
- **AI is optional and private.** Features that call an AI provider must work with AI off, send
  only aggregates/metadata, and document exactly what they send.
- **Mobile first.** Every screen must work at 320 px without horizontal scrolling, meet WCAG 2.2 AA,
  and run on iOS/Safari 14+.
- The project's rules live in [`.specify/memory/constitution.md`](.specify/memory/constitution.md);
  features are specified in [`specs/`](specs/) with [Spec Kit](https://github.com/github/spec-kit)
  (`/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`).

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
cd backend  && uv run ruff check app tests alembic && uv run pytest
cd cli      && uv run ruff check . && uv run pytest      # bizview CLI, schemas, SQL rules
cd frontend && npx tsc --noEmit -p . && npm test && npm run build && npm run check:compat
cd frontend && npx playwright install && npm run e2e      # Chromium/Firefox/WebKit, 320/375 px
bash deploy/tests/test_install.sh                         # installer (REAL_DOCKER=1 for compose check)
```

Run these checks locally before proposing a change — they are the checks the maintainers run.
Backend tests use the PostgreSQL database in `DATABASE_URL_BI` and create and drop temporary
`app_test_*` schemas there.

## Vibe reporting: CLI, preset and extension

`cli/` is the `bizview` command and the single source of the artifact JSON Schemas and SQL rules;
the backend depends on it (path dependency), so the CLI and the installation always validate the
same way. The Spec Kit preset, extension and agent rules for customer workspaces are package data
in `cli/bizview_cli/workspace_template/`. To try a change end to end:

```bash
cd cli && uv run bizview init /tmp/ws --name demo --agent claude --no-git
cd /tmp/ws && specify preset resolve spec-template      # → the bizview preset
```

Changing an artifact schema or the SQL rules is a product change: update
`specs/005-vibe-reporting/contracts/artifacts.md`, the CLI tests, and the backend tests together.
Never add customer specs, queries or names to this repository — they belong in the customer's
workspace.

## Pull requests

1. Open an issue first for anything larger than a small fix, so we can agree on the approach.
2. Keep changes focused; include tests for behaviour changes.
3. Update `CHANGELOG.md` under *Unreleased*.
4. Sign off your commits (`git commit -s`) to certify the
   [Developer Certificate of Origin](https://developercertificate.org/).
5. Interface text is Spanish and lives in `frontend/src/i18n/es.ts`; code, comments, and docs are
   English.

## Releases (maintainers)

Bump `VERSION`, move the *Unreleased* notes in `CHANGELOG.md` under the new version, then tag
`v<VERSION>`; the tag must equal the `VERSION` file. The images are built and pushed from a
maintainer's machine with `./deploy.sh` (Docker Hub: `bizview-backend` and `bizview-web`). A GitHub
release carries the notes, not build artifacts.

## Code of conduct

Everyone taking part must follow the [Code of Conduct](CODE_OF_CONDUCT.md).
