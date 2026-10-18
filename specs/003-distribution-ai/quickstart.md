# Quickstart & Validation: Distribution & AI

**Feature**: [spec.md](./spec.md) | **Contracts**: [api](./contracts/api.md), [installer](./contracts/installer.md)

## Install a customer (production)

```bash
curl -fsSL https://github.com/<owner>/bizview/releases/latest/download/install.sh | sudo bash
# or unattended:
curl -fsSL …/install.sh | sudo bash -s -- --yes --dir /opt/bizview \
  --db-url 'postgresql://user:pass@db:5432/bizview' --admin-email admin@customer.com \
  --site dashboard.customer.com --start
```

Upgrade: set `BIZVIEW_VERSION` in `/opt/bizview/.env`, then
`docker compose pull && docker compose up -d` in that folder.

## Enable AI

In the installation's `.env`: `AI_PROVIDER=anthropic`, `AI_API_KEY=sk-ant-…` (model defaults to
`claude-opus-5-5`), or `AI_PROVIDER=openai_compatible`, `AI_BASE_URL=http://ollama:11434/v1`,
`AI_MODEL=llama3.1`. Restart, then super user → *Inteligencia artificial* → *Probar conexión*.

## Validation scenarios

| # | Scenario | Expected | Covers |
|---|---|---|---|
| 1 | `install.sh --yes` with all options into an empty folder | layout of the installer contract, `.env` mode 600, password printed once | US1, FR-003, FR-004 |
| 2 | Run it again without `--force` | exit 3, nothing changed | FR-005 |
| 3 | Run without docker in PATH | exit 1, nothing created | FR-005 |
| 4 | `--start` with local images | sign-in page served; super user can sign in | US1, SC-001 |
| 5 | `grep -ri` for customer names / credentials in the repository | nothing | SC-005 |
| 6 | Empty `ORGANIZATION_NAME` | only product name shown | FR-002 |
| 7 | `/api/health`, `/api/config` | include `version`; config has `source_url`, `license`, `ai_enabled` | FR-007, FR-015 |
| 8 | AI off → AI page | "desactivada" with instructions; `ai_enabled=false` | FR-008 |
| 9 | Anthropic with wrong key → test | `invalid_key`, key absent from response and logs | FR-010, FR-012 |
| 10 | OpenAI-compatible to a closed port → test | `unreachable` within timeout | SC-004 |
| 11 | Admin (not super user) → `/api/admin/ai` | 403 | FR-011 |
| 12 | Footer on every page | version + "Código fuente · AGPL-3.0" link | FR-015 |
| 13 | CI on a pull request without secrets | frontend, lint, installer jobs pass; DB tests skipped | FR-016 |
| 14 | Tag `vX.Y.Z` ≠ `VERSION` | release job fails early | FR-017 |
