# Quickstart — prove mailing lists end to end

Feature 058. Commands run from the repository root with the project's virtualenv (`.venv`) and a
PostgreSQL database in `DATABASE_URL_BI`.

## 1. Migrate and configure

```bash
cd backend && ../.venv/bin/python -m alembic upgrade head && cd ..
. .venv/bin/activate
export SMTP_HOST=localhost SMTP_PORT=1025 SMTP_FROM=boards@example.com
export EMAIL_ALLOWED_DOMAINS=          # empty: any domain
export EMAIL_BATCH_SIZE=50 EMAIL_SEND_RATE=10
```

Add a capture SMTP server for a local run (`python -m aiosmtpd -n -l localhost:1025`) or point the
installation at the provider. `GET /api/health` and the **Administración → Correo** card should say
email is available.

## 2. The suite that proves the behaviour

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_mail_lists.py tests/test_mail_send_batches.py -q
cd ../cli && .venv/bin/python -m pytest tests/test_distributions.py -q
cd ../frontend && npx vitest run tests/unit/mail-lists.test.tsx
```

Expected: green. The backend tests cover address parsing (bare, `Nombre <correo>`, duplicates, the
sender's own address), the domain filter empty and set, list CRUD + CSV, paused members, dynamic role
lists, deletion pausing subscriptions, a 1,500-address send as one job with batched and paced
messages, `EMAIL_SENDING_PAUSED`, `EMAIL_FROM_MODE=user`, and no refusal for size or frequency.

## 3. The flow by hand

1. Sign in as an administrator, open **Administración → Listas de correo**, **Nueva lista**, paste:

   ```text
   ana@example.com, Ana
   luis@example.com
   ```

   Export it: the CSV comes back with `correo,nombre,pausado`.
2. Open a dashboard, **⋯ → Enviar por correo**, add the list, a colleague and a pasted address; the
   counter shows the resolved total.
3. Send. **⋯ → Envíos** lists the send with one row per address and its status.
4. Create a subscription for the same list; run one worker tick
   (`bizview` worker or `pytest tests/test_mail_subscriptions.py -q -k list`).
5. Break one delivery (stop the SMTP server), send again, then **Reenviar los fallidos** with the
   server back: only the failed address is queued.

## 4. Authored project

```bash
cd /tmp && bizview init workspace --name demo --path demo-bizview && cd demo-bizview
# distributions/001-envio/distribution.yaml with recipients: {lists: ["Gerencia comercial"]}
bizview validate                     # passes the shape
# an address in `lists:`  → refused
```

Applying the project in the app requires the list to exist; otherwise apply is refused naming it.

## 5. Gates

```bash
sh scripts/gates/all.sh          # includes the grep gate for the removed limits
python3 scripts/check_docs_parity.py
```

The grep gate fails if `MAX_RECIPIENTS`, `SENDS_PER_HOUR` or an hourly-limit message comes back.
