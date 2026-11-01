# Research — BI-ready sources

## R1. The brief overstates what is missing

**Decision**: the specification and the plan start from what 019 shipped — read-only sessions,
`SET LOCAL statement_timeout`, a per-source concurrency cap, a cached result, a deny-list, a read log
— and add only the declaration, the scope, the per-source limits, the health view and the snapshot.

**Rationale**: `engine/direct.py`, `config.py` and `security/profile.py` already implement every
protection the brief lists as absent. Building them again would be a rewrite of a working path with
no user-visible change, and would put SC-002/SC-003 at risk for nothing.

**Alternatives considered**: rewrite the direct path as the brief describes — rejected: it trades
working code for the same behaviour.

## R2. One function answers "may this object be read?"

**Decision**: `engine/direct.py` owns `permitted(source, schema, object)`, which consults the
declaration; the validator calls it (through the sources API) and the engine calls it again before
opening a connection. Two callers, one implementation.

**Rationale**: the scope must hold whichever door a request comes through — a validated report, an
imported one, a share link, a TV page or a token. A rule implemented twice drifts.

**Alternatives considered**: validator-only — the engine would then trust a definition that arrived
after validation (an applied version, an import).

## R3. `direct.tables` accepts two shapes

**Decision**: `alias: schema.object` (a string) is accepted for a BI-ready source, with the columns
read from the source's structure; `alias: {table, columns}` stays, which is what `source: bi` and
every 019 report use.

**Rationale**: the first is the reason an author (or an AI with only the structure pack) can write a
report without copying a column list; the second is the only shape that works where the installation
may not read the structure (a legacy source, a test fixture).

**Alternatives considered**: migrate 019 documents to the new shape — a rewrite of working reports to
gain nothing, and 015's validation is built on the declared contract.

## R4. The limits move onto the source, the environment stays as the default

**Decision**: `bi_ready` carries `timeout_s`, `cache_ttl_s`, `max_rows`, `max_parallel` and
`timezone`. `DIRECT_REPORT_CONCURRENCY`, `DIRECT_REPORT_WARN_ROWS`, `DIRECT_BI_ROLE` and
`DIRECT_REPORTS_BI` keep working as the installation-wide defaults a source without a declaration
uses.

**Rationale**: the customer's warehouse is not the customer's API: one source needs 5 s, another
120 s. Installation-wide constants force the most demanding source onto all of them. Keeping the
constants as defaults is what lets an installation upgrade without touching every source.

**Alternatives considered**: delete the constants — an installation would lose its knobs mid-flight,
and the internet-profile rule that requires a read-only role lives in them.

## R5. Proving the credential is read-only, empirically

**Decision**: at save, in a rolled-back transaction: `SELECT 1` must succeed, and `CREATE TEMP TABLE`
must fail. The proof is recorded with its timestamp and repeated daily by the worker; a change is
audited and notified.

**Rationale**: reading a role's grants is not enough (it may own a table, or be a member of a role
that can write). Attempting a harmless write and being refused is the only proof that does not
depend on how the customer configured their grants.

**Alternatives considered**: assert `NOT rolcanlogin`/`rolsuper` from `pg_roles` — cheap, but says
nothing about ownership or membership.

## R6. `materialize: daily` stores figures, never rows

**Decision**: the worker runs the report's own query once a day and stores the **payload the engine
already produces** (the same JSON a tile receives) in a product table keyed by report and day. The
dashboard reads it and says "datos de ayer".

**Rationale**: it gives a heavy warehouse one query a day instead of one per viewer without inventing
an ETL, without touching `ds_*`, and without a new data path: the payload is what the cache already
holds.

**Alternatives considered**: snapshot to rows in a product table — that is an integration by another
name, with schema, typing and retention to design; deferred.

## R7. The structure pack is `describe`, not a zip

**Decision**: FR-011 is satisfied by marking the `describe` payload (`BI-ready: yes`, the allowed
schemas/objects, the limits, personal-data flags) and by the pack's `PROMPT.md` explaining how to
write a direct report and when an integration is the better answer. The 043 WS-B zip
(`structure.md` + `structure.json`) is left where it is: unbuilt, and not this feature's to build.

**Rationale**: `GET /api/sources/{name}/describe` already returns structure, types, keys and row
counts, and `bizview describe` already turns it into what an AI reads. A second format would be a
second thing to keep true.

**Alternatives considered**: build the 043 zip here — it would double the feature's surface to
deliver a file format nothing consumes yet.

## R8. Health comes from the table that already exists

**Decision**: the source page reads `direct_read_log` over the last 24 h: count, p50/p95
`duration_ms`, failures by `outcome`, and how often `stale_served` was true. No new table, no new
metric pipeline.

**Rationale**: 019's log is exactly the record the question needs. A new metrics store would be a
second source of truth for the same events.

**Alternatives considered**: counters in `settings` — cheaper to read, wrong after a restart, and
unable to answer "which report".

## R9. Personal data keeps 015's rule

**Decision**: a column whose name looks personal is refused unless the report declares it in
`allow_personal` and its spec records the decision. The heuristic list is the one 015 shipped.

**Rationale**: one rule, already documented, already tested.

**Alternatives considered**: a per-source allow-list of personal columns — more places to get it
wrong; the decision belongs to the report, which is where the purpose is written down.

## R10. Migration of what exists

**Decision**: one migration adds `data_source.bi_ready` (JSONB, default `{}`) and backfills it from
`direct_reports = true` (a BI-ready declaration with no scope, meaning "all objects the deny-list
allows", which is today's behaviour). The boolean stays, read as the fallback.

**Rationale**: an installation that turned direct reports on keeps them on, with the same reach it
has today; nothing narrows behind the owner's back.

**Alternatives considered**: derive the declaration from the boolean on read — then the first save
of any source silently narrows every other source's scope.
