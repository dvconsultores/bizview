# Installing Bizview AI Powered for a customer

Bizview is one open-source product. Each customer gets an **installation**: a folder on their
server with the settings and a compose file that runs the published images of one product
version. No code is copied or changed per customer.

```text
/opt/bizview/                 one installation (one customer)
├── bizview.yml               backend + web images pinned to BIZVIEW_VERSION
└── .env                      all settings (mode 600: database, super user, AI)
```

A server folder needs only `bizview.yml` and `.env`: the SPA and the logo are inside the
`bizview-web` image, so there is no `branding/` folder, and nothing mounts a customer checkout,
so there is no `workspace/` folder. The only host folders are `projects/` and `attachments/` (the
in-app data), which the compose file creates. `deploy/install.sh` writes exactly this pair and
starts it; if you copy the files from this repository, the same two files are all you need.

## 1. Requirements

- Linux server (amd64 or arm64) with [Docker Engine](https://docs.docker.com/engine/install/) and
  Docker Compose v2 (`docker compose version`).
- A PostgreSQL database for the product (the "BI database"), reachable from the server. The
  product creates its tables in the database's `public` schema. Recommended: a dedicated database
  and a role that owns it, not the `postgres` superuser.
- For HTTPS: a domain name pointing to the server, and host 443 or 80 free for the automatic
  certificate (see below when both belong to another service).

### When 80 and 443 already belong to another service

Automatic HTTPS needs one of those two host ports free: the TLS-ALPN challenge runs on 443 and
the HTTP challenge on 80. On a shared server where both are taken, publish a different host port
(`HTTPS_PORT=8443`) and choose the certificate source with `CADDY_TLS`:

| `CADDY_TLS` | What Caddy does | What else is needed |
|---|---|---|
| `auto` (default) | obtains and renews a certificate | host 443 or 80 reachable |
| `internal` | serves a certificate from its own local CA | a proxy in front that accepts it, e.g. Cloudflare with SSL mode **Full** (not *Full (strict)*) |
| `file` | serves the certificate pair in `CADDY_TLS_DIR` (`origin.pem` + `origin-key.pem`, default `./deploy/caddy/certs`) | a valid pair, e.g. a Cloudflare Origin CA certificate; needed for **Full (strict)** |

Nothing is issued by those two modes, so no host port is needed for certificates; the container
still listens on 443 inside and you publish whatever `HTTPS_PORT` says. If a CDN sits in front,
point it at that port: Cloudflare accepts the origin HTTPS ports 443, 2053, 2083, 2087, 2096 and
8443, set per hostname in an **Origin Rule** (Rules → Origin Rules → *Destination Port*). With
Cloudflare proxying a name that is not reachable at the origin, visitors see **525** (TLS
handshake failed) — that is this situation, not an application error.

If the plan does not offer **Destination Port** on an Origin Rule (the selector is missing from the
"Then…" section), the edge can only reach the origin on its standard ports. Terminate TLS at the
proxy instead, as described next: the proxy listens on 443 and forwards to `HTTPS_PORT`.

### Behind Nginx Proxy Manager (or any TLS-terminating proxy)

Keep `SITE_ADDRESS` a **domain** and `CADDY_TLS=internal`: the proxy terminates the public
certificate and Bizview keeps answering HTTPS on its published port, so the `internet` profile and
the addresses built from `SITE_ADDRESS` stay correct. In Nginx Proxy Manager, **Hosts → Proxy
Hosts → Add Proxy Host**:

| Field | Value |
|---|---|
| Domain Names | `bi.example.com` |
| Scheme | `https` |
| Forward Hostname / IP | the Docker host (`172.17.0.1`, or the host's LAN IP), or the Caddy container's name if both share a network |
| Forward Port | the published `HTTPS_PORT` (`9443` in this example) |
| Block Common Exploits | on |
| Websockets Support | on (unused today, harmless) |

On the **Advanced** tab:

```nginx
proxy_ssl_server_name on;                  # nginx sends no SNI by default …
proxy_ssl_name bi.example.com;             # … and Caddy refuses a TLS connection without it
proxy_ssl_verify off;                      # Caddy's internal CA is not in the proxy's trust store
client_max_body_size 100m;                 # match CADDY_MAX_REQUEST_BODY (attachments, project zips)
proxy_read_timeout 300s;
```

The first two lines are not optional: with `SITE_ADDRESS` set to a name, Caddy holds a certificate
only for that name and answers a connection without SNI with `tlsv1 alert internal error`, which
the proxy reports as **502**. That is also why pointing the proxy at `HTTP_PORT` instead does not
help: Caddy redirects plain HTTP to HTTPS there.

On the **SSL** tab request a certificate (Let's Encrypt needs the domain reachable on port 80) or
upload one, then enable **Force SSL** and **HTTP/2**. Nothing else is required: the app uses no
WebSockets, no server-sent events, and uvicorn already runs with `--proxy-headers`.

Finally, tell Caddy to trust the proxy, or every client looks like the proxy address (rate
limiting, audit and `ADMIN_ALLOWED_NETWORKS` all see one IP). Use the proxy's container network
when Nginx Proxy Manager is in front, or Cloudflare's ranges when the CDN reaches the origin
directly; a space-separated list is accepted. Cloudflare's published ranges as of this writing
(re-copy from <https://www.cloudflare.com/ips/> if they change):

```dotenv
TRUSTED_PROXIES=103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 104.16.0.0/13 104.24.0.0/14 108.162.192.0/18 131.0.72.0/22 141.101.64.0/18 162.158.0.0/15 172.64.0.0/13 173.245.48.0/20 188.114.96.0/20 190.93.240.0/20 197.234.240.0/22 198.41.128.0/17 2400:cb00::/32 2405:8100::/32 2405:b500::/32 2606:4700::/32 2803:f800::/32 2a06:98c0::/29 2c0f:f248::/32
```

The `Host` header must reach Caddy unchanged (NPM's default `proxy_set_header Host $host`), or
`CADDY_ALLOWED_HOSTS` answers **421**.

### Cloudflare or NPM shows an error instead of the app

The address works from the server but not from outside, so the edge cannot reach the app. Each
Cloudflare error names a different fault; check it before changing anything:

| Code | Meaning | Usually |
|---|---|---|
| **521** | origin refused the connection | nothing listening on the port the edge targets (stack down, wrong `HTTPS_PORT`) |
| **525** | TLS handshake with the origin failed | the edge targets a **plain-HTTP** port (`HTTP_PORT`, e.g. `8090`) instead of the TLS one (`HTTPS_PORT`, `9443`), or the proxy host has **no certificate** |
| **526** | origin certificate invalid | Cloudflare **Full (strict)** while Caddy uses `CADDY_TLS=internal`; switch to **Full** or supply a Cloudflare Origin CA pair with `CADDY_TLS=file` |
| **502** | proxy reached the app, which did not answer | the proxy sends **no SNI** (`proxy_ssl_server_name on;` + `proxy_ssl_name <domain>;`), cannot verify Caddy's internal CA (`proxy_ssl_verify off;`), or targets the wrong port |
| **421** | the app refused the `Host` | the proxy rewrote `Host`, or the name is missing from `CADDY_ALLOWED_HOSTS` |

Two commands separate "the app is fine" from "the edge is misconfigured", run on the server:

```bash
# the app over TLS, with the right SNI (a bare -H Host is not enough: TLS needs the name)
curl -sk -o /dev/null -w '%{http_code}\n' \
  --resolve bi.example.com:9443:127.0.0.1 https://bi.example.com:9443/api/health
# a certificate for the name on the port the edge uses (empty output = nothing TLS there)
echo | openssl s_client -connect 127.0.0.1:443 -servername bi.example.com 2>&1 | grep -E 'subject=|issuer='
```

The first returning `200` and the second returning nothing means the app is healthy and the
terminating proxy has no certificate: add one to the proxy host (NPM's **SSL** tab), or point the
edge straight at `HTTPS_PORT` and use SSL mode **Full**.

A `tlsv1 alert internal error` from the first command means the name used in it does not match
`SITE_ADDRESS`; Caddy only holds a certificate for that name.

To test the origin while the record is proxied, set the DNS record to **DNS only** (grey cloud)
temporarily and address the origin by IP with the name as SNI:

```bash
curl -k --resolve bi.example.com:9443:<origin-ip> https://bi.example.com:9443/api/health
```

## 2. Install

An installation is the compose file plus its settings, nothing else: copy [`bizview.yml`](../bizview.yml)
and a filled-in `.env` into a folder, create the two data folders owned by the container user, and
start it:

```bash
mkdir -p projects attachments
sudo chown -R 10001:10001 projects attachments   # the containers run as uid 10001
docker compose -f bizview.yml up -d
```

The containers run as **uid 10001** (`app`), so `projects/` and `attachments/` must be owned by it.
Docker would create them as root, and the app could read but not write them: BI projects and chat
images then fail at first use, and the log says `PROJECTS_DIR … is not writable`.

[`deploy/install.sh`](../deploy/install.sh) does that for you. Run it with `sudo bash`.
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
| `PRODUCT_NAME`, `ORGANIZATION_NAME`, `LOGO_URL` | names shown to users; the logo ships in the `bizview-web` image, and `LOGO_URL` points at another one |
| `FOOTER_CREDIT` | who publishes this installation, shown after the license in every footer (default `GlobalDV`) |
| `SITE_ADDRESS` | `:80` for plain HTTP, or a domain for automatic HTTPS; a domain makes shared-dashboard links and links in emails use `https://<domain>/s/…` (see "Email and shared links") |
| `HTTP_PORT`, `HTTPS_PORT` | published ports (see "When 80 and 443 already belong to another service") |
| `CADDY_TLS` | `auto` (default), `internal` or `file`: where Caddy gets its certificate |
| `CADDY_TLS_DIR` | host folder with `origin.pem` + `origin-key.pem` when `CADDY_TLS=file` (default `./deploy/caddy/certs`) |
| `COOKIE_SECURE` | `true` with HTTPS (required in production) |
| `SOURCE_URL` | optional: override the source-code link shown to users |
| `DEFAULT_LOCALE` | Interface, API messages, emails and Telegram fall back to this language (`es` or `en`, default `es`) when neither the account nor the browser decides. It does NOT affect the `bizview` CLI. |
| `TIMEZONE` | time zone of integration schedules and report periods (e.g. `America/Caracas`) |
| `DIRECT_REPORTS_BI` | default `true`: direct reports may read tables of the BI database; `false` turns `source: bi` off |
| `DIRECT_REPORT_CONCURRENCY` | default 2, 1–20: direct queries at once per source |
| `DIRECT_REPORT_WARN_ROWS` | default 5000000: above this estimated row count a direct table needs an index led by its date column |
| `DIRECT_BI_ROLE` | optional read-only database role for `source: bi`; required on the `internet` profile when `DIRECT_REPORTS_BI=true`; see §5 |
| `AI_*` | optional AI provider (see below) |

After editing: `cd /opt/bizview && docker compose -f bizview.yml up -d`.

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
`docker compose -f bizview.yml up -d`.

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
  restart, run `docker compose -f bizview.yml run --rm backend python -m app.cli rotate-secret-key`, then remove
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

**You do not need this.** To report on your own data, register the database in
**Administración → Fuentes de datos** and report from that source, or let an integration put the
data in a dataset (`ds_<integration>`) and report from it. Both work with
`DIRECT_REPORTS_BI=false`, need no database role, and are read-only by construction. The
`bi` source below exists only for reading tables of the **product's own** database, which an
internet-facing installation must not allow without the read-only role.

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

## 6. Vibe reporting

Integrations (ETL) and reports are **specs**. They come from **BI projects** (feature 020), edited
in the app and applied from **Proyectos**: applying a project creates a workspace version with it
and the other applied projects, and that version is what reports and integrations read. There is
nothing to copy to the server and nothing to mount, and the compose file already runs everything
the product needs, so there is no extra process to install or schedule.

A `bizview init` checkout can still be applied through **Espacio de trabajo → Validar → Aplicar**
(`/admin/espacio`, which has no tile in Administración since the 024 polish); the shipped
`bizview.yml` does not mount one. Applying copies the validated version into the database (the
engine never runs files that changed after validation); **Volver a la versión anterior** rolls
back. **Administración → Integraciones** shows each integration's runs, checks and next run, and
runs one on demand. Dataset tables live in schemas `ds_<integration>` of the product database,
owned by the engine.

## 7. AI (optional)

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
`AI_VISION` decides whether a model may receive images). The containers that use it must be able
to write there: the app reads the images and sweeps the ones that never became a message. It must
be **part of the backups** with `projects/` and the database.

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
2. The stack must reach `https://api.telegram.org` (outbound HTTPS only; no public address is
   needed).
3. Sign in as the super user → **Seguridad** → **Ingreso con Telegram**: enter the bot name and
   credential, **Guardar**, **Probar**, then switch **Activar ingreso con Telegram** on.

The credential is encrypted with `BIZVIEW_SECRET_KEY`, never shown again, and re-encrypted by
`rotate-secret-key`. Changing it turns the option off until the bot is tested again.

### Sign in with Google (optional)

Off by default. When `GOOGLE_AUTH_ENABLED=true`, the sign-in screen shows **Continuar con Google**
next to the password form; email and password keep working. The browser goes to
`/api/auth/google/start` and Google returns to `/api/auth/google/callback`, so the authorised
redirect URI of the client is `https://<your-domain>/api/auth/google/callback`.

The client id and secret belong to **this installation's** Google Cloud project, never to a client
held by the vendor: no two installations share a credential, and revoking one client affects only
that installation.

1. In the [Google Cloud console](https://console.cloud.google.com/), create a project (or pick an
   existing one) for this installation.
2. Configure the **OAuth consent screen**: **Internal** when the users belong to a Google Workspace
   domain of the customer, or **External** with the people listed as test users while the app is
   unpublished.
3. **Credentials** → **Create credentials** → **OAuth client ID**, application type **Web
   application**. Under **Authorised redirect URIs** add exactly
   `https://<your-domain>/api/auth/google/callback`, with the domain of `SITE_ADDRESS`.
4. Copy the client id and the client secret into the installation's `.env`
   (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`), set `GOOGLE_AUTH_ENABLED=true`, and restart:
   `docker compose -f bizview.yml up -d`.
5. Optional: `GOOGLE_ALLOWED_DOMAINS=cliente.com,socio.com` restricts which email domains may sign
   in (empty = any domain). `GOOGLE_REDIRECT_URI` overrides the redirect URI and is only for
   unusual proxy setups; empty derives it from `SITE_ADDRESS`.

Two behaviours to understand before enabling it:

- **It does not create accounts.** A Google sign-in succeeds only when the verified Google email
  belongs to an existing, active user: invite the person (**Administración → Usuarios**) first,
  then they can use Google. An unknown email gets the same failure as a wrong password, so the flow
  cannot be used to discover who has an account, and the first successful sign-in links that Google
  identity to the user. Never create or promote a user through it.
- **An invited user still sets a password on first sign-in.** Every account keeps a usable password,
  so it keeps a way in that does not depend on Google: a new user signs in for the first time (with
  Google or with the temporary password) and the product asks them to set their own password before
  they continue. From then on Google is an alternative, never a replacement.
- **Administrators keep their second factor.** Google proves *who* the person is; it does not
  replace the two-step code that the `internet` profile requires of administrators. Both methods
  end in the same sign-in, so an administrator still enters (or enrols) their code.

The client secret is read only by the backend: it is never returned by an API response, never
written to the logs and never sent to the browser. It lives in `.env`, so it is covered by that
file's permissions and not by the product's encrypted settings.

Troubleshooting:

- **Use your own client.** A client copied from another installation fails at the callback, because
  the redirect URI does not belong to it; and one leaked secret would then expose every
  installation sharing it.
- **`redirect_uri_mismatch`** means the console entry is not character-for-character
  `https://<your-domain>/api/auth/google/callback`: HTTPS, no trailing slash, the domain of
  `SITE_ADDRESS`. Fix the entry (or `GOOGLE_REDIRECT_URI`) and restart.
- **`access blocked`** means the consent screen is **External** and the person is not listed as a
  test user, or the app is unpublished. Add them as a test user, or use an **Internal** consent
  screen in the customer's Workspace domain.
- **Nobody is locked out.** Password sign-in works in every one of those cases — and with
  `GOOGLE_AUTH_ENABLED=false` — so the super user can still enter with email and password and fix
  the settings (see §10 to recover the super user).

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

   Email is on when `SMTP_HOST` and `SMTP_FROM` are set. After any change restart the stack
   (`docker compose -f bizview.yml up -d`); an invalid value stops it at startup with a message
   naming the variable.
3. Mail leaves from the stack, so it must be able to reach the SMTP host and port (outbound
   only; no public address is needed).
4. Check the setup with a test email (there is no email option in **Administración**):
   `docker compose -f bizview.yml run --rm backend python -m app.cli mail-test <address>` sends one message and
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

## 8. Upgrade

```bash
cd /opt/bizview
sed -i "s/^BIZVIEW_VERSION=.*/BIZVIEW_VERSION='0.2.0'/" .env
docker compose -f bizview.yml pull && docker compose -f bizview.yml up -d
```

Migrations run automatically. Going back to an older version is not supported once a newer one
has migrated the database: restore a backup instead (next section). Read the release notes
before upgrading.

The stack also runs **`watchtower`** (container `bizview-watchtower`): every
`WATCHTOWER_POLL_INTERVAL` seconds (default 300) it pulls a newer image of the tag in
`BIZVIEW_VERSION` and recreates only the containers of this installation, one service at a time,
so the site stays up. It is scoped by label and never touches other stacks on the host. Two
consequences:

- with `BIZVIEW_VERSION=latest`, a publish updates the installation by itself — the commands
  above are then only needed to pin a version;
- with a fixed tag such as `0.1.0`, nothing happens until you change the tag, which keeps an
  upgrade a deliberate act (the recommended setting for a customer).

To check immediately instead of waiting: `docker compose -f bizview.yml run --rm watchtower
--run-once`. It needs the Docker socket, which can control every container on the host; remove the
`watchtower` service from the compose file if that is not acceptable, and upgrade with the commands
above.

## 9. Backup and restore

The database holds all product data (users, access, audit, applied workspace versions, file
history of the projects, run history, and the `ds_*` datasets, which can also be rebuilt by a
full run); the installation folder holds the settings, the **`projects/` folder**
(the files of every BI project — back it up with the database) and the **`attachments/` folder**
(`ATTACHMENTS_DIR`: the images attached to the chat as report briefs, feature 024; they are not
in the database, not in a project folder and not in a project export, so a backup without it
loses them); the logo is inside the `bizview-web` image.

```bash
pg_dump --format=custom --file bizview-$(date +%F).dump "$DATABASE_URL_BI"   # database
tar czf bizview-install-$(date +%F).tgz -C /opt bizview                        # settings + projects + attachments
```

Restore: `pg_restore --clean --dbname "$DATABASE_URL_BI" bizview-YYYY-MM-DD.dump`, put the
folder back, `docker compose -f bizview.yml up -d`. Keep backups encrypted: they contain the `.env` secrets.

## 10. Recover the super user

Forgotten password or locked out: set the new password in `SUPER_USER_PASSWORD` in `.env`, then

```bash
cd /opt/bizview && docker compose -f bizview.yml run --rm backend python -m app.cli reset-superuser-password
```

Changing the variable alone does nothing: a password changed in the interface always wins.

Lost authenticator **and** recovery codes: `docker compose -f bizview.yml run --rm backend python -m app.cli
reset-superuser-mfa`, then sign in and enroll again. Other users: the super user resets them in
their user page (*Restablecer doble factor*).

## 11. Uninstall

```bash
cd /opt/bizview && docker compose -f bizview.yml down -v     # stops containers, removes certificate volumes
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
