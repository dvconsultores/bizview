# Quickstart & validation: An image brief in the report chat

**Feature**: [spec.md](./spec.md) · [plan.md](./plan.md) · [contracts](./contracts/attachments.md)

## Run

```bash
cd backend && uv run pytest tests/test_assistant_attachments.py tests/test_ai.py tests/test_assistant_api.py
cd frontend && npm test -- assistant-attachments
```

Full flow with the running app (`python starter.py`) and a real provider
(`AI_PROVIDER=anthropic`, `AI_VISION=true`): sign in, create a project, attach a report mockup
(PNG, ≤ 5 MB) in the composer, send "quiero un reporte así" and follow the assistant through
`/speckit-specify` → `/speckit-plan` → `/speckit-tasks`.

## Validation scenarios

| # | Scenario | Expected | Covers |
|---|---|---|---|
| 1 | Attach a PNG mockup with one sentence | The answer states what it read (views, dimensions, metrics, layout) and the spec files are written through the command in use | US1, FR-001, FR-002 |
| 2 | Correct the brief in words ("ranking by product, not branch") | Artifacts change; the image stays in the conversation context | US1 AS2 |
| 3 | Attach a photo / a logo | The assistant says it cannot read a report brief from it and asks what is needed; no invented report | US1 AS3, R7 |
| 4 | `AI_VISION=false` (text-only model) | The composer warns before sending; sending keeps the text and the answer says the image was not read; **no** artifact claims to follow it | US2, FR-004, SC-002 |
| 5 | Send an image while vision is off (API directly) | `409 vision_unavailable`, message not created, nothing stored against it | FR-004, contracts §2 |
| 6 | Attach 6 MB / an SVG / a `.png` that is really a PDF | `413` / `415` with the reason in Spanish and English | FR-003, R5 |
| 7 | First image of a person | One-time notice before it leaves the installation; cancel → nothing sent | US3, FR-006, SC-006 |
| 8 | Read the audit and the security overview | The attachment appears (session, count, bytes, short hash, provider, model); no content, no original name | FR-007, FR-014, SC-003 |
| 9 | `GET /api/assistant/attachments/{id}` as another user / through a share link | `404` in both cases | FR-009 |
| 10 | Delete the image from the message; delete the conversation | Message text stays and the project is untouched; after deleting the conversation neither row nor file remains | FR-010, FR-008, SC-004 |
| 11 | Export the project zip / mirror the workspace Git | No attachment anywhere in either | SC-004 |
| 12 | Image-only message; caption that contradicts the picture | A question, and the conflict is surfaced — never a refusal and never a silent choice | FR-005, R7 |
| 13 | Text-only message, `/speckit-*` commands, tool payloads | Byte-for-byte today\'s behaviour (the regression suites pass unchanged) | FR-011, SC-005 |
| 14 | Opt-in live evaluation with 10 reference mockups | ≥ 8 produce a matching report spec in ≤ 3 rounds | SC-001 |
