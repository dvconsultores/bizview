# Phase 1 — Data model: autonomous mode

New migration: `backend/alembic/versions/0024_autonomous_mode.py` (down_revision
`0023_command_spec_resolution`). Product DB is PostgreSQL; column idioms follow `app/models.py`
(`BigInteger` identity PKs, `Text` for enums checked with `_in(...)`, `JSONB`, `timestamptz`
`server_default=func.now()`).

## 1. `assistant_session` (changed)

Existing table (014/017/020/021/023/024). One column added:

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `mode` | `Text` | `NOT NULL`, `DEFAULT 'edit'`, `CHECK mode IN ('ask','edit','auto')` | FR-000; per conversation |

The conversation's current contract is its **newest `assistant_auto_run` row** (`ix_auto_run_session`
serves the lookup). There is deliberately no `assistant_session.auto_run_id`: the FK back to the run
while the run points at the session is a table cycle, which makes Alembic's `compare_metadata` skip
every foreign key of both tables (it warns and cannot sort them).

Derived state (not stored): `mode='auto'` **and** the newest run's `status IN ('confirmed','running')`
= a live contract; any other combination with `mode='auto'` = contracted mode, contract spent
(US2/AC2, clarification 1).

## 2. `assistant_auto_run` (new) — the run contract and its outcome

| Field | Type | Rules |
|---|---|---|
| `id` | `BigInteger` identity PK | |
| `session_id` | `BigInteger` `NOT NULL` FK `assistant_session(id)` `ON DELETE CASCADE` | |
| `project_id` | `BigInteger` `NOT NULL` FK `project(id)` `ON DELETE CASCADE` | the project the run edits |
| `contract` | `JSONB` `NOT NULL` | see §3; validated by `RunContract` (pydantic) and re-checked in the gate |
| `status` | `Text` `NOT NULL` `DEFAULT 'confirmed'` | `confirmed` \| `running` \| `applied` \| `stopped` \| `failed` |
| `stop_reason` | `Text` `NULL`, `char_length ≤ 120` | `limit:tokens`, `limit:previews`, `limit:applies`, `limit:wall_clock`, `stopped:user`, `stopped:mode`, `revoked:role`, `blocked:<reason>`, `error:<code>` |
| `stage` | `Text` `NULL` | `discover` \| `specify` \| `clarify` \| `plan` \| `tasks` \| `implement` \| `converge` \| `preview` \| `apply` |
| `previews` | `Integer` `NOT NULL` `DEFAULT 0`, `CHECK ≥ 0` | FR-003 counter |
| `applies` | `Integer` `NOT NULL` `DEFAULT 0`, `CHECK ≥ 0` | FR-003 counter |
| `tokens` | `Integer` `NOT NULL` `DEFAULT 0`, `CHECK ≥ 0` | charged by `_count_usage` |
| `version_id` | `BigInteger` `NULL` FK `workspace_version(id)` | set by the apply |
| `summary` | `JSONB` `NULL` | FR-004/US1 AC4: version, integration and report ids, schedule, decisions taken, preview row counts, tokens |
| `watch_integration` | `Text` `NULL` | comma-separated integration ids watched after apply (FR-008) |
| `watch_state` | `Text` `NULL` | `pending` \| `ok` \| `failed` \| `rolled_back` |
| `confirmed_by` | `BigInteger` `NOT NULL` FK `app_user(id)` | the single step-up |
| `confirmed_at` | `timestamptz` `NOT NULL` `DEFAULT now()` | wall-clock origin |
| `confirmed_ip` | `INET` `NULL` | audit parity with the rest of the admin actions |
| `started_at` | `timestamptz` `NOT NULL` `DEFAULT now()` | |
| `ended_at` | `timestamptz` `NULL` | |

Indexes: `ix_auto_run_session (session_id, started_at DESC)`,
`ix_auto_run_watch (watch_state) WHERE watch_state = 'pending'`.

**Lifecycle**

```text
confirmed ──first tool call──> running ──apply ok──> applied
     │                            │
     │                            ├── limit:* / stopped:user / stopped:mode / revoked:role
     │                            ├── blocked:<reason>
     │                            └── error:<code>
     └── cancel (no row is written)      → stopped | failed
```

`applied` may still move to `watch_state='failed'` (FR-008) and to `rolled_back` when
`auto_rollback` restores the previous version; the run `status` itself stays `applied` because a
version *was* applied, and the summary records the rollback.

**Invariants**

- At most one run per session with `status IN ('confirmed','running')`:
  `ux_auto_run_active (session_id) UNIQUE WHERE status IN ('confirmed','running')`.
- `applies <= contract.limits.applies`, `previews <= contract.limits.previews` (checked in code; the
  CHECK above is the backstop).
- `status='applied'` implies `version_id IS NOT NULL`.
- A contract is never mutated after `confirmed`: limits changes need a new row.

## 3. `contract` JSONB shape

Validated by `backend/app/assistant/auto.py` (`RunContract`, pydantic v2) and described in
`contracts/run-contract.schema.json`:

| Key | Type | Rule |
|---|---|---|
| `goal` | string ≤ 2000 | the user's request (FR-001) |
| `sources` | `[{name, tables[]?}]` | empty = no restriction; a listed name restricts every source tool (US3/AC2) |
| `stages` | array ⊆ `["draft","preview","apply"]`, non-empty | "hasta vista previa" = `["draft","preview"]` (US3/AC1) |
| `limits.tokens` | int 10 000…`AI_CHAT_BUDGET_MAX` | |
| `limits.previews` | int 0…20 | |
| `limits.applies` | int 0…5 | default 1 |
| `limits.wall_clock_seconds` | int 60…7200 | default 1800 |
| `modify_existing` | bool, default false | US4/AC2 |
| `auto_rollback` | bool, default true | FR-008 |
| `visible_to` | array ⊆ `("admin","user")` (the `ROLES` constant), default `[]` | FR-009; `[]` = no grants = staff only; `user` grants access to the active `user`-role accounts; `admin` is accepted and changes nothing (`dashboards.visible_for` shows every non-hidden dashboard to admins) |
| `profile_id` | int \| null | provenance when a profile was used (US5) |

## 4. `assistant_run_profile` (new) — US5

| Field | Type | Rules |
|---|---|---|
| `id` | `BigInteger` identity PK | |
| `name` | `Text` `NOT NULL`, unique, `1…60` chars | shown in the dialog |
| `contract` | `JSONB` `NOT NULL` | same shape as §3 minus `goal` (the goal is always the request) |
| `created_by` | `BigInteger` FK `app_user(id)` | |
| `created_at` / `updated_at` | `timestamptz` | |
| `deleted_at` | `timestamptz NULL` | soft delete, audited |

## 5. Tables read, not changed

| Table | Use |
|---|---|
| `assistant_command_run` | each stage of an Auto run is a row here (`command`, `spec`, `resolved_from`, `status`, `files`); `run_command` creates the next one |
| `assistant_message` | transcript: contract line, stage chips, refusal chips, run summary (FR-006, FR-010) |
| `workspace_version` | the applied version (`assistant_auto_run.version_id`) |
| `integration_run` | the first scheduled run after apply (`status`, `checks`, `version_id`) — FR-008 |
| `dashboard_access` | `visible_to` grants (FR-009) |
| `audit_event` | new kinds listed in the plan §Data |

## 6. Audit kinds added

`assistant_mode_changed`, `assistant_contract_confirmed`, `assistant_run_started`,
`assistant_run_applied`, `assistant_run_stopped`, `assistant_run_rolled_back`,
`assistant_profile_created`, `assistant_profile_edited`, `assistant_profile_deleted` — the
`audit_event.kind` CHECK is rebuilt in the same migration (drop + add constraint, the 0022/0023
idiom).
