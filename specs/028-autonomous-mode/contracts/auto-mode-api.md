# Contract: mode and run-contract API

**Owner**: `backend/app/api/assistant.py` (+ `api/schemas.py`). Consumers: `frontend/src/api/client.ts`,
`frontend/src/components/assistant/`.

All routes keep the existing rules of `api/assistant.py`: prefix `/api/assistant`, super user only
(`require_superuser`), session ownership (`_own_session`), the global CSRF middleware, JSON errors in
the usual `{error: {code, message, fields?}}` shape with Spanish/English messages from `M()`.

## 1. `POST /sessions/{id}/mode`

```json
{ "mode": "ask" }
```

- `200` → `{ "session": <session payload> }` (the payload now carries `mode`, `contract`,
  `contract_status`, `stage`).
- `422 mode_invalid` — not one of `ask` / `edit` / `auto`.
- `409 assistant_archived` / `409 read_only` — as today.
- Switching **to** `auto` stores the intent only; the response says
  `"contract_status": "none"` until §2 is confirmed.
- Switching **down** (`auto` → `edit`, `edit` → `ask`) while a run is in flight calls the existing
  `service.stop()` first; the response is `contract_status: "stopped"`, `stop_reason: "stopped:mode"`.
- Audited as `assistant_mode_changed` (from, to, session id).

## 2. `POST /sessions/{id}/contract`

```json
{
  "contract": { "...": "run-contract.schema.json" },
  "password": "…",
  "code": "123456",
  "profile_id": 3
}
```

`code` is required when `security.profile.mfa_required_for(role)` is true (profile `internet` and the
actor is an administrator) and ignored otherwise.

- `201` → `{ "run": <auto run payload>, "session": <session payload> }`; the run is `confirmed`
  and `session.mode = "auto"`. The conversation's live contract is its newest run row.
- `422 contract_invalid` — schema violation; `fields` maps each invalid key to a message.
- `401 step_up_failed` — wrong password or TOTP; throttled and audited (`reauth_failed`) exactly as
  `/api/auth/reauth`, and a lockout applies.
- `409 contract_active` — this conversation already has a `confirmed`/`running` contract.
- `409 not_open` — the conversation is archived.
- `202` is **not** used: confirming a contract never starts a run by itself; the next user message
  does (`POST /sessions/{id}/messages`).
- Audited as `assistant_contract_confirmed` (run id, stages, limits).

`sources` entries name sources the actor can already use; an unknown source is `422
contract_invalid` (`fields.sources`).

## 3. `POST /sessions/{id}/contract/cancel`

No body. Closes the dialog intent: `204`. Writes no row, changes no mode (spec, "Rules of the
selector": cancelling leaves the mode where it was).

## 4. `GET` `POST` `PATCH` `DELETE` `/run-profiles[/{id}]`

```json
{ "name": "Reporte sobre ERP, hasta aplicar", "contract": { "...": "without goal" } }
```

- `GET` → `{ "items": [{id, name, contract, updated_at}] }`.
- `POST` `201`, `PATCH` `200`, `DELETE` `204` (soft delete).
- `422 name_taken` / `422 profile_invalid`.
- Audited as `assistant_profile_created` / `_edited` / `_deleted`.
- A profile only prefills the dialog: §2 still requires the password (+ TOTP) for every run.

## 5. Session payload additions

`GET /sessions`, `GET /sessions/{id}`, and every response that returns a session gain:

```json
{
  "mode": "auto",
  "contract": {
    "id": 41,
    "status": "running",
    "stop_reason": null,
    "stage": "implement",
    "limits": { "tokens": 400000, "previews": 5, "applies": 1, "wall_clock_seconds": 1800 },
    "used": { "tokens": 128400, "previews": 1, "applies": 0, "elapsed_seconds": 412 },
    "stages": ["draft", "preview", "apply"],
    "sources": [], "modify_existing": false, "auto_rollback": true, "visible_to": []
  },
  "contract_status": "running"
}
```

`contract` is `null` when the conversation never had a contract. `contract_status` is the pill state:
`none` | `confirmed` | `running` | `applied` | `stopped` | `failed` | `spent`.

## 6. Errors the UI must render as chips

| Code | Where | Message (es / en) |
|---|---|---|
| `assistant_mode_ask_refused` | tool result in `ask` | "Modo Preguntar: cambia a Editar para escribir" / "Ask mode: switch to Edit to write" |
| `assistant_contract_required` | `run_preview`/`apply_draft`/`run_command` without a live contract | "Este run no tiene contrato vigente" / "This run has no live contract" |
| `assistant_contract_source_not_allowed` | source tool outside `sources` | "El contrato no permite esa fuente" / "The contract does not allow that source" |
| `assistant_contract_stage_not_allowed` | tool outside `stages` | "El contrato no permite esa etapa" / "The contract does not allow that stage" |
| `assistant_contract_limit_reached` | any limit | "Se alcanzó el límite del contrato: {limit}" / "Contract limit reached: {limit}" |
