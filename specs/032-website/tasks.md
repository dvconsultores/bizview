# Tasks — 032-website

Feature: [spec.md](./spec.md) · Plan: [plan.md](./plan.md) · Deploy:
[`docs/DEPLOY.md`](https://github.com/dvconsultores/bizview-site/blob/main/docs/DEPLOY.md)

The code lives in the private repository `dvconsultores/bizview-site` (plan D1); paths below are
relative to its root. The rows marked **owner** need a Vercel project, a Cloudflare zone, a demo
installation or a recording — none of which this environment has — and each one names the file that
already carries what it needs.

## Phase 1 — Foundations (FR-001, FR-002, FR-004, FR-012b, FR-014)

- [X] T001 `package.json`, `tsconfig.json`, `vite.config.ts`, `postcss.config.js`,
  `tailwind.config.js` importing the product's `theme`, `.gitignore` (FR-001, FR-002)
- [X] T002 `scripts/sync-tokens.mjs`: extract `:root` and the dark block from
  `frontend/src/index.css` into `src/tokens.css`, the dark theme written twice for a JS-free page (FR-002)
- [X] T003 `scripts/build-content.mjs`: merge the private overlay, compare key paths across
  languages, refuse empty strings and `___` placeholders, `--strict` requires prices and contacts (FR-004, FR-014)
- [X] T004 `content/{es,en}.json`: 101 keys each, identical shapes, copy grounded in the
  "what the product is today" list (FR-004, SC-007)
- [X] T005 `content/private.example.json`: the overlay shape, prices keyed by option id (FR-014)
- [X] T006 `vercel.json`: framework preset, `cleanUrls`, trailing slash, `/es/*` redirect,
  CSP / `X-Content-Type-Options` / `Referrer-Policy` / `Permissions-Policy` / HSTS, long cache for
  hashed assets (FR-012b)

## Phase 2 — US1: understand BizView on a phone (P1)

- [X] T007 `src/sections.tsx` `Header`: brand, four in-page links from lg up, language switch with
  `hreflang`, "Obtenerlo" call to action that fits a 360 px header (US1/AC1)
- [X] T008 `src/sections.tsx` `Hero`: eyebrow, headline, one sentence, **Ver demo** + **Instalar
  gratis**, and the counter row below the shot on phones so headline, actions and shot fit 375×667 (US1/AC2, SC-002)
- [X] T009 `src/components/PhonePreview.tsx`: the demo dashboard drawn with the tokens — status bar,
  app header, KPI row with deltas, bars, donut; donut and caption from 640 px up so the frame ends
  inside the first screen (FR-007 until the demo exists, plan D3)
- [X] T010 `src/seo.ts`: per-language title, description, canonical, `hreflang` pair, OG and Twitter
  tags, JSON-LD `SoftwareApplication` with AGPL and a free self-hosted price (FR-003, FR-010)

## Phase 3 — US2: see how it is made (P1)

- [X] T011 `src/sections.tsx` `How`: five steps, each in a card, with the template download beside
  them (FR-005, US2/AC1)
- [X] T012 The step that names the AI lists ChatGPT, Claude, DeepSeek, Gemini and Copilot as text and
  says "la IA que ya usas"; no vendor is required (US2/AC2, D8)
- [X] T013 `content.links.release` points at the published `bizview-starter-template.zip` release
  asset (FR-005, 057/046)

## Phase 4 — US3: choose how to get BizView (P1)

- [X] T014 `src/sections.tsx` `Pricing`: three options stacked on phones and side by side from lg,
  each with one action (FR-005, US3/AC1)
- [X] T015 `src/whatsapp.ts`: WhatsApp deep links with a message in the visitor's language per option,
  `mailto:` beside each one, `null` instead of a link to nowhere (FR-006, US3/AC2, US3/AC3)
- [X] T016 The consulting message asks which ERP and which source kind (FR-006)

## Phase 5 — US4: trust (P2)

- [X] T017 `src/sections.tsx` `Trust`: eight claims, each linking to the file that backs it, the link
  text derived from that path with `fileLabel` (US4/AC1)
- [X] T018 The section says "Funciona con la IA que ya usas"; there is no `claudeConnector` flag in
  the content schema (US4/AC2)

## Phase 6 — US5, US6: demo, features, FAQ, maintenance (P1–P2)

- [X] T019 `src/sections.tsx` `Features` (12 items), `Sources` (7 kinds + ERP chips), `Audience`,
  `Faq` (8 questions with native `<details>`), `Closing`, `Footer` (FR-005)
- [X] T020 Language switch is a link, the FAQ is `<details>`, dark mode is a media query: the page
  needs no JavaScript (FR-001, FR-009, D5)
- [X] T021 `src/content.ts`: typed accessors, translated anchors (`#como-funciona` ↔ `#how-it-works`),
  `home()` per locale, `fileLabel` (FR-003, FR-004)
- [X] T022 `content/private.json` is git-ignored and the strict build refuses a placeholder price or
  contact (FR-014, SC-005)

## Phase 7 — Delivery and documents

- [X] T023 `scripts/prerender.mjs` + `src/prerender.tsx`: both documents, sitemap, `robots.txt`,
  `noindex` on any non-production `VERCEL_ENV` (FR-001, FR-010, FR-012)
- [X] T024 `scripts/og.mjs` and `public/og/{es,en}.png`: the 1200×630 cards, drawn from the content
  file with the product's accent (FR-010, D7)
- [X] T025 `tests/`: content parity and empties, tokens drift, the document contract (no module
  script, one `<h1>`, canonical, hreflang, JSON-LD), copy lint over the components, contact links
  (FR-004, SC-001, SC-004, SC-006)
- [X] T026 `docs/DEPLOY.md`: Vercel project, environment variables, the Cloudflare → Vercel
  DNS table, verification commands, rollback, and the move to `bizview-site` (FR-019, FR-020)
- [X] T027 Root `README.md` / `README.es.md` point at `getbizview.com` instead of a domain the
  product does not own (FR-013)
- [X] T028 Measured at 375×667 and 360×780: no horizontal overflow, headline + both actions + whole
  phone shot inside the first screen, in both languages (SC-002)
- [X] T029 `npm test` 21 passed, `npm run typecheck` clean, `npm run build:preview` 240 kB with no
  JavaScript, `npm run build` refuses to run without `content/private.json` and publishes the prices
  when it is present (SC-003, SC-004) — re-run from a clean clone of `bizview-site`, where the tokens
  arrive through `PRODUCT_DIR`/`PRODUCT_THEME_TAG` instead of the sibling folder
- [X] T029a `vitest` scoped to `tests/**`: a product checkout inside `.product/` turned 4 test files
  into 77 and 66 failures the first time the site ran outside the product repository

## Phase 8 — Owner and ops (not implementable here)

- [X] T030 Extract the site into the private repository `dvconsultores/bizview-site` with
  `git subtree split --prefix=website` and push it; the folder then left the product repository in the
  same pass, before anything was pushed, so the public history never contained it (FR-014)
- [ ] T031 **owner** Create the Vercel project (framework Vite, build `npm run build`, output `dist`,
  Node from `engines`), set `PRODUCT_THEME_TAG`, `DEMO_URL` and the analytics key, add
  `content/private.json` from the secret store (FR-012, FR-012a)
- [ ] T031a **owner** Push the release tag the site should pin (`git push origin v0.2.0`), or set
  `PRODUCT_THEME_TAG` to a tag that already carries the 0.2.0 tokens: `v0.1.0` does not, and the build
  says so instead of failing in PostCSS (plan D6)
- [ ] T032 **owner** Cloudflare: apex `A 76.76.21.21` and `www` `CNAME cname.vercel-dns.com`, both
  DNS only; leave `bi` and the mail records alone; run the six `curl`/`dig` checks (FR-015–FR-020)
- [ ] T033 **owner** Deploy the demo installation (seeded generic data, read-only demo role, auto
  sign-in), set `DEMO_URL`, and replace the drawn `PhonePreview` with real screenshots by flipping
  `media.useMockups` (FR-007, US5)
- [ ] T034 **owner** Record the ≤ 30 s clip (fill `REQUEST.md` → AI → zip → import → dashboard on a
  phone), MP4 + WebM, ≤ 2 MB, poster, lazy (FR-008)
- [ ] T035 **owner** Lighthouse mobile ≥ 90 in the four categories on the deployed URLs, both
  languages, both themes (FR-009, SC-001)
- [ ] T036 **owner** Re-run `npm run og` and commit when the headline or the subtitle changes (D7)
- [ ] T037 **owner decision** Optionally add language auto-detection on `/` (one inline script +
  a CSP hash, plan's deviation note) if a non-Spanish visitor landing on Spanish copy turns out to
  matter more than `script-src 'none'`
