# Agent Instructions — Bizview workspace

## Hard rules (layout v2)

- **No spec, no work**: create artifacts only for an approved spec in the same project's `specs/` folder.
- Specs are numbered per project with three digits, consecutively, and numbers are never reused (`projects/<slug>/specs/001-…`, `002-…`).
- Every spec.md carries the kind line `**Tipo**: fuente | integracion | reporte | distribucion` (English `**Type**: source | integration | report | distribution` is also accepted).
- An artifact's `spec:` field is `specs/NNN-<nombre>` inside its own project.
- Integration, report, and distribution ids are unique across the whole workspace.
- Distributions send reports only to roles (`admin`/`user`), never to email addresses.
- Declarative only: SQL must be read-only (single SELECT or WITH per file); YAML describes artifacts; never commit credentials, row values, or secrets.
- Reuse existing integrations before creating a new one.
- A report declares at least one filter (`filters: [<dimension>]`); without one Bizview refuses to
  apply it, and `bizview validate` says so as a warning.
- A column the validator flags as personal data (email, phone, document id, chat id, payment,
  birth date, a customer's name…) is either excluded or listed in the integration's spec as
  `**Datos personales**: <columns>`. Bizview refuses to apply the project until it is.
- Run `bizview validate --write-lock` and fix every error before committing.
