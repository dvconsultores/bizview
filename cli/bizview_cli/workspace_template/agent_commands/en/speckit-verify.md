---
description: Verifies an implemented spec with real checks (validation, queries and preview) and reports the result per user story.
argument_hint: ""
source: speckit-verify
---
# /speckit-verify

## Goal
Prove the spec with the checks the product already owns, not with an opinion: validation of the
draft, `check_query`/`check_request` for every query and request of the spec's integration, and one
preview. Each user story ends with pass/fail and the reason.

## Command
- When this stage opens the product has already run the checks and published them in the
  conversation (validation, one check per file, the preview and the verdict per story). Read them.
- This stage **writes no files**: you have neither `propose_draft` nor `edit_draft`. If something
  fails, say which file fixes it and go back to the stage that owns it with `run_command`
  (`speckit-implement`, `speckit-converge`, `speckit-plan` or `speckit-tasks`).
- Every return counts as a cycle: three are allowed. On the third one, stop and write the report
  with the failure; never invent a check that passes.
- Use `check_query` or `run_preview` only to repeat a specific check; the preview counts against the
  contract.

## What you report
- One line per check with its result and detail, and one line per user story (`US1`, `US2`, …) with
  its Independent Test and pass/fail.
- When everything passes: "Verification complete" and the next action is applying (when the contract
  allows it) or "Pending for the human: Apply".
