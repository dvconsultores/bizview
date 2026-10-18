# Bizview AI Powered

Bizview is a self-hosted, mobile-first business-intelligence product. A report is a
**declarative spec** — YAML plus read-only SQL — kept in a Git workspace, and Bizview runs exactly
what the spec says: nothing without one. An optional AI assistant (the **Asistente**) writes those
same declarative artifacts from a request, and product code validates and renders them — the model
never generates code that the server executes.

Every organization installs the same published version on its own server; branding, database,
language and AI are settings, never code changes. License:
[GNU AGPL-3.0-or-later](LICENSE). Status: `0.1.0`.

## Capabilities

| Capability | Where it is specified |
|---|---|
| **Spec-driven reporting**: integrations and reports are files validated against the JSON Schemas and SQL rules shipped by the `bizview` CLI; the API and the CLI always validate the same way | [005](specs/005-vibe-reporting/spec.md) |
| **ETL integrations** from PostgreSQL, SOAP, REST and Supabase, run by the worker on a schedule with incremental windows | [005](specs/005-vibe-reporting/spec.md), [016](specs/016-supabase-source/spec.md) |
| **Direct-source reports** over an existing table — no integration, no copy | [019](specs/019-direct-source-reports/spec.md) |
| **BI projects**: one folder per project with numbered specs, file history and an in-browser editor | [020](specs/020-bi-projects/spec.md) |
| **Asistente**: a chat bound to the project's scope that works through the Spec Kit commands, drafting, validating and previewing before anything is applied | [014](specs/014-vibe-chat/spec.md), [017](specs/017-agentic-vibe-chat/spec.md), [021](specs/021-speckit-chat-commands/spec.md), [024](specs/024-image-brief-chat/spec.md) |
| **Declarative layouts** for dashboards and PDFs: one `layout` document, written by the Asistente or by a person, rendered by the application's own React SVG chart components on screen and by ReportLab on the server for the PDF | [026](specs/026-declarative-layouts/spec.md) |
| **Sharing**: expiring read-only dashboard links and dashboards sent by email | [018](specs/018-dashboard-sharing/spec.md) |
| **Sign in with Telegram**, linked from the user's profile | [007](specs/007-telegram-sign-in/spec.md) |
| **English and Spanish** across the interface, API messages and emails | [022](specs/022-i18n-en-es/spec.md) |
| **Dark mode** | [006](specs/006-dark-mode/spec.md) |
| **PDF and CSV export**, with PDFs rendered server-side | [005](specs/005-vibe-reporting/spec.md), [026](specs/026-declarative-layouts/spec.md) |
| **Administration**: users, roles, access, audit log and an `internet` security profile | [002](specs/002-auth-admin-home/spec.md), [004](specs/004-data-sources-security/spec.md) |
| **In-app guide** (`/ayuda`, and `/ayuda` in the chat), update notice and project search | [023](specs/023-chat-app-guide/spec.md), [025](specs/025-app-updates-and-search/spec.md) |

The product is mobile first: every screen works from 320 px on iOS/Safari 14+, Android and desktop
browsers, and meets WCAG 2.2 AA. Reports, layouts and integrations are written in each customer's
own workspace ([docs/VIBE-REPORTING.md](docs/VIBE-REPORTING.md)); this repository holds the product.

## Quick start (development)

Requirements: Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node.js 24, and a PostgreSQL
database you can write to. **No database container ships with this repository** — PostgreSQL is
always external, in development as well as in production.

```bash
cp .env.example .env        # set DATABASE_URL_BI, SUPER_USER_EMAIL, SUPER_USER_PASSWORD
```

Run everything with the helper, or each part on its own:

```bash
python starter.py           # installs dependencies, migrates, runs backend + frontend
# http://localhost:5173

cd backend  && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
cd frontend && npm ci && npm run dev        # proxies /api to http://localhost:8000
cd cli      && uv sync && uv run bizview --help
```

A production-like stack with Caddy, built from this tree:

```bash
docker compose -f bizview.yml up -d --build   # http://localhost:8081
```

For a local stack set `SITE_ADDRESS=:80`, `CADDY_ALLOWED_HOSTS=localhost`, `COOKIE_SECURE=false`
and `SECURITY_PROFILE=private`; the domain, HTTPS ports and `internet` values in `.env.example`
are for a server.

Tests and conventions: [CONTRIBUTING.md](CONTRIBUTING.md).

## Deploy on a server

The compose file is [`bizview.yml`](bizview.yml), with the compose project name `bizview`, so its
containers (`bizview-*`), network and volumes never collide with other stacks on the same host. It
runs Caddy (the built SPA plus the `/api` proxy), the FastAPI backend and the worker; PostgreSQL is
external. A server installation folder needs only `bizview.yml` and `.env`: the SPA and the logo
are inside the `bizview-web` image, and the only host folders are `projects/` and `attachments/`
(the in-app data).

```bash
cp .env.example .env      # then edit it
```

Two flows share this one file. The services run the images named by `BIZVIEW_IMAGE_PREFIX` —
`<prefix>/bizview-backend` and `<prefix>/bizview-web` — at the tag in `BIZVIEW_VERSION`
(default prefix `andresdom2004`, tag `latest`):

```bash
# developer: build both images from this tree
docker compose -f bizview.yml up -d --build

# server: pull the images deploy.sh published, then start
docker compose -f bizview.yml pull
docker compose -f bizview.yml up -d
```

**Ports.** Caddy always listens on 80 and 443 inside the container; only the published host ports
are configurable (both TCP and UDP, which HTTP/3 needs). The compose fallbacks are **8081**
(`HTTP_PORT`) and **8443** (`HTTPS_PORT`) because they are safe on a shared host. To answer on the
standard HTTPS port, set `HTTPS_PORT=443` — this requires host port 443 to be free, and automatic
HTTPS then uses the TLS-ALPN challenge on 443, so port 80 can stay with another stack. If 443 is
already taken, either publish 8443 and use `https://<domain>:8443` in the address, or keep Caddy
behind the existing reverse proxy with `SITE_ADDRESS=:80`.

**Domain and TLS.** Set `SITE_ADDRESS` to the public domain (for example `bi.example.com`) and list
the same name in `CADDY_ALLOWED_HOSTS`: a space-separated allow-list of `Host` names that Caddy
serves; any other host gets `421 Misdirected Request` before it reaches the application. With the
domain set, Caddy obtains and renews the certificate automatically, but the ACME challenge must be
reachable: publish `HTTPS_PORT=443` (TLS-ALPN, the usual choice when port 80 belongs to another
stack) or `HTTP_PORT=80` (HTTP-01). If neither host port is free, keep Caddy behind the existing
reverse proxy (`SITE_ADDRESS=:80`), which then terminates TLS itself.

On a shared host where another stack already owns 80/443 there are two options: free the ports for
this Caddy (it must terminate TLS itself), or keep Caddy behind the existing reverse proxy — then
set `SITE_ADDRESS=:80`, publish `HTTP_PORT` on a free port, point the proxy at it, and set
`TRUSTED_PROXIES` to the proxy's network so client addresses cannot be forged.

**Anything reachable from the internet** should run with:

```dotenv
SECURITY_PROFILE=internet   # HTTPS everywhere, two-step sign-in for administrators
COOKIE_SECURE=true
CADDY_ALLOWED_HOSTS=bi.example.com
```

**Publishing images.** `./deploy.sh` logs in to Docker Hub with `DOCKER_USERNAME` /
`DOCKER_PASSWORD` from `.env`, then builds and pushes both images from this machine —
`<user>/bizview-backend` (the `worker` service reuses this same image) and `<user>/bizview-web`
(Caddy + SPA) — tagged `latest` and the `VERSION` value. On the server, set
`BIZVIEW_IMAGE_PREFIX` to that same user and `BIZVIEW_VERSION` to the tag, so `pull` gets exactly
what was pushed. No SSH is involved.

**The customer path is different**: [`deploy/install.sh`](deploy/install.sh) writes an installation
folder in `/opt/bizview` that runs published images — `<prefix>-backend` and `<prefix>-web`, the
same two images `./deploy.sh` pushes to Docker Hub — and upgrades by changing a version. Run it
from a checkout of this repository:

```bash
sudo bash deploy/install.sh --version 0.1.0 --image-prefix andresdom2004/bizview
```

A copy taken from the repository is unstamped, so unattended runs need `--version` and
`--image-prefix`; a stamped copy (placeholders filled in) can be attached to a release by hand.
Requirements, branding, upgrades and backups are in [docs/INSTALL.md](docs/INSTALL.md).

## Configuration

[`.env.example`](.env.example) is the authoritative list; the main groups:

| Group | Settings |
|---|---|
| Images | `BIZVIEW_IMAGE_PREFIX` (Docker Hub user or registry prefix; the stack runs `<prefix>/bizview-backend` and `<prefix>/bizview-web`), `BIZVIEW_VERSION` (image tag) |
| Site and TLS | `SITE_ADDRESS` (public domain, or `:80` behind another TLS terminator), `CADDY_ALLOWED_HOSTS` (space-separated `Host` allow-list), `HTTP_PORT` (default 8081), `HTTPS_PORT` (default 8443; `443` needs the port free), `TRUSTED_PROXIES`, `PRODUCT_NAME`, `ORGANIZATION_NAME`, `LOGO_URL` |
| Security | `SECURITY_PROFILE` (`private` / `internet` / `auto`), `COOKIE_SECURE`, `BIZVIEW_SECRET_KEY` (encrypts stored credentials; back it up separately), `SUPER_USER_EMAIL`, `SUPER_USER_PASSWORD` (first start only), `ADMIN_ALLOWED_NETWORKS`, `LOGIN_RATE_LIMIT` |
| Database | `DATABASE_URL_BI` (always external), `DIRECT_REPORTS_BI`, `DIRECT_BI_ROLE`, `DB_POOL_SIZE` |
| AI (optional) | `AI_PROVIDER` (`none` by default), `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL`, `AI_CHAT_TOKEN_BUDGET`, `AI_VISION` |
| Mail and sharing | `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `EMAIL_ALLOWED_DOMAINS`, `SHARE_LINKS_ENABLED` |
| Workspace and projects | `WORKSPACE_DIR` (optional customer Git checkout), `PROJECTS_DIR_HOST`, `PROJECT_MAX_MB`, `ATTACHMENTS_DIR_HOST`, `TIMEZONE`, `DEFAULT_LOCALE`, `SOURCE_URL` |

## Architecture

```text
browser ──HTTPS──▶ Caddy (SPA + /api proxy + certificates) ──▶ FastAPI backend ──▶ PostgreSQL (external)
                                                                    ├──▶ worker (ETL, mail, scheduled runs)
                                                                    └──▶ AI provider (optional)
BI projects (projects/: specs, YAML, SQL) ─────────────────────▶ backend + worker ──▶ data sources
```

- **Caddy** serves the built React SPA, proxies `/api`, adds the security headers and terminates TLS.
- **FastAPI** (SQLAlchemy, Alembic) owns sessions, reports, projects and the AI tool surface.
- **Worker** (`python -m app.worker`) runs integrations, sends mail and finishes scheduled work.
- **PostgreSQL** is external; the product owns only the tables in its `public` schema.
- **`cli/`** holds the `bizview` command, the artifact JSON Schemas and the SQL rules — the single
  source of validation that both the CLI and the backend use.
- **Specs** live in [`specs/`](specs/) with
  [Spec Kit](https://github.com/github/spec-kit); the project's principles are in
  [`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## Security

Report vulnerabilities privately through GitHub's *Security* tab — never in a public issue. Scope
and timelines: [SECURITY.md](SECURITY.md).

- `SECURITY_PROFILE=internet` requires HTTPS everywhere and two-step sign-in for administrators.
- Credentials of data sources and bot secrets are encrypted at rest (AES-256-GCM) with
  `BIZVIEW_SECRET_KEY` and are write-only in the API; they never leave the server.
- Sign-in is rate-limited per account and per network address, sensitive changes require the
  password again, and administration changes are audited.
- Data-source connections refuse loopback, link-local, cloud-metadata and internal addresses.
- AI is optional and off by default (`AI_PROVIDER=none`); features must work without it, and only
  aggregates and metadata are sent to a provider — never detailed rows.
- Keep `.env` private (the installer writes it with mode 600) and back up `BIZVIEW_SECRET_KEY`
  separately from the database.

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) explains the workflow, the checks, and how to propose a change.
Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[GNU Affero General Public License v3.0 or later](LICENSE). Running a modified version for others
over a network obliges you to offer them its source code — the application shows a link to the
source on every page (`SOURCE_URL`). The license does not grant rights to the "Bizview" name or
logo.
