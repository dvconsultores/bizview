# Data model: Views instead of modals, wider layout, Ubuntu font

No persistent data, API or migration changes.

## Client-side state

- **Open view** (per `View` instance, in memory): `id`, `title`, open flag. Lives only in React
  state; never in storage or URL.
- **History marker**: `location.state.view: string[]` — ids of views opened on this history
  entry. Carries no content; an entry whose ids are not open is ignored (research R3).
- **One-time secret** (temporary password, recovery codes): component state of the screen that
  received it from the API; discarded when its view closes (FR-005).
- **Step-up request**: one pending `Promise<boolean>` shared by concurrent `ask()` calls.
