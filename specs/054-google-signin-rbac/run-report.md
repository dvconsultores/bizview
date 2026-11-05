# Run report — 054-google-signin-rbac

**Request**: the owner's brief of 2026-11-04 (*Google button with the official logo, and role mapping
for Google sign-in*), run as specify → clarify → plan → tasks → analyze → implement → converge →
verify.

**Feature**: `specs/054-google-signin-rbac/` · **Branch**: `main` (no branch created, per the
repository rules)

## Stages

| # | Stage | Result |
| --- | --- | --- |
| 1 | specify | [spec.md](./spec.md) — 5 user stories (branding, domains, provisioning, rules, linking), FR-001…FR-019, SC-001…SC-006, 4 decisions |
| 2 | clarify | 7 decisions (normalisation, one access shape, the `full_name` fallback, empty domain list, admin default role, rules on every sign-in, input limits) |
| 3 | plan | [plan.md](./plan.md) — migration, policy service, admin API, callback, sign-in screen, Seguridad card, constitution check |
| 4 | research | [research.md](./research.md) — what 027 left, why the policy is one service, the Google brand variants, the test seams |
| 5 | quickstart | [quickstart.md](./quickstart.md) — the automated gates and the manual checks |
| 6 | tasks | [tasks.md](./tasks.md) — 28 tasks, all implemented and ticked |
| 7 | analyze | 2 decisions (the admin's password reset is the only way in for a provisioned account; the catalogue stays one endpoint) |
| 8 | implement | backend (model, migration, policy, API, callback, refusal path), frontend (button, card, i18n), docs, guide, e2e and the identity hook |
| 9 | converge | round 1: 4 decisions (RoleTiles instead of a select, the catalogue rides with the settings, the card is always mounted, the specific sign-in sentences deleted) |
| 10 | verify | see below |
| 11 | converge (round 2) | 6 findings appended as T029–T034 — one CRITICAL (principle V was never amended), one HIGH (the env seed was displayed but never validated), three MEDIUM, one LOW — then implemented |
| 12 | verify (round 2) | see *Convergence round 2* below |

## What changed

**Backend**

- `app/models.py`: `AppUser.auth_provider` (`password` | `google`) and a nullable `password_hash`;
  `GoogleSettings` (singleton) and `GoogleRule` (ordered, first match wins); six audit kinds.
- `alembic/versions/0051_google_rbac.py`: the two columns, the two tables and the recreated
  `audit_event.kind` constraint carrying 0050's list (including `source_structure_generated`) plus
  the six new kinds.
- `app/services/google_policy.py` (new): normalisation, the settings row or the env seed, first-match
  rule evaluation, `grant` (materialises `none` / `all_public` / `list` into `dashboard_access`),
  `provision`, `apply_to_existing`.
- `app/api/google_admin.py` (new): `GET/PUT /api/admin/google` and the rules CRUD + reorder, superuser
  only, step-up on every write, audited.
- `app/api/oauth.py`: the callback resolves the identity through the policy — linked subject, email,
  provisioning, refusal — and returns the audit detail (`how`, `rule`, `rule_applied`) while the page
  keeps one generic sentence.
- `app/api/auth.py`: an account without a hash is refused through the same `INVALID` path, and the
  refusal is not counted as a failed attempt (a password cannot be guessed for it).
- `app/api/testhooks.py`: `POST /api/testing/google-identity` answers the token exchange with the
  identity a test asks for (through the `google.client()` seam).
- `app/guide/{es,en}/ingreso-con-google.md` + `index.yaml` (topic 54) and the Google bullet in
  `ingreso.md`.

**Frontend**

- `components/GoogleSignInButton.tsx` (new): Google's four-colour mark inlined, light and dark
  variants from the resolved theme, 44 px, the same height as the Telegram button.
- `pages/SignIn.tsx`: the branded button, the generic refusal, the order kept.
- `api/google.ts` + `api/types.ts` (new types): the settings, rule and access shapes and the calls.
- `components/GoogleAdminCard.tsx` (new), mounted in `pages/admin/Security.tsx`: domains (with the
  env provenance), alta automática with default role and access, vincular por correo, the ordered
  rules editor (`group` greyed as *próximamente*) and the provider-off notice.
- `i18n/es.ts` + `en.ts`: every label of the button and the card; the three specific sign-in
  sentences removed.

## Convergence round 2 — what the second pass changed

The convergence run compared the delivered code with the spec, the plan and the constitution and
found six gaps; all six are fixed here (T029–T034):

- **T029 (CRITICAL): principle V was never amended.** The constitution still called Google sign-in
  *invite-only (it never creates or promotes a user)*, which is what this feature lifts. It is now
  **3.3.0** with a Sync Impact Report: automatic sign-up on the allowed domains (never a superuser,
  no password) and an ordered rule list that may decide role and access, never for superusers and
  never for existing accounts unless the installation asks. The plan's Constitution Check, the
  CHANGELOG entry and this report no longer claim "no change".
- **T030 (HIGH): the environment seed is validated.** `GOOGLE_ALLOWED_DOMAINS=https://www.getbizview.com;`
  used to be shown on the card as a domain while refusing every sign-in. Now the usable entries are
  kept, the rejects are reported (`domains_rejected`) and shown as a warning, and a seed that yields
  nothing admits **nobody** instead of falling back to "any domain". `valid_domain()` is shared by the
  seed and by `validate_settings`, so the card can no longer display a value it would refuse to save.
- **T031 (MEDIUM): the access is for `user` accounts.** Provisioning and rule application skip the
  grants when the outcome role is `admin` (it sees the catalogue by role), and the card says so under
  **Acceso por defecto**.
- **T032 (MEDIUM): a covered rule is marked.** A rule whose condition and value repeat an earlier
  enabled rule can never decide anything; the row carries "Tapada por la regla N" / "Shadowed by rule N".
- **T033 (MEDIUM): FR-012's second clause is asserted** — an admin resets a provisioned account's
  password, the account signs in with it, the forced change blocks everything else, and the Google
  link still works.
- **T034 (LOW): the unused `POST /api/testing/google-reset` is gone**, so the plan's "one test hook"
  is once again true.

The help topic gained the two sentences the card now carries (the rejected env value and the
`Usuario`-only access), in both languages.

## Verification

| Check | Command | Result |
| --- | --- | --- |
| Types | `npx tsc -b` | clean |
| Unit suite | `npx vitest run` | 68 files, **711 passed** (new: `google-signin-button.test.tsx`, `google-admin-card.test.tsx`; updated: `google-sign-in.test.tsx`, `no-raw-colors.test.ts`, `guide-drift.test.ts`) |
| Build | `npm run build` | ✓ built |
| Policy + callback | `pytest tests/test_google_rbac.py tests/test_google_sign_in.py` | **41 passed** (three new: the mis-typed seed, the admin without grants, the admin's password reset) |
| Admin matrix | `pytest tests/test_admin_matrix.py tests/test_migrations.py tests/test_audit_constraint_upgrade.py` | 32 passed (the matrix now covers the six new `/api/admin/google` operations; the constraint accepts every kind in `models.AUDIT_KINDS`) |
| Auth suite | `pytest tests/test_auth.py` | 1 pre-existing failure: `test_public_config_and_health` expects `/api/health` without the `ai` block that `bda8b1b` added — unrelated to this feature and untouched here |
| Guide | `pytest tests/test_guide.py tests/test_guide_api.py` | 12 passed (topic count 53 → 54) |
| Browser, the new flow | `npx playwright test tests/e2e/google-rbac.spec.ts --project=chromium-375` | **3 passed** again after round 2: provisioned account lands with the default role and its public dashboards, the admin's role survives the next sign-in, a foreign domain is refused with the generic sentence and `domain_not_allowed` in the audit, the card saves a domain and creates an email rule |
| Browser, the rest | — | not executed: the suite rebuilds a throwaway schema over the external database (6+ min per boot) and the other flows do not touch Google. `backend.sh` now sets `GOOGLE_AUTH_ENABLED`/`GOOGLE_CLIENT_ID`, which is the only shared file it touches |

## Decisions recorded in the spec

23 entries under *Decisiones tomadas (modo autónomo)* — four from `specify`, seven from `clarify`,
two from `analyze`, four from `implement`/`converge` (two of them superseding earlier ones, with the
reason) and five more from the convergence round (the amendment, the seed's fail-closed rule, the
`user`-only grants, the shadow hint and the dropped hook).

## Pending for the human

- Review the sign-in page and the card on a real installation with a Google client: the two button
  variants, and the card's rules list once a rule matches a real account.
- `tests/test_auth.py::test_public_config_and_health` still fails for the `ai` block in `/api/health`
  (from `bda8b1b`). It is a defect of that change, not of this one; fixing it means deciding whether
  the health payload keeps the block.
- The constitution is now **3.3.0**: the Auth bullet no longer says Google sign-in is invite-only.
  Worth a read before it becomes the baseline for the next feature that touches sign-in.
- `.env` on the development machine carries `GOOGLE_ALLOWED_DOMAINS=https://www.getbizview.com;`,
  which is now reported on the card instead of silently refusing everybody; the value should be the
  bare domain (`getbizview.com`). The file holds credentials and was left untouched.
- Nothing needs applying from this side: the migration runs on start, the policy defaults to feature
  027's behaviour (env domains, no provisioning), and `GOOGLE_ALLOWED_DOMAINS` keeps working as the
  initial value.
