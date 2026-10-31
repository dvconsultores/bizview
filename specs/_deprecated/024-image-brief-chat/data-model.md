# Data model: An image brief in the report chat

**Feature**: [spec.md](./spec.md) · [plan.md](./plan.md)

## `assistant_attachment` (new table, migration `0020_assistant_attachments`)

| Column | Type | Rules |
|---|---|---|
| `id` | bigint identity | primary key |
| `session_id` | bigint | → `assistant_session.id`, `ON DELETE CASCADE` |
| `message_id` | bigint null | → `assistant_message.id`, `ON DELETE CASCADE`; null while the send is in flight |
| `media_type` | text | one of `image/png`, `image/jpeg`, `image/webp`, `image/gif`, decided by magic bytes |
| `byte_size` | integer | ≤ `ATTACHMENTS_MAX_MB` × 1 MB |
| `sha256` | text(64) | file name on disk; the audit reference |
| `original_name` | text null | shown to the viewer only, never logged, sanitized on display |
| `created_by` | bigint | → `app_user.id` |
| `created_at` | timestamptz | default `now()` |

Indexes: `(session_id)`, `(message_id)`, `(sha256)`.

**Lifetime**: created by the upload endpoint (attached to a session, no message yet), bound to the
message when the send succeeds, deleted (row + file) when the conversation is deleted or the person
removes it. An upload that never becomes a message is garbage-collected by age (plan §Storage).

## `app_user.attachments_notice_at` (new column)

`timestamptz null` — when this person accepted the one-time notice that images leave the installation
to the configured AI provider. Null = the notice has not been shown/accepted yet.

## Settings (config)

| Setting | Default | Meaning |
|---|---|---|
| `ATTACHMENTS_DIR` | `ROOT / "attachments"` | where the files live (never inside `PROJECTS_DIR`) |
| `ATTACHMENTS_MAX_PER_MESSAGE` | `4` | images accepted in one message |
| `ATTACHMENTS_MAX_MB` | `5` | size limit per image |
| `AI_VISION` | `auto` | `auto` → on for the Anthropic-style provider, off for OpenAI-compatible; `true`/`false` override |

## Relationships

```
assistant_session 1─n assistant_attachment 0─1 assistant_message
app_user          1─n assistant_attachment        (created_by)
app_user          1─1 attachments_notice_at       (the consent timestamp)
```

## Validation rules

- Media type by magic bytes; anything else → 415 `attachment_type`.
- Size and count → 413 `attachment_too_large` / 409 `attachment_limit`.
- Session must exist and belong to the caller (or be read by an administrator) → 404 otherwise.
- Sending attachment ids that are not the caller\'s, already bound, or of another session → 404
  `attachment_not_found` (never leak that it exists).
- Vision off → 409 `vision_unavailable` before anything is stored against a message.
