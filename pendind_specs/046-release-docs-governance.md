# Prompt — 046-release-docs-governance: README, SECURITY, constitution, code of conduct, contributing, version 0.2.0

Paste everything below the line into the coding agent with the repository open. Run it after
045 (agent removed) and alongside 043 WS-B/WS-C; it is the release wrapper of the refactor.

---

You are working on the BizView repository (public: https://github.com/dvconsultores/bizview,
AGPL-3.0-or-later). Read `.specify/memory/constitution.md` and
`specs/043-bizview-refactor-external-authoring/spec.md` (workstream I). Implement
**046-release-docs-governance** end to end as `/speckit-specify` (from this text) →
`/speckit-plan 046-release-docs-governance` → `/speckit-tasks` → `/speckit-implement`. Do not
ask me questions; take the decisions written here.

## Goal

Make every document that describes the product true again after the refactor: Bizview is a
runtime that describes sources, validates, imports, runs and shares projects authored outside
it. Ship as **0.2.0** under the plain name **Bizview**.

## 1. Constitution → 2.0.0 (MAJOR)

Edit `.specify/memory/constitution.md` through `/speckit-constitution` with a Sync Impact Report:

- **Preamble**: "Bizview ingests raw data from existing sources, transforms it into optimized
  models and serves mobile-first dashboards and PDFs. Projects (integrations and reports) are
  authored outside Bizview — by people or by any AI — against a published contract, and enter
  only through validation and import."
- **IV. Folders**: remove `backend/app/assistant/`; add `cli/bizview_cli/workspace_template/`
  as the source of the authoring pack and `examples/` (optional golden projects); note that
  `custom_queries/` is superseded by project folders.
- **VIII. AI Is Optional and Private**: keep; add "Bizview does not author artifacts with AI.
  AI inside the product is limited to read-only help and to connectors that consume approved
  reports. Structure packs sent to external AIs contain structure, counts and shapes only —
  never credentials, hosts or row values."
- **IX. Spec-Driven Reporting**: redefine as in 043 (spec.md mandatory with kind and Approved
  status; plan/tasks optional for imported projects; declarative artifacts; the engine refuses
  anything unvalidated; projects enter through import).
- **Constraints**: add import limits (file types, sizes, assets per 044 when present) and the
  rule that the validator's schemas in `cli/` are the single source used by CLI, backend and the
  pack.
- **Governance**: unchanged. Version 2.0.0, Last Amended today; list deprecated specs in the
  report.

## 2. README (EN) and README.es.md

Rewrite both around the loop, same structure in both languages:

1. Hero: "Bizview — Your business data on your phone. Build the reports with any AI; Bizview
   validates, runs and shares them." One screenshot placeholder, three actions (Install ·
   Hosted · Connect my ERP) linking to the site.
2. **Install (Docker Compose)**: the two-file download (`bizview.yml`, `.env.example`) from the
   repo, four `.env` values, `chown` line, `pull` + `up -d`, private vs public server, upgrade via
   Watchtower or pinned `BIZVIEW_VERSION`. Keep it to one screen.
3. **How it works** — eight steps: add a source → download the authoring pack → fill
   `REQUEST.md` → build with any AI (or by hand) → validate with the CLI → import → apply →
   share. One sentence each, with the CLI commands.
4. **What it does**: capabilities table without any assistant row; add rows for import/export,
   authoring pack, structure packs, visual components (044) when merged.
5. **Configuration** table (groups that matter; `AI_PROVIDER` described as "help only,
   optional").
6. **Architecture** diagram (no AI provider arrow for authoring; help agent optional).
7. **Security**, **Contributing**, **License** — short, linking to the files below.
8. Remove every mention of the assistant, Spec Kit commands inside the app, modes, budgets,
   "AI Powered".

## 3. SECURITY.md

Rewrite: supported versions table (0.2.x supported; 0.1.x security fixes for 60 days after
0.2.0); how to report privately (GitHub Security tab, expected acknowledgement within 3 business
days, fix target 30 days for high severity); scope (product code, CLI, images, compose, the
authoring pack format); out of scope (customer projects' own SQL/YAML, third-party APIs,
installations' infrastructure); hardening notes that are true now: `SECURITY_PROFILE=internet`,
credentials AES-256-GCM write-only, read-only origins, SSRF rules for sources and image fetches,
import validation (types, sizes, content sniffing, SVG sanitization), no AI authoring, structure
packs never contain data. Remove anything about the assistant's data boundary.

## 4. CODE_OF_CONDUCT.md and CONTRIBUTING.md

- Adopt the Contributor Covenant 2.1 verbatim with a contact email (`security@`/`conduct@` on
  the project domain — use the address already in SECURITY.md or `developer@dvconsultores.com`
  if none).
- CONTRIBUTING.md: how to run the dev stack (moved here from the old README), the Spec Kit
  workflow for product features (specify → plan → tasks → implement, `/speckit.all` for the
  repo if present), tests and lints, how to add a guide topic (033) and a `## Docs` section to a
  spec, how to propose a schema change (schemas in `cli/` are versioned with `format_version`;
  bump + migration note + pack regeneration), commit and PR conventions, AGPL contributor note
  (no CLA; contributions under AGPL-3.0-or-later).

## 5. Version and naming

- Bump to `0.2.0` everywhere the version lives (backend `pyproject`, frontend `package.json`,
  CLI, `deploy/`, image tags, `/api/health`, footer); add a single source of truth
  (`VERSION` file or one module) if there is not one, and a CI check that all copies match.
- Product name: `PRODUCT_NAME` default `Bizview`; footer "© 2026 Bizview · Versión 0.2.0 ·
  AGPL-3.0 · GlobalDV"; remove "AI Powered" from strings, meta tags, manifest, images' alt
  text, docs and the site copy (`bizview-site` repo: open an issue or PR there with the new
  hero line). Installations may still set any `PRODUCT_NAME`.
- CHANGELOG 0.2.0: Added (authoring pack, structure packs, import as front door, lite specs,
  visual components if merged), Changed (README/docs/constitution 2.0.0, naming), Removed
  (every spec listed by 045), Security (import validation, SSRF for image fetch).
- Tag `v0.2.0`; release notes = CHANGELOG section + the before/after numbers from 045.

## 6. Docs folder

- `docs/AUTHORING.md`: the contract (folder layout, `PROMPT.md`/`REQUEST.md`, schemas, rules,
  lite specs, validation, `problems.json`, assets when 044 lands), with one worked example
  (CoinMarketCap) at the end.
- `docs/IMPORT.md`: upload → map → collisions → validate → preview → apply; CLI equivalents.
- `docs/INSTALL.md`: keep, trim anything about the assistant; `docs/VIBE-REPORTING.md`: update
  or merge into AUTHORING.md and leave a redirect note.
- Help topics (033 format) regenerated to match; the `docs-lint` gate passes.

## Gates

- grep gate from 045 extended to docs: no `AI Powered|Asistente|speckit-all|run contract` in
  README*, SECURITY.md, CONTRIBUTING.md, docs/, help topics (allowlist for the deprecated
  specs folder and CHANGELOG).
- Version check: one source of truth; `/api/health.version == 0.2.0`.
- Markdown lint + link check on all top-level docs.

Commits: (1) constitution 2.0.0, (2) README EN/ES, (3) SECURITY + CODE_OF_CONDUCT +
CONTRIBUTING, (4) version/naming + CI check, (5) docs/ + help topics, (6) CHANGELOG + tag.
