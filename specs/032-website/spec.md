# Feature Specification: BizView public website

**Feature Branch**: `032-website`

**Created**: 2026-10-13 · **Revised**: 2026-11-07 (aligned with the product as shipped through 057; hosting on Vercel behind Cloudflare DNS)

**Status**: Draft

**Input**: Owner, 2026-10-13: "build the web, same look and feel of the app, English and Spanish; I
will deploy a demo page with a demo dashboard". Owner, 2026-11-06: "update it based on all app
features". A single-page marketing site for BizView that looks like the product (050 design system,
047/051 themes), is available in Spanish and English, shows what the product does today — dashboards
authored outside the app with the AI you already use and imported as one zip — presents the three
ways to get BizView (install free, hosted, consulting/integration), links to the public repository,
the docs and a live demo, and converts through WhatsApp and email. Static: no backend, no accounts.

**Depends on**: the public repository (published); a demo installation (seeded data, read-only
demo user) deployed separately — the site only links to it; the published
`bizview-starter-template.zip` (057) to offer as a direct download.

**Repository**: the site lives in its own private repository (`bizview-site`), not in the public
product repository. It carries prices, contact details and marketing copy; AGPL covers the product,
not a site that links to it. No constitution amendment is needed.

## What the product is today (the site must say this, nothing older)

- **Authoring happens outside Bizview** with any AI — ChatGPT, Claude, DeepSeek, Gemini, Copilot,
  Claude Code — or by hand: Bizview hands you a starter zip (prompt, request template, your source's
  structure, schemas, a working skeleton), your AI returns one project zip, Bizview validates,
  imports, runs and renders it. There is **no chat inside the product** (045) and **no AI key is
  needed** to run it (constitution VIII). AI inside Bizview is optional and used for one thing:
  describing a source's structure ("Generar estructura con IA", 048/052) — never for reading rows.
- **Spec-driven**: every integration and report ships with its spec, plan and tasks; nothing runs
  without them (constitution IX). Projects are isolated (037), re-imported as revisions (055), with
  import allowances (049) and validation identical to the CLI (`bizview validate`).
- **Sources**: PostgreSQL (incl. Supabase), REST and SOAP, read-only, credentials never leave the
  installation; the structure pack carries no credentials, hosts or row values.
- **Dashboards**: mobile first; periods and comparison (previous period / previous year); filters;
  KPIs with delta and sparkline; bar, line, area, pie, donut, table, trend, ranking; visual
  components gauge, share, index and asset tiles with images (044); declarative web and PDF
  layouts (026); hover values and full-screen cards (056); themes per installation and per report,
  light/dark (047/051); auto-refresh (015); PDF and CSV export; `materialize: daily` for heavy
  sources.
- **Sharing**: expiring links, send by email with PDF, scheduled deliveries (018), mailing lists
  and any-address recipients (058 when shipped); Telegram sign-in (007) and Google sign-in with role
  rules (027/054); roles user / admin / superuser; 2FA; audit; security profiles private/internet.
- **Operations**: Docker Compose, two images, Watchtower upgrades, Caddy TLS; `bizview.yml`;
  health and version endpoints; i18n ES/EN across app, help and docs (022, 057b); in-app help.
- **Open source**: AGPL-3.0, source link on every page of the app (003).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand BizView in 30 seconds on a phone (Priority: P1) 🎯

A business owner lands from X or LinkedIn on their phone. In the first screen they see what BizView
is (their ERP's numbers on their phone, built with the AI they already use), a phone-frame screenshot
of a real dashboard (the demo's "Ventas por marca": KPI row, bars, donut), and the primary actions.
They can switch to English with one tap.

**Independent Test**: Lighthouse mobile ≥ 90 in performance and accessibility; hero, screenshot and
primary action visible at 375×667 without scrolling.

**Acceptance Scenarios**:

1. **Given** a Spanish browser, **When** the page loads, **Then** it is in Spanish with an "EN"
   switch; English browsers get English with "ES"; the choice is in the URL (`/`, `/en/`).
2. **Given** the hero, **Then** it shows the headline ("Tus indicadores, claros y a mano" — the same
   line as the app's sign-in), one sentence ("Describe el tablero a tu IA, importa el zip, míralo
   en el teléfono"), the phone-frame screenshot and two actions: **Ver demo** and **Instalar gratis**.
3. **Given** the clip, **When** in view, **Then** it plays muted and looped with a poster, ≤ 2 MB,
   ≤ 30 s, and shows the real flow: fill `REQUEST.md` → paste into an AI → zip → *Importar proyecto*
   → *Aplicar* → dashboard on a phone. Reduced-motion users get the poster.

---

### User Story 2 - See how it is made (Priority: P1)

A section "Cómo funciona" with five steps and one screenshot each: **1 Conecta tu fuente** (read-only,
credentials stay home) · **2 Descarga el paquete inicial** (what the zip contains, in one line) ·
**3 Dale el paquete a tu IA** (logos of ChatGPT, Claude, DeepSeek, Gemini, Copilot as text labels, not
trademarks) · **4 Importa el zip** (validation report, revisions) · **5 Míralo y compártelo**
(phone, PDF, email, link). A secondary action downloads `bizview-starter-template.zip` from the
public repository release.

**Acceptance Scenarios**:

1. **Given** step 2, **When** "Descargar plantilla" is pressed, **Then** it downloads the latest
   release asset from the product repository (URL in the content file).
2. **Given** step 3, **Then** no AI vendor is presented as required; the copy says "la IA que ya usas".

---

### User Story 3 - Choose how to get BizView (Priority: P1)

Three options side by side on desktop, stacked on phones: **Instálalo gratis** (open source, Docker
Compose, your server), **Nosotros lo alojamos** (monthly price per installation, from the content
file), **Lo conectamos a tu ERP** (consulting: structure, authoring, first dashboards, training).
Each has one action.

**Acceptance Scenarios**:

1. **Given** "Instálalo gratis", **Then** it opens the README install section (`docker compose -f
   bizview.yml up -d`).
2. **Given** "Nosotros lo alojamos" or "Lo conectamos", **Then** WhatsApp opens with a prefilled
   message in the visitor's language; the second asks which ERP and which source kind
   (PostgreSQL / REST / SOAP).
3. **Given** a desktop visitor, **Then** an email link is offered next to every WhatsApp action.

---

### User Story 4 - Trust: open, private, isolated (Priority: P2)

"Abierto y privado": AGPL-3.0 with source link; one installation and database per customer; origin
databases read-only; no AI key required and AI never reads your rows; structure packs without
credentials or data; personal-data columns excluded by default and declared when used; roles, 2FA,
audit, security profiles; sign-in with Google or Telegram. Each claim links to the file that backs
it (license, constitution, `docs/INSTALL.md` security section, 048/052 spec).

**Acceptance Scenarios**:

1. **Given** the trust section, **Then** every claim has a repository link and the links resolve
   (checked at build).
2. **Given** the content flag `claudeConnector`, **Then** the old "Funciona con Claude" block is
   removed from the content schema; the section says "Funciona con la IA que ya usas".

---

### User Story 5 - See it working (Priority: P2)

"Ver demo" opens the demo installation already signed in as a read-only demo user on "Ventas por
marca" (seeded generic data), with the Filtros/Parámetros sheet, PDF download and the full-screen
card available; a "Volver al sitio" link returns.

**Acceptance Scenarios**:

1. **Given** "Ver demo", **Then** it opens `DEMO_URL` from the content file in a new tab with
   `?lang=` matching the site language.
2. **Given** the demo is down, **Then** the site is unaffected.

---

### User Story 6 - Maintain it without touching code (Priority: P2)

Texts, prices, the ERP list, the feature list, screenshots and links live in `content/es.json` and
`content/en.json`; the site rebuilds in CI; a missing key in one language fails the build.

### Edge Cases

- 2G/3G: page ≤ 1.5 MB without the clip; AVIF/WebP with `srcset`; clip lazy.
- No JavaScript: content and links work; only language auto-detect and the clip need JS.
- Long ERP names and ES/EN length differences tested at 375 px in both languages.
- Dark mode follows the system with the product tokens; screenshots provided in both themes.
- Social preview: Open Graph and Twitter images per language, 1200×630, generated at build.
- Legal: footer links to the license and to the public **Privacidad** and **Términos** pages
  (`/privacidad/`, `/terminos/`, and `/en/privacy/`, `/en/terms/`); no cookie banner (cookieless
  analytics).

## Requirements *(mandatory)*

### Structure and stack
- **FR-001**: Private repository `bizview-site`, same frontend stack as the product (React, Vite,
  Tailwind), pre-rendered static HTML, no runtime API, no forms, no accounts.
- **FR-002**: Visual system from the product: the design tokens of 050 (`docs/DESIGN-SYSTEM.md`)
  and the default theme of 047/051, Lucide icons, the same button and card styles. The tokens are
  fetched at build from the public repository at a pinned release tag (`PRODUCT_THEME_TAG`); the
  build fails if the tag is missing.
- **FR-003**: Routes `/` (es), `/en/` (en), `/privacidad/` + `/en/privacy/` and `/terminos/` +
  `/en/terms/`; `hreflang` and canonical; section anchors mapped between languages
  (`#como-funciona` ↔ `#how-it-works`, `#precios` ↔ `#pricing`).

### Content
- **FR-004**: All copy, prices, ERP list, feature list, links (repo, docs, releases asset, demo,
  WhatsApp, email, X, LinkedIn) and flags live in `content/{es,en}.json`, validated against one
  schema; missing keys fail the build; zero hard-coded strings (lint).
- **FR-005**: Sections in order: hero · clip · **Cómo funciona** (5 steps) · **Qué incluye**
  (feature grid: mobile-first dashboards, visual components, themes, PDF/CSV, periods and
  comparison, sharing and email, sign-in options, revisions, validation = CLI, help ES/EN) ·
  **Fuentes** (PostgreSQL/Supabase, REST, SOAP + ERP templates list) · **Cómo lo obtienes** (3
  options) · **Abierto y privado** · **Para quién** (owner on the phone / IT that wants control /
  consultants who author for clients) · FAQ (8 questions, including "¿Necesito una clave de IA?"
  → no; "¿Qué IA puedo usar?" → any; "¿Ve la IA mis datos?" → only the structure you give it;
  "¿Puedo editar en la app?" → yes, the editor and re-import; "¿Cómo actualizo?" → Watchtower) ·
  footer.
- **FR-006**: Contact actions are WhatsApp deep links with prefilled messages per language and
  option, plus `mailto:`.

### Media
- **FR-007**: Screenshots come from the demo installation (generic seeded data; constitution: no
  customer names), both themes, phone frame in CSS. Required set: sign-in (Google + Telegram
  buttons), home tiles, "Ventas por marca" on a phone, full-screen card, Parámetros sheet, Proyectos
  with the import validation report, Fuentes structure screen, PDF page.
- **FR-008**: The clip is MP4 + WebM, ≤ 2 MB, muted, looped, lazy, poster, ≤ 30 s, showing the
  five-step flow of US2.

### Performance, accessibility, SEO
- **FR-009**: Lighthouse mobile ≥ 90 in all four categories; WCAG AA; keyboard; reduced motion.
- **FR-010**: Per-language title, description, Open Graph, Twitter cards, `sitemap.xml`,
  `robots.txt`, JSON-LD `SoftwareApplication` (license AGPL-3.0, free price for self-hosted).
- **FR-011**: Cookieless analytics (Plausible/Umami), none when the key is empty.
- **FR-011a**: Public privacy-policy and terms-of-service pages, in both languages, linked from the
  footer and listed in `sitemap.xml`, so Google's OAuth consent screen can be verified for external
  users. They are static documents (no hydration bundle), name the data controller, the Google
  scopes and data use, retention, sharing, user rights and a contact address, and carry their
  update date.

### Delivery
- **FR-012**: The site is hosted on **Vercel** as a static project connected to the private
  `bizview-site` repository: every push to `main` deploys production, every pull request gets a
  preview URL. Build command `npm run build`, output `dist/`, Node version pinned in
  `package.json` `engines`. No serverless functions, no edge middleware (the site is static).
- **FR-012a**: Build-time secrets and settings (`PRODUCT_THEME_TAG`, `DEMO_URL`, the analytics key)
  are Vercel environment variables, not committed; the build fails when `PRODUCT_THEME_TAG` is
  missing, as FR-002 requires.
- **FR-012b**: Vercel project settings: framework preset Vite; clean URLs on; trailing slash
  consistent with FR-003 (`/` and `/en/`); `vercel.json` carries the security headers
  (`Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`,
  `Permissions-Policy`) and long cache headers for hashed assets.
### Domain and DNS (Cloudflare → Vercel)
- **FR-015**: Vercel serves `getbizview.com` (canonical) and `www.getbizview.com` (301 to the apex).
  Both are added as domains of the Vercel project; Vercel issues and renews the TLS certificates.
- **FR-016**: DNS stays in Cloudflare. Records:
  - `getbizview.com` — `A` → Vercel's apex IP (`76.76.21.21`, or the value Vercel's domain screen
    shows at setup time), **DNS only (grey cloud)**.
  - `www` — `CNAME` → `cname.vercel-dns.com`, **DNS only (grey cloud)**.
  - `bi` — unchanged: the existing record to the Contabo installation (Caddy issues its own TLS
    there); this spec never edits it.
  - Existing `MX`, `TXT` (SPF/DKIM/DMARC) and verification records are kept.
- **FR-017**: Cloudflare proxy (orange cloud) is **off** for the two Vercel records. Reason: Vercel
  validates the domain and issues certificates against the origin; with the proxy on, SSL mode must
  be "Full (strict)" and Vercel's challenge can fail, and the site ends with two CDNs in front of a
  static page. If the owner later wants Cloudflare in front (WAF, analytics), it is turned on only
  with SSL/TLS mode **Full (strict)** and "Always Use HTTPS", and documented as a change.
- **FR-018**: No Cloudflare Page Rule or Redirect Rule is needed for the apex: Vercel serves it
  directly. The only redirect is `www` → apex, done in Vercel (project domain setting), not in
  Cloudflare, so there is one source of truth. If a legacy host previously served `getbizview.com`
  (GitHub Pages or other), its records are removed in the same change.
- **FR-019**: `docs/DEPLOY.md` in `bizview-site` records the Vercel project, the environment
  variables, the exact DNS table (host · type · value · proxy status), the owner of the Cloudflare
  zone and of the Vercel team, and the rollback procedure (promote the previous deployment in
  Vercel; DNS does not change on rollback).
- **FR-020**: Verification at launch: `dig getbizview.com A`, `dig www.getbizview.com CNAME`,
  `curl -I https://getbizview.com` (200, Vercel headers, HSTS), `curl -I https://www.getbizview.com`
  (301 → apex), `curl -I https://bi.getbizview.com` (still the Contabo installation, unchanged),
  and the site in both languages from a phone on mobile data.

- **FR-013**: The public README keeps the same hero (screenshot, one line, install commands) and
  links to the site; the README is the only marketing content in the public repository (046).
- **FR-014**: Public vs private: product repository = backend, worker, frontend, cli, deploy, docs,
  starter pack and template zip, demo seed; private = site, hosting scripts, paid templates,
  prices, contacts.

## Success Criteria *(mandatory)*

- **SC-001**: Lighthouse mobile ≥ 90 in all four categories, both languages, both themes.
- **SC-002**: Hero with screenshot and actions visible without scrolling at 375×667.
- **SC-003**: Page weight ≤ 1.5 MB without the clip, ≤ 3.5 MB with it.
- **SC-004**: 100 % of content keys in both languages (gate); 0 hard-coded strings (lint).
- **SC-005**: A content change reaches production with one commit and no code change.
- **SC-006**: Site and product share tokens at the pinned tag; reviewed once in both themes.
- **SC-007**: No sentence on the site describes a feature the product does not ship (checklist
  against CHANGELOG at release: the "What the product is today" list above is the source).
- **SC-008**: `https://getbizview.com` and `https://www.getbizview.com` resolve to the Vercel
  deployment with valid TLS (www redirects 301 to the apex); `https://bi.getbizview.com` still
  serves the Contabo installation; a push to `main` is live in under five minutes; a pull request
  produces a preview URL.
- **SC-009**: `docs/DEPLOY.md` matches the live Cloudflare zone and Vercel project (reviewed at
  launch and on every DNS change).

## Assumptions

- The demo installation is a normal BizView install with `SECURITY_PROFILE=internet`, seeded
  generic data (the Ventas por marca shape with invented brands and names), a read-only demo role
  and auto sign-in by link; specified separately; the site only needs its URL.
- Hosted pricing is one monthly figure per installation; tiers can be added in content later.
- Domain and analytics account exist before launch.
- `getbizview.com` is registered and its DNS is managed in **Cloudflare**; `bi.getbizview.com`
  already points to the production BizView installation on **Contabo** and is not touched by this
  spec.