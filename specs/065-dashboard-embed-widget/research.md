# Research — 065 dashboard embed widget

Feature 018 is the reference: tokens hashed with SHA-256, a sessionless read-only door, per-address
throttling, and the report rendering behind it. The questions below are the ones where 065 could
have gone two ways; each answer is what the code does.

## R1 — A widget is a new table, not a new kind of share link

**Decision**: `dashboard_widget` + `dashboard_widget_site`, with their own key hash.

**Why**: `share_link.expires_at` is `NOT NULL` with `CHECK (expires_at > created_at)`, and the
service enforces 1..90 days. A widget has **no expiry by default** and an optional date. Adding a
`kind` column would make `expires_at` nullable, change the `expiry` check, and rewrite
`links.counted_active` — the function that also counts pending email sends and excludes subscription
links. That is the behaviour the brief says must stay exactly as it is (90 days, 20 links), and it is
covered by a suite that would have to be re-read rather than left alone. A widget also carries data a
share link does not (allowed sites, appearance options, a request ceiling) and lacks data it has (a
note, an email/subscription origin, the first-load theme rule).

**Consequence**: the sharing screen shows two counters (20 links, 50 widgets) that never mix, and
`backend/tests/test_sharing_links.py` runs unchanged — itself the proof that 018 did not move.

## R2 — The framing permission is decided by the backend and copied by Caddy

Browser framing is decided by the framed **document** (`frame-ancestors` / `X-Frame-Options`). The
document is the SPA, served by Caddy, and Caddy cannot know which widget a key belongs to. Three
shapes were possible:

1. **A global exception** — `frame-ancestors *` (or the listed hosts) for `/w/*` in the Caddyfile.
   Refused: it is exactly the weakening the brief forbids; it would let any site frame any key, and it
   keeps the permission away from the widget.
2. **The backend serves the document** — it would have to ship the SPA build and render HTML, which
   the constitution forbids ("no HTML rendering from the API", and Caddy is the edge that serves the
   app).
3. **Caddy asks the backend, then serves the file** — `forward_auth` on `/w/*` calls
   `GET /api/widgets/frame/<key>` (Caddy's `uri` joins the stripped path), the backend answers `200`
   with the CSP computed **from that widget's sites**, and Caddy copies `Content-Security-Policy`,
   `X-Robots-Tag` and `Cache-Control` onto the static response. Chosen.

`forward_auth`'s `copy_headers` copies the answer's headers onto the **request** (Caddy's design:
they are meant for an upstream), so two `header` directives after it put those values on the response,
and a `route` block keeps that order (Caddy's default order would run `try_files` first and rewrite
`{uri}` to `/index.html`). Before the answer arrives, `/w/*` already carries the site-wide
`frame-ancestors 'none'`, and the replacement is conditional on the answer actually carrying a policy:
failing closed is structural, not a convention. `deploy/tests/test_caddy_widget.sh` runs a real
`caddy:2-alpine` against a stub backend and asserts all of it, including that a client cannot forge
the header it would be copied from.

The default refusal is not removed: it is scoped with `@not_widget not path /w/*`, so every other
path keeps the exact header pair it has today. The backend's `/frame` endpoint **always** answers
`200`: an unknown key gets `frame-ancestors 'none'`, so the failure mode is "nothing is framed", never
"anything is framed". A known widget that is revoked, expired or withdrawn keeps its listed origins
(so the host page can render the neutral message) while its data endpoints answer the neutral `404`.

`X-Frame-Options` is not sent on the widget document: modern browsers give `frame-ancestors`
precedence, and the value browsers understand for an allow-list (`ALLOW-FROM`) is obsolete; sending
`DENY` there would contradict the CSP. Every other route keeps both headers.

The CSP string is duplicated (Caddy's default for other routes, the backend's for a widget). A test
compares the two and fails on drift (`test_widget_csp_matches_the_edge_default`).

## R3 — The widget never touches the session

- The API surface (`/api/widgets/...`) has **no auth dependency**; it is mounted like `/api/shared/`
  and the middleware marks it public (`X-Robots-Tag`, `no-store`, `no-referrer`).
- The shell's `/api/me` bootstrap is skipped on `/w/*` (`AuthProvider.isWidgetPage`; the share-link
  page keeps the behaviour it had in feature 018). The locale and theme providers are nested inside `AuthProvider`, so the page is
  still *inside* it — but no request carries the viewer's cookie, which is the property FR-010 asks
  for. The browser test asserts that no `/api/me` request is made by the widget document.
- The test that matters: an admin's session cookie on a widget request returns byte-identical output
  to an anonymous request (and no `Set-Cookie` is emitted).
- The framed document never learns the widget's list of sites (review, second pass): it asks with
  `?parent=<the origin in document.referrer>` and gets that origin back only when the list allows it,
  so the sizing message still reaches only an allowed parent while one widget serving two customers
  publishes neither domain. The snippet's iframe asks the browser for `referrerpolicy="origin"` so a
  host page's own policy cannot hide it.

## R4 — The test page uses a signed preview ticket, not the key

FR-002 says the snippet is shown only at creation and at replacement; FR-011 says the key is stored so
a database copy does not reveal it. If the test page framed `/w/<key>`, the product would have to
keep the key recoverable for ever. Instead:

- the key is stored as SHA-256 only, exactly like a share-link token (cannot be recovered);
- the backend signs a short-lived ticket `pv.<widget id>.<expiry>.<hmac>` with
  `BIZVIEW_SECRET_KEY` (30 minutes); `POST …/widgets/{id}/frame` returns the URL
  `/w/pv.…`;
- the widget resolver accepts either a key or a ticket, so preview goes through **the same
  sessionless code path** (and therefore proves FR-010 and US2 story 5);
- preview mode does not increment the usage figures (FR-019) and its framing allowance is
  `frame-ancestors 'self'`, so the in-product test page works with no external site listed.

Tickets are not a second permanent door: they cannot be minted without an admin session, they expire,
and they are refused for a widget that is not active. The `.` in a ticket cannot appear in a key
(`secrets.token_urlsafe` alphabet), so the two token kinds are unambiguous.

## R5 — The request ceiling: 300 requests per minute per widget

The spec leaves the number open and requires it to be an installation setting (FR-015). Chosen:
**`WIDGET_RATE_LIMIT=300`** requests per widget per minute, across all visitors.

Reasoning: one visitor's first paint is one definition request plus one data request (two filters
load their options lazily); a visitor who plays with the period and two filters costs a handful more.
Three hundred a minute is roughly **5 requests per second sustained** — dozens of simultaneously
active visitors — while a scripted loop against a copied key is cut off within seconds. It is high
enough that ordinary use never notices and low enough that one leaked key cannot compete with the
installation's signed-in readers (SC-009). It is bounded (1..100 000) so an operator can raise it for
a very busy public page or lower it for a sensitive one.

Mechanism: the counter lives on the widget row (`rate_window_start`, `rate_count`) and is bumped with
one atomic `UPDATE … RETURNING` per request, so it is exact across Uvicorn workers (an in-process
counter, like `throttle.public_check`, would be N× the configured ceiling). The update touches one
row per widget, so a hammered widget locks only its own row and never the signed-in dashboards.
The visitor gets `429 rate_limited` with `retry_after_seconds`, which the widget page renders as
"try again in a moment" inside the host page (the host page is unaffected).

The per-address limits of 018 still apply on top (`throttle.public_check`), and guessing an unknown
key still counts as a share-link failure (`throttle.share_register_failure`), so a widget cannot be
used to launder key guessing.

**Not counted**: `/frame` (the document decision) and the image/asset routes. The former must never
fail, or the host page would show a broken navigation instead of the widget's own message; it is a
header-only answer with one lookup. The latter serve files already on disk: the ceiling exists for the
report queries that use the database (SC-009), and a dashboard with image tiles makes dozens of picture
requests per view. The image routes keep the per-address limits and every validity check. Measured on
the layout report: 2 counted requests + 54 picture requests per page view (see the second pass in
[run-report.md](./run-report.md)).

## R6 — Allowed sites are canonical origins

A site is `scheme://host[:port]`, lowercased, default port omitted. Refused: no scheme, a scheme other
than `http`/`https`, a path (other than `/`), a query, a fragment, user info, a wildcard anywhere
(including `*` alone), an empty or malformed host, an invalid port. At least one site is required at
creation and at most 10 (FR-009); duplicates after canonicalisation collapse into one.

`http` is accepted on purpose: the spec's own edge case says a host page can be HTTP, and the
installation's own security profile decides whether the product itself may be. The entry must match
the scheme the host page really uses — `http://localhost:5173` and `https://example.com` are
different origins, and a mismatch shows nothing, as the spec requires.

Development mark: `localhost`, `*.localhost`, and loopback/private IP addresses (RFC 1918, `::1`,
`169.254/16`, `fc00::/7`) are stored with `development = true` and shown with a badge wherever the
sites are listed (FR-020).

## R7 — Appearance options

`theme`: `light`, `dark` or NULL (follow the visitor). `language`: `es`, `en` or NULL (follow the
visitor, i.e. browser then installation default). `show_title`, `show_filters` default true;
`pdf_enabled` defaults **false** (FR-024).

A control switched off is refused when requested directly: `POST …/pdf` answers the neutral `404`
when `pdf_enabled` is false (and when the report itself disallows PDF); with `show_filters` false the
data, PDF and filter-options endpoints **ignore** `period`, `compare`, `from`, `to` and `filter.*`, so
editing the widget URL cannot reach a different slice. The definition response reports the effective
flags, so the page and the data agree.

## R8 — Limits and counting

- 50 **active** widgets per dashboard (FR-006), counted separately from 20 share links; revoked and
  expired widgets do not count. Creation takes the dashboard row with `FOR UPDATE` (the same pattern
  as `links.ensure_capacity`) so two concurrent creations cannot exceed the limit.
- A visit is one loaded widget document (the definition request), not each data refresh, so "times
  shown" matches a page view; preview does not count.
- States: `revoked` (revocation is permanent, FR-022), `expired` (optional date passed), `active`.

## R9 — Rejected ideas, recorded

- **`frame-ancestors *` on `/w/*` + a Referer check in the API**: weaker (browsers stop being the
  gate; the shell would be framable everywhere) and it moves the decision into JavaScript.
- **Serving each visitor only their own rows**: out of scope by the spec's assumptions (the host
  server would have to vouch for the visitor and the engine would have to lock filters).
- **A Second Factor for copies of the key**: nothing in the browser can distinguish a copied key
  from a visitor; the spec accepts this explicitly (warning + ceiling + replacement + revocation).
- **Reusing `login_throttle` for the per-widget ceiling**: its key is an address and its windows are
  minute-aligned per address; a widget needs one counter per widget, not per address.
- **Encrypting the key so the test page can always show the snippet**: it would make FR-002's
  "shown once" a policy of the UI over a recoverable secret, and it contradicts FR-011's spirit.
