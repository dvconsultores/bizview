---
description: "Task list for feature 003 — Distribution & AI"
---

# Tasks: Distribution & AI

**Input**: `/specs/003-distribution-ai/` (plan, spec, research, data-model, contracts, quickstart)

**Tests**: included (installer script test, backend endpoint and provider tests, browser smoke).

**Execution mode**: Claude designs and audits; DeepSeek drafts selected files; Claude reviews,
corrects, and tests before a task is checked.

## Phase 1: Setup

- [X] T001 Create `VERSION` (`0.1.0`), `LICENSE` (AGPL-3.0-or-later full text from SPDX), `CHANGELOG.md` (Keep a Changelog, entry 0.1.0 listing features 002–003)
- [X] T002 [P] Declare the license: `license = "AGPL-3.0-or-later"` in `backend/pyproject.toml`, `"license": "AGPL-3.0-or-later"` in `frontend/package.json`; add `anthropic>=1.9,<2` and `httpx>=0.27` to backend runtime dependencies
- [X] T003 [P] Remove any customer name from the repository (FR-001); verify with a case-insensitive search

## Phase 2: Foundational

- [X] T004 Extend `backend/app/config.py`: `version` (env `BIZVIEW_VERSION`, else root `VERSION` file, else `dev`), `source_url` (default project repository URL), `ai_provider` Literal[`none`,`anthropic`,`openai_compatible`] default `none`, `ai_api_key: SecretStr | None`, `ai_model: str | None` (1–100 chars), `ai_base_url: str | None` (http/https), `ai_timeout_seconds: float` 1–300 default 30; empty strings → None
- [X] T005 Backend image: `ARG BIZVIEW_VERSION=dev` → `ENV BIZVIEW_VERSION` in `backend/Dockerfile`; dev `docker-compose.yml` passes `BIZVIEW_VERSION` from `VERSION`
- [X] T006 Extend `backend/app/api/health.py`: `/api/health` adds `version`; `/api/config` adds `version`, `source_url`, `license`, `ai_enabled`

## Phase 3: User Story 1 — Install for a new customer (P1) 🎯 MVP

- [X] T007 [US1] Write `deploy/install.sh` per contracts/installer.md (options, `/dev/tty` prompts, docker/compose check, refuse overwrite without `--force`, generated password, domain → HTTPS settings, embedded `docker-compose.yml` and `.env` templates, placeholders `__BIZVIEW_VERSION__` / `__IMAGE_PREFIX__`, `--start` waits for health, exit codes 0–4)
- [X] T008 [US1] Write `deploy/tests/test_install.sh`: fake `docker` shim on PATH for the prerequisite check; unattended install into a temp dir → layout, modes, `.env` keys, generated password printed; second run → exit 3; `--force` → overwrites; no docker → exit 1; missing answer with `--yes` → exit 2; domain → COOKIE_SECURE=true and ports 80/443; `docker compose config` on the result when real docker exists
- [X] T009 [US1] Local end-to-end: build `local/bizview-backend` and `local/bizview-web` images, install into a scratch folder with `--image-prefix local/bizview --start --http-port 18080`, sign in, remove the installation (research R7)

## Phase 4: User Story 2 — Brand and configure without code (P2)

- [X] T010 [US2] Write `docs/INSTALL.md`: requirements, install (interactive/unattended), settings reference, branding, AI, upgrade, backup/restore, recovery, uninstall, managing many customers with a private operations repository (config only, encrypted secrets)

## Phase 5: User Story 3 — Configure and verify AI (P3)

- [X] T011 [P] [US3] `backend/app/ai/__init__.py`: `AIError(code, message)` with FR-012 codes, `AIReply(text, latency_ms)`, `AIStatus`, `get_provider(settings)`, `redact(message, secret)` (truncate 200 chars, replace key)
- [X] T012 [P] [US3] `backend/app/ai/anthropic_provider.py`: official SDK client (`api_key`, optional `base_url`, `timeout`, `max_retries=1`); `complete()` with `output_config.effort` (`low` for the test), `max_tokens`, refusal fallback on supported models via `client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default")`; `stop_reason == "refusal"` → `refused`; exception chain per research R6
- [X] T013 [P] [US3] `backend/app/ai/openai_compatible.py`: `httpx` POST `{base}/chat/completions` with optional bearer key; status → codes; timeouts/transport errors
- [X] T014 [US3] `backend/app/ai/service.py` (`status()`, `test_connection()` with latency) and `backend/app/api/ai.py` (`GET /api/admin/ai`, `POST /api/admin/ai/test`, super user only), registered in `main.py`
- [X] T015 [US3] Tests `backend/tests/test_ai.py`: settings → status/missing/enabled; permission (admin 403, user 403, super 200); test endpoint with a fake provider (ok and each error code); key never in any response; OpenAI-compatible provider with `httpx.MockTransport` (200, 401, 404, 429, 500, timeout, connect error); Anthropic provider unreachable base URL → `unreachable`; opt-in live test (`AI_LIVE_TESTS=1`) invalid key → `invalid_key`
- [X] T016 [US3] Frontend `frontend/src/pages/admin/AI.tsx` (status card: activada/desactivada/incompleta with icon + text, provider, model, endpoint, key configured yes/no, missing settings; "Probar conexión" button with result: success + latency + reply, or reason in Spanish; how-to-enable help when off), route `/admin/ia`, nav item "IA" (super user), types, Spanish strings

## Phase 6: User Story 4 — Publish releases (P4)

- [X] T017 [US4] `.github/workflows/ci.yml` per research R4 (jobs: frontend, backend-lint, installer, backend-tests gated on `CI_DATABASE_URL`)
- [X] T018 [US4] `.github/workflows/release.yml` per research R4 (tag = VERSION check, QEMU + buildx, GHCR login with `GITHUB_TOKEN`, backend and web images amd64+arm64 tagged version + latest with OCI labels and license, stamp installer, `gh release create` with `install.sh`)

## Phase 7: User Story 5 — Contribute (P5)

- [X] T019 [P] [US5] `CONTRIBUTING.md` (local run with `starter.py`, tests, spec-kit workflow, style, DCO sign-off), `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `SECURITY.md` (private reporting, supported versions), `.github/ISSUE_TEMPLATE/{bug_report,feature_request}.md`, `.github/pull_request_template.md`
- [X] T020 [US5] `frontend/src/components/SourceFooter.tsx`: version + "Código fuente · AGPL-3.0" link from `/api/config`; shown on sign-in, change-password, and at the end of every page in the app shell; profile page shows version and link
- [X] T021 [US5] README rewrite: what it is, features, install for a customer (link docs/INSTALL.md), develop (`starter.py`), folder map, license + trademark note

## Phase 8: Polish & Verification

- [X] T022 Run backend suite, frontend unit tests + build + compat, installer test, ShellCheck (if available), Playwright smoke; fix findings
- [X] T023 Validate workflows (`actionlint` if available, else YAML parse) and quickstart scenarios 1–12
- [X] T024 Security audit of the diff (secrets handling, installer file modes, AI key redaction, permission checks) and mark tasks complete

## Dependencies & Execution Order

Phase 1 → Phase 2 → stories. US1 needs T004–T006 (version in images). US3 is independent of
US1/US2. US4 needs the installer (T007) and version (T001). US5 needs `/api/config` (T006).

## Parallel Opportunities

T002/T003; T011/T012/T013; T016 with T017–T019; documentation tasks alongside code.

## Implementation Strategy

MVP = US1 (a customer can be installed from images). Then AI (US3), releases (US4), contribution
files and source footer (US5), docs.
