# Contract: `/speckit-all` (039)

What the command accepts, what it may write, when it stops, and what it leaves behind. Product
code enforces every clause in bold; the prompt restates them for the model.

## 1. Invocation

```text
/speckit-all <request | spec id> [--until <stage>] [--force]
```

| Part | Rules |
|---|---|
| `<request \| spec id>` | Free text (≤ 4000 chars, `MAX_ARGS`). Resolved by `resolve.resolve` in the 029 order: explicit folder → `NNN` → title/slug → `current_spec`. Free text that names no spec is a **brief**: stage 1 creates the spec(s). |
| `--until <stage>` | One of `specify · clarify · plan · tasks · analyze · implement · converge · verify` (case-insensitive). Anything else is refused with `422 commands.until_invalid`, listing the stages. The stage named is **included**. |
| `--force` | Stripped by `resolve.strip_force`; bypasses the completion table (`data-model.md` §4) and the `_idempotence` guard of every stage. |

Preconditions

- **Mode `auto` and a live contract** (028). In `ask`/`edit` the reply is
  `assistant.mode.offer_auto` ("Pasar a Auto") plus a suggestion chip; **no run is created**.
- Auto with no live contract opens one through `ensure_auto_contract` (selecting Auto is the
  authorisation; `internet` installations still require the step-up they already require).
- The conversation's project only (037). A path outside it is refused before any write.

## 2. Stage plan

```text
specify → clarify → plan → tasks → analyze → implement → converge → verify
   1         2        3       4        5          6          7         8
```

- Fixed list, from `pipeline.STAGES`; no project-specific stages (spec Assumptions).
- Two specs run sequentially: every integration spec (`kind: integracion`) through stage 8, then
  every report spec. `session.current_spec` follows with `set_current_spec`.
- A stage is opened **only** through `run_command(spec, command)` (`speckit-verify` included), so
  it is an audited `assistant_command_run` with 021's scope and 028's ceiling.

**Refusals (one line, no provider retry)**

| Condition | Code |
|---|---|
| `run_command` names a stage that is not `cursor` | `pipeline.order` |
| `run_command` names a stage after `--until` | `pipeline.until` |
| `run_command speckit-all` inside a pipeline | `pipeline.no_restart` |
| a stage is opened after the contract lost `draft` | `assistant.contract.stage_not_allowed` |
| a write outside the current stage's scope | `commands.path_not_allowed` (021) |
| a write to another spec's folder | `commands.path_other_spec` (029) |

## 3. Writes

| Rule | Path | Shape |
|---|---|---|
| `run_report` | `specs/<spec>/run-report.md` | full write, product-generated (`data-model.md` §6) |
| `decisions_append` | `specs/<spec>/spec.md` | additions inside `## Decisiones tomadas (modo autónomo)` only |

`speckit-all`'s own run writes nothing else. Every other write belongs to the stage run that is
open, under that stage's existing rule.

## 4. Autonomy contract (the block both toolchains ship)

Between `<!-- bizview:contrato-autonomo -->` and `<!-- /bizview:contrato-autonomo -->` in
`agent_commands/es/speckit-all.md`, `agent_commands/en/speckit-all.md` and
`.claude/skills/speckit-all/SKILL.md`. The wording is per locale (a Spanish prompt cannot be
byte-identical to an English one), so what `test_speckit_all_contract.py` asserts is what must
agree: the markers once per file, the **same six rules**, the **same eight stages in the same
order** (that line is byte-identical in all four files, this contract included) and the decision
heading the guard reads. The block below is the Spanish one:

```markdown
<!-- bizview:contrato-autonomo -->
- No preguntas: ninguna etapa termina pidiendo al humano una decisión ni una confirmación. Una
  duda se resuelve con esta precedencia — constitución, el texto de la spec, otras specs del
  proyecto, los valores por defecto del paquete de autoría — y se registra.
- Toda decisión se escribe como `- [etapa] decisión — porqué` bajo
  «## Decisiones tomadas (modo autónomo)» en `specs/<spec>/spec.md`, y se copia al run report.
- El orden de etapas es fijo y se avanza solo con `run_command`; una etapa no se salta ni se repite.
- Un artefacto completado no se vuelve a escribir: la misma etapa dos veces no produce diff salvo
  que cambien sus entradas.
- Se detiene solo por: un conflicto de constitución que exige enmienda, la verificación que sigue
  fallando tras 3 ciclos de arreglo, una acción que el contrato no permite, o una fuente o
  credencial que falta. Cualquier otra cosa es una decisión, no una parada.
- Al terminar escribe `run-report.md` y, en «Pendiente para el humano», solo lo que de verdad lo
  necesita (Aplicar si el contrato no lo permite). Nunca instrucciones de cómo seguir.
<!-- /bizview:contrato-autonomo -->
```

## 5. Stop conditions (enforced in code)

| # | Condition | Detected by | `stop_reason` |
|---|---|---|---|
| 1 | contract limit reached (tokens/previews/applies/wall clock) | `auto.limit_refusal` | `limit:<name>` |
| 2 | "Detener" or mode switched down | `service.stop` / `auto.mode_of` | `stopped:user` |
| 3 | provider credit / key / model error | 035 map in `_provider_error` | `provider:<code>` |
| 4 | transient provider failure, after one retry | 035 rules | `provider:<code>` |
| 5 | verify still failing after 3 cycles | `pipeline.state.verify_cycles` | `verify:failed` |
| 6 | constitution conflict needing an amendment | `guard` refusal | `constitution:conflict` |
| 7 | the brief needs a source that is not enabled | specify stage result (014/037) | `source:missing` |
| 8 | an action the contract does not allow | `auto.mode_gate` | `contract:<stage>` |

Everything else is a decision (§4). A stop keeps every file already written and leaves
`cursor` where it was, so `/speckit-all <id>` resumes there.

## 6. Conversation surface

`GET /assistant/sessions/<id>` → `command_runs[]` (`_run_json`), one entry per stage run, plus

```json
"pipeline": {"id": 128, "cursor": 4, "total": 8, "stage": "analyze",
             "until": null, "spec": "002-ventas-facturacion", "spec_index": 0}
```

| Surface | Reads | Renders |
|---|---|---|
| chip per stage (`CommandRunChip`) | `command`, `spec`, `status`, `pipeline.cursor/total` | `Auto · /speckit-plan 002-ventas-facturacion ✔ · 3/8` |
| status bar (`ModeSelector`) | `pipeline` | `Etapa 4/8 · analyze` |
| report card (`RunReportCard`) | `tool_payload.run_report` | the §6 table of `data-model.md`, collapsed |

`next_step` stays 021's: a `speckit-all` run adds no `_NEXT_AFTER` entry, because the report — not
another command — is the next thing. When the pipeline stopped before `implement`, the run's own
reply carries a `/speckit-implement <spec>` suggestion instead.

## 7. Repo toolchain command

`.claude/skills/speckit-all/SKILL.md`

```text
/speckit.all <request | spec id> [--until <stage>] [--force]
```

Same stages, same §4 block, same §5 stop conditions, with repo tools:

| Stage | Repo tool |
|---|---|
| specify … converge | the matching `/speckit-*` skill in `.claude/skills/` (`.specify/scripts/bash/setup-*.sh` for paths) |
| verify | `pytest` (targeted), `npm run build`, `npx vitest run`, plus the feature's own quickstart checks |
| report | `run-report.md` written by hand at the end, same sections as `data-model.md` §6 |

`--until tasks` is the documented dry run (in-app guide 033 and the skill's first paragraph).
