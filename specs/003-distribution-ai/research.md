# Research: Distribution & AI

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-29

Decisions taken autonomously with the recommended option, at the user's request.

## R1. One product, one installation folder per customer

- **Decision**: the public repository contains only the generic product. Each customer gets an
  *installation folder* on their server (default `/opt/bizview`), created by the installer:
  `docker-compose.yml` (images pinned by `BIZVIEW_VERSION`), `.env` (mode 600), `branding/`,
  `queries/` (reserved for feature 001's source-database query profile). Customers never build.
  Operators who manage many customers may keep a **private** operations repository with one
  folder per customer holding only these files (secrets encrypted, e.g. sops/age) — documented,
  not part of the product.
- **Rationale**: the pattern of self-hosted open-source products (Metabase, n8n, Plausible): one
  codebase, upgrades flow to everyone, customer differences are data.
- **Alternatives**: a code folder or branch per customer (rejected: forks stop receiving fixes);
  one multi-tenant SaaS (rejected: the user installs on each customer; data stays on premises).

## R2. Installer

- **Decision**: a single self-contained `deploy/install.sh` (bash, `set -euo pipefail`) that
  embeds the installation templates, so one downloaded file is enough
  (`curl -fsSL …/install.sh | bash`). Options: `--dir`, `--db-url`, `--admin-email`,
  `--admin-password`, `--site`, `--http-port`, `--https-port`, `--product-name`, `--org-name`,
  `--version`, `--image-prefix`, `--yes` (non-interactive), `--force`, `--start`. Missing answers
  are asked on `/dev/tty` (works when piped). It checks `docker` and `docker compose` first,
  refuses to overwrite an existing `.env` without `--force`, generates a 20-character super-user
  password when none is given and prints it once, derives `COOKIE_SECURE=true` and ports 80/443
  when `--site` is a domain. Release builds replace the placeholders `__BIZVIEW_VERSION__` and
  `__IMAGE_PREFIX__` with the tag and `ghcr.io/<owner>/bizview`.
- **Rationale**: SC-001 (under 10 minutes), FR-003–FR-006; one file avoids template drift between
  the script and a separate template folder.
- **Alternatives**: Ansible/Helm (rejected: heavier than the audience needs; can come later);
  a Python installer (rejected: servers may lack Python; bash + Docker is the only prerequisite).

## R3. Versioning

- **Decision**: `VERSION` file at the repository root (SemVer, starts at `0.1.0`). The backend
  image receives it as build argument `BIZVIEW_VERSION` (also readable from the file in
  development); it is exposed in `/api/health` and `/api/config` and shown in the interface.
  Release tags are `v<VERSION>`; the release pipeline refuses a tag that does not match the file.
- **Rationale**: FR-007; support needs to know what a customer runs.

## R4. Release and checks (GitHub Actions)

- **Decision**:
  - `ci.yml` on every push and pull request: frontend (type check, unit tests, build, compat
    check), backend lint (ruff), installer check (shellcheck + generate an installation into a
    temporary folder + `docker compose config`), and backend tests **only when the repository
    secret `CI_DATABASE_URL` exists** (they run in a temporary `app_test_*` schema of that
    database, per feature 002). No database container (constitution: databases are external).
  - `release.yml` on tags `v*`: verify tag = `VERSION`; build and push multi-arch images
    (`linux/amd64`, `linux/arm64`) `ghcr.io/<owner>/bizview-backend` and `…/bizview-web` tagged
    `<version>` and `latest`; stamp the installer; create the GitHub release with `install.sh`
    using the `gh` CLI and the built-in token.
- **Rationale**: FR-016, FR-017; GHCR is free for public images and needs no extra account.
- **Alternatives**: Docker Hub (rejected: rate limits, extra credentials).

## R5. License and source offer

- **Decision**: AGPL-3.0-or-later. `LICENSE` holds the full text (SPDX copy); `pyproject.toml` and
  `package.json` declare it. Setting `SOURCE_URL` (default: the project repository) feeds a
  "Código fuente · AGPL-3.0" link in the footer of every page and on the profile page, satisfying
  the AGPL §13 offer to network users. README states that the license does not grant use of the
  "Bizview" name. `CODE_OF_CONDUCT.md` is the Contributor Covenant 2.1.
- **Rationale**: FR-014, FR-015; AGPL keeps hosted forks open (same choice as Metabase, Grafana).
- **Alternatives**: Apache-2.0 (maximum adoption, but allows closed hosted forks); MIT (same).

## R6. AI provider layer

- **Decision**: package `backend/app/ai/` with one interface, `complete(prompt, *, system,
  max_tokens) -> AIReply`, raising `AIError(code, message)` with the FR-012 codes, and two
  providers:
  - **`anthropic`** (default when AI is on): the official `anthropic` Python SDK (1.x). Default
    model `claude-opus-5-5`. Requests set `output_config={"effort": "low"}` for the connection
    test (thinking cannot be disabled on this model; effort is the control) and `max_tokens=1024`
    so thinking cannot exhaust the budget. For models that support it (`claude-opus-5-5`,
    `claude-opus-5`, `claude-sonnet-5-5`, `claude-fable-5-1`) requests use the beta endpoint with
    server-side refusal fallback (`betas=["server-side-fallback-2026-07-01"]`,
    `fallbacks="default"`). `stop_reason == "refusal"` maps to `refused`. SDK exceptions map most
    specific first: `AuthenticationError`→`invalid_key`, `PermissionDeniedError`→`forbidden`,
    `NotFoundError`→`model_not_found`, `RateLimitError`→`rate_limited`,
    `APITimeoutError`→`timeout`, `APIConnectionError`→`unreachable`,
    `APIStatusError`→`provider_error`. `max_retries=1`, timeout from settings.
  - **`openai_compatible`**: any endpoint implementing `POST {base}/chat/completions` (OpenAI,
    Ollama, vLLM, LM Studio, DeepSeek…), via `httpx`; model and base URL required; key optional
    (local models). HTTP 401/403/404/429 map like above; transport errors → `unreachable`,
    timeouts → `timeout`.
  - Settings: `AI_PROVIDER` (`none` | `anthropic` | `openai_compatible`, default `none`),
    `AI_API_KEY` (secret), `AI_MODEL`, `AI_BASE_URL`, `AI_TIMEOUT_SECONDS` (default 30). The key
    is a `SecretStr`, never serialised; error messages are truncated to 200 characters and have
    the key redacted before they leave the provider layer.
  - Endpoints (super user only): `GET /api/admin/ai` (status) and `POST /api/admin/ai/test`
    (connection test). `GET /api/config` gains `ai_enabled`.
- **Privacy rule** (FR-013): the provider layer only receives strings composed by product code;
  each future feature documents its prompt inputs, which must be aggregates/metadata.
- **Alternatives**: calling Claude through an OpenAI-compatible shim (rejected: loses Claude
  features such as refusal fallback and effort; Anthropic recommends the official SDK); a
  multi-provider framework such as LiteLLM or LangChain (rejected: large dependency for two
  adapters).

## R7. Local end-to-end verification of an installation

- **Decision**: build both images locally with a `local/bizview` prefix, run the installer
  unattended into a scratch folder with `--image-prefix local/bizview --version <VERSION>` and a
  free port, start it against `DATABASE_URL_BI`, sign in, then remove it. The scratch
  installation uses the same database and version as the development stack, so migrations are a
  no-op and the super user already exists.
