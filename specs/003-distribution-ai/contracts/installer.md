# Installer Contract — `deploy/install.sh`

```text
install.sh [--dir DIR] [--db-url URL] [--admin-email EMAIL] [--admin-password PW]
           [--site ADDRESS] [--http-port N] [--https-port N]
           [--product-name NAME] [--org-name NAME]
           [--version X.Y.Z] [--image-prefix REGISTRY/OWNER/bizview]
           [--yes] [--force] [--start] [--help]
```

| Option | Default | Notes |
|---|---|---|
| `--dir` | `/opt/bizview` | created if missing |
| `--db-url` | asked | must start with `postgresql://` or `postgres://` |
| `--admin-email` | asked | must contain `@` and a dot after it |
| `--admin-password` | generated (20 chars) | printed once at the end when generated; ≥ 10 chars. Prefer generating it: a password on the command line can end up in shell history |
| `--site` | `:80` | a domain enables automatic HTTPS, `COOKIE_SECURE=true`, ports 80/443 |
| `--http-port` / `--https-port` | 80 / 443 | published ports |
| `--product-name` | `Bizview AI Powered` | |
| `--org-name` | empty | |
| `--version` | stamped at release (`__BIZVIEW_VERSION__`) | required when running an unstamped copy |
| `--image-prefix` | stamped at release (`__IMAGE_PREFIX__`) | required when running an unstamped copy |
| `--yes` | off | never prompt; missing required answers → exit 2 |
| `--force` | off | overwrite existing `.env` and `docker-compose.yml` (branding/queries kept) |
| `--start` | off | run `docker compose up -d` and wait for health |

Exit codes: `0` success · `1` prerequisite missing (docker/compose) · `2` invalid or missing
answer · `3` existing installation without `--force` · `4` start failed.

Created layout (`.env` `0600`, `docker-compose.yml` `0644`, folders `0755`):

```text
DIR/
├── .env                 # all settings (see .env keys below)
├── docker-compose.yml   # backend + web, images ${BIZVIEW_IMAGE_PREFIX}-{backend,web}:${BIZVIEW_VERSION}
├── branding/            # logos; served at /branding/<file>
└── queries/             # source-database query profile (feature 001)
```

`.env` keys: `BIZVIEW_VERSION`, `BIZVIEW_IMAGE_PREFIX`, `DATABASE_URL_BI`, `SUPER_USER_EMAIL`,
`SUPER_USER_PASSWORD`, `PRODUCT_NAME`, `ORGANIZATION_NAME`, `LOGO_URL`, `SITE_ADDRESS`,
`HTTP_PORT`, `HTTPS_PORT`, `COOKIE_SECURE`, `SOURCE_URL`, `AI_PROVIDER`, `AI_API_KEY`,
`AI_MODEL`, `AI_BASE_URL`, `AI_TIMEOUT_SECONDS`, `LOG_LEVEL`.

Upgrade: edit `BIZVIEW_VERSION`, then `docker compose pull && docker compose up -d`.
