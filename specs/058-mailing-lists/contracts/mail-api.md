# Contract — mailing lists and sending

Feature 058. All endpoints are authenticated (`current_user`); the send endpoints additionally require
access to the dashboard, exactly as in feature 018. There is no public surface.

## Lists — `/api/mail/lists`

| Method | Path | Body / query | Answer |
|---|---|---|---|
| `GET` | `/api/mail/lists` | `?scope=mine\|shared\|all&q=` | `{items: [ListJson], can_share: bool}` |
| `POST` | `/api/mail/lists` | `ListIn` | `201 ListJson` |
| `GET` | `/api/mail/lists/{id}` | | `ListJson` with members |
| `PATCH` | `/api/mail/lists/{id}` | `ListPatch` | `ListJson` |
| `DELETE` | `/api/mail/lists/{id}` | | `204` (soft delete, pauses subscriptions) |
| `PUT` | `/api/mail/lists/{id}/members` | `{members: [{address, name?, paused?}]}` | `ListJson` |
| `POST` | `/api/mail/lists/{id}/members/import` | `{text: "correo,nombre\n…"}` or `text/csv` | `{added, updated, skipped, errors: [{line, value, code}]}` |
| `GET` | `/api/mail/lists/{id}/export` | | `text/csv` attachment `lista-<name>.csv`, columns `correo,nombre,pausado` |
| `POST` | `/api/mail/lists/{id}/members/{member_id}/pause` | `{paused: bool}` | `ListJson` |

`ListJson`:

```json
{
  "id": 7, "name": "Gerencia comercial", "description": "Comerciales activos",
  "visibility": "compartida", "kind": "members", "role": null,
  "owner": {"id": 3, "name": "Ana Pérez"}, "mine": true, "editable": true,
  "count": 14, "paused": 1,
  "members": [{"id": 31, "address": "ana@cliente.com", "name": "Ana", "paused": false}],
  "created_at": "2026-11-06T10:00:00Z", "updated_at": "2026-11-06T10:00:00Z"
}
```

`members` is present only on `GET /{id}` and on the write answers. A `role` list answers
`kind: "role"`, `role: "admin"`, `count` = live users of that role, `members: []`.

Errors: `404 list_not_found`, `403 list_not_editable`, `422` with `fields`; `list_too_large` when the
cap would be passed; `name_taken` on the per-owner unique name.

## Sending — `/api/dashboards/{code}/email`

`POST` body gains two fields; `users` and `emails` stay:

```json
{
  "users": [12],
  "lists": [7],
  "emails": ["ana@cliente.com", "Luis Pérez <luis@cliente.com>"],
  "subject": "Ventas de octubre",
  "message": "Adjunto el cierre.",
  "selection": {"period": "last_month", "compare": "previous_period"},
  "attach_pdf": true,
  "link_days": 7,
  "save_as_list": "Gerencia comercial"
}
```

Answer `201 SendJson` (unchanged shape) with `count` and `kinds`.

`GET /api/dashboards/{code}/email` (options) adds:

```json
{
  "max_recipients": null,
  "allowed_domains": [],
  "free_addresses_role": "user",
  "sending_paused": false,
  "batch_size": 50,
  "send_rate": 10,
  "individual_messages": false,
  "from_mode": "installation",
  "lists": [{"id": 7, "name": "Gerencia comercial", "count": 14, "visibility": "compartida"}]
}
```

`max_recipients: null` is the contract for "no ceiling"; the frontend renders no limit.

`GET /api/dashboards/{code}/email/sends?limit=50` → `{items: [SendJson]}` — the history; `SendJson`
gains `kinds` and `deliveries` with `address` **masked** (`a***@dominio`) and `error`.

`POST /api/dashboards/{code}/email/sends/{send_id}/resend-failed` → `201 SendJson` — a new send with
only the failed deliveries of that send, same subject/message/selection/attachments.

## Subscriptions — `/api/dashboards/{code}/subscriptions`

`SubscriptionIn` gains `lists: [int]`; the answer's `recipients` gains
`{"kind": "list", "id": 7, "name": "Gerencia comercial", "count": 14}`; `paused_reason` is returned
when set and cleared when the subscription is patched.

## Distribution artifact — `distributions/<id>.yaml`

```yaml
recipients:
  roles: [admin]                    # unchanged
  lists: ["Gerencia comercial"]     # new: names, never addresses
  users: [12]                       # unchanged
```

Rules enforced by `distribution.schema.json` and re-checked by the import:

- `lists` entries: 1..200 characters with no `@` — an address is refused with *addresses are not
  allowed in a distribution; name a list instead*;
- apply refuses a name with no matching live list, naming it (`distribution_list_missing`).

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `EMAIL_ALLOWED_DOMAINS` | *(empty)* | empty = any domain; a list restricts free addresses and list members |
| `EMAIL_BATCH_SIZE` | `50` | recipients per BCC message (`1..500`) |
| `EMAIL_SEND_RATE` | `10` | messages per second (`0` = unlimited) |
| `EMAIL_INDIVIDUAL_MESSAGES` | `false` | one message per recipient instead of BCC batches |
| `EMAIL_SENDING_PAUSED` | `false` | hold the queue, keep accepting sends |
| `EMAIL_FROM_MODE` | `installation` | `installation` = SMTP_FROM + Reply-To sender; `user` = From sender |
| `EMAIL_FREE_ADDRESSES_ROLE` | `user` | `admin` restricts free addresses to administrators |
