# Research — 064 view as table

- `viewCsvTable` only knows ranking/table today; every card in 064 needs rows. A new model module is
  cheaper and testable than teaching the CSV helper every chart shape.
- The payload already contains `top_n`/`limit` results; `truncated` is added in the engine so the UI
  never guesses from the row count.
- `full=1` on the existing route avoids a second endpoint and a second auth path. The cache key must
  include the flag or a full request would poison the normal payload.
- `CardDialog` is the single allowed modal; adding a mode toggle inside it keeps focus trap, Esc and
  ← → behaviour in one place.
- There is no XLSX writer in the product and no share-link export flag; both are recorded as
  decisions rather than invented APIs.
