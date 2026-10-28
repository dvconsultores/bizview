# DIAGNOSIS — why `/speckit-all` cannot finish `001-mercado-cripto` (041-speckit-all-root-cause)

Date: 2026-10-28. Method: code reading end to end first, then evidence, then failing tests.
All file references are to the current `main` (f7feae3).

## 0. Evidence situation

- `tmp/evidence/bizview-chats.json` (from ~/Downloads, exported 2026-10-19) is a **different
  conversation** (project `artemisa`, spec `001-integracion-facturas`). It contains none of the
  failure signatures (no guard message, no `FileChanged`, no "sin cambios desde la lectura
  anterior"). It is NOT the primary record the prompt assumed.
- `tmp/evidence/backend.log` (docker logs dashboard-backend-1, 676 862 lines): no `FileChanged`,
  no `IntegrityError` — consistent with the code: `FileChanged` is converted to a chat message by
  `_post_error` and `log.exception` goes to the worker thread's logger inside the container that
  actually served the conversation. The local container's recent log is dominated by DB
  connectivity errors to 190.120.249.37:5432.
- `tmp/evidence/coinmarketcap-project/` (zip of 2026-10-24): the project **before** the stuck
  convergence round — only `requests/listings.yaml` exists; `global-metrics.yaml`,
  `fear-greed.yaml` and tasks T025–T028 were created later, in the conversation's draft.
- Conclusion: the production transcript quoted in the task brief is the behavioural record; every
  cause below is proven **in the code** and will be reproduced by scripted FakeProvider tests.

## 1. What each piece does (method step 1)

- `app/assistant/service.py` — one worker thread per turn (`run_turn` → `_attempt_turn` →
  `_turn`). The round loop (service.py:2452) runs until no tool calls, a stage budget, a
  repeated identical failing call, or `max_rounds` — which is **None in Auto mode** (owner,
  2026-10-27: "never because a round counter ran out"). Any exception that escapes `_turn`
  reaches `_post_error`, which writes «Ocurrió un error inesperado; lo hecho hasta la última
  ronda se guardó. (TypeName)» (`_error_text`, service.py:2166).
- `app/assistant/tools.py` — tool dispatch with run-scope guards and memoisation
  (`run_tool`, tools.py:922). All agent writes go through `_write_ops` (tools.py:1879), which
  calls `_requests_checked` (the `fields` guard, tools.py:1849), then `fs.apply_ops`, catching
  `fs.FileChanged` into a recoverable ToolError.
- `app/assistant/origin.py` — `check_query` handles SQL files, request YAMLs **and** direct
  reports (one tool for all three; there is no `check_request` tool anywhere in the repo).
  `run_check` (origin.py:1046) checks the **current draft content** and stores
  `session.query_checks[path] = {sha256, ok, columns, error, at}` — note: **no `keys`**.
- `app/assistant/commands/pipeline.py` — the `/speckit-all` state machine; `write_report`
  (pipeline.py:738) writes `specs/<spec>/run-report.md` via `fs.apply_ops` **without
  `base_sha256` and without `force`**.
- `app/projects/fs.py` — `apply_ops` is the only write path; `base_check` (fs.py:423) raises
  `FileChanged` whenever the op's `base_sha256` differs from the recorded revision — including
  when the op sends **no base at all** for an existing file (`None != sha`).
- `app/engine/extract.py` — runs REST/Supabase requests; `_records` (extract.py:386) maps
  `fields` with `text_value(json_path(...))`, raw value to text. **`timestamp_units` appears
  nowhere in the engine.**
- `cli/bizview_cli/validate.py` — accepts `timestamp_units` and only refuses a unit that names
  no mapped field (`_timestamp_units`, validate.py:689).
- `app/assistant/history.py` — replayed history keeps full tool data only for the newest
  exchange; older ones travel as their stored one-line summary.
- `app/assistant/preview.py` — maps the Postgres «date/time field value out of range» family to
  `preview.timestamp_unit_mismatch`, whose text tells the agent to set `timestamp_units`.

## 2. Proven causes

### C1 (H1, reshaped) — the `fields` guard is unsatisfiable for exactly the files it exists for

`_requests_checked` (tools.py:1849) refuses any `write` of a request YAML during
`speckit-implement`/`fix` unless `session.query_checks[path]["ok"] is True`.

But `check_query` can only check the **current** draft content (`run_check`, origin.py:1051:
`text = files.get(path)`; there is no way to pass proposed content), and for a request file
`ok = not missing and not missing_columns and not mismatched` (`_shape_result`, origin.py:840)
— i.e. `ok` means "the current file already matches the live response and the dataset".

So when a request file is wrong — the only situation in which the agent must write it —
`check_query` necessarily records `ok: false`, and the guard then refuses the corrected write
with «Antes de escribir `fields` … ejecuta `check_query`». Running `check_query` again cannot
change the outcome (same file, same response); the memo (`_check_query_deps`, tools.py:840)
even replays the cached failure («Usó la estructura ya consultada de "coinmarketcap"»).
**Deadlock.** The agent re-reads («sin cambios desde la lectura anterior» ×5), re-plans, retries
— and because Auto mode has no round cap, the loop runs until `ai_stage_token_budget`.

Two adjacent defects in the same guard (refined after the reproduction run):
- `keys` ARE stored when the agent calls the `check_query` **tool** on a request path — the 040
  wrapper `_check_query` (tools.py:2199–2208) merges `{ok, keys}` into the entry. But the guard
  never reaches them: it blocks on `ok is not True` first (tools.py:1864). And `origin.run_check`
  itself builds a **replacement** entry without `keys` (origin.py:1093–1104), so any other caller
  (`recheck_draft`, the direct-report path) wipes the stored keys.
- The docstring says `check_request`; the real tool is `check_query` (the i18n message is right).

This exactly reproduces the transcript: guard message → memoised check → re-reads → repeat.
T026 (`fields` of `global-metrics.yaml`) and T028 (endpoint discrepancy) are unfinishable.

### C2 (H2, reshaped) — `write_report` writes with no base: the second report always crashes the turn

`pipeline.write_report` (pipeline.py:759) sends `{"op": "write", "path": "specs/<spec>/run-report.md",
"content": …}` with no `base_sha256` and no `force`. `fs.base_check` treats a missing base on an
existing file as a conflict and raises `FileChanged`. The report content embeds tokens and
timestamps, so a second report for the same spec is always different bytes → always a write →
always `FileChanged`.

No caller catches it: `end()` (service.py:2381) → `_report_at_end` → `write_report` → the
exception unwinds through `_turn` to `_post_error` → «Ocurrió un error inesperado; lo hecho
hasta la última ronda se guardó. (FileChanged)».

The first stop of a `/speckit-all` run writes the report fine; **every later stop or finish of
the same spec dies**, which is why the conversation can never end — even the C1 loop's own
budget-stop is killed by C2 on its way out. (The comment in `_report_on_stop`, service.py:1854,
states the intended replace semantics; the write path cannot replace.)

H2's original form (stale `seen` hash from `read_draft`) is ruled out: `edit_draft` computes
`base_sha256` from the file's current content (tools.py:2047,2080), and a stale `seen` yields a
recoverable ToolError («léelo con read_draft»), not an exception; `_write_ops` catches
`fs.FileChanged` (tools.py:1888).

### C3 (H4) — `timestamp_units` exists in the checker and the validator, not in the engine

`check_request` detection (origin.py:811–849), the validator rule (validate.py:689) and the
preview error text (`preview.timestamp_unit_mismatch`, es.py:562 — "revisa `timestamp_units` en
la petición") all exist since 040 (E). The engine does not: `extract._records` copies the raw
value (`text_value`), and `timestamp_units` is read nowhere under `app/engine/`. A fear & greed
epoch (`1730000000`) COPY'd into `snapshot_at timestamptz` fails in Postgres with the
out-of-range family — and the error message sends the agent to declare a knob that **has no
runtime effect**. T025 (`snapshot_at` mapping of `fear_greed`) is unfinishable; the agent
declares the unit, validation passes, preview fails again, loop.

### C4 — no round-level no-progress detector (the prompt's fix 5, confirmed necessary)

The loop's only repetition brake is `last_failed == signature` (service.py:2687): the *same*
call failing twice *consecutively*. One successful `read_draft` in between resets it
(service.py:2683) — which is precisely the production pattern (read ×5, then write, then guard
error). With `max_rounds = None` in Auto, nothing else stops the C1/C3 loops before the stage
budget (`blocked:stage_budget`, service.py:2613).

### C5 — the guard deadlock survived the first fix when the check reads NO shape (run 133)

Production DB evidence (session 24; runs 129 `FileChanged`, 130/132/133 `blocked:stage_budget`,
~600k tokens each, still on pre-fix images). Run 133's transcript (messages 7546–7594): the agent
checks `fear-and-greed.yaml`, the checker answers `'$.data' no es una lista en la respuesta` with
`keys: []` (origin.py returns the error **before** reading any shape when `records` resolves to an
object), and from then on every corrective `edit_draft` — including the ones that fix `records:`
— is refused with «Antes de escribir `fields`…» until the stage budget kills the run. The first
041 guard fix accepted a failed check **with keys**; a structural failure stores an entry with no
keys, which the guard treated like no check at all. Unsatisfiable again: only a fixed file could
produce keys, and only keys allowed fixing the file. Fix: a stored check entry for the path —
whatever it found — authorizes the write; keys, when present, still validate plain field tokens.

### C6 — the platform cannot read an object-shaped endpoint at all (the deepest cause)

Both endpoints this spec needs return `data` as a single JSON object. The engine
(`extract._records`) and the checker (`origin._run_check_request`, both occurrences) rejected any
`records` path that resolves to a dict — so datasets `global_metrics` and `fear_greed` were
**impossible to implement** no matter what the agent wrote; every run could only loop until a
budget or a guard stopped it. Fix: a dict at the records path counts as a one-record list in the
engine and the checker, and the `records` schema description says so. With C6 fixed the checker
reads the object's real keys, which also feeds the C5 guard the information it wants.

## 3. Ruled out

- **H1 as stated** (guard demands a tool that doesn't exist for REST): `check_query` accepts
  `requests/*.yaml` paths (origin.py:1076–1081) and the i18n message names `check_query`. The
  unsatisfiability is the `ok is True` requirement (C1), not the tool name.
- **H2 as stated** (stale read-cache hash sent as revision): see C2; `edit_draft` bases are
  fresh, `_write_ops` catches the conflict. The escaping `FileChanged` comes from
  `write_report`'s base-less write.
- **H3** (unchanged-read short form still sends content): deliberate, dated regression note at
  tools.py:2129–2133 — a 2026-10-26 fix made the short form short, and the model lost the file
  («no puedo leer el contenido real», 20M tokens). Across turns, `history.build` already replays
  old tool results as one-line summaries (history.py:243–246), so reads don't compound between
  turns; within one long Auto turn they do, but the cure is stopping the loop (C4), not
  truncating reads again.
- **H5** (inconsistent saved state after the crashes): the orphan `tool_result` bug is fixed —
  results are written once per round, paired by `call_id`/`assistant_message_id`
  (service.py:2728–2731); `IntegrityError` became a named `StateConflict` stop (040 Step 0,
  service.py:2138); `rewind` points the cursor back at the unfinished stage (pipeline.py:705).
  The stuck conversation can resume once C1–C3 are fixed; nothing in the saved state re-enters
  the dead end by itself (the dead end was live code, not state).

## 4. Fix design (approved shape, adjusted to what was proven)

1. **Guard (C1)** — `run_check` stores `keys` (and keeps `skipped`) in `query_checks[path]`.
   `_requests_checked` accepts a write when the last check **read the shape** (`keys` non-empty,
   or `skipped`, or `ok is True`) and then validates the **new** content's `fields` against
   those `keys`. A check that errored (no shape) still blocks. Docstring names `check_query`.
   Refinement found while making the dead 040 (E) check live: it compared output **column
   names** to response keys, which false-positives on any renamed column
   (`snapshot_at: snapshot`). The live check judges the mapped **path** instead, and only when
   it is a plain top-level key — nested or indexed paths are judged by the check itself.
2. **Report write (C2)** — `write_report` sends `force: True` (the run report is generated,
   deterministic, pipeline-owned; a revision is still recorded for audit). Constitution IX is
   untouched: the report never marks tasks done.
3. **Engine (C3)** — `extract._records` converts mapped values whose column is declared in
   `timestamp_units`: `seconds`/`milliseconds` → UTC ISO-8601 (`iso8601` passes through);
   non-numeric values pass through so Postgres still names bad data. Plus a preview-time range
   check is NOT added: the existing Postgres error already maps to the named message, and after
   this fix the declared unit actually applies.
4. **No-progress stop (C4)** — in the round loop: after 3 consecutive rounds with the identical
   set of tool-call signatures and no file written, end the stage with
   `blocked:no_progress`, naming the repeating tools and the last error. Honors the owner's
   "no round counter" rule: it stops on proven lack of progress, not on a count.

## 5. Verification (ran 2026-10-28)

- `tests/test_assistant_root_cause_041.py` (7 tests): each cause reproduced failing for the
  claimed reason first (guard ToolError `check_request_first`; `fs.FileChanged` from the second
  `write_report`; raw epoch out of `_records`; 6 provider rounds instead of a stop), then green
  after the fixes. Two are regression guards that already passed (keys stored by the 040 tool
  wrapper; an **unchecked** request still blocks).
- C5/C6 (added after the run-133 evidence, same file, now 10 tests): the structural-failure
  entry blocked the `records` fix (ToolError, C5), `extract._records` raised on an object (C6),
  and `check_query` read no keys from an object response — all three failed for the claimed
  reason first, then green after the guard, engine and checker fixes.
- `tests/test_assistant_root_cause_041_e2e.py`: the production transcript replayed in the real
  `/speckit-implement` loop — unchecked write refused, failed check reads the shape, the same
  write then lands, run `completed`, no «error inesperado», corrected `fields` +
  `timestamp_units` on disk.
- Detector refinement found by the suites: identical *successful* rounds are a working pattern
  (the discovery limit's own test scripts three of them), so only an identical round that also
  failed and wrote nothing counts; `blocked:no_progress` after three.
- Affected suites green: test_assistant_request_shape, test_assistant_guard,
  test_assistant_loop, test_assistant_speckit_all, test_assistant_commands_guard,
  test_assistant_preview — except three failures that also fail on clean main f7feae3
  (pre-existing, NOT from 041; verified in a worktree at that commit):
  `test_assistant_guard.py::test_discovery_limit_restricts_then_returns_after_draft`,
  `test_assistant_loop.py::test_context_too_long_retries_with_latest_round`,
  `test_assistant_loop.py::test_context_too_long_twice_reports_error` (the two context tests
  expect the old provider message; the code now answers with the 040 stage-resume text).
- Frontend suite: green (vitest, exit 0). Full backend suite: result recorded below when done.

## 6. Production steps

- Deploy: rebuild the backend image; no DB migration (`query_checks` is JSONB; no schema
  change). The worker image shares the engine code (`timestamp_units`), so rebuild it too.
- The stuck conversation IS resumable after deploy: `/speckit-all 001-mercado-cripto`. The
  rewound cursor repeats the unfinished stage; the previously impossible writes become possible
  (the guard accepts a checked file whatever the check found; `timestamp_units` is honored at
  extraction; both object-shaped endpoints — `global-metrics/quotes/latest` and
  `fear-and-greed/latest` — now extract as one record). The saved state is consistent (results
  paired per round, 036), so nothing re-enters the dead end.
- Note on the current draft: `fear-and-greed.yaml` carries an invalid scalar
  `timestamp_units: seconds` (schema wants a map). The engine ignores a non-dict and the
  validator flags it, so the agent will be told and can fix it — no manual edit needed.
- If the conversation's token budget is spent, start a fresh conversation on the same project:
  the files and specs carry over.
