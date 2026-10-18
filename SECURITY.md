# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Report them privately through
GitHub: *Security* tab → *Report a vulnerability* in this repository. Include the affected
version (shown in the footer of the application and at `/api/health`), steps to reproduce, and
the impact you observed.

We aim to acknowledge reports within 3 business days and to publish a fix or mitigation within
30 days for confirmed issues, crediting the reporter unless they prefer otherwise.

## Supported versions

Security fixes are released for the latest minor version. Installations upgrade by changing
`BIZVIEW_VERSION` in their `.env` and restarting (see `docs/INSTALL.md`).

## Built-in protections

- Credentials of data sources and two-step secrets are encrypted at rest (AES-256-GCM) with
  `BIZVIEW_SECRET_KEY`, which never enters the database; they are write-only in the API.
- `SECURITY_PROFILE=internet` enforces HTTPS everywhere and two-step sign-in for administrators.
- Sign-in is limited per account (5 failures → 15 min) and per network address (20 failures per
  15 min); sensitive changes require re-entering the password; optional admin network allow-list.
- Data-source connections refuse loopback, link-local, cloud-metadata and internal addresses
  (checked at every connection), never follow redirects, and parse XML without DTDs or entities.

## Scope notes for operators

- Keep each installation's `.env` private (the installer creates it with mode 600); it holds the
  database URL, the super-user password, the secret key, and any AI key. Back up
  `BIZVIEW_SECRET_KEY` separately from database backups.
- Use a domain for `SITE_ADDRESS` in production so Caddy serves HTTPS, and keep
  `COOKIE_SECURE=true`.
- Prefer a database role that owns only the product's tables over a PostgreSQL superuser.
- AI keys are never returned by the API or written to logs; rotate them at the provider if an
  installation's `.env` is exposed.
