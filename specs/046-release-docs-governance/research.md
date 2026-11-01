# Research — 046 release, documentation and governance

Phase 0. Each decision is the one this plan implements; the alternatives are recorded so a reviewer
can see what was rejected and why.

## R1. Which number the constitution carries

**Decision**: finish the amendment's substance and keep the number the file already records
(3.0.0 from 2.1.0), writing the reasoning into the Sync Impact Report: the brief calls it "2.0.0"
because it was written against a copy of the file before 043's own amendment landed; that amendment
already stated that from 2.1.0 a MAJOR bump is 3.0.0 and that its "2.0.0" label was the intent, not
the number. This feature adds the preamble wording, the folder-list corrections and the constraints
the brief lists, and records the release as the amendment that 0.2.0 ships under.

**Rationale**: renumbering a MAJOR amendment *downwards* to satisfy a label would make the file's
own history contradictory, which is exactly what a constitution must not be. The substance (what
the brief actually cares about) is identical either way.

**Alternatives considered**: (a) renumber to 2.0.0 and drop the 2.1.0 → 3.0.0 report — loses the
recorded decision and re-opens the ambiguity; (b) leave the number alone and skip the amendment —
leaves the preamble and the constraints describing the old product.

## R2. Where the version lives

**Decision**: `VERSION` at the repository root is the single source of truth. The backend already
reads it at startup (`_file_version`), `deploy.sh` already tags images from it, and the Dockerfiles
already receive it as a build argument. `scripts/gates/07-version.sh` asserts:
`VERSION` = `backend/pyproject.toml` version = `frontend/package.json` version =
`cli/pyproject.toml` version, and that a running backend's `/api/health` reports the same value
(when a backend is reachable; the gate skips that half with a stated reason when it is not).

**Rationale**: the number is already load-bearing in three places; adding a fourth (a generated
header) would create another copy to drift. The gate is what makes "one truth" true.

**Alternatives considered**: a Python constant — the Dockerfiles and `deploy.sh` would have to
import it; a generated `version.py` + gitignore — nobody can read the version without building.

## R3. The product name

**Decision**: `PRODUCT_NAME` default becomes `Bizview` (backend `config.py` and the frontend's
`BrandingContext` fallback). The rename reaches every shipped string, page title, manifest, image
alternative text, package description and document. An installation keeps the ability to set any
name; the check that forbids "AI Powered" looks at the repository's own files, never at a running
installation's rendered screens.

**Rationale**: the suffix was part of the authoring-agent positioning; shipping it into 0.2.0 would
contradict the release notes. Keeping `PRODUCT_NAME` configurable is existing product behaviour and
is not part of this rewrite.

**Alternatives considered**: keep the suffix — contradicts the release's own story; hardcode the
name — breaks installations that branded their server.

## R4. Document set: what is rewritten, what is added, what retires

**Decision**:
- Rewritten: `README.md`, `README.es.md`, `SECURITY.md`, `CONTRIBUTING.md`, `docs/INSTALL.md`
  (trim), the constitution.
- Added: `docs/AUTHORING.md` (the contract, the eight steps, one worked example),
  `docs/IMPORT.md` (upload → map → collisions → validate → preview → apply, with CLI equivalents).
- Retired: the parts of `docs/VIBE-REPORTING.md` that `docs/AUTHORING.md` supersedes; the file
  keeps a short redirect note so inbound links still work.
- Confirmed, not rewritten: `CODE_OF_CONDUCT.md` is already the Contributor Covenant 2.1; it gains
  the contact address only.

**Rationale**: one document per reader. An author reads AUTHORING; an operator reads INSTALL; a
reporter reads SECURITY. `VIBE-REPORTING.md` became a second, longer version of AUTHORING with the
agent's workflow inside it.

**Alternatives considered**: keep `VIBE-REPORTING.md` as the authoring guide and fix it in place —
it is organised around the removed agent's commands, so "fixing it" is rewriting it under a name
that no longer describes it.

## R5. How the help topics stay in step

**Decision**: the help topics (`backend/app/guide/{es,en}/*.md` + `index.yaml`) are edited with the
documents in the same commit, and `scripts/gates/08-markdown.sh` includes them in its structural
checks. The existing `tests/test_guide.py` already enforces section parity, ids, aliases and the
`commands` allowlist; this feature adds nothing to the runtime help.

**Rationale**: the help is reader-facing documentation of the same behaviour; letting it drift is
how the assistant's text survived inside the product after the assistant left.

**Alternatives considered**: generate the help from `docs/` at build time — the help is in two
languages with its own metadata (`roles`, `routes`, `aliases`), and generating it would be a new
product feature rather than a documentation fix.

## R6. The gates

**Decision**: extend 045's suite rather than build a parallel one:
- `01-vocabulary.sh` gains the documents (`README*`, `SECURITY.md`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `docs/`, the help topics) with the existing allowlist for the changelog,
  the deprecated specs and the migrations.
- `07-version.sh` (new): one source of truth, every copy agrees, `/api/health` agrees when a
  backend is reachable.
- `08-markdown.sh` (new): fenced blocks balanced, table column counts consistent, relative links
  resolve, headings unique per file, no trailing spaces in headings, and the two READMEs carry the
  same section headings.
- `all.sh` runs them; `.github/workflows/gates.yml` already runs `all.sh`.

**Rationale**: one command, one CI job, one place to read what is forbidden. A second suite would
be the thing nobody runs.

**Alternatives considered**: a Node markdown linter (adds a dependency for a hand-written corpus);
a Python one (same, plus a plugin policy).

## R7. Reconciling the brief's "0.2.0" with the tree

**Decision**: `VERSION` and every copy become `0.2.0`. The CLI's `pyproject` is at `0.3.0` today
(it is published separately and versioned independently); it is aligned to `0.2.0` as part of the
release **and** the gate treats a deliberate CLI-only bump as a failure, so the release must move
them together from now on. Recorded here because silently "fixing" a lower CLI number to match the
product would have hidden the divergence.

**Rationale**: a reader who installs the product and runs the CLI must not see two numbers.

**Alternatives considered**: keep the CLI versioned separately and exempt it from the gate — the
brief asks for one truth, and a separate number is what produced today's mismatch.

## R8. The site repository

**Decision**: `bizview-site` is external. The new hero line is recorded as an external dependency
with an owner (`dvconsultores`) in the release notes and the changelog entry, and the release does
not block on it.

**Rationale**: a release cannot wait on a repository this one cannot see; recording the dependency
is what makes it not be forgotten.

**Alternatives considered**: copy the site copy into this repository — out of scope and it would
be the second source of truth.
