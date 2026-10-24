# Bizview AI Powered

**English** · [Español](README.es.md)

Your business data on your phone, with a chat that builds the reports.

Bizview is a self-hosted, mobile-first BI product. Every integration and every report is a
**declarative spec** (YAML plus read-only SQL), validated before it runs: nothing runs without one.
An optional AI assistant writes those same specs from a plain request; product code validates and
renders them, and the model never produces code that the server executes.

Each organization installs the same published version on its own server. Branding, database,
language and AI are settings, never code changes.

<!-- screenshot: phone dashboard + chat clip (see website repo) -->

## Install (Docker Compose)

Requirements: a Linux server with Docker and Docker Compose, and a **PostgreSQL** database you can
write to (Bizview never ships a database container; it is always external). For a public server,
also a domain pointing at it.

```bash
mkdir -p /opt/bizview && cd /opt/bizview
curl -fsSLO https://raw.githubusercontent.com/dvconsultores/bizview/main/bizview.yml
curl -fsSL  https://raw.githubusercontent.com/dvconsultores/bizview/main/.env.example -o .env
```

No clone needed: [`bizview.yml`](bizview.yml) is the whole stack (Caddy, backend, worker and
Watchtower) running the published images `dvconsultores/bizview-backend` and
`dvconsultores/bizview-web`. Edit `.env` — four values are enough to start:

```dotenv
DATABASE_URL_BI=postgresql://user:password@host:5432/bizview
SUPER_USER_EMAIL=you@example.com
SUPER_USER_PASSWORD=choose-a-long-password     # first start only
BIZVIEW_SECRET_KEY=<openssl rand -hex 32>      # encrypts stored credentials; back it up
```

Then:

```bash
mkdir -p projects attachments && sudo chown -R 10001:10001 projects attachments  # containers run as uid 10001
docker compose -f bizview.yml pull
docker compose -f bizview.yml up -d
```

(`projects/` and `attachments/` are the only host folders; without the `chown` the app can read
them but not write.) To build the images from source instead, clone the repository and run
`docker compose -f bizview.yml up -d --build`.

- **Local or private network**: open `http://<server>:8081`. Keep `SECURITY_PROFILE=private`.
- **Public server**: set `SITE_ADDRESS=bi.example.com`, `CADDY_ALLOWED_HOSTS=bi.example.com`,
  `SECURITY_PROFILE=internet`, `COOKIE_SECURE=true`, `HTTPS_PORT=443`. Caddy obtains the
  certificate automatically. Open `https://bi.example.com`.

Sign in with the super user, add a data source, and either write a spec in a workspace or open the
**Asistente** and ask for a report.

**Upgrade**: with the default `BIZVIEW_VERSION=latest`, Watchtower pulls new images automatically
(every 5 minutes, only the Bizview containers). To pin a version, set `BIZVIEW_VERSION=0.1.0` and
upgrade by changing it and running `docker compose -f bizview.yml pull && docker compose -f
bizview.yml up -d`. Ports, TLS behind another proxy, Cloudflare, backups and branding:
[docs/INSTALL.md](docs/INSTALL.md).

## What it does

| Capability | Spec |
|---|---|
| Spec-driven integrations (PostgreSQL, REST, SOAP, Supabase) run by a worker on a schedule | [005](specs/005-vibe-reporting/spec.md), [016](specs/016-supabase-source/spec.md) |
| Reports with metrics, dimensions, views, filters and periods; direct-source reports over an existing table | [005](specs/005-vibe-reporting/spec.md), [019](specs/019-direct-source-reports/spec.md) |
| **Asistente**: a chat that drafts, validates and previews specs through Spec Kit commands before anything is applied | [014](specs/014-vibe-chat/spec.md), [017](specs/017-agentic-vibe-chat/spec.md), [021](specs/021-speckit-chat-commands/spec.md) |
| Declarative layouts for dashboards and PDFs, rendered by the app on screen and by ReportLab on the server | [026](specs/026-declarative-layouts/spec.md) |
| BI projects: a folder per project with numbered specs, history and an in-browser editor; export as zip | [020](specs/020-bi-projects/spec.md) |
| Sharing: expiring read-only links, email delivery, scheduled sends | [018](specs/018-dashboard-sharing/spec.md) |
| Spanish and English, dark mode, PDF and CSV export | [022](specs/022-i18n-en-es/spec.md), [006](specs/006-dark-mode/spec.md) |
| Administration: users, roles, access, audit log, `internet` security profile, sign in with Google or Telegram | [002](specs/002-auth-admin-home/spec.md), [004](specs/004-data-sources-security/spec.md), [027](specs/027-google-sign-in/spec.md), [007](specs/007-telegram-sign-in/spec.md) |
| In-app guide, update notice, project search | [023](specs/023-chat-app-guide/spec.md), [025](specs/025-app-updates-and-search/spec.md) |

Mobile first: every screen works from 320 px, WCAG 2.2 AA. How to write reports:
[docs/VIBE-REPORTING.md](docs/VIBE-REPORTING.md).

## Configuration

[`.env.example`](.env.example) is the full list. The groups you will touch:

| Group | Settings |
|---|---|
| Database | `DATABASE_URL_BI` |
| Site and TLS | `SITE_ADDRESS`, `CADDY_ALLOWED_HOSTS`, `HTTP_PORT` (8081), `HTTPS_PORT` (8443; `443` on a public server), `CADDY_TLS`, `TRUSTED_PROXIES` |
| Security | `SECURITY_PROFILE` (`private` / `internet`), `COOKIE_SECURE`, `BIZVIEW_SECRET_KEY`, `SUPER_USER_EMAIL`, `SUPER_USER_PASSWORD` |
| Branding | `PRODUCT_NAME`, `ORGANIZATION_NAME`, `LOGO_URL`, `DEFAULT_LOCALE`, `TIMEZONE` |
| AI (optional, off by default) | `AI_PROVIDER` (`none` / `anthropic` / `openai`), `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL` (any OpenAI-compatible endpoint, including local models) |
| Mail and sharing | `SMTP_*`, `EMAIL_ALLOWED_DOMAINS`, `SHARE_LINKS_ENABLED` |
| Images | `BIZVIEW_IMAGE_PREFIX`, `BIZVIEW_VERSION` |

## How it is built

```text
browser ──HTTPS──▶ Caddy (SPA + /api + certificates) ──▶ FastAPI backend ──▶ PostgreSQL (external)
                                                              ├──▶ worker (ETL, mail, schedules)
                                                              └──▶ AI provider (optional)
projects/ (specs, YAML, SQL) ────────────────────────────▶ backend + worker ──▶ data sources
```

Python 3.12 / FastAPI / SQLAlchemy / Alembic / ReportLab; React 19 / Vite / Tailwind; Caddy. The
`cli/` folder holds the `bizview` command and the JSON Schemas and SQL rules that both the CLI and
the backend validate with. Specs live in [`specs/`](specs/) with
[Spec Kit](https://github.com/github/spec-kit); principles in
[`.specify/memory/constitution.md`](.specify/memory/constitution.md).

Development setup, tests and conventions: [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

- `SECURITY_PROFILE=internet`: HTTPS everywhere, two-step sign-in for administrators, sign-in
  throttling, step-up confirmation for sensitive changes.
- Data-source credentials are encrypted at rest (AES-256-GCM) with `BIZVIEW_SECRET_KEY` and are
  write-only: never returned, shown or logged. Back the key up separately from the database.
- The origin databases are read-only for Bizview; connections refuse loopback, link-local and
  cloud-metadata addresses.
- AI is off by default; only structure, aggregates and metadata are ever sent to a provider, never
  rows, credentials or personal data. A local model keeps everything on your server.

Report vulnerabilities privately through GitHub's *Security* tab: [SECURITY.md](SECURITY.md).

## License

[GNU AGPL-3.0-or-later](LICENSE). If you run a modified version for others over a network you must
offer them its source; the app links to the source on every page (`SOURCE_URL`). The license does
not grant rights to the "Bizview" name or logo.
