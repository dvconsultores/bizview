# Contract: agent tools per mode and contract

**Owner**: `backend/app/assistant/tools.py` (`TOOL_SPECS`, `offered_tool_specs`, `run_tool`,
`mode_gate`), with `assistant/service.py` for the stage transition. Consumers: the provider loop and
the transcript renderer (`CommandRunChip.tsx`).

## 1. Matrix (what the model is offered / what the gate accepts)

| Tool | `ask` | `edit` | `auto` + live contract |
|---|---|---|---|
| `list_sources`, `describe_source`, `profile_source` | yes (source allow-list) | yes | yes (source allow-list) |
| `get_workspace`, `get_authoring_guide`, `get_app_guide`, `get_project_overview` | yes | yes | yes |
| `read_draft` | yes | yes | yes |
| `check_query` | only without `path` | yes | yes |
| `update_notes` | no | yes | yes |
| `propose_draft`, `edit_draft` | no | yes | yes |
| `set_current_spec` | no | yes (inspection set) | yes |
| `run_command` | no | no (the user types the command) | yes, `stages` includes `draft` |
| `run_preview` | no | only inside a command that lists it | yes, `stages` includes `preview` |
| `apply_draft` | no | no | yes, `stages` includes `apply` |
| `finish_command`, `suggest_command` | no | yes | yes |

`ask` = `ASK_TOOLS` (the read set). `edit` = today's `guard.allowed_tools(definition)` (unchanged
behaviour, so regression tests of 014/017/021 keep passing). `auto` = `edit` + the four Auto tools,
clipped by the contract.

Refusals are tool results (not exceptions to the user): the model receives the code and the
localized message, the transcript shows a chip, and the run continues (it may adapt) or stops with
`blocked:<reason>`.

## 2. New tool specs

### `run_command`

```json
{
  "name": "run_command",
  "description": "Avanza el run a una etapa de Spec Kit sobre una spec del proyecto (el mismo ejecutor que /speckit-…). Cierra la etapa anterior y abre la nueva; luego sigue trabajando con las herramientas de esa etapa. Nunca pidas al usuario ejecutar el comando.",
  "parameters": {
    "type": "object",
    "properties": {
      "spec": { "type": ["string", "null"], "description": "Carpeta NNN-nombre; nulo solo cuando la etapa la crea (/speckit-specify)." },
      "command": { "type": "string", "enum": ["speckit-specify", "speckit-clarify", "speckit-plan", "speckit-tasks", "speckit-implement", "speckit-converge"] },
      "arguments": { "type": "string", "description": "Resto de argumentos del comando." }
    },
    "required": ["command"]
  }
}
```

Side effects, in order: close the running `assistant_command_run` (`completed` with its `files`, or
`interrupted`); resolve the target spec with `commands/resolve.py` (argument → number → title →
`current_spec`) and set `session.current_spec`; `commands.runs.create(...)` for the new stage; set
`session.command_run` and `assistant_auto_run.stage`; return the stage context (command prompt,
tool set, spec status) as the tool result. Audited by the command run row itself; the run's
`stage` is also visible in the status bar.

Refusals: `assistant_contract_stage_not_allowed` (stage outside the contract),
`blocked:spec_not_found` when the resolved spec does not exist and the command needs one.

### `apply_draft`

```json
{
  "name": "apply_draft",
  "description": "Aplica el proyecto de la conversación como una versión nueva del workspace (la misma validación, bloqueo y auditoría que el botón Aplicar). Requiere contrato vigente con la etapa `apply` y aplica como máximo `limits.applies` veces.",
  "parameters": { "type": "object", "properties": {}, "required": [] }
}
```

Equivalent to `POST /sessions/{id}/apply` without the per-call step-up (authorised by the contract,
014 FR-006 as amended) and with `source="chat:<id>:auto"`. Refusals: `assistant_contract_required`,
`assistant_contract_stage_not_allowed`, `assistant_contract_limit_reached` (`limit:applies`),
plus the unchanged readiness/revalidation errors (`not_ready`, `query_check_failed`) which the agent
must fix and retry.

## 3. Source allow-list

Checked in `_dispatch` before the tool runs, for `list_sources` (filters the list),
`describe_source` / `profile_source` (name, and `table`/`path` when given) and `check_query`
(`source`). A name outside the contract returns `assistant_contract_source_not_allowed` with the
allowed names; the refusal text never includes table data (VIII).

The contract can only *narrow*: an empty `sources` list means "no extra restriction", never "all
sources bypassing 015 FR-007" — personal-data columns stay excluded.

## 4. Counters and stops

| Event | Effect |
|---|---|
| `run_command` | no counter; the stage switch is recorded in `assistant_command_run` |
| `run_preview` | runs inline (`preview.run_draft_preview`, `time_limit_s=120`), bumps `session.stats['previews']` and `assistant_auto_run.previews += 1`; refused when `> limits.previews` |
| `apply_draft` | `assistant_auto_run.applies += 1`; refused when `> limits.applies` |
| any round | tokens charged to `session.tokens_used`; stop when `> limits.tokens` |
| any tool | stop (`limit:wall_clock`) when `now - confirmed_at > limits.wall_clock_seconds` |
| `stop()` / mode down | `_ClaimLost` at the next `_commit_round`; no apply starts afterwards |

`_finish_auto_run(...)` writes `status`, `stop_reason`, `summary`, `ended_at` and the audit entry in
one transaction; the draft, `working_state` and `command_run` rows stay as they were (SC-002).

## 5. What the model must not do (checked, not just asked)

`_auto_blocked_reason(final_message, contract)` inspects the final assistant message of an Auto run.
If it tells the human to select a spec, run a command or press "Aplicar" — and the contract still
had stages left — the run is stored as `blocked:<reason>` and the message is replaced by the summary.
Fixtures assert this on every Auto run (SC-007).
