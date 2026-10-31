# Implementation Plan — 045 remove the in-app authoring agent

**Spec**: [spec.md](./spec.md) · **Inventory**: [inventory.md](./inventory.md)

## Approach

Delete by inventory, in an order that keeps the tree runnable after every commit: the surface that
*uses* the agent goes before the agent itself, so no commit leaves imports pointing at a missing
module. The rescue migration lands before the drop, in the same commit, so no state exists where the
data is gone and the rescue has not run.

Order (mirrors the six commits the brief asks for):

1. **inventory** — this folder.
2. **frontend removal** — components, pages, routes, strings, tests; the app compiles and the
   suites pass with the agent gone from the screens.
3. **backend removal** — `app/api/assistant.py`, `app/assistant/**`, the narrative generator, the
   routes and hooks that called them; the app imports and runs.
4. **migration + settings** — rescue applied drafts into their projects, drop the tables and the
   settings, `AI_PROVIDER` stays help-only.
5. **tests, fixtures, dependencies, gates** — delete the suites, measure, add the five gates.
6. **docs, specs, constitution, CHANGELOG**.

## Key decisions

- **D1 — rescue before drop, one transaction.** The rescue reads `assistant_session.draft` for
  conversations whose draft was applied and writes the spec documents through the project write path
  (`fs.apply_ops`) so the write is versioned and audited like any other. Projects that already hold
  the folder are left alone (`on conflict do nothing`), so a double run is a no-op (FR-012).
- **D2 — transcripts are not kept.** The brief says so; only applied *content* is rescued.
- **D3 — the narrative generator goes, its schema key stays.** `ai_narrative` remains in
  `report.schema.json` and in the payload, marked deprecated-ignored by the plan, so no author's
  project fails validation on upgrade. The route and the generator go.
- **D4 — the help function keeps `complete()`.** `app/ai` loses tool calling, rounds, vision and the
  stage budgets; the client, provider selection and `complete()` stay.
- **D5 — migration files stay in history.** A migration records what ran; the new one drops the
  result. Editing old migrations would break every installed database.
- **D6 — the gates are scripts, not prose.** Each is a shell script with an allowlist file the
  reviewer can read, wired into one `make`-style entry point that CI calls.

## Configuration surface after the change

`AI_PROVIDER` (default `none`, described as help-only), `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL`,
`AI_TIMEOUT_SECONDS`. Everything else that began with `AI_CHAT_` or carried a budget is gone.

## Measured baseline (SC-005)

| Metric | Before |
|---|---|
| `backend/app` Python | 40 898 lines |
| `backend/tests` Python | 36 814 lines |
| `frontend/src` TS/TSX | 32 027 lines |
| frontend runtime / dev dependencies | 17 / 14 |

Backend **image** size needs a Docker build; recorded as not measured here, with the command to
reproduce it (`docker build backend`), rather than guessed.

## Risks

- **R1 — an applied draft that is not in the expected shape.** Rescue copies documents as-is; a
  malformed draft is rescued malformed and never blocks the upgrade.
- **R2 — a project deleted after apply.** Nothing to rescue; the step skips it and says so in the log.
- **R3 — hidden coupling.** `grep` for each removed symbol before deleting its module; the suites
  after each commit are the real check.
- **R4 — the gates are too strict.** They carry an explicit allowlist; a false positive is a change
  to the allowlist with a reason, never a silent exclusion.

## Constitution impact

Principle IX is redefined: authoring happens **outside** Bizview against the published contract. The
folder list loses `backend/app/assistant/`. Version 2.0.0.
