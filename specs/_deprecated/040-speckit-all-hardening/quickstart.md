# Quickstart: `/speckit-all` hardening (040)

## 1. The plan loops back (A)

In a project conversation, in **Auto**:

```text
/speckit-all 001-mercado-cripto
```

* When `converge` adds tasks, the next chip is
  `Auto · /speckit-implement 001-mercado-cripto · ronda 2` and after it `converge` runs again
  (at most 2 convergence rounds), then `verify`.
* When `verify` fails, the next chip is `implement` and then `verify` again (at most 3 cycles).
* While `tasks.md` has unticked tasks, `verify` never starts: the plan implements first.

The run report lists the tokens per stage and stops with a named reason when it must.

## 2. Honest fixes (B)

Open the project's problems panel with a spec whose `tasks.md` still has `- [ ]` lines:

* The problem no longer offers a fix that ticks the tasks; its advice is
  `/speckit-implement <spec> --only T025,T026`.
* The chat offers the **Implementar tareas pendientes** chip with those ids already written.
* Ticking a task from any other command fails with
  «Las tareas se marcan al implementarlas».

## 3. Bounded context and tools (C, D)

* A run compresses the conversation at most once per run; if it needs more, it stops with
  `blocked:context_exhausted` and `/speckit-all <spec>` resumes at the same stage.
* Every stage is sent only its tool group (≤ 25 tools) and `get_app_guide(topic)` for the guide.
* `AI_STAGE_TOKEN_BUDGET` (default 600 000) stops a stage with `blocked:stage_budget`.
* «Detalles técnicos» shows the tool count and the prompt size of every round.

## 4. The two data defects (E)

1. In `/speckit-implement`, `check_query` on `integrations/<id>/requests/<file>.yaml` returns the
   response's actual `keys` and, for every epoch/ISO value, its `timestamp_units`.
2. Writing `fields` without that check is refused; a column the response does not have is refused
   naming the real keys.
3. A wrong unit is a content fix: set `timestamp_units.<col>` to the reported unit and re-check.

## 5. Tests

```bash
cd backend && .venv/bin/python -m pytest tests/test_assistant_speckit_all_rounds.py \
  tests/test_assistant_stage_bounds.py tests/test_assistant_request_shape.py \
  tests/test_assistant_loop_state_conflict.py -q
cd cli && .venv/bin/python -m pytest tests/test_fix_policy.py -q
```
