# Installing Bizview AI Powered for a customer

Bizview is one open-source product. Each customer gets an **installation**: a folder on their
server with the settings and a compose file that runs the published images of one product
version. No code is copied or changed per customer.

```text
/opt/bizview/                 one installation (one customer)
├── bizview.yml               backend + web images pinned to BIZVIEW_VERSION
└── .env                      all settings (mode 600: database, super user, AI)
```

The logo ships inside the `bizview-web` image, so there is no `branding/` folder, and the shipped
compose file mounts no customer checkout, so there is no `workspace/` folder either.
`deploy/install.sh` still writes the older shape (`docker-compose.yml` plus `branding/` and an
empty `workspace/`, which that file mounts read-only); such an installation keeps working as it
is. When you copy the files from this repository, `bizview.yml` + `.env` are all the server needs.

## 1. Requirements

- Linux server (amd64 or arm64) with [Docker Engine](https://docs.docker.com/engine/install/) and
  Docker Compose v2 (`docker compose version`).
- A PostgreSQL database for the product (the "BI database"), reachable from the server. The
  product creates its tables in the database's `public` schema. Recommended: a dedicated database
  and a role that owns it, not the `postgres` superuser.
- For HTTPS: a domain name pointing to the server, and ports 80 and 443 open.

## 2. Install

Get [`deploy/install.sh`](../deploy/install.sh) from this repository and run it with `sudo bash`.
Interactive (asks for the missing answers):

```bash
sudo bash deploy/install.sh
```

Unattended (answers on the command line):

```bash
sudo bash deploy/install.sh \
  --yes --dir /opt/bizview \
  --version 0.1.0 \
  --image-prefix andresdom2004/bizview \
  --db-url '******db.internal:5432/bizview' \
  --admin-email admin@customer.com \
  --site dashboard.customer.com \
  --org-name 'Customer Inc.' \
  --start
```

A copy taken from this repository is **unstamped**: its version, image prefix and source URL
placeholders are not filled in, so `--version X.Y.Z` and `--image-prefix <registry/owner/bizview>`
are required with `--yes` (an interactive run asks for them). A stamped copy can be attached to a
GitHub release by hand; nothing is attached automatically.

The installer checks Docker, writes the installation folder, and with `--start` starts it and
waits until it is healthy. When no `--admin-password` is given it **generates one and prints it
once** (it is also stored in `.env`). All options: `install.sh --help`.

Sign in at the printed address with the super user. The first start creates the tables and the
super user; later starts only apply new migrations.

## 3. Settings (`.env`)

| Setting | Meaning |
|---|---|
| `BIZVIEW_VERSION` | product version to run (upgrade = change it) |
| `BIZVIEW_IMAGE_PREFIX` | where the images come from: `<prefix>-backend` and `<prefix>-web`. `./deploy.sh` pushes to Docker Hub (`andresdom2004/bizview-backend`, `andresdom2004/bizview-web`), so that prefix is `andresdom2004/bizview`; any registry that stores the same two images works. An unstamped `install.sh` requires `--image-prefix`. |
| `DATABASE_URL_BI` | the product's PostgreSQL database |
| `SUPER_USER_EMAIL`, `SUPER_USER_PASSWORD` | used only to create the super user on first start, and by the recovery command |
| `PRODUCT_NAME`, `ORGANIZATION_NAME`, `LOGO_URL` | branding (see below) |
| `FOOTER_CREDIT` | who publishes this installation, shown after the license in every footer (default `GlobalDV`) |
| `SITE_ADDRESS` | `:80` for plain HTTP, or a domain for automatic HTTPS; a domain makes shared-dashboard links and links in emails use `https://<domain>/s/…` (see "Email and shared links") |
| `HTTP_PORT`, `HTTPS_PORT` | published ports |
| `COOKIE_SECURE` | `true` with HTTPS (required in production) |
| `SOURCE_URL` | optional: override the source-code link shown to users |
| `DEFAULT_LOCALE` | Interface, API messages, emails and Telegram fall back to this language (`es` or `en`, default `es`) when neither the account nor the browser decides. It does NOT affect the `bizview` CLI. |
| `TIMEZONE` | time zone of integration schedules and report periods (e.g. `America/Caracas`) |
| `DIRECT_REPORTS_BI` | default `true`: direct reports may read tables of the BI database; `false` turns `source: bi` off |
| `DIRECT_REPORT_CONCURRENCY` | default 2, 1–20: direct queries at once per source |
| `DIRECT_REPORT_WARN_ROWS` | default 5000000: above this estimated row count a direct table needs an index led by its date column |
| `DIRECT_BI_ROLE` | optional read-only database role for `source: bi`; required on the `internet` profile when `DIRECT_REPORTS_BI=true`; see §5 |
| `AI_*` | optional AI provider (see below) |

After editing: `cd /opt/bizview && docker compose up -d`.

### Language (English / Spanish)

Feature 022 adds English alongside Spanish across the product. The active UI language is
resolved in this order:

1. The account's saved language, chosen via the language switcher in the header or settings.
   If the account is set to follow the browser, no saved language exists.
2. The browser's `Accept-Language` header.
3. The installation default `DEFAULT_LOCALE`, which can be `es` or `en` and defaults to
   `es`.

The sign-in page and the public shared-dashboard page have their own switcher. The choice is
remembered on that device and saved to the account after signing in. Switching does not
reload the page and keeps report filters.

API errors are returned in the request's language using the same order. Emails and their PDF
attachments are rendered per recipient: recipients with an account language get it;
addresses without an account, or accounts without a saved language, get `DEFAULT_LOCALE`
because there is no browser at send time. Telegram bot replies use the linked account
language, then Telegram's language code, then `DEFAULT_LOCALE`.

To change the default language, set `DEFAULT_LOCALE=en` in `.env` and run
`docker compose up -d`.

Report specs can carry optional English labels for titles, descriptions, metrics, and
dimensions; see `docs/VIBE-REPORTING.md`, section "English labels (optional)".

## 4. Security profile and secret key

- **`SECURITY_PROFILE`** — the installer asks for it:
  - `private` — local network: plain HTTP allowed for the product and for data sources;
    two-step sign-in optional.
  - `internet` — reachable from the internet: HTTPS required for the product and every data
    source, secure cookies, and **two-step sign-in mandatory for administrators**. Requires a
    domain in `SITE_ADDRESS`; the product refuses to start otherwise.
  - `auto` — `internet` when `SITE_ADDRESS` is a domain, `private` otherwise.
- **`BIZVIEW_SECRET_KEY`** encrypts data-source credentials and two-step secrets. The installer
  generates it. **Back it up in a password manager, separately from database backups**: without
  it, stored credentials cannot be decrypted (re-enter them and re-enroll two-step sign-in). The
  product refuses to start if encrypted data exists and the key is missing or wrong.
- **Rotate the key** (yearly, or if `.env` may have leaked): put the current key in
  `BIZVIEW_SECRET_KEY_PREVIOUS`, a new one in `BIZVIEW_SECRET_KEY`
  (`python3 -c "import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"`),
  restart, run `docker compose run --rm backend python -m app.cli rotate-secret-key`, then remove
  `BIZVIEW_SECRET_KEY_PREVIOUS` and restart.
- Optional: `ADMIN_ALLOWED_NETWORKS=10.0.0.0/8` (administration only from these networks),
  `SOURCES_ALLOW_PRIVATE_NETWORKS=false` (data sources only on public addresses),
  `TRUSTED_PROXIES` (only when a load balancer sits in front of this server).

## 5. Data sources

The super user registers the origin systems in **Administración → Fuentes de datos**
(PostgreSQL, SOAP/SAP, REST). Credentials are write-only and encrypted. Use read-only accounts —
the connection test warns otherwise. Installations upgraded from a version that used
`DATABASE_URL_ORIGIN` import it once as "Origen (importado)"; delete the variable afterwards.

### Direct reports on the BI database (`DIRECT_BI_ROLE`)

Direct reports with `source: bi` read the BI database through the normal pooled
connection, read-only. When `DIRECT_BI_ROLE` is set, each such session runs
`SET LOCAL ROLE <role>` for the read-only transaction of the direct session, so it only
has the grants the DBA gives that role: USAGE on the schemas that hold allowed tables and
SELECT on those tables, nothing on product tables.

**Views and functions (residual risk).** Validation and the first read walk the
dependencies of each declared view or materialized view and refuse any that reads a
product table, but the walk cannot see a product table reached through a function called
inside a view. PostgreSQL checks a view's tables with the privileges of the view's owner
(unless the view is created `WITH (security_invoker = true)`, PostgreSQL 15+), and a
`SECURITY DEFINER` function runs with its owner's privileges — so the role alone does not
help when such objects are owned by the application user. Rules: views and functions
reachable by the direct role must be owned by a role with no privileges on product
tables (e.g. the role of the process that maintains the reporting tables), never by the
application user (`bizview`); do not grant `EXECUTE` on `SECURITY DEFINER` functions
owned by the application user to the direct role or to `PUBLIC`; prefer
`security_invoker` views. A separate restricted connection
(`DATABASE_URL_BI_DIRECT`) is planned as a follow-up.

This role is **required** when `SECURITY_PROFILE=internet` and `DIRECT_REPORTS_BI=true`,
and recommended always.

A DBA must run once; the example uses the application database user `bizview`:

```sql
CREATE ROLE bizview_direct NOLOGIN;

-- tables in public: one GRANT per allowed table, by name
GRANT USAGE ON SCHEMA public TO bizview_direct;
GRANT SELECT ON public.bi_ventas TO bizview_direct;  -- repeat for each allowed table

-- dedicated reporting schema (or ds_*): schema-wide grants are fine
GRANT USAGE ON SCHEMA reporting TO bizview_direct;
GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO bizview_direct;
ALTER DEFAULT PRIVILEGES FOR ROLE erp_loader IN SCHEMA reporting
    GRANT SELECT ON TABLES TO bizview_direct;

GRANT bizview_direct TO bizview;
```

In `public` never use `GRANT SELECT ON ALL TABLES IN SCHEMA public` or
`ALTER DEFAULT PRIVILEGES ... IN SCHEMA public`: they would cover product tables.
Never grant any privilege on product tables to `bizview_direct`. When an allowed table in
`public` is dropped and recreated, re-run its `GRANT SELECT`. For `ds_*` schemas the
owner is the application user `bizview`, so use `FOR ROLE bizview` in the
`ALTER DEFAULT PRIVILEGES` line. Also make sure the `PUBLIC` pseudo-role does not have
privileges on product tables (`REVOKE ALL ... FROM PUBLIC` on those tables if necessary).

Note: the engine drops and recreates a `ds_<id>` schema when an integration is removed or
re-applied, which loses schema-level grants. The grants shown above must be re-run after
such a recreation. For a stable setup, create a dedicated reporting schema maintained by
the external process, apply the grants there, and keep `ds_*` schemas out of direct
reports. Set `DIRECT_BI_ROLE=bizview_direct` in `.env` and restart the application.

## 6. Vibe reporting: workspace and worker

Integrations (ETL) and reports are **specs**. The shipped `bizview.yml` runs a `worker` service
(same image as the backend) for the integration schedules. Integrations and reports come from
**BI projects** (feature 020), edited in the app and applied from **Proyectos**: applying a
project creates a workspace version with it and the other applied projects, and that version is
what reports and integrations read. No checkout or extra folder is needed on the server.

A customer Git checkout is still supported as an **optional** source (created with `bizview init`;
author guide: [VIBE-REPORTING.md](VIBE-REPORTING.md)). The shipped compose file does not mount it.
To use one, add `- ${WORKSPACE_DIR:-./workspace}:/workspace:ro` to both the `backend` and `worker`
services, change their `WORKSPACE_PATH` to `/workspace`, and clone the repository once:

```bash
git clone <customer workspace repo> workspace
```

A workspace can use the legacy flat layout or the **project layout** (`projects/<slug>/…`, created
by `bizview init` and `bizview project new`). Git projects appear in **Proyectos** read-only; a
project edited in the app with the same slug makes the Git apply stop and name it ("Convertir en
proyecto de la aplicación" moves a Git project to the app for good).

A mounted checkout is validated and applied in **Espacio de trabajo → Validar → Aplicar**
(`/admin/espacio`: the screen has no tile in Administración since the 024 polish); BI projects are
validated and applied from **Proyectos**. Applying copies the validated
version into the database (the engine never runs files that changed after validation);
**Volver a la versión anterior** rolls back. **Administración → Integraciones** shows each
integration's runs, checks and next run, and runs one on demand. Dataset tables live in schemas
`ds_<integration>` of the product database, owned by the engine.

## 7. Branding

The logo ships inside the `bizview-web` image and Caddy serves it at `/branding/logo.svg`; there
is nothing to copy to the server. To use another logo, either mount a folder over `/branding` in
the `caddy` service (`- ./branding:/branding:ro`) or point `LOGO_URL` at any reachable URL, then
set:

```ini
LOGO_URL=/branding/logo.svg
PRODUCT_NAME='Bizview AI Powered'
ORGANIZATION_NAME='Customer Inc.'
# FOOTER_CREDIT='Customer Inc.'    # the credit at the end of the footer (default GlobalDV)
```

With no logo, the product shows a text mark built from the product name.

## 8. AI (optional)

AI is off by default and everything works without it. It is used for report narratives (only
with the aggregated metrics the spec lists) and by the assistant, which proposes integration and
report drafts from source structure and aggregates — never detailed records, passwords, or
personal data.

Claude (Anthropic):

```ini
AI_PROVIDER=anthropic
AI_API_KEY=sk-ant-...
# AI_MODEL=claude-opus-5-5   (default)
```

A local model, so no data leaves the customer's network (any OpenAI-compatible server, e.g.
[Ollama](https://ollama.com), vLLM, LM Studio):

```ini
AI_PROVIDER=openai_compatible
AI_BASE_URL=http://ollama.internal:11434/v1
AI_MODEL=llama3.1
# AI_API_KEY=   (only if the server needs one)
```

Restart, sign in as the super user → **IA** → **Probar conexión**. The page reports success and
response time, or the reason for failure (invalid key, model not found, unreachable, …). The key
is never shown.

### Projects and assistant (Proyectos)

Every conversation works inside a **BI project**: a folder `projects/<slug>/` on the backend
volume (`PROJECTS_DIR`, default `./projects` next to the compose file) with its specs,
integrations, reports and distributions. **Proyectos** lists them; each project opens a cloud
editor (files, problems, history) next to its conversations. `PROJECT_MAX_MB` (default 20) limits
the size of one project. Applying a project creates a workspace version with it and the other
applied projects; the version records which project owns each artifact.

A mockup attached to a conversation as the report brief is stored outside the project, in
`ATTACHMENTS_DIR` (default `./attachments` next to the compose file, mounted as
`ATTACHMENTS_DIR_HOST`; `ATTACHMENTS_MAX_MB` 5 and `ATTACHMENTS_MAX_PER_MESSAGE` 4 by default;
`AI_VISION` decides whether a model may receive images). The backend and the worker both need
that folder writable — the worker sweeps uploads that never became a message — and it must be
**part of the backups** with `projects/` and the database.

The super user describes a dashboard in a conversation; the assistant reads only source
structure and aggregates, checks its queries, runs a preview and leaves the draft "Listo
para aplicar". Applying stays a human action with password confirmation. DeepSeek worksthrough `AI_PROVIDER=openai_compatible` with the endpoint and model below.

```ini
AI_PROVIDER=openai_compatible
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-chat
AI_CHAT_TOKEN_BUDGET=400000
AI_CHAT_CACHED_TOKEN_WEIGHT=0.1
AI_CHAT_MAX_ROUNDS=60
AI_CHAT_MAX_TOKENS=16000
AI_CHAT_BUDGET_STEP=100000
AI_CHAT_BUDGET_MAX=2000000
AI_CHAT_MAX_PREVIEWS=5
AI_TOOL_TIMEOUT_SECONDS=20
AI_CHAT_TIMEOUT_SECONDS=180
AI_AGENT_DISCOVERY_LIMIT=15
AI_CHAT_BUSY_STALE_SECONDS=900
AI_AGENT_MAX_CONCURRENT=4
```

A message starts an autonomous run that keeps working on the server (the page can be closed) until
the agent asks a business question or reports, the draft is "Listo para aplicar",
`AI_CHAT_MAX_ROUNDS` rounds, two identical failing tool calls, or the budget reaches
`AI_CHAT_BUDGET_MAX`. The budget grows by `AI_CHAT_BUDGET_STEP` automatically (audited as
automatic); "Detener" stops a run keeping the rounds already saved; at most
`AI_AGENT_MAX_CONCURRENT` runs work at once per backend process; applying stays a human action
with password confirmation. Each round's answer is limited to `AI_CHAT_MAX_TOKENS` tokens
(default 16000, 1024–64000; a complete draft with specs, YAML and SQL needs several thousand, so
lower it only for small models). Each chat call of the assistant waits up to `AI_CHAT_TIMEOUT_SECONDS`
(default 180; `AI_TIMEOUT_SECONDS` keeps governing narratives and the connection test); a timeout
is retried once per run, then the run stops with a progress summary and keeps the draft. Within a
run, repeating a discovery call on the same target (`describe_source`, `profile_source`,
`get_authoring_guide`, `check_query`) answers the earlier result without contacting the source
("tabla", "/tabla" and "public.tabla" are the same Supabase/REST table) and `refresh` is honoured
once per target; after `AI_AGENT_DISCOVERY_LIMIT` discovery calls (default 15) without a draft the
agent is offered only the draft tools until it proposes one. Prompt tokens the provider serves from its
cache (DeepSeek `prompt_cache_hit_tokens`, OpenAI `cached_tokens`, Anthropic cache reads) count
`AI_CHAT_CACHED_TOKEN_WEIGHT` (default 0.1) of a token against the budget; the conversation
statistics keep the raw input, cached and output totals. Each agent round is saved as it finishes, so
a restart mid-answer keeps the earlier rounds. While the assistant works on a conversation,
a second message, preview, apply, archive or budget extension is refused ("El asistente sigue
trabajando…"). The busy mark is refreshed after every saved round; a mark not refreshed for
`AI_CHAT_BUSY_STALE_SECONDS` is treated as an interrupted answer and the next message resumes
it; it must exceed 2 × `AI_CHAT_TIMEOUT_SECONDS` + `AI_TOOL_TIMEOUT_SECONDS` (checked at
startup), so raise it when you raise the chat timeout. The assistant header's "Mapa del agente"
(also from the session indicator and the "● N herramientas" pill) shows the current run as a
floating card over the chat: the agent, one node per tool call with its status and duration, and
background tasks such as the preview; it reads `GET /api/assistant/sessions/{id}/activity` every
2 s while open and the agent works.

### Sign in with Telegram (optional)

Off by default. When on, users who link their Telegram account from **Perfil** can sign in by
approving a request in Telegram and picking the code shown on screen; email and password keep
working. Administrators on the `internet` profile still enter their two-step code.

1. In Telegram, talk to [@BotFather](https://t.me/BotFather) → `/newbot`. Note the bot name (it
   ends in `bot`) and its credential. Use one bot per installation and do not set a webhook.
2. The `worker` service must reach `https://api.telegram.org` (outbound HTTPS only; no public
   address is needed).
3. Sign in as the super user → **Seguridad** → **Ingreso con Telegram**: enter the bot name and
   credential, **Guardar**, **Probar**, then switch **Activar ingreso con Telegram** on.

The credential is encrypted with `BIZVIEW_SECRET_KEY`, never shown again, and re-encrypted by
`rotate-secret-key`. Changing it turns the option off until the bot is tested again.

### Email and shared links (optional)

Both are off by default. Email lets users send a dashboard PDF from the dashboard and lets
administrators schedule sends. Shared links let administrators create read-only links that
expire after 1–90 days.

1. Ask the customer's mail provider for an SMTP account: host, port (usually `587` with
   STARTTLS or `465` with SSL/TLS), username, password, and an address you may send from.
2. The installation's `.env` (the same file as the AI settings; there is no form in the product)
   already contains these variables commented out. Uncomment and fill them:

   ```
   SMTP_HOST=smtp.cliente.com
   SMTP_PORT=587
   SMTP_SECURITY=starttls       # starttls | ssl | none; empty = ssl on 465, else starttls
   SMTP_USER=bizview@cliente.com
   SMTP_PASSWORD=...
   SMTP_FROM=bizview@cliente.com
   SMTP_FROM_NAME=Cliente Demo  # optional; defaults to ORGANIZATION_NAME
   EMAIL_ALLOWED_DOMAINS=cliente.com,socio.com   # empty = installation users only
   SHARE_LINKS_ENABLED=true     # lets administrators press Compartir on a dashboard
   ```

   Email is on when `SMTP_HOST` and `SMTP_FROM` are set. Restart the `backend` and `worker`
   services (`docker compose up -d`) after any change; an invalid value stops them at startup
   with a message naming the variable.
3. The `worker` service sends the mail. It must be able to reach the SMTP host and port
   (outbound only; no public address is needed).
4. Check the setup with a test email (there is no email option in **Administración**):
   `docker compose run --rm backend python -m app.cli mail-test <address>` sends one message and
   prints success or a sanitized reason (never the password).

Safety notes. `SMTP_SECURITY=none` is refused at startup on the `internet` profile, and STARTTLS
verifies the certificate. `SMTP_PASSWORD` stays in the installation environment: it is never
stored in the database, returned by the API, shown or logged, and must be ASCII without line
breaks. Test emails and sends are audited.

Limits. At most 20 recipients per send, 30 sends per user per hour, and a 10 MB PDF; when a PDF
exceeds that limit with **Incluir enlace** checked the email carries only the link, and without a
link the delivery fails with the reason "El PDF supera 10 MB y no se pidió un enlace.". Failed
deliveries retry after 1, 5 and 15 minutes, and the status of every recipient is listed under
**Envíos**.

Links. Anyone holding a link sees that one dashboard read-only until it expires or is revoked
(**Revocar**), with at most 20 active links per dashboard. Links are stored only as a hash, so a
lost link cannot be shown again — create a new one. Setting `SHARE_LINKS_ENABLED=false` (and
restarting) stops all links at once. The public page is not indexed by search engines and is rate-limited per
address.

Links in emails. When an administrator ticks **Incluir enlace** in **Enviar por correo**, the
outgoing email gets a private link valid N days (1–90), created with the note "Correo:
<asunto>". The sender owns one link per send, not per recipient, and the link counts toward the
20 active links per dashboard while queued or active; at the limit the send with a link is
refused and the email can be sent without one. Scheduled sends (**Envíos programados**) reuse a
single link owned by each subscription and do not count toward the limit; a replacement is
created only when the current link expires within one day or is revoked. **Enlaces activos**
inside **Compartir** shows the origin of each link ("Creado a mano", "Creado por un envío por
correo", "Creado por un envío programado") and marks subscription links as not counted. Revoking
a subscription's link stops it at once and the next scheduled run creates a fresh one. When
shared links are off (`SHARE_LINKS_ENABLED=false`) at run time, a scheduled send goes without a link (PDF only) and
one that has only a link is skipped for that run. Link ciphertexts kept for retries and reuse
are encrypted with `BIZVIEW_SECRET_KEY` and re-encrypted by `rotate-secret-key`.

Link addresses. With a domain in `SITE_ADDRESS`, links in the share view and in emails
(including scheduled ones) are `https://<domain>/s/…`. Without a domain (`:80`), a link created
from the browser uses the address the administrator is using, and scheduled emails fall back to
`http://localhost` — so set a domain in `SITE_ADDRESS` before including links in scheduled
emails. Recipients outside the network need the site to be reachable from where they open it.

Scheduled sends use the installation time zone (`TIMEZONE`).

## 9. Upgrade

```bash
cd /opt/bizview
sed -i "s/^BIZVIEW_VERSION=.*/BIZVIEW_VERSION='0.2.0'/" .env
docker compose pull && docker compose up -d
```

Migrations run automatically. Going back to an older version is not supported once a newer one
has migrated the database: restore a backup instead (next section). Read the release notes
before upgrading.

## 10. Backup and restore

The database holds all product data (users, access, audit, applied workspace versions, file
history of the projects, run history, and the `ds_*` datasets, which can also be rebuilt by a
full run); the installation folder holds the settings, the **`projects/` folder**
(the files of every BI project — back it up with the database) and the **`attachments/` folder**
(`ATTACHMENTS_DIR`: the images attached to the chat as report briefs, feature 024; they are not
in the database, not in a project folder and not in a project export, so a backup without it
loses them); the logo is inside the `bizview-web` image, and an optional Git workspace lives in
its own repository.

```bash
pg_dump --format=custom --file bizview-$(date +%F).dump "$DATABASE_URL_BI"   # database
tar czf bizview-install-$(date +%F).tgz -C /opt bizview                        # settings + projects + attachments
```

Restore: `pg_restore --clean --dbname "$DATABASE_URL_BI" bizview-YYYY-MM-DD.dump`, put the
folder back, `docker compose up -d`. Keep backups encrypted: they contain the `.env` secrets.

## 11. Recover the super user

Forgotten password or locked out: set the new password in `SUPER_USER_PASSWORD` in `.env`, then

```bash
cd /opt/bizview && docker compose run --rm backend python -m app.cli reset-superuser-password
```

Changing the variable alone does nothing: a password changed in the interface always wins.

Lost authenticator **and** recovery codes: `docker compose run --rm backend python -m app.cli
reset-superuser-mfa`, then sign in and enroll again. Other users: the super user resets them in
their user page (*Restablecer doble factor*).

## 12. Uninstall

```bash
cd /opt/bizview && docker compose down -v     # stops containers, removes certificate volumes
```

The database is not touched; drop it separately if the customer no longer needs the data.

## Managing many customers

Keep the product repository generic. If you operate installations for several customers, keep a
**private operations repository** with one folder per customer containing only that customer's
installation files — never code:

```text
ops-bizview/                       (private)
├── acme/     .env.enc  bizview.yml
└── globex/   .env.enc  bizview.yml
```

Encrypt the `.env` files (for example with [sops](https://github.com/getsops/sops) + age) and
upgrade customers by changing `BIZVIEW_VERSION` per folder. Customer-specific needs become
settings or extension points in the product, never a fork.
