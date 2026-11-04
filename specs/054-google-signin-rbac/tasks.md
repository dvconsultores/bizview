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
