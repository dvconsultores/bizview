---
description: Updates the project constitution with principles and governance rules.
argument_hint: "<principles or changes>"
source: speckit-constitution
---
# /speckit-constitution

## Scope
This command only updates the project constitution at `.specify/memory/constitution.md`. Classify
the text of the user message that started this command into constitution content versus separate
intents (feature work, reports, integrations, etc.). Never carry out those separate intents; at the
end, suggest the right command in a `Next Actions` section (for example `/speckit-specify ...`);
omit the section when there are none. If you are unsure whether something is constitution content,
ask the user and end your turn without `finish_command`.

## Current constitution
The current constitution (in the context, inside a `<datos origen="..." confianza="no">` block) is
both the scaffold and the source of current values. If it is not in the context, read it with
`read_draft`. Keep its heading structure. `[ALL_CAPS]` placeholders get concrete values from the
user's input or the project; an unknown ratification date becomes `TODO(RATIFICATION_DATE): ...`.
The last-amended date is today only when something changes. Respect the number of principles the
user asks for: they may want more or fewer.

## Versioning
Semantic bump: MAJOR for incompatible removals or redefinitions of principles; MINOR for a new
principle or section, or materially expanded guidance; PATCH for wording or clarifications. If it
is ambiguous, explain the reasoning before deciding.

## Principles
Each principle has a short name and declarative, testable rules (MUST/SHOULD with the rationale).
No vague language.

## Governance
The governance section states the amendment procedure, the versioning policy and the compliance
review.

## Protected block
The block between `<!-- bizview:reglas-instalacion -->` and `<!-- /bizview:reglas-instalacion -->`
holds the installation's rules (credentials only in the encrypted catalogue, read-only sources, no
rows or personal data in files, BI-only scope, applying is a human action). Copy it byte for byte;
never change, move or remove it. If the user asks to weaken or remove one of those rules, refuse
that part, explain why (they belong to the installation, not to the project) and continue with the
rest. The server rejects any write that alters the block.

## Sync impact report
Add an HTML comment at the top of the file (old → new version, modified principles, added or
removed sections, deferred TODOs). It is review material.

## Validation before writing
Check that no unexplained bracket tokens remain, the version line matches the report, dates are ISO
YYYY-MM-DD, there is a single blank line between sections and no trailing spaces.

## Writing
Write the whole file once with `edit_draft` (`write` op on `.specify/memory/constitution.md`, after
reading it).

## Final message
Report the new version and why, the deferred TODOs and the `Next Actions` (if any). Then call
`finish_command` with a one-line summary; if you need an answer from the user, ask and end your turn
without `finish_command`.
