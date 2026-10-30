# Installation email

## What it is for

It explains how the email used by sends and shared links is configured.

## Who can use it

Only the **Superuser** (or whoever runs the server): email is configured in the installation's
settings file, not on screens.

## How to

1. In the installation's `.env` file set `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY` (`starttls`,
   `ssl` or `none`), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` and, optionally,
   `SMTP_FROM_NAME`.
2. To allow external emails, list their domains in `EMAIL_ALLOWED_DOMAINS` (comma separated).
3. To allow shared links, set `SHARE_LINKS_ENABLED=true`. Links use the installation's public
   address (`SITE_ADDRESS`).
4. Restart the installation and test sending with the server's `mail-test` command.

## Common problems

- Without email set up, **Send by email** and **Scheduled sends** say email sending is not
  available; the rest of the app works the same.
