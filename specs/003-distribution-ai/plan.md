# Implementation Plan: Distribution & AI

**Branch**: `003-distribution-ai` | **Date**: 2026-09-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-distribution-ai/spec.md`

## Summary

Turn the platform into one open-source product (AGPL-3.0-or-later) installed per customer from
published images. A self-contained `deploy/install.sh` creates an installation folder (settings,
compose file pinned to a version, branding, queries). GitHub Actions check every change and, on a
version tag, publish multi-arch `bizview-backend` / `bizview-web` images to GHCR plus the stamped
installer. The backend gains a version, a source-code link (AGPL §13), and an optional AI provider
layer — Claude through the official `anthropic` SDK (default `claude-opus-5-5`) or any
OpenAI-compatible endpoint — with a super-user status page and connection test. See
[research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5 / Node 24 (frontend), bash (installer)

**Primary Dependencies**: feature 002 stack + `anthropic` 1.x (Claude provider), `httpx`
(OpenAI-compatible provider; already a test dependency, now runtime); GitHub Actions
(`docker/setup-qemu-action`, `docker/setup-buildx-action`, `docker/login-action`,
`docker/build-push-action`, `astral-sh/setup-uv`, `actions/setup-node`); ShellCheck in CI

**Storage**: none new (settings only; database unchanged)

**Testing**: pytest (settings, endpoints, provider error mapping with mock transports; one
opt-in live test against the Anthropic API); bash installer test script; Vitest; Playwright
(footer + AI page smoke)

**Target Platform**: customer Linux servers with Docker Engine + Compose v2, amd64 or arm64

**Project Type**: web application + distribution tooling

**Performance Goals**: AI test returns within timeout + 2 s (SC-004); install < 10 min (SC-001)

**Constraints**: AI off by default; key never exposed; no customer data in the repository;
databases external (no database containers, including CI)

**Scale/Scope**: many independent installations; 1 installer, 2 workflows, 2 endpoints, 1 page

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Rule | Status | Evidence |
|---|---|---|
| I. Mobile-first, Tailwind | PASS | AI page and footer built with the existing kit, tested at 320/375 px |
| II. API never queries origin | PASS | no origin access added |
| III. Origin read-only | PASS | untouched |
| IV. Separated concerns by folder | PASS | AI in `backend/app/ai/`; installer and Caddy in `deploy/`; workflows in `.github/` |
| V. Fixed stack | **AMEND → 1.4.0** | adds AI provider layer (`anthropic` SDK; OpenAI-compatible over `httpx`), GHCR distribution, and GitHub Actions; recorded as constitution 1.4.0 before implementation |
| VI. Data tuning | PASS | n/a |
| Constraints (JSON API, Alembic, external DB) | PASS | no schema change; CI uses an external database secret, never a container |

Post-design re-check: PASS with amendment 1.4.0 (principles VII *One Product, Many Installations*
and VIII *AI Is Optional and Private* added).

## Project Structure

### Documentation (this feature)

```text
specs/003-distribution-ai/
├── plan.md  research.md  data-model.md  quickstart.md  tasks.md
├── contracts/api.md  contracts/installer.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
VERSION                       # 0.1.0
LICENSE                       # AGPL-3.0-or-later full text
CONTRIBUTING.md  CODE_OF_CONDUCT.md  SECURITY.md  CHANGELOG.md
.github/
├── workflows/ci.yml          # frontend, lint, installer, backend tests (if CI_DATABASE_URL)
├── workflows/release.yml     # tag v* → images (amd64+arm64) + release with install.sh
├── ISSUE_TEMPLATE/bug_report.md  feature_request.md
└── pull_request_template.md
deploy/
├── install.sh                # self-contained installer (contracts/installer.md)
├── tests/test_install.sh     # installer test (no docker needed except compose config)
└── caddy/                    # web image (unchanged, now also published)
docs/INSTALL.md               # implementer guide: install, brand, AI, upgrade, backup, many customers
backend/app/
├── ai/__init__.py            # AIError, AIReply, get_provider()
├── ai/anthropic_provider.py  # official SDK, refusal fallback, error mapping
├── ai/openai_compatible.py   # httpx chat/completions
├── ai/service.py             # status(), test_connection()
├── api/ai.py                 # GET /api/admin/ai, POST /api/admin/ai/test
├── api/health.py             # + version, source_url, license, ai_enabled
└── config.py                 # + version, source_url, AI_* settings
backend/tests/test_ai.py  test_config_version.py
frontend/src/
├── pages/admin/AI.tsx        # super user AI status + test
├── components/SourceFooter.tsx
└── (AppShell nav item "IA", SignIn + Profile footer/version)
```

**Structure Decision**: no new top-level service. Distribution lives in `deploy/` and
`.github/`, AI inside the backend package that owns API features.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| New stack components (AI SDK, GHCR, Actions) | user requirement: AI powered, open source, installed per customer | handled by constitution amendment 1.4.0, not a violation after amendment |
