# Bizview

🇬🇧 **English** · 🇪🇸 [Español](README.es.md)


**Your business data on your phone. Build the reports with any AI — Bizview validates, runs and
shares them.**

Bizview is a self-hosted, mobile-first BI product. Every integration and every report is a
**declarative spec** (YAML plus read-only SQL). You write those specs **outside** Bizview — by hand,
in the project editor, or with whatever AI you prefer — against a published contract, and the
product validates them, imports them, runs them every day and shares the result. The product never
authors, and no model ever produces code the server executes.

[Install](#install-docker-compose) · [Hosted product](https://bizview.com) · [Connect my ERP](docs/AUTHORING.md)

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
`dvconsultores/bizview-web`. Four values in `.env` are enough to start:

```dotenv
DATABASE_URL_BI=******host:5432/bizview
SUPER_USER_EMAIL=you@example.com
SUPER_USER_PASSWORD=choose-a-long-password     # first start only
BIZVIEW_SECRET_KEY=<openssl rand -hex 32>      # encrypts stored credentials; back it up
```

Then:

```bash
mkdir -p projects image-cache && sudo chown -R 10001:10001 projects image-cache  # containers run as uid 10001
docker compose -f bizview.yml pull
docker compose -f bizview.yml up -d
```

(`projects/` and `image-cache/` are the host folders the app writes; without the `chown` it can read
them but not write.) To build the images from source instead, clone the repository and run
`docker compose -f bizview.yml up -d --build`.

- **Local or private network**: open `http://<server>:8081`. Keep `SECURITY_PROFILE=private`.
- **Public server**: set `SITE_ADDRESS=bi.example.com`, `CADDY_ALLOWED_HOSTS=bi.example.com`,
  `SECURITY_PROFILE=internet`, `COOKIE_SECURE=true`, `HTTPS_PORT=443`. Caddy obtains the
  certificate automatically. Open `https://bi.example.com`.

**Upgrade**: with the default `BIZVIEW_VERSION=latest`, Watchtower pulls new images automatically
(every 5 minutes, only the Bizview containers). To pin a version, set `BIZVIEW_VERSION=0.2.0` and
upgrade by changing it and running `docker compose -f bizview.yml pull && docker compose -f
bizview.yml up -d`. Ports, TLS behind another proxy, Cloudflare, backups and branding:
[docs/INSTALL.md](docs/INSTALL.md).

## How it works

1. **Add a source** — **Fuentes de datos → Nueva**, with the credentials, then **Probar**.
2. **Describe it** — **Estructura** generates the source's structure: tables, columns, types, counts
   and shapes. Never rows, never a credential.
3. **Download the starter pack** — **Proyectos → Nuevo proyecto → Descargar paquete inicial** writes
   `bizview-starter-<slug>.zip`: the rules, `REQUEST.md`, the spec and artifact skeletons, the schemas
   and, when you pick one, the source's structure. From a terminal:
   `bizview init project "Ventas" --source "Origen ventas"`. Without an installation, take
   [bizview-starter-template.zip](bizview-starter-template.zip).
4. **Write the request** — `REQUEST.md`: what the dashboard answers, for whom, with which filters and
   period, in which style.
5. **Build it with any AI (or by hand)** — paste `PROMPT.md` + `REQUEST.md` (+ `structure.md`) into
   ChatGPT, Claude, Gemini, DeepSeek or Copilot, or open the folder with a coding tool, and ask for
   the project. The answer is one zip with `specs/NNN-name/`, `integrations/<id>/` and `reports/<id>/`
   at its root.
6. **Import** — **Proyectos → Importar proyecto** reads the zip, maps the folders, lists what it
   ignores, checks the two budgets and validates with the same validator the CLI runs. The project is
   saved as a draft: nothing runs yet.
7. **Apply and share** — **Aplicar** composes a new version of the installation and registers the
   schedules; **Compartir** mints a read-only link and **Enviar por correo** schedules the PDF.

The contract, every file and a complete worked example: [docs/AUTHORING.md](docs/AUTHORING.md). The
import path and what happens on apply: [docs/IMPORT.md](docs/IMPORT.md).

**Author with your own AI:** the pack contains `PROMPT.md` (the rules and the nine checks),
`REQUEST.md` (your brief), the JSON Schemas the validator uses, `CONTENIDO.md`/`CONTENTS.md` (what
every file is for) and `QUE-HACE-BIZVIEW.md`/`WHAT-BIZVIEW-DOES.md` (what import and apply do). No AI
key is needed in Bizview: your AI works outside and Bizview validates, runs and shares the result.

## How it works inside

Your `report.yaml` never becomes code, and nothing is written by the app.
**Apply** validates the tree again and composes an immutable version where each report is a dashboard row.
**Context** resolves every `uses` alias to `ds_<integration>.<dataset>` and takes the column contracts from the integration.
**A request** carries period, comparison and filters; its hash plus the last successful load is the cache key, and that is what the ETag answers.
**Each view becomes one SQL aggregation per period** — the comparison is a second run over the previous range — and the browser draws the payload with your `layout.web`, or one card per view when you declared none.
**Freshness is the last load**: a new run changes the data version and the numbers recompute on the next request.

Step by step, with the file behind each step and the diagram: [docs/RENDERING.md](docs/RENDERING.md).

## What it does

| Capability | Spec |
|---|---|
| Spec-driven integrations (PostgreSQL, REST, SOAP, Supabase) run by a worker on a schedule | [005](specs/005-vibe-reporting/spec.md), [016](specs/016-supabase-source/spec.md) |
| Reports with metrics, dimensions, views, filters and periods; direct-source reports over an existing table | [005](specs/005-vibe-reporting/spec.md), [019](specs/019-direct-source-reports/spec.md) |
| Declarative layouts for dashboards and PDFs, rendered by the app on screen and by ReportLab on the server | [026](specs/026-declarative-layouts/spec.md) |
| BI projects: a folder per project with numbered specs, history and an in-browser editor; export as zip | [020](specs/020-bi-projects/spec.md) |
| Import as the front door: upload → map → budgets → validate → preview → draft, and re-import as a revision with its own history | [046](specs/046-release-docs-governance/spec.md), [055](specs/055-project-reimport/spec.md) |
| The starter pack: a downloadable zip with the prompt, the request, the schemas and the skeletons, served by the app and published as a template | [043](specs/043-bizview-refactor-external-authoring/spec.md), [057](specs/057-docs-help-starter-zip/spec.md) |
| Structure packs: a source's structure and counts as a document an external AI reads instead of connecting | [048](specs/048-bi-ready-sources/spec.md), [052](specs/052-source-structure-chat/spec.md) |
| Visual components: gauge, index, share and asset blocks, project images and a URL-image cache | [044](specs/044-visual-components-and-assets/spec.md) |
| Two import allowances (artifacts and images) that an installation can raise, measured before anything is written | [049](specs/049-import-limits-assets/spec.md) |
| A design system shared by screens, PDFs and emails | [050](specs/050-ui-design-system/spec.md) |
| Themes as data: a library of tokens an author can ship inside a project and apply to a report | [047](specs/047-themes-as-data/spec.md), [051](specs/051-theme-application/spec.md) |
| Parameters and filters as one inline sheet on the report page | [053](specs/053-parameters-sheet/spec.md) |
| Sign in with Google, with domain rules and role mapping | [054](specs/054-google-signin-rbac/spec.md) |
| Sharing: expiring read-only links, email delivery to any list of addresses, scheduled sends | [018](specs/018-dashboard-sharing/spec.md), [058](specs/058-mailing-lists/spec.md) |
| Spanish and English, dark mode, PDF and CSV export | [022](specs/022-i18n-en-es/spec.md), [006](specs/006-dark-mode/spec.md) |
| Administration: users, roles, access, audit log, `internet` security profile, sign in with Google or Telegram | [002](specs/002-auth-admin-home/spec.md), [004](specs/004-data-sources-security/spec.md), [027](specs/027-google-sign-in/spec.md), [007](specs/007-telegram-sign-in/spec.md) |
| In-app guide, update notice, project search | [023](specs/023-chat-app-guide/spec.md), [025](specs/025-app-updates-and-search/spec.md) |

Mobile first: every screen works from 320 px, WCAG 2.2 AA. How to write reports:
[docs/AUTHORING.md](docs/AUTHORING.md).

## Configuration

[`.env.example`](.env.example) is the full list. The groups you will touch:

| Group | Settings |
|---|---|
| Database | `DATABASE_URL_BI` |
| Site and TLS | `SITE_ADDRESS`, `CADDY_ALLOWED_HOSTS`, `HTTP_PORT` (8081), `HTTPS_PORT` (8443; `443` on a public server), `CADDY_TLS`, `TRUSTED_PROXIES` |
| Security | `SECURITY_PROFILE` (`private` / `internet`), `COOKIE_SECURE`, `BIZVIEW_SECRET_KEY`, `SUPER_USER_EMAIL`, `SUPER_USER_PASSWORD` |
| Branding | `PRODUCT_NAME`, `ORGANIZATION_NAME`, `LOGO_URL`, `DEFAULT_LOCALE`, `TIMEZONE` |
| Projects | `PROJECTS_DIR`, `PROJECT_MAX_MB`, `IMAGE_CACHE_DIR`, `IMAGE_CACHE_DAYS` |
| AI (optional, off by default, **help only**) | `AI_PROVIDER` (`none` / `anthropic` / `openai_compatible`), `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL` (any OpenAI-compatible endpoint, including local models) |
| Mail and sharing | `SMTP_*`, `EMAIL_ALLOWED_DOMAINS`, `SHARE_LINKS_ENABLED` |
| Images | `BIZVIEW_IMAGE_PREFIX`, `BIZVIEW_VERSION` |

## How it is built

```text
browser ──HTTPS──▶ Caddy (SPA + /api + certificates) ──▶ FastAPI backend ──▶ PostgreSQL (external)
                                                              ├──▶ worker (ETL, mail, schedules, image cache)
                                                              └──▶ AI provider (optional, help page only)
projects/ (specs, YAML, SQL, assets) ────────────────────▶ backend + worker ──▶ data sources
                                                  authoring happens outside ──▶ import ──┘
```

Python 3.12 / FastAPI / SQLAlchemy / Alembic / ReportLab; React 19 / Vite / Tailwind; Caddy. The
`cli/` folder holds the `bizview` command, the JSON Schemas and the SQL rules that the CLI, the
backend and the authoring pack all read — one source for the contract. Specs live in
[`specs/`](specs/) with [Spec Kit](https://github.com/github/spec-kit); principles in
[`.specify/memory/constitution.md`](.specify/memory/constitution.md).

Development setup, tests and conventions: [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

- `SECURITY_PROFILE=internet`: HTTPS everywhere, two-step sign-in for administrators, sign-in
  throttling, step-up confirmation for sensitive changes.
- Data-source credentials are encrypted at rest (AES-256-GCM) with `BIZVIEW_SECRET_KEY` and are
  write-only: never returned, shown or logged. Back the key up separately from the database.
- The origin databases are read-only for Bizview; connections refuse loopback, link-local and
  cloud-metadata addresses, and so do the fetches of an image a report asks for by URL.
- Import validates before anything runs: file types, sizes, content sniffing and SVG sanitisation.
- No AI authors inside the product. The optional provider serves the read-only help page; the
  structure packs you hand to an external AI contain structure, counts and shapes — never
  credentials, hosts or row values.

Report vulnerabilities privately through GitHub's *Security* tab: [SECURITY.md](SECURITY.md).

## Contributing

Issues and pull requests are welcome: read [CONTRIBUTING.md](CONTRIBUTING.md) for the development
stack, the specification workflow and the checks a pull request has to pass, and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for how we treat each other.

## License

[GNU AGPL-3.0-or-later](LICENSE). If you run a modified version for others over a network you must
offer them its source; the app links to the source on every page (`SOURCE_URL`). The license does
not grant rights to the "Bizview" name or logo.
