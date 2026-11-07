# Tasks: Google button branding and role mapping

**Feature**: `054-google-signin-rbac` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Legend: `[P]` parallel-safe, `[US1]`…`[US5]` user story from the spec. Order is execution order; a
task is ticked only when it is implemented and its file exists.

## Phase 1 — the data the policy owns

- [x] T001 `backend/app/models.py`: `AppUser.password_hash` nullable and `auth_provider` (`password` |
      `google`, default `password`); `GoogleSettings` (singleton) and `GoogleRule`; six new
      `AUDIT_KINDS`
- [x] T002 `backend/alembic/versions/0051_google_rbac.py`: the two columns, the two tables, the
      recreated `audit_event.kind` constraint carrying 0050's list plus the six kinds
- [x] T003 `[P]` `backend/tests/test_migrations.py`: `APP_TABLES` gains `google_settings` and
      `google_rule`

## Phase 2 — one policy service

- [x] T004 `backend/app/services/google_policy.py`: `normalise_domains`, `settings(db)` (row or the
      env seed), `update_settings`, `rule_outcome(rules, identity)`, `access_for(db, access)`
      (materialises `none` / `all_public` / `list` into dashboard ids), `provision`, `apply_to_existing`
- [x] T005 `[P]` `backend/tests/test_google_rbac.py` (policy half): normalisation, env seed vs row,
      first-match ordering, case-insensitive email/domain, superuser exclusion, access materialisation

## Phase 3 — the admin API

- [x] T006 `backend/app/api/google_admin.py`: `GET/PUT /api/admin/google` (settings + dashboard
      catalogue), `GET/POST/PUT/DELETE /api/admin/google/rules`, `PUT .../rules/reorder`; superuser,
      step-up on writes, validation of role/mode/limits, `group` refused, audit per change
- [x] T007 `backend/app/main.py`: mount the router
- [x] T008 `[P]` `backend/tests/test_google_rbac.py` (API half): 403 for non-superusers, step-up
      required, reorder keeps positions contiguous, validation errors, audit entries

## Phase 4 — the callback (FR-010…FR-015)

- [x] T009 `backend/app/auth/google.py`: `Identity` carries `name` (from the ID token)
- [x] T010 `backend/app/api/oauth.py`: domain check through the policy, provisioning, rules for new
      and (when allowed) existing users, audit details `domain_not_allowed` / `no_user` /
      `provisioned` / `rule:<id>`
- [x] T011 `backend/app/api/auth.py`: password sign-in refuses an account with no hash through the
      same `INVALID` + throttle + audit path
- [x] T012 `[P]` `backend/tests/test_google_sign_in.py`: provisioning (first and second sign-in), a
      foreign domain, the generic codes, the password refusal, unchanged 027 behaviour with
      provisioning off

## Phase 5 — the sign-in screen

- [x] T013 `frontend/src/components/GoogleSignInButton.tsx`: the inline four-colour G, light and dark
      variants from the resolved theme, label prop, 44 px, same height as Telegram
- [x] T014 `frontend/src/pages/SignIn.tsx`: use the button, keep the Telegram icon, keep the order,
      map every refusal to the generic sentence (except a cancelled consent)
- [x] T015 `[P]` `frontend/tests/unit/google-signin-button.test.tsx`: both variants, the four brand
      paths, hidden when the provider is off, axe-friendly markup
- [x] T016 `frontend/tests/unit/no-raw-colors.test.ts`: the logo component joins the documented
      per-file exceptions

## Phase 6 — the Seguridad card

- [x] T017 `frontend/src/api/types.ts` + `frontend/src/api/google.ts`: settings, rule and dashboard
      types plus the calls
- [x] T018 `frontend/src/components/GoogleAdminCard.tsx`: domains, alta automática, rol por defecto,
      acceso por defecto (with the dashboard picker), aplicar a existentes, the ordered rules editor
      (add/edit/delete/move, `group` disabled as *próximamente*)
- [x] T019 `frontend/src/pages/admin/Security.tsx`: mount the card
- [x] T020 `[P]` `frontend/tests/unit/google-admin-card.test.tsx`: renders the settings, saves the
      domains, reorders a rule, shows the `group` row disabled

## Phase 7 — words and docs

- [x] T021 `frontend/src/i18n/es.ts` + `en.ts`: every label of the button and the card, and the
      generic failure
- [x] T022 `backend/app/i18n/es.py` + `en.py`: validation and audit-adjacent messages the API returns
- [x] T023 `backend/app/guide/{es,en}/ingreso-con-google.md` + `backend/app/guide/index.yaml`: the
      topic (033)
- [x] T024 `.env.example`: `GOOGLE_ALLOWED_DOMAINS` is the initial value only
- [x] T025 `CHANGELOG.md` under Unreleased: Added (branding, domains, provisioning, rules) and the
      `auth_provider`/nullable password note

## Phase 8 — the flow end to end

- [x] T026 `backend/app/api/testhooks.py`: `POST /api/testing/google-identity` overriding
      `google.exchange` (only with `BIZVIEW_TEST_HOOKS=1`)
- [x] T027 `frontend/tests/e2e/google-rbac.spec.ts`: provisioned user → default dashboards → admin
      changes the role → next sign-in keeps the admin's role
- [x] T028 Gates: `pytest` (the four suites), `tsc -b`, `vitest run`, `npm run build`

## Phase 9: Convergence

- [x] T029 **CRITICAL** Amend `.specify/memory/constitution.md` principle **V. Fixed Technology
      Stack, Auth** so it stops bounding Google sign-in as invite-only: number the provisioning
      (opt-in, allowed domain only, default role `usuario`/`admin`, never superuser) and the ordered
      rules that may change a role, keep every existing bound that still holds (off by default,
      per-installation OAuth client, the `internet` profile's second factor, password sign-in
      unchanged), add the Sync Impact Report (MINOR, trigger: owner brief 2026-11-04) and bump the
      version; then correct the "Constitution: no change" line in `spec.md`, `plan.md`, the CHANGELOG
      entry and `run-report.md` per Constitution V (contradicts)
- [x] T030 Validate the environment seed in `app/services/google_policy.py`: pass
      `Settings.google_domains` through the same domain validator `validate_settings` uses and keep
      only what it accepts (or report the rejects on the card) so `public_settings` can never display
      a domain the API would refuse to save — `https://www.getbizview.com;` currently makes every
      Google sign-in fail with `domain_not_allowed` while the card looks healthy; add a backend test
      for a rejected seed per FR-004 and US2/AC1 (partial)
- [x] T031 Grant the provisioning access only to `user` accounts and say so on the card: skip
      `grant()` in `provision()` when the resolved role is `admin` (admins see the whole catalogue by
      role, and the edge case says the new admin has no dashboards of their own), and add the
      one-line label under **Acceso por defecto** stating it applies to `usuario` accounts per the
      spec's Edge Cases and the [clarify] decision (contradicts)
- [x] T032 Warn about a shadowed rule in `frontend/src/components/GoogleAdminCard.tsx`: a rule whose
      condition and value repeat an earlier enabled rule never decides anything, so mark it on the row
      with a hint (i18n es/en) instead of letting it look active per the spec's Edge Cases (missing)
- [x] T033 Assert FR-012's second clause in `backend/tests/test_google_rbac.py`: an admin resets the
      password of a provisioned account through `POST /api/admin/users/{id}/password`, the account
      then signs in with it, `must_change_password` forces the change, and the Google link is untouched
      per FR-012 and the [analyze] decision that claims this flow is already asserted (missing)
- [x] T034 Justify or drop `POST /api/testing/google-reset` in `backend/app/api/testhooks.py`: either
      restore the `google.client` seam from it after the e2e suite (so the hook is the one the plan
      counts) or delete it, since nothing references it per the plan's test-hook scope (unrequested)

## Convergence 059 — sign-in on a phone (2026-11-06)

Feature 059 changed the layout of `/ingresar` below 640 px and the two-provider row; the 054 contract
(real mark, equal height, `type=button`, the start endpoint) is unchanged.

- [x] C059-1 `frontend/src/pages/SignIn.tsx`: the hero is the page header on a phone (logo 40 px,
      product name 18 px, organisation 12 px, tagline only from 600 px of height), the card no longer
      overlaps it and starts below it, and the root is `min-h-dvh` with `scroll-pb-32`.
- [x] C059-2 The language toggle left its absolute position over the product name: it is a compact
      segmented control under the header, right aligned.
- [x] C059-3 `GoogleSignInButton` gained `compact`: brand mark + `google.signInShort`, with
      `aria-label={google.signIn}` so the accessible name is still the full sentence. Google and
      Telegram share one `grid-cols-2` row when both are enabled (`telegram.signInShort` for the
      Telegram button) and take the full width when only one is.
- [x] C059-4 `Input`/`PasswordField`/`Select` are 44 px under 640 px (`max-sm:min-h-11`), and the email
      field now declares `autocomplete="email"` (it was `username`), the password
      `current-password`.
- [x] C059-5 `frontend/tests/unit/sign-in-phone.test.tsx` and the `sign-in on a phone` cases of
      `frontend/tests/e2e/mobile-first.spec.ts` pin the layout; the 054 tests
      (`google-sign-in.test.tsx`, `google-signin-button.test.tsx`, `e2e/google-rbac.spec.ts`) still pass.
