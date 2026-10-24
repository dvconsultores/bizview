# Feature Specification: BizView public website

**Feature Branch**: `032-website`

**Created**: 2026-10-13

**Status**: Draft

**Input**: Owner, 2026-10-13: "build the web, same look and feel of the app, English and Spanish; I
will deploy a demo page with a demo dashboard". A single-page marketing site for BizView that looks
like the product (feature-010 visual system), is available in Spanish and English, presents the three
ways to get BizView (install free, hosted, consulting/integration), links to the public repository and
to a live demo installation, and converts through WhatsApp and email. Static: no backend, no accounts.

**Depends on**: the public repository being published; a demo installation (seeded data, read-only
demo user) deployed separately — the site only links to it. The "Funciona con Claude" section depends
on 016 and is hidden until it ships.

**Repository**: the site lives in its own private repository (`bizview-site`), not in the public
product repository. It carries prices, contact details and marketing copy, which are not part of the
product; AGPL covers the product and its modifications, not a site that links to it. The product
repository stays public and unchanged, so no constitution amendment is needed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand BizView in 30 seconds on a phone (Priority: P1) 🎯

A business owner lands from X on their phone. In the first screen they see what BizView is (their
ERP's sales on their phone), a phone screenshot of a real dashboard, and a short clip of the chat
building a report. They can switch to English with one tap.

**Why this priority**: the site exists to turn X traffic into installs and conversations.

**Independent Test**: Lighthouse mobile ≥ 90 in performance and accessibility; the hero, the
screenshot and the primary action are visible at 375×667 without scrolling.

**Acceptance Scenarios**:

1. **Given** a visitor with a Spanish browser, **When** the page loads, **Then** it is in Spanish, with
   an "EN" switch; an English browser gets English with an "ES" switch; the choice is kept in the URL
   (`/` and `/en/`) so links can be shared in either language.
2. **Given** the hero, **When** it renders, **Then** it shows the headline, one sentence, a phone-frame
   screenshot of the dashboard, and two actions: "Ver demo" and "Instalar gratis".
3. **Given** the chat clip, **When** it is in view, **Then** it plays muted, loops, has a poster image,
   and weighs under 2 MB; reduced-motion users get the poster only.

---

### User Story 2 - Choose how to get BizView (Priority: P1)

The visitor sees three options side by side on desktop, stacked on phones: install it yourself
(free, open source), have Global DV host it (monthly price), or have Global DV connect it to their
ERP (consulting). Each has one action.

**Acceptance Scenarios**:

1. **Given** "Instálalo gratis", **When** pressed, **Then** it opens the repository README section with
   the install commands (and the "Deploy on Railway" button when available).
2. **Given** "Nosotros lo alojamos", **When** pressed, **Then** it opens WhatsApp with a prefilled
   message in the visitor's language ("Hola, quiero BizView alojado"); the price shown comes from the
   content file, not from code.
3. **Given** "Lo conectamos a tu ERP", **When** pressed, **Then** it opens WhatsApp with a prefilled
   message that asks which ERP they use.
4. **Given** a desktop visitor without WhatsApp, **When** they press any contact action, **Then** an
   email link is offered next to it.

---

### User Story 3 - Trust: open source, private, isolated (Priority: P2)

A cautious IT person wants to know where the data goes. A section states: AGPL-3.0 license with a
link to the source, each customer in its own installation and database, origin databases read-only,
AI optional with a local-model option, and (when 016 ships) "works with Claude".

**Acceptance Scenarios**:

1. **Given** the trust section, **Then** every claim links to the file in the repository that backs it
   (license, constitution, security profile docs).
2. **Given** the feature flag `claudeConnector` is off, **Then** the "Funciona con Claude" block is not
   rendered at all (not hidden with CSS).

---

### User Story 4 - See it working (Priority: P2)

The visitor presses "Ver demo" and lands on the demo installation already signed in as a read-only
demo user, on the sales dashboard with seeded data. From the demo's top bar a "Volver al sitio" link
returns to the site.

**Acceptance Scenarios**:

1. **Given** "Ver demo", **When** pressed, **Then** it opens `DEMO_URL` from the content file in a new
   tab, with `?lang=` matching the site language.
2. **Given** the demo is down, **Then** the site is unaffected (no runtime dependency); the link just
   fails on the demo side.

---

### User Story 5 - Maintain it without touching code (Priority: P2)

The owner edits texts, prices, the ERP list, screenshots and links in content files, in both
languages, and the site rebuilds in CI.

**Acceptance Scenarios**:

1. **Given** `content/es.json` and `content/en.json`, **When** a key is missing in one language,
   **Then** the build fails naming the key.
2. **Given** a change on `main` of `bizview-site`, **Then** GitHub Actions builds and publishes the
   static output; the product repository is not involved.

### Edge Cases

- Visitors on 2G/3G: total page weight under 1.5 MB excluding the clip; images in AVIF/WebP with
  width-based `srcset`; the clip loads lazily.
- No JavaScript: all content and links work; only the language auto-detect and the clip autoplay
  need JS.
- Very long ERP names and English/Spanish length differences: layouts tested at 375px in both
  languages.
- Dark mode: follows the system like the app (feature-010 tokens); screenshots are provided in both
  themes or shown in a neutral frame.
- Social preview: Open Graph and Twitter card images per language, 1200×630, generated at build.
- Legal: footer links to the license, privacy notice and the Global DV company page; no cookie
  banner because no cookies are set (analytics is cookieless).

## Requirements *(mandatory)*

### Structure and stack
- **FR-001**: The site lives in the private repository `bizview-site` and is built with the same
  frontend stack as the product (React 19, Vite, Tailwind) as static HTML (pre-rendered), with no
  runtime API, no forms, no accounts.
- **FR-002**: It MUST reuse the product's visual system: the Tailwind theme and tokens (colors, type
  scale, radius, spacing, light/dark), the same icon set (Lucide) and the same button and card
  styles, so a visitor who opens the demo sees the same product. The theme file is NOT copied: the
  site build fetches `frontend/src/theme.*` from the public product repository at a pinned release
  tag (`PRODUCT_THEME_TAG` in the site config) and fails if the fetch or the tag is missing. Updating
  the look is a tag bump, so a product redesign never breaks the site on the day it ships.
- **FR-003**: Routes: `/` (es) and `/en/`; `hreflang` and canonical tags for both; the language switch
  keeps the section (`#precios` ↔ `#pricing` mapped).

### Content
- **FR-004**: All copy, prices, ERP list, links (repo, demo, WhatsApp number, email, X profile) and
  feature flags live in `content/{es,en}.json`; the build validates both files against one schema
  and fails on missing keys.
- **FR-005**: Sections in order: hero; chat clip; "Cómo lo obtienes" (three options); supported
  sources (PostgreSQL, REST, SOAP, plus the ERP templates list); "Abierto y privado" trust section;
  "Funciona con Claude" (flag); FAQ (6–8 questions); footer.
- **FR-006**: Contact actions are WhatsApp deep links (`wa.me`) with prefilled messages per language
  and option, plus `mailto:` alternatives.

### Media
- **FR-007**: Hero screenshot and section images come from the demo installation (generic seeded
  data; constitution VII: no customer names). Phone frame rendered in CSS, not baked into images.
- **FR-008**: The chat clip is an MP4 (H.264) + WebM, ≤ 2 MB, muted, looped, lazy, with poster; max
  30 s.

### Performance, accessibility, SEO
- **FR-009**: Lighthouse mobile ≥ 90 on performance, accessibility, best practices, SEO; WCAG AA
  contrast on both themes; keyboard-reachable actions; `prefers-reduced-motion` respected.
- **FR-010**: Per-language `<title>`, meta description, Open Graph and Twitter cards, `sitemap.xml`,
  `robots.txt`, JSON-LD `SoftwareApplication`.
- **FR-011**: Cookieless analytics (Plausible or Umami script, configurable in content; none when
  the key is empty).

### Delivery
- **FR-012**: GitHub Actions workflow in `bizview-site` builds and publishes the static output
  (GitHub Pages or Railway static service, chosen in the plan); custom domain with HTTPS.
- **FR-013**: The README of the public product repository MUST show the same hero (screenshot, one
  line, install commands) and link to the site, so GitHub visitors get the same first impression.
  The README is the only marketing content that lives in the public repository.
- **FR-014**: What stays public vs private: the product repository holds backend, worker, frontend,
  cli, deploy, docs, the workspace template, free templates and the generic demo seed data; the
  private repository holds the site, Railway provisioning scripts, paid templates and anything with
  prices, contacts or customer specifics.

## Success Criteria *(mandatory)*

- **SC-001**: Lighthouse mobile ≥ 90 in all four categories, both languages, both themes.
- **SC-002**: First screen (hero with screenshot and actions) visible without scrolling at 375×667.
- **SC-003**: Page weight ≤ 1.5 MB without the clip, ≤ 3.5 MB with it, on first load.
- **SC-004**: 100% of content keys present in both languages (build gate); 0 hard-coded strings in
  components (lint rule).
- **SC-005**: A content change (price, ERP added) reaches production with one commit and no code
  change.
- **SC-006**: Visual check: side-by-side screenshots of the site and the product share tokens
  (colors, type, radius) — asserted by the build fetching the product's theme file at the pinned tag,
  and reviewed once in both themes.

## Assumptions

- The demo installation is a normal BizView install with `SECURITY_PROFILE=internet`, seeded generic
  data, a read-only "demo" role and auto sign-in by link; it is specified separately (026-demo) and the
  site only needs its URL.
- Pricing for the hosted option is a single monthly figure per installation for now; tiers can be
  added to the content file later without a code change.
- Domain and analytics account exist before launch; both are configuration.