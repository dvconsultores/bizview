# Research: An image brief in the report chat

**Feature**: [spec.md](./spec.md) · **Date**: 2026-10-12

## R1. Transport: provider-native content parts, base64 in the existing bodies

- **Decision**: `ChatMessage` gains `images: tuple[ImagePart, ...] = ()` where
  `ImagePart = (media_type, data_bytes)`. Each provider maps it in its own request body:
  the Anthropic-style provider sends a content list with `{"type": "image", "source": {"type":
  "base64", "media_type": ..., "data": ...}}` blocks before the text block; the OpenAI-compatible
  provider sends `{"type": "image_url", "image_url": {"url": "data:<media_type>;base64,..."}}`.
- **Rationale**: no new dependency (the app already speaks JSON over `anthropic`/`httpx`), the images
  stay inside the request the guard already redacts, and both provider families accept exactly this
  shape. `ChatMessage` remains provider-neutral: it holds bytes and a media type, nothing else.
- **Alternatives considered**: a URL the provider fetches (rejected — our providers cannot reach a
  private installation, and it would put attachments on a public route); uploading to a provider
  files API first (rejected — a second vendor surface for no gain, and it does not exist for every
  compatible endpoint); sending the image only as an OCR-ed text description (rejected — it needs a
  local vision model we do not ship, and it loses the layout the feature is about).

## R2. Capability: explicit, per installation, visible before sending

- **Decision**: new setting `AI_VISION` (`auto` | `true` | `false`, default `auto`). `auto` resolves
  to **enabled for the Anthropic-style provider** and **disabled for the OpenAI-compatible provider**
  (whose catalogue we cannot know), and `true`/`false` overrides both. `GET /api/config` exposes
  `vision_enabled`, so the composer can warn *before* the person sends.
- **Rationale**: honesty is a requirement (FR-004/SC-002); a probe request would cost a real call per
  change of model and can still be wrong, while an explicit setting is inspectable, documented and
  testable. The runtime refuses images when vision is off (409 `vision_unavailable`) instead of
  dropping them silently.
- **Alternatives considered**: probing the provider at startup (rejected: cost, flakiness, and it
  cannot cover a model swapped at runtime); a per-model allow-list shipped in the product (rejected:
  it ages badly and the product supports any OpenAI-compatible endpoint).

## R3. Storage: a product-owned directory plus one table, outside the project

- **Decision**: files at `<ATTACHMENTS_DIR>/<session_id>/<sha256>.<ext>` (default
  `ATTACHMENTS_DIR = ROOT / "attachments"`, next to `projects/`), row in `assistant_attachment`
  (session, message, media type, byte size, sha256, original name, author, created). Content is
  served by `GET /api/assistant/attachments/{id}` to the conversation\'s owner or an administrator;
  the SHA-256 name means a re-sent identical image costs no extra space and no filename ever comes
  from the client.
- **Rationale**: the project folder is the customer\'s authored artifact and is exported/applied —
  the brief must not enter it (FR-008/SC-004); the session directory mirrors how the product already
  keeps per-project files on disk; the checksum gives deduplication *and* the audit reference.
- **Alternatives considered**: storing the bytes in the database (rejected: 5 MB rows in the product
  database, worse backups); inside `PROJECTS_DIR` (rejected: exports, Git and apply would carry it);
  a public object store (rejected: a new dependency and an outward-facing surface for no need).

## R4. Lifetime: the conversation\'s, and nothing else\'s

- **Decision**: deleting a conversation deletes its attachments (rows via cascade, files by the
  service); removing one attachment from a message keeps the message text; a project export, the
  workspace Git repo, the applied version and the project zip never contain an attachment.
- **Rationale**: the brief belongs to the conversation that produced the artifacts (US4), and FR-010
  requires that removing it cannot break the project.
- **Alternatives considered**: keeping attachments after the conversation is deleted (rejected:
  orphaned customer pictures on disk); copying them into the project (rejected: see R3).

## R5. Limits and acceptance (server-authoritative)

- **Decision**: up to **4** images per message, **5 MB** each, media types **PNG, JPEG, WebP** and
  static **GIF**; the server decides by **magic bytes** (not by the declared type or the file name)
  and re-checks the size after reading; the client mirrors the limits and shows the reason. Settings:
  `ATTACHMENTS_MAX_PER_MESSAGE`, `ATTACHMENTS_MAX_MB`.
- **Rationale**: magic-byte sniffing is the cheap, dependency-free way to avoid handing a mislabelled
  file to a provider; SVG and PDF are excluded because a provider cannot read them as an image and
  they carry script/document semantics.
- **Alternatives considered**: trusting the browser\'s `Content-Type` (rejected: trivially wrong);
  transcoding with Pillow (rejected: a new dependency and a CPU cost for no user-visible gain);
  no limits (rejected: a 40 MB photo would be a 50 MB base64 prompt).

## R6. Privacy: a one-time notice, then a deliberate send

- **Decision**: a per-person timestamp (`app_user.attachments_notice_at`) records that the notice was
  accepted; the composer shows it before the first image leaves the installation and lets the person
  cancel; the audit event `assistant_attachment_sent` stores conversation, count, bytes, a short
  checksum, provider and model — never content, never the original name; the guide gains a topic
  explaining that an image is a *design brief* and must not contain customer data.
- **Rationale**: constitution VIII is a product promise; the notice is what turns "the model can see
  images" into an informed, consented action, and the audit gives the owner observability (FR-007,
  FR-014) without turning the log into a picture library.
- **Alternatives considered**: no notice (rejected: silently changes what leaves the installation);
  a per-message confirmation (rejected: friction on a repeated, benign action); storing the notice
  only in the browser (rejected: it must hold for a person across devices).

## R7. Untrusted input, and the scope gate

- **Decision**: images are packaged into the prompt as a clearly labelled block ("datos no
  confiables: boceto adjunto") in the same spirit as project documents and tool results (021); the
  BI-only scope gate runs on the message text as usual and an image-only message is answered with a
  question ("¿qué necesitas con esta imagen?"), never a refusal and never an invented report; a
  caption that contradicts the picture is surfaced, not silently resolved.
- **Rationale**: a picture is the easiest place to hide an instruction; keeping it data-only is the
  only safe framing, and it keeps the 021 guarantees intact.
- **Alternatives considered**: passing the image without a label (rejected); refusing image-only
  messages as off-topic (rejected: attaching a mockup with no words is a legitimate, common action).

## R8. Leak rules (what the tests assert)

- **Decision**: no image bytes, base64 fragments, original names or hashes-longer-than-12-chars in
  any log line, audit detail, assistant message stored as text, or error message; the existing
  payload-leak test (`tests/test_assistant_api.py::test_payload_audit_no_secrets_or_rows`) is
  extended with an image case, and the conversation JSON returns attachment *metadata* only, with
  content behind its own authorised endpoint.
- **Rationale**: SC-003 is a hard requirement and the cheapest way to keep it is to make the
  returned shape and the logged shape different from the stored bytes.
- **Alternatives considered**: returning base64 in the conversation payload (rejected: it duplicates
  the picture into every poll of the chat).
