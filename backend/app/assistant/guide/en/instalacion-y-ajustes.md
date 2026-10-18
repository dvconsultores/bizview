# Installation and settings

## What it is for

It sums up how a BizView installation is configured, how it is upgraded and what to back up.

## Who can use it

Only the **Superuser** or whoever runs the server.

## How to

Settings live in the `.env` file of the installation folder; after changing them, restart the
installation. By area:

- Branding: `ORGANIZATION_NAME` and `LOGO_URL`.
- Security: `SECURITY_PROFILE` (`auto`, `private` or `internet`).
- AI: `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL` and the chat budgets
  (`AI_CHAT_TOKEN_BUDGET`, `AI_CHAT_BUDGET_MAX`).
- Language and time: `DEFAULT_LOCALE` (`es` or `en`) and `TIMEZONE`.
- Projects: `PROJECTS_DIR` and `PROJECT_MAX_MB`.
- Direct reports and ETL: `DIRECT_REPORTS_BI` and `TRANSFORM_MAX_ROWS`.
- Email: see Installation email.

## Options

- Upgrade: change `BIZVIEW_VERSION` in `.env` and start the installation again.
- Backups: the database, the `projects/` folder and the encryption key; without the key, stored
  credentials cannot be read.
- Server commands: `rotate-secret-key` (rotates the encryption key) and `reset-superuser-mfa`
  (resets the **Superuser**'s two-factor).
