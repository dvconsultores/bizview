# Security policy

🇬🇧 English · 🇪🇸 [Español](SECURITY.es.md)

Bizview is a self-hosted product: the code, the CLI and the images are ours; the server, the
database and the data are yours. This page says how to report a problem and what the product
protects by itself.

## Reporting a vulnerability

**Do not open a public issue.** Report privately through GitHub: *Security* tab → *Report a
vulnerability* in this repository. In the report, include:

- the affected version (the footer of the application and `/api/health` show it),
- what you did, what happened and what you expected,
- the impact you observed, and the smallest reproduction you can manage.

We acknowledge reports within **3 business days** and aim to publish a fix or a mitigation within
**30 days** for confirmed high-severity issues, crediting the reporter unless they prefer
otherwise. A report about an installation's configuration (a weak password, an exposed database) is
answered with advice, not a fix: that layer belongs to the operator.

If you need an encrypted channel or a different contact, write to **security@dvconsultores.com**.

## Supported versions

| Version | Supported |
|---|---|
| 0.2.x | Yes — security fixes and normal releases |
| 0.1.x | Security fixes only, for 60 days after 0.2.0 |

Upgrades are `BIZVIEW_VERSION` in the installation's `.env` plus `docker compose pull && docker
compose up -d`, or Watchtower doing it automatically (see [`docs/INSTALL.md`](./docs/INSTALL.md)).
0.2.0 removes the in-app authoring agent; its upgrade copies every applied conversation's
specification documents into its project folder before dropping the agent's tables, and refuses to
drop anything if a copy cannot be verified.

## Scope

**In scope** — the code in this repository: the backend and its API, the worker, the web interface,
the CLI (`cli/`), the container images and the compose file, the authoring pack's format and its
schemas, and the import path that consumes them.

**Out of scope** — a customer's own project files (their SQL and YAML are theirs: a badly written
query is a project defect, not a product vulnerability), the configuration of an installation, the
data sources Bizview reads, third-party services and the hosting infrastructure.

Send a product vulnerability here even if you found it through an installation you do not own; tell
us the installation only if you have permission to name it.

## Built-in protections

- **Credentials** of data sources and two-step secrets are encrypted at rest (AES-256-GCM) with
  `BIZVIEW_SECRET_KEY`, which never enters the database; they are write-only in the API — never
  returned, shown or logged.
- **`SECURITY_PROFILE=internet`** enforces HTTPS everywhere and two-step sign-in for administrators;
  sensitive changes require re-entering the password; administrators' network addresses can be
  allow-listed.
- **Sign-in limits**: per account (5 failures → 15 minutes) and per network address (20 failures
  per 15 minutes).
- **Origins are read-only** for Bizview. Connections refuse loopback, link-local, cloud-metadata and
  internal addresses, checked at every connection; redirects are not followed; XML is parsed
  without DTDs or entities. The same address rules apply to the **image fetch** a report can ask for
  by URL, which is size-capped, content-sniffed and cached outside the project.
- **Import validates before anything runs**: file types, sizes, path traversal, content sniffing for
  images, SVG sanitisation (no scripts, no external references), and the same JSON Schemas the CLI
  validated against. A malformed archive leaves nothing half-imported.
- **No AI authors inside the product.** The optional provider serves the read-only help page; the
  structure packs a customer hands to an external AI contain structure, counts and shapes — never
  credentials, hosts or row values.

## Notes for operators

- Keep the installation's `.env` private (the installer writes it mode 600): it holds the database
  URL, the super-user password, the secret key and any AI key. Back up `BIZVIEW_SECRET_KEY`
  separately from the database.
- Use a domain for `SITE_ADDRESS` in production so Caddy serves HTTPS, and keep `COOKIE_SECURE=true`.
- Prefer a database role that owns only the product's tables over a PostgreSQL superuser.
- AI keys are never returned by the API nor written to logs; rotate them at the provider if an
  installation's `.env` is exposed.
- Google sign-in is optional and off by default (`GOOGLE_AUTH_ENABLED=false`). Enabling it means an
  authentication round-trip to Google (`/api/auth/google/start` then `/api/auth/google/callback`)
  where the installation sends the authorization code and the standard OAuth parameters — no
  business data and no report data.
