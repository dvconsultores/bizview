# Implementation Plan: An image brief in the report chat

**Branch**: `024-image-brief-chat` | **Date**: 2026-10-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/024-image-brief-chat/spec.md`

## Summary

Give a chat message zero or more images and pass them to the model as provider-native **image content
parts** (base64 in the existing request bodies, no new dependency, no URL the provider fetches). The
chat stays what it is — BI-scoped, command-driven, text-first — and gains one new input: an image is
treated as an **untrusted design brief**, labelled as such in the prompt, recorded in the audit
without its content, stored outside the project folder, and honest about itself: when the configured
model cannot see, the composer warns before sending, the API refuses the images with a clear reason if
they are sent anyway, and the answer never pretends to have read them.

## Technical Context

**Language/Version**: Python 3.12+ / React 19 + TypeScript (existing)

**Primary Dependencies**: none new — `anthropic` and `httpx` already carry JSON bodies; images are
base64 inside them. `Pillow` is **not** used: magic-byte sniffing plus size limits only

**Storage**: one new table `assistant_attachment` (session, message, media type, size, sha256,
original name, author, created) + files under a configured directory (`ATTACHMENTS_DIR`, default
`attachments/` beside `projects/`); deleted with the conversation; **never** inside `PROJECTS_DIR`,
the workspace Git repo, the project zip or the applied version

**Testing**: `backend/tests/test_assistant_attachments.py` (limits, sniffing, ownership, deletion,
vision off, audit, payload-leak), provider mapping in `tests/test_ai*.py`, frontend unit tests for the
composer, opt-in live evaluation for "brief → report spec" (`tests/live/`)

**Target Platform**: unchanged (Linux server + browser; mobile-first composer)

**Project Type**: full-stack change inside the existing product (backend + frontend + migration)

**Performance Goals**: attach + send of an in-limit image under 2 s on localhost (SC-005); no
regression for text-only messages

**Constraints**: images never reach the AI without the one-time notice; no image bytes, names or
content in logs/audit/errors (SC-003); the scope gate and command guards of 021 keep applying; every
new string in Spanish and English; `ChatMessage` stays provider-neutral

**Scale/Scope**: up to 4 images per message, 5 MB each, PNG/JPEG/WebP (+static GIF); one migration;
no change to the report/PDF engine, the project layout or the workspace format

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict |
|---|---|
| I. Mobile-First | **PASS** — the composer is a mobile control (tap to attach, preview, remove, 44 px targets) |
| II. Backend as ETL | **PASS** — untouched; the feature adds no origin reads |
| III. Source of truth external | **PASS** — nothing is written to an origin |
| IV. Separated concerns | **PASS** — the model table lives with the assistant models, the files under a product-owned directory, the UI in the assistant components |
| V. Fixed technology stack | **PASS** — no new component, no new library (base64 inside the existing provider bodies) |
| VI. Data tuning over raw storage | **PASS** |
| VII. One product, many installations | **PASS** — limits and the directory are settings; strings localized |
| VIII. AI optional and private | **PASS by design, and it is the feature\'s hard part**: images are sent only after a one-time notice, labelled as untrusted brief data, never logged with content, and the feature refuses to *extract* customer data from a picture (out of scope in the spec) |
| IX. Spec-driven reporting | **PASS** — the image ends up as authored artifacts (report spec/definition), never as an opaque instruction |

**Gate: PASS.** No amendment needed.

## Project Structure

### Documentation (this feature)

```text
specs/024-image-brief-chat/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/attachments.md        # API + provider payload contract
└── tasks.md                        # /speckit-tasks output
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0020_assistant_attachments.py   # new table + the notice column
├── app/
│   ├── config.py                    # ATTACHMENTS_DIR, AI_VISION, limits
│   ├── models.py                    # AssistantAttachment
│   ├── ai/__init__.py               # ImagePart + ChatMessage.images (provider-neutral)
│   ├── ai/anthropic_provider.py     # image blocks
│   ├── ai/openai_compatible.py      # image_url data: URLs
│   ├── assistant/service.py         # store, label as untrusted, audit, prompts
│   ├── assistant/attachments.py     # sniff/limits/store/load/delete (new)
│   ├── api/assistant.py             # upload + attachment fetch + send with ids
│   ├── api/schemas.py               # MessageCreate.attachments, AttachmentOut
│   ├── i18n/{es,en}.py              # limits, notice, errors, "not read"
│   └── assistant/guide/             # a topic: "Brief con una imagen" + drift
└── tests/test_assistant_attachments.py, tests/test_ai*.py (mapping), leak test

frontend/src/
├── components/assistant/Composer*.tsx   # attach, preview, remove, notice, vision warning
├── api/assistant.ts                     # uploadAttachment + send(payload with ids)
└── i18n/{es,en}.ts                      # new strings
frontend/tests/unit/assistant-attachments.test.tsx, no-literals/labels drift
```

**Structure decision**: the attachment is a first-class part of the assistant domain (table, service,
API) and a product-owned file on disk; the project folder, the workspace and the report engine are
deliberately untouched, so nothing of the brief can leak into what a customer exports.

## Phase 0: Outline & Research

`research.md` (R1–R8) fixes the transport, capability detection, storage and lifetime, limits,
the notice, the untrusted-input treatment, and the leak rules, with the alternatives considered.

## Phase 1: Design & Contracts

- [data-model.md](./data-model.md) — the attachment entity, its lifetime and the notice column.
- [contracts/attachments.md](./contracts/attachments.md) — endpoints, payloads, provider mapping,
  limits and error codes.
- [quickstart.md](./quickstart.md) — validation scenarios end to end.

## Risks

- **A silent privacy hole** is the one unacceptable outcome: every path that leaves the installation
  is gated by the notice and covered by the leak test (SC-003), and the guide explains what an image
  brief is for.
- **Prompt injection through a picture** (text inside the image trying to issue instructions): images
  are labelled untrusted brief data exactly like project documents and tool results in 021, and the
  scope gate and command guards are unchanged.
- **Provider drift** (a model that claims vision and fails, or a local model that ignores parts):
  capability is explicit (`AI_VISION`), the answer is always explicit about whether the picture was
  read, and a failed read is a clear message, never a fabricated report.
- **Base64 in the prompt budget**: images consume tokens; the composer shows the size and the limits,
  and the assistant\'s budget accounting counts them like any other input.
- **Storage growth**: files follow the conversation and are deleted with it; the plan records the
  directory in the backup/restore documentation so a restored installation keeps its history
  consistent (contracts, not code).
