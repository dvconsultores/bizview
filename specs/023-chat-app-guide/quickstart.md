# Quickstart & Validation: Chat app guide

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Prerequisites

- A development checkout with the backend (`backend/`, `uv sync`) and frontend (`frontend/`,
  `npm ci`) installed.
- For the DB tests: `DATABASE_URL_BI` set; tests run in `app_test_*` schemas only.
- For the live eval only: an AI provider key (`AI_LIVE_API_KEY`). Nothing else contacts a live
  provider.
- For the usability check: an installation (or `python starter.py`) with AI enabled, one data
  source that passes **Probar conexión**, and an existing BI table (for example `bi_ventas`).

## Drift tests (run on every change to the guide or the UI)

The guide must cover every route, Administración tile and command, and its bold labels must be
the labels the catalogues show (SC-001).

```bash
cd backend  && uv run pytest tests/test_guide.py      # index, bodies, labels, links, index size
cd frontend && npm test -- guide-drift                # routes in App.tsx, tiles, role links
```

A failure names the topic, the file and the fix (add a topic, rename a bold label, or list a
non-catalogue term in `backend/app/assistant/guide/labels-allow.txt`).

## Behaviour tests (fake provider, no live AI)

```bash
cd backend && uv run pytest tests/test_guide_api.py tests/test_guide_answers.py \
  tests/test_project_overview.py
cd frontend && npm test -- help-page chat-links
```

They cover the guide API by role and language, every topic answered from the guide in es and en,
`/ayuda` with no provider call (SC-003), the project overview (stages, next command, no personal
data) and the Ayuda page.

## Opt-in live eval (SC-002)

Contacts the live provider and costs tokens. 50 synthetic questions
(`backend/tests/live/guide_eval.yaml`, 25 es + 25 en); scoring is deterministic (topic fetched,
expected words, valid `app:` links). Pass: ≥ 45/50.

```bash
cd backend
AI_LIVE_TESTS=1 AI_LIVE_API_KEY=... [AI_LIVE_BASE_URL=https://api.deepseek.com] \
  [AI_LIVE_MODEL=deepseek-chat] uv run pytest tests/live/test_guide_eval.py -s
```

The test prints one row per question (`OK`/`FAIL`, tokens, failed checks) and the total. If a
local model scores below 90%, record the failing rows; the plan's follow-up is a deterministic
"Tema probable" hint, only if measured.

## Manual usability check (SC-004)

Goal: a first-time super user completes **"crear un reporte directo sobre una tabla existente"**
guided only by the chat, in under 10 minutes.

1. **Participant**: someone with a super user account who has never used BizView's projects or
   the chat. Do not explain the app beforehand.
2. **Setup**: a new, empty project in **Proyectos**; the BI table exists and is not yet in any
   report.
3. **Task given**: "Crea un reporte directo sobre la tabla `bi_ventas` usando solo el chat para
   saber qué hacer." The participant may type `/ayuda` or ask questions; the observer does not
   help.
4. **Timer**: start when the participant opens the project; stop when the report opens from
   **Tableros** after **Aplicar proyecto**.
5. **Record**:
   - total time and pass (< 10 min) / fail;
   - the questions asked and the guide topics or `/ayuda` replies used;
   - each place the participant got stuck, and for how long;
   - any wrong, missing or broken answer or link (topic id and language);
   - the language used (es or en).
6. **After**: file each problem as a guide fix (topic body or `index.yaml`) and re-run the drift
   tests.
