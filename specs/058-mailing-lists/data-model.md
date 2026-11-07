# Data model — mailing lists

Feature 058. Additive: nothing of feature 018 changes shape except the removal of two constants and
two new nullable columns.

## `mail_list`

| Column | Type | Rules |
|---|---|---|
| `id` | `bigint identity` | primary key |
| `owner_id` | `smallint` → `app_user.id`, `ON DELETE CASCADE` | who edits it |
| `name` | `text` | `1..80`, unique per owner among live rows (partial unique index on `owner_id, lower(name)` where `deleted_at is null`) |
| `description` | `text null` | `<= 200` |
| `visibility` | `text` | `personal` \| `compartida` |
| `kind` | `text` | `members` \| `role` |
| `role` | `text null` | required when `kind = 'role'`, one of `user`, `admin` (never `superuser`) |
| `created_at`, `updated_at` | `timestamptz` | |
| `deleted_at` | `timestamptz null` | soft delete (R8) |

Invariants
- `(kind = 'role') = (role is not null)`.
- `visibility = 'compartida'` only for an owner whose role is `admin` (enforced in the service, so a
  demoted owner keeps the list working and only loses the right to create new shared ones).
- Deleting (soft) pauses every subscription whose `recipients` contains `{"list": id}` with
  `paused_reason = 'list_deleted'`.

## `mail_list_member`

| Column | Type | Rules |
|---|---|---|
| `id` | `bigint identity` | primary key |
| `list_id` | `bigint` → `mail_list.id`, `ON DELETE CASCADE` | |
| `address` | `text` | normalised; unique per list (`unique(list_id, address)`) |
| `name` | `text null` | display name, `<= 120` |
| `paused` | `boolean` | default false |
| `created_at` | `timestamptz` | |

Invariants
- At most 1,000 members per list (refused with `list_too_large` naming the cap).
- An address present twice updates the name instead of duplicating.

## `email_send` (changed)

| Column | Type | Rules |
|---|---|---|
| `kinds` | `jsonb` | `{"users": n, "lists": [names], "emails": n}` — counts and list names, never addresses (FR-018) |

`dashboard_id`, `requested_by`, `subject`, `message`, `selection`, `attach_pdf`, `link_days`,
`status` unchanged.

## `email_delivery` (unchanged)

One row per address, `status ∈ {queued, sent, failed, skipped}`, `attempts`, `error`, plus a new
nullable `list_id` so the history can say a person came from a list (informative only; resolution is
a snapshot at send time).

## `email_subscription` (changed)

| Column | Type | Rules |
|---|---|---|
| `paused_reason` | `text null` | `list_deleted` \| `role_empty` \| null; cleared when the subscription is edited or resumed |

`recipients` (JSON) gains `{"list": <id>}` entries beside `{"user_id": …}`, `{"role": …}` and
`{"email": …}`. Existing rows stay valid: `{"role": …}` is unchanged.

## State

`EmailSend.status`: `queued → sending → done | failed | partial` (as today).
`EmailDelivery.status`: `queued → sent | failed | skipped` (as today); `failed` is retryable three
times with backoff before it stays failed — and the history offers **Reenviar los fallidos**, which
creates a new send with only those addresses (`kind` copied, `resend_of` recorded in `selection`).

## Portability

Lists are installation data, not project data: nothing of this model is written to a project folder or
exported with a project. A project names a list; the installation owns it.
