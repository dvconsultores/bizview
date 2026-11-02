# Research — 049 import limits and assets

Decisions behind the plan, each with what was rejected and why. R1–R9 are referenced from
[plan.md](./plan.md) and from the task list.

---

## R1 — A path belongs to exactly one budget, and the layout says which

**Decision**: `cli/bizview_cli/layout.py` gains `budget_of(path) -> "assets" | "artifacts" | None`,
derived from the same `PROJECT_PATTERNS` table that already decides whether a path is allowed:
`assets/**` is the asset budget, every other allowed pattern is the artifact budget, and a path no
pattern matches returns `None` (it belongs to no budget — it is ignored, or refused if it is
disallowed).

**Rationale**: today three places answer "is this a project file" (`layout.is_allowed`, `fs.check_rel`,
`validate._ignored_files`) and two places answer "how big may it be" (`fs.check_limits`,
`fs.check_asset_limits`) — and the second pair disagreed about *what to count*, which is exactly the
reported defect. Making the classification a property of the layout means a new artifact folder added
in one place is automatically counted correctly everywhere. The constitution names the layout as the
single source of the authoring contract.

**Rejected**: a prefix test (`path.startswith("assets/")`) repeated in the importer, the fs checks, the
CLI and the browser. Four copies of one rule is how this bug happened; a fifth is not the fix.

---

## R2 — The six numbers are installation settings: a DB singleton with NULL = inherit

**Decision**: a new singleton table `project_limits` with six **nullable** columns
(`artifact_max_files`, `artifact_max_kb`, `artifact_max_mb`, `asset_max_files`, `asset_max_kb`,
`asset_max_mb`). A NULL means "use the deployment default", which comes from `Settings`
(`project_max_files=400`, `project_max_kb=2048`, `project_max_mb=20`, `project_asset_max_files=2000`,
`project_asset_max_kb=300`, `project_asset_max_mb=25`). A super user edits the six numbers in
**Administración → Proyectos → Límites de importación**; the endpoint writes the whole row and audits it.

**Rationale**: the owner asked for "settings with defaults, super user editable in Administración →
Proyectos". NULL-as-inherit keeps an existing operator's `PROJECT_MAX_MB` in force (the spec's edge
case: "an operator's explicit values are kept") while still letting an installation raise a number
from the app without a redeploy. This mirrors `appearance_settings` (030/047): a singleton row, a
`PUT /api/admin/settings/…`, an audit event, `updated_by`.

**Rejected**:
- *Env-only* (like `project_max_mb` today): cannot be edited in the app; the owner asked for it.
- *A DB row seeded with the defaults, all columns NOT NULL*: silently freezes an installation whose
  operator later raises `PROJECT_MAX_MB` in `.env`, which the spec forbids.
- *A generic key/value settings table*: there is none in this product, and inventing one for six
  numbers is a bigger surface than a typed, check-constrained row.

---

## R3 — One tally implementation, in the CLI package, imported by the backend

**Decision**: `cli/bizview_cli/budgets.py` holds `Budget` (name, max files, max KB per file, max MB
total, the folders it owns), `Tally` (files, bytes, largest file, over-limit reason), `tally(entries)`
and the classification helper. The backend imports it (`from bizview_cli import budgets`) exactly as it
already imports `bizview_cli.layout`.

**Rationale**: the constitution requires the CLI, the backend and the pack to read the contract from
one place. Both sides must answer the question "what does this project cost" identically (SC-005), and
the only way to guarantee that is one implementation. The backend already depends on `bizview-cli`.

**Rejected**: implementing the tally server-side and having the CLI shell out or duplicate it. Duplicate
= drift, and the drift is the defect being fixed.

---

## R4 — The zip-bomb protection moves to per-entry budgets

**Decision**: `_entries()` in `backend/app/projects/zip.py` stops summing every entry against one cap.
Instead it classifies each entry (`layout.budget_of`), accumulates per budget, and refuses with the
budget's own message. The structural cap `MAX_ENTRIES` becomes
`artifact_max_files + asset_max_files` **file** entries (directories do not count; the loop still stops
after `2 ×` that many entries as a hard bound). The ratio (`file_size / compress_size > 100`) and the
"declared size equals bytes read" checks are unchanged.

**Rationale**: a count cap of 1 000 was a proxy for "a real project is small". A project is now allowed
2 400 files, so the proxy must follow the budgets — but the thing that protects against a bomb is the
ratio and the absolute bytes, and those stay exactly as they are. Counting per budget also gives the
refusal its message for free.

**Rejected**: raising `MAX_ENTRIES` to a round 3 000. It would be a third number, unrelated to either
budget, that drifts the moment a budget changes.

---

## R5 — "Harmless" is decided by extension and by bytes; "disallowed" fails the import

**Decision**: two rules, applied to every entry that no budget owns:

1. **Disallowed content fails the whole import** — extension in
   `{.js,.mjs,.cjs,.ts,.sh,.bash,.zsh,.bat,.cmd,.ps1,.vbs,.scr,.exe,.dll,.so,.dylib,.jar,.class,.py,
   .rb,.php,.pl,.lua,.wasm,.com,.msi,.bin}`, **or** bytes starting with `\x7fELF`, `MZ`, `#!`, `\xCA\xFE
   \xBA\xBE` / `\xFE\xED\xFA`, or `<script` — refused with `zip_disallowed`, naming the path.
2. **Everything else** (text, images outside `assets/`, any file under a pack folder) is appended to
   `ignored` and the import continues.

**Rationale**: today every non-layout file is silently ignored, including a `.js`, so a project could
carry a script into the installation folder and nobody would say so. The prompt requires that a `.js`
still fails while the pack's own files import. Extensions alone are not enough (a PNG named `.js` is
still a script by name, and an ELF named `.txt` is still executable by content), so both are checked.

**Rejected**: trusting the extension only (a `README.js` is refused — fine — but `payload.txt` with an
ELF header is not); or refusing every unknown file (that is the behaviour the prompt removes).

---

## R6 — The pre-flight reads the archive's index in the browser, with no new dependency

**Decision**: `frontend/src/lib/zipIndex.ts` reads the **End Of Central Directory** record (scanning
backwards over at most 65 557 bytes for the `PK\x05\x06` signature), follows `offsetOfCentralDirectory`,
and walks the central-directory entries (`PK\x01\x02`), returning `{name, size}[]`. Zip64 and a spanned
archive return an empty result, and the caller then falls back to "no pre-flight, let the server
decide". `importPreflight.ts` tallies that list against the limits the server published.

**Rationale**: the whole point is to refuse **before** uploading, so it cannot be a server call. The
central directory is the archive's own table of contents: no decompression, no library, ~80 lines, and
a unit test can build a zip in memory and assert the reader's output. The declared `uncompressedSize`
is what we report — and the server re-measures the real bytes, so a lying index helps nobody.

**Rejected**: adding `jszip` (a runtime dependency, and its API is archive-shaped, not index-shaped);
reading the local file headers instead (they repeat the name but not reliably the size, and a data
descriptor may follow the content — the central directory is authoritative).

---

## R7 — `POST /api/projects` answers `410 Gone`; `/slug` is removed

**Decision**: the creation route stays declared, documented, and answers
`410 Gone` with code `project_creation_removed` and a message pointing at import. `GET /api/projects/slug`
(the slug suggester, whose only caller was the create form) is deleted outright. `project_service.create()`
is untouched: the importer calls the service directly, not the API.

**Rationale**: the prompt asks for "a documented error response, without interfering with the import API
or internal project initialization". 410 is exactly "this used to exist and no longer does"; a 404 would
look like a typo, and a 403 would suggest a permission problem. Deleting `/slug` is safe because nothing
else reads it (verified by grep over `backend/`, `frontend/`, `cli/` and the e2e suite).

**Rejected**: deleting the route (a stale client gets an unhelpful 405/404); returning 403 (implies the
caller lacks a right that no one has); leaving the route working "just in case" (the release gate in the
prompt forbids an independently callable creation API).

---

## R8 — Export is unchanged, and "re-import an export" is the acceptance test

**Decision**: `export()` keeps writing exactly the layout files plus the pack files. A test imports a zip,
exports it, imports the export, and asserts the second import's tallies are inside the budgets and its
`ignored` list contains nothing from the project itself.

**Rationale**: the export already includes `.bizview/**` and `README.md` (agent scaffolding, FR-005's
"pack files"), which lands in `ignored` on the way back in. That is correct behaviour, but it is worth an
assertion: it is the cheapest proof that the budgets are large enough for what the product itself hands
out, and that the ignored list is honest rather than a silent drop.

**Rejected**: stripping the pack files from the export ("cleaner"). They are there so an agent can work
on the project after a round trip; removing them would break that for a cosmetic gain.

---

## R9 — One shared per-file limit, and it is 2 MB

**Decision**: the artifact per-file limit becomes a budget field (`artifact_max_kb`, default 2048) used by
`fs.check_limits`, the zip importer and `bizview validate`. The CLI's two hard-coded `512 * 1024` checks
read the same default. `assets.MAX_KB` (300) is folded into the asset budget so there is a single source.

**Rationale**: the spec states artifacts are ≤ 2 MB per file (031 FR-004 as written), while the code
enforces 512 KB; a project that passes one and fails the other is the same class of defect as the reported
one. Unifying them at the documented number is the only way the CLI and the server can agree (FR-006).

**Rejected**: keeping 512 KB (contradicts the spec and the prompt) and raising to 2 MB in the backend only
(then `bizview validate` refuses files the server would accept — worse than the status quo).
