# Implementation Plan: BizView public website

**Branch**: `main` (feature `032-website`) | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

**Where the code is**: the private repository `dvconsultores/bizview-site`. This folder holds the
product's record of the feature — what it must do, how it was decided, what is left — while the site's
own `docs/DEPLOY.md` holds the operations. Every path below is relative to that repository's root.

## Summary

A marketing site that looks like the product and is finished markup: two pre-rendered documents
(`/` in Spanish, `/en/` in English), one stylesheet, no JavaScript at all. The language switch is a
link, the FAQ is `<details>`, and dark mode arrives through `prefers-color-scheme` with the product's
own tokens — the page renders correctly before any byte of script would have run, because there is
none. All copy, prices, links and flags live in `content/{es,en}.json`, validated against one schema,
so a text change is a commit and no code change (SC-005).

## Technical Context

**Stack**: React 19 + Vite 8 + Tailwind 3.4 (the product's own `tailwind.config.js`), TypeScript,
`vitest` for the contract tests, Playwright only for the optional OG-card script.

**Rendering**: `vite build` for the hashed stylesheet, `src/prerender.tsx` renders both routes with
`renderToStaticMarkup`, `scripts/prerender.mjs` writes `dist/index.html` and `dist/en/index.html`
over the template and deletes the JavaScript chunk. `sitemap.xml` and `robots.txt` are written last;
a non-production `VERCEL_ENV` gets `Disallow: /`.

**Tokens**: `scripts/sync-tokens.mjs` extracts the `:root` and dark-theme blocks from
`frontend/src/index.css` into `src/tokens.css`, and `tailwind.config.js` imports the product's
`theme` object directly. `tests/tokens.test.ts` re-runs the extraction and fails on drift (SC-006).

**Content**: `scripts/build-content.mjs` merges the optional private overlay, checks that both
languages have the same key paths, refuses empty strings and template placeholders, and in
`--strict` (what `npm run build` runs) requires the hosted price, the consulting price, the WhatsApp
number and the email address. `src/content.generated.json` is the only file the components read.

**Deliverable shape**: the repository root — `npm ci && npm run build` produces `dist/`, which is
what `vercel.json` publishes.

### Layout and weight

| | |
|---|---|
| Documents | 2 × ~48 kB of HTML |
| Stylesheet | 26 kB, one file, no code splitting |
| Social cards | 2 × ~43 kB PNG |
| Total | ~240 kB, no JavaScript, no web font, one round trip (SC-003: ≤ 1.5 MB) |

## Constitution Check

| Principle | How it is satisfied |
|---|---|
| Mobile first | The page is written at 375 px first and every section is a single column there; the hero shows head­line, both actions and the phone shot inside 375×667 (measured, SC-002). |
| No product claim the build does not ship | The copy list is checked against CHANGELOG at release (SC-007); the site says "authoring happens outside BizView", never that the product chats. |
| Tokens, no literals | Colours, radii and shadows come from the product's tokens; components use the same `.card` / `.btn-*` shapes as the app. |
| i18n | Two content files, same key set, `hreflang` pair, translated anchors, language switch in the header. |
| No secrets in the repository | Prices and contacts live in the git-ignored `content/private.json`; the strict build refuses to ship without them. |
| Tests before merge | 21 unit/contract tests: content parity, tokens drift, document contract, copy lint, contact links. |

## Decisions

**D1 — the site lives in the private `bizview-site` repository.**
It was written inside the product repository and extracted with `git subtree split`, which carried the
folder's history across, *before* anything was pushed: the public history never contains a file of it,
so nothing about prices or contacts can be downloaded with the AGPL code. The only link back is the
product's two token files, resolved at a pinned tag (`D6`).

**D2 — prices and contacts are an overlay, not content.**
`content/es.json` and `content/en.json` hold the structure (`pricing.options`, `pricing.prices` keyed
by option id) with `null` for the two paid prices and the contact details. `content/private.json`
(git-ignored, shape in `content/private.example.json`) fills them. `npm run build` fails while any of
them is null, so a deployment cannot publish "___ / mes", and the public repository cannot carry a
customer's number.

**D3 — the hero art is drawn, not photographed.**
FR-007 wants screenshots of the demo installation; the demo is a separate deployment that does not
exist yet, and a wrong or stale picture is worse than an honest drawing. `PhonePreview` draws the
demo's "Ventas por marca" (KPI row, bars, donut) with the product's tokens at phone width, so it
stays correct as the tokens change and weighs nothing. `media.useMockups` in the content file is the
switch: when `public/shots/phone.png` exists, the component renders the real screenshot instead.

**D4 — no web font.**
The product's stack starts with Plus Jakarta Sans and falls back to the system UI. Requesting the
font would add a render-blocking round trip for a page whose whole budget is one; the fallbacks are
visually close and Lighthouse mobile stays clean.

**D5 — no JavaScript, including for the language switch and the FAQ.**
`/` and `/en/` are two documents, the switch is an `<a>` with `hreflang`, the FAQ is `<details>`, and
dark mode is a media query over the same token block. This is what makes "works without
JavaScript" true rather than aspirational, and it is why the CSP can say `script-src 'none'`.

**D6 — the tokens come from the product at a pinned tag.**
`scripts/product-source.mjs` resolves them in order: `PRODUCT_DIR`, the sibling `../frontend` (while
the site sat inside the product repository), then `PRODUCT_THEME_TAG` — a shallow `git` clone of the
tag, with `raw.githubusercontent.com` as the fallback when `git` is absent. A build with none of the
three fails, and so does one whose tag predates the 0.2.0 tokens, with a sentence naming the tag.
`scripts/sync-tokens.mjs` and the Tailwind config read the materialised copy in `.product/`, so the
same code runs in both repositories; the drift test is the gate.

**D7 — the social cards are committed, not generated on deploy.**
`npm run og` renders both 1200×630 cards from the same content file with Playwright. Generating them
during the Vercel build would add a browser download to every deploy for two files that change only
when the headline does.

**D5b — no automatic language detection** (see the deviation below): the cost of one inline script
outweighs the one tap it saves.

**D8 — the "How it works" step 3 names no required vendor.**
The step lists ChatGPT, Claude, DeepSeek, Gemini and Copilot as plain text labels — never as
requirements, never with their marks, and the sentence around them says "la IA que ya usas"
(US2/AC2). There is no `claudeConnector` flag anywhere in the content schema (US4/AC2).

## Not implemented here — needs the owner or a different environment

| Spec item | Why | Where it is tracked |
|---|---|---|
| FR-001/FR-014, private `bizview-site` repository | Done: `git subtree split`, pushed, folder removed from this repository before the push | T030 |
| FR-012, the Vercel project and its environment variables | Needs Vercel account access | T031 |
| FR-015–FR-020, the Cloudflare records and the launch checks | Needs the Cloudflare zone | T032, `docs/DEPLOY.md` has the exact table |
| FR-007, real screenshots of the demo | The demo installation does not exist yet | T033 (D3 leaves the switch in place) |
| FR-008, the ≤ 30 s clip | Needs the demo and a recording | T034 |
| `DEMO_URL` | Same | T033; the content file points at the installation today |

**One deliberate deviation.** US1/AC1 says an English browser gets English automatically. Doing that
without a server means a script that reads `navigator.language` and rewrites the URL — which would
undo D5 (a finished document, `script-src 'none'`) and introduce a redirect loop unless the language
switch carries an exception. The site keeps the no-JavaScript property and defaults to Spanish, with
the switch one tap away in the header and both documents linked by `hreflang`; a visitor on a
non-Spanish browser lands on `/` and reads the "EN" button. If the owner prefers auto-detection, it is
one inline script on both documents plus a `sha256` hash in the CSP — recorded as T037 and not taken
here.

## Structure

```
index.html                   the template the pre-renderer fills (`@head`, `@app`)
  vercel.json                build, redirects, security headers, cache policy (FR-012b)
  content/{es,en}.json       all copy, prices structure, links, flags (FR-004)
  content/private.example.json  the overlay shape (FR-014)
  public/og/{es,en}.png      the social cards (FR-010)
  scripts/sync-tokens.mjs    product tokens → src/tokens.css (FR-002)
  scripts/build-content.mjs  merge + validate, strict for production (FR-004, FR-014)
  scripts/prerender.mjs      both documents, sitemap, robots (FR-001, FR-010)
  scripts/og.mjs             the social cards (FR-010)
  src/content.ts             the typed accessors, anchors per language, `fileLabel`
  src/sections.tsx           hero · how · features · sources · pricing · trust · audience · faq · closing
  src/seo.ts                 head tags, JSON-LD, sitemap, robots
  src/prerender.tsx          `renderDocument` — the two documents as strings
  src/components/            `Icons`, `PhonePreview`
  tests/                     content parity, tokens drift, document contract, copy lint
  docs/DEPLOY.md             Vercel, env vars, DNS table, rollback, moving out (FR-019)
```
