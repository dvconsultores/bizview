# Commands to specify

## What it is for

These commands set the project's principles and create and clarify each spec.

## Who can use it

Only the **Superuser**, in a project's chat.

## How to

- `/speckit-constitution <principles or changes>`: updates the project constitution
  (`.specify/memory/constitution.md`). The installation rules block does not change: if you ask to
  weaken it, the agent explains why not.
- `/speckit-specify <description>`: creates a new `specs/NNN-name/` spec with its `spec.md`, the
  `**Tipo**:` line (source, integration, report or distribution) and the quality checklist
  `checklists/requirements.md`. It uses the project's next free number, leaves at most 3 questions
  marked `[NEEDS CLARIFICATION]` and the spec becomes the conversation's **Current spec**.
- `/speckit-clarify`: asks up to 5 questions, one at a time, and records each answer under
  `## Clarifications` in `spec.md`.

## Options

- `/speckit-clarify` works on the **Current spec**; if there is none, the chat asks you to pick it.
- Each command changes only its own files: if it tries another one, the server refuses it.
- While a command waits for your answer you can reply in the chat or press **Finish**.
