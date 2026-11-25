# Feature Specification: Embed a dashboard as a widget in another web page

**Feature Branch**: `065-dashboard-embed-widget`

**Created**: 2026-11-24

**Status**: Draft

**Input**: Owner brief of 2026-11-24: "create a widget for a dashboard to allow a developer to
integrate in their web", made secure, testable "in the same web page" before a developer's site is
involved, and able to be "unlimited". Today a dashboard can leave the product only as a share link
(018) that expires in at most 90 days, and the product refuses to be shown inside any other page.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Put a dashboard inside another site (Priority: P1)

An admin opens a dashboard's sharing screen, chooses **Insertar en un sitio web**, names the widget,
lists the sites allowed to show it (for example `https://www.cliente.com`) and receives a snippet.
A developer pastes the snippet into a page of that site and the dashboard appears there, read-only,
with its filters, without anybody signing in to Bizview.

**Why this priority**: it is the whole feature: a dashboard that lives inside the customer's own
web page instead of behind a link.

**Independent Test**: create a widget for one dashboard with one allowed site, paste the snippet in
a page served from that site and from a second, unlisted site; the first shows the dashboard with
the same numbers as the signed-in view, the second shows nothing.

**Acceptance Scenarios**:

1. **Given** embedding is enabled for the installation and the dashboard is shareable, **When** an
   admin creates a widget with a name and at least one allowed site, **Then** the product shows the
   snippet once, ready to copy, together with the warning of FR-012.
2. **Given** a page on an allowed site that contains the snippet, **When** a visitor without a
   Bizview account opens it, **Then** the dashboard renders inside the page with the current data.
3. **Given** the same snippet on a site that is not in the widget's list, **When** a visitor opens
   that page, **Then** the browser shows no dashboard and no data.
4. **Given** an embedded dashboard, **When** the visitor changes the period or a filter, **Then**
   the widget updates in place and the host page does not reload or navigate.
5. **Given** an installation with embedding disabled, or a project whose sharing policy forbids
   sharing, **When** an admin opens the sharing screen, **Then** the option to create a widget is
   absent or refused with the reason.
6. **Given** the creation form, **When** the admin leaves the name or the allowed sites empty,
   **Then** both fields are marked as required, the form does not send the request, and the message
   appears at the empty field saying what is missing; a field the product rejects is reported the
   same way, never only as "check the data you entered".

---

### User Story 2 - Try the widget before a developer touches their site (Priority: P1)

Right after creating a widget, the admin presses **Probar**. A test page inside Bizview shows the
widget exactly as a foreign page would hold it: framed, without the product's navigation, at a
width the admin can switch between phone, tablet and desktop. The same page shows the snippet and
the list of allowed sites, so the admin can confirm what the developer will get.

A developer who wants to try it from their own machine adds a local address (for example
`http://localhost:5173`) to the allowed sites and removes it when done.

**Why this priority**: without it the first real test happens on a customer's production site.

**Independent Test**: create a widget with no external site listed, open **Probar** and see the
dashboard framed at three widths; add a local address, serve a blank page with the snippet from it
and see the same dashboard.

**Acceptance Scenarios**:

1. **Given** a widget just created, **When** the admin opens **Probar**, **Then** the dashboard
   appears framed inside the test page, without Bizview's menu, header or sign-in controls.
2. **Given** the test page, **When** the admin switches between phone, tablet and desktop widths,
   **Then** the widget re-flows to each width and its height follows its content.
3. **Given** the test page, **When** it loads the widget, **Then** the visit is not counted in the
   widget's usage figures.
4. **Given** a widget whose list contains a local development address, **When** the admin views the
   widget, **Then** the entry is marked as a development address so it is not forgotten.
5. **Given** a signed-in admin viewing the test page, **When** the widget loads, **Then** it shows
   what an anonymous visitor would see, not what the admin's own account may see.

---

### User Story 3 - Know where each widget lives and switch it off (Priority: P2)

On the dashboard's sharing screen the admin sees every widget: name, allowed sites, who created it,
when it was last shown and how many times. The admin can edit the allowed sites, replace the
snippet with a new one (the old one stops working), or revoke the widget.

**Why this priority**: a widget has no expiry by default, so control and revocation are what keep
it safe over months.

**Independent Test**: create two widgets, load one from its site, then revoke it; the list shows
its usage, the revoked widget shows the neutral message on the host page within a minute, and the
other keeps working.

**Acceptance Scenarios**:

1. **Given** a widget in use, **When** the admin opens the list, **Then** it shows the widget's
   name, allowed sites, creator, creation date, expiry if any, last view and view count.
2. **Given** a widget, **When** the admin revokes it, **Then** every page that holds its snippet
   shows a neutral "not available" message and no data, at the latest one minute later.
3. **Given** a widget, **When** the admin replaces its snippet, **Then** the old snippet stops
   working, the new one works, and the allowed sites, name and usage history are kept.
4. **Given** a widget, **When** the admin removes a site from its list, **Then** that site stops
   showing the dashboard while the others continue.
5. **Given** any creation, edit, replacement, revocation or deletion, **When** it happens,
   **Then** it is recorded in the audit log with the actor and the widget.
6. **Given** a widget in any state, **When** the admin deletes it after confirming, **Then** it
   leaves the list for ever; an active one stops serving at that moment, and the audit entry keeps
   what it was (name, dashboard, sites, state and visits) without its key.

---

### User Story 4 - Make the widget look at home (Priority: P3)

The admin chooses, per widget, the theme (light, dark or follow the visitor), the language (Spanish,
English or follow the visitor), and whether the dashboard title, the filter controls and the PDF
download are shown. The widget takes the width the host page gives it and grows to the height of
its content, so the host page shows no inner scrollbar.

**Why this priority**: the widget is already useful without it; this is what makes it look like
part of the customer's site.

**Independent Test**: create a widget with dark theme, English, no title and no PDF; the host page
shows the dashboard in dark, in English, without title or PDF button and without an inner
scrollbar at 375 px and at 1280 px.

**Acceptance Scenarios**:

1. **Given** a widget set to a fixed theme and language, **When** a visitor opens the host page,
   **Then** the widget uses them regardless of the visitor's device settings.
2. **Given** a widget with the title, filters or PDF switched off, **When** it renders, **Then**
   those controls are absent and cannot be reached by editing the page address.
3. **Given** a host page 375 px wide, **When** the widget renders, **Then** it shows the phone
   layout with no horizontal scroll and no inner vertical scrollbar.

---

### Edge Cases

- The dashboard is withdrawn, its report leaves the active version, or its project stops allowing
  sharing: the widget shows the same neutral message as a revoked one; it works again by itself if
  the dashboard returns.
- A visitor copies the snippet's address and opens it directly in a browser tab: they see the same
  widget alone, with no route into the rest of the product; this is the same exposure as the host
  page itself and is covered by FR-012's warning.
- A program outside a browser requests the widget's data with the copied key: the product cannot
  tell it from a visitor, so it is served; this is why FR-012's warning exists and why the request
  ceiling of FR-015 applies per widget.
- The host page is HTTP and the installation is HTTPS: the allowed site must be listed with the
  scheme it really uses; a mismatch shows nothing.
- An allowed-site entry is malformed, contains a path, or is a wildcard for every site: it is
  refused when the widget is saved.
- A visitor is signed in to Bizview in another tab: the widget still shows only the widget's view.
- The widget reaches its request ceiling: visitors see a short "try again in a moment" message
  inside the widget and the host page is unaffected.
- The same dashboard is embedded twice on one page, or two widgets of different dashboards share a
  page: each renders and filters independently.
- The widget reaches its optional expiry date: it behaves like a revoked widget and the list shows
  it as expired.
- A dashboard reaches the maximum number of active widgets: creation is refused with the limit in
  the message; revoked and expired widgets do not count.
- A host page still holds the snippet of a widget that was deleted: it shows the same neutral
  message as a revoked one, and deleting again finds nothing.
- An admin deletes a revoked or expired widget: it leaves the list; revocation is the state that
  keeps a widget as history, deletion is the one that removes it.
- The name or the allowed sites are submitted empty: the form refuses before sending and marks the
  field, so the request never reaches the product.

## Requirements *(mandatory)*

### Functional Requirements

**Creating and embedding**

- **FR-001**: an admin MUST be able to create a widget for one dashboard from that dashboard's
  sharing screen, giving it a name (required, up to 80 characters) and a list of allowed sites.
- **FR-002**: the product MUST give the admin a copy-ready snippet that a developer can paste into
  a web page without writing any other code, and MUST show it only at creation and at replacement.
- **FR-003**: a widget MUST show exactly one dashboard, read-only, with the same data the
  dashboard shows a signed-in reader for the same period and filters.
- **FR-004**: a widget MUST work for visitors who have no Bizview account and MUST never ask them
  to sign in.
- **FR-005**: a widget MUST have no expiry by default; the admin MAY set an expiry date.
- **FR-006**: a dashboard MUST accept up to 50 active widgets, counted separately from its share
  links; the limit and the count MUST be visible on the sharing screen.
- **FR-007**: embedding MUST be off for an installation until its operator enables it, MUST depend
  on share links being enabled, and MUST honour each project's sharing policy.

**Security**

- **FR-008**: a widget MUST be displayed only inside pages of the sites on its own list; every
  other page of the product MUST keep refusing to be shown inside another site, as today.
- **FR-009**: an allowed site MUST be a full site address (scheme, host and optional port); paths,
  wildcards covering every site and malformed entries MUST be refused; a widget holds at most 10.
- **FR-010**: a widget MUST never use, read or expose the Bizview session of the person looking at
  it, and MUST offer no route into the rest of the product.
- **FR-011**: the key inside a snippet MUST be unguessable, MUST be stored so that a copy of the
  product's database does not reveal it, and MUST be replaceable without recreating the widget.
- **FR-012**: the creation screen and the widget list MUST state in plain words that anyone who can
  see a page holding the widget can see all of that dashboard's data, and that filters are a
  convenience for the visitor, not a restriction.
- **FR-013**: a revoked, expired or unavailable widget MUST show one neutral message that does not
  reveal which of those happened, the dashboard's name or any data, and MUST stop serving data at
  the latest one minute after the change.
- **FR-014**: the widget MUST ask search engines not to index it and MUST not be kept by browsers
  or intermediaries after the visit.
- **FR-015**: the product MUST limit how many requests one widget may make per minute across all
  visitors, in addition to today's per-address limits, and MUST tell the visitor to retry when the
  ceiling is reached; the ceiling is set per installation.
- **FR-016**: creating, editing, replacing, revoking and deleting a widget MUST be recorded in the
  audit log with the actor, the widget, the dashboard and the allowed sites; a deletion MUST keep,
  in that entry, enough to know what was removed (see FR-028).
- **FR-017**: messages exchanged between the widget and its host page (for sizing) MUST carry no
  dashboard data, and each side MUST ignore messages from anywhere but the other.

**Testing**

- **FR-018**: every widget MUST have a test page inside the product, open to admins only, that
  shows the widget framed as a foreign page would, at phone, tablet and desktop widths, next to
  its snippet and allowed sites.
- **FR-019**: the test page MUST work without any external site on the widget's list and MUST not
  count towards the widget's usage figures.
- **FR-020**: a local development address MAY be listed as an allowed site and MUST be marked as
  such wherever the widget's sites are shown.

**Managing**

- **FR-021**: the sharing screen MUST list a dashboard's widgets with name, allowed sites, creator,
  creation date, expiry, state (active, revoked, expired), last view and view count.
- **FR-022**: an admin MUST be able to rename a widget, edit its allowed sites and appearance
  options, replace its snippet, revoke it and delete it; a revoked widget cannot be restored, and a
  deleted widget leaves the dashboard's list for ever (FR-028).

**Appearance**

- **FR-023**: the widget MUST show the dashboard without the product's navigation, account
  controls or footer links into the product; the installation's legal-page links remain.
- **FR-024**: per widget the admin MUST be able to set theme (light, dark, follow visitor),
  language (Spanish, English, follow visitor), and whether title, filters and PDF download are
  shown; PDF is off by default and a control switched off MUST also be refused when requested
  directly.
- **FR-025**: the widget MUST fill the width its host gives it, MUST grow to the height of its
  content so the host shows no inner scrollbar, and MUST stay readable at 375 px.
- **FR-026**: the admin help (ES/EN), the operator's installation guide and the CHANGELOG MUST
  document enabling the feature, creating and testing a widget, deleting one, the warning of FR-012
  and the required fields of FR-027.

**Required fields**

- **FR-027**: the name and the list of allowed sites MUST be required, and the form MUST show that
  before the admin submits. An empty required field MUST stop the form from sending the request and
  MUST be reported at that field, in the interface language, with a message that says what is
  missing. A field the product rejects MUST be reported the same way — at the field, in words —
  whether the error comes from the request model or from the rule that validates the value; the
  generic "check the data you entered" MUST NOT be the only thing the admin sees for a missing name
  or a missing site. The edit form of an existing widget MUST follow the same rules, and an example
  shown inside a field MUST NOT be mistakable for content the admin entered.

**Deleting**

- **FR-028**: an admin MUST be able to delete a widget in any state (active, revoked or expired),
  after a confirmation that states plainly, for an active widget, that it will stop working on the
  sites that embed it. Deleting an active widget MUST stop it serving at once, like revocation, and
  MUST remove it and its allowed sites from the product. Deletion MUST work while embedding is
  switched off, like revocation. It MUST be recorded in the audit log with the widget, the
  dashboard, the name, the allowed sites, the state it had and its visit count, and never its key.
  A widget of one dashboard MUST NOT be deleted through another, a non-administrator MUST NOT delete
  at all, and the administrator-network restriction MUST cover the action. The count of active
  widgets and the per-dashboard limit MUST stay correct afterwards. Revocation MUST keep its current
  meaning and its current route.

### Key Entities

- **Widget**: a standing permission to show one dashboard inside other sites. It has a name, the
  dashboard, a secret key (never stored readable), its allowed sites, appearance options, an
  optional expiry, who created it and when, whether and when it was revoked, and usage figures. A
  revoked widget stays in the list as history; a deleted one is removed with its sites, and only
  its audit entry remains.
- **Allowed site**: one site address a widget may be shown in; may be flagged as a development
  address.
- **Snippet**: the text a developer pastes into a page; it carries the widget's key and nothing
  else that is secret.
- **Dashboard**: unchanged; a dashboard has zero or more widgets, separate from its share links.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: an admin creates a widget and sees it working on the test page in under 2 minutes,
  without leaving the product and without help.
- **SC-002**: a developer who receives the snippet shows the dashboard on their page in under 5
  minutes by pasting it, with no other change to their site.
- **SC-003**: in every tested browser, a page on an unlisted site that holds a valid snippet shows
  no dashboard data, and every product page other than a widget still cannot be framed.
- **SC-004**: a visitor signed in to Bizview as an admin sees in the widget exactly what an
  anonymous visitor sees.
- **SC-005**: a revoked widget stops showing data on its host pages within 1 minute.
- **SC-006**: the embedded dashboard shows its first numbers within 2 seconds on a 4G connection,
  the same target as the signed-in dashboard.
- **SC-007**: at 375 px and at 1280 px the host page shows no inner scrollbar and no horizontal
  scroll caused by the widget.
- **SC-008**: a widget with no expiry keeps working after 90 days with no action from anyone.
- **SC-009**: one widget hammered past its ceiling does not slow the signed-in dashboards of the
  same installation beyond their normal response target.

## Assumptions

- "Test in the same web page" means a test page inside Bizview itself (User Story 2), so the first
  trial needs no external site. Trying it on a page of the public website (032) is a later use of
  the same snippet and needs nothing extra.
- "Unlimited" means unlimited in time: a widget does not expire unless the admin sets a date. The
  number of widgets is deliberately not unlimited: 50 active per dashboard, separate from the 20
  share links, because every widget is a standing public door that someone must be able to review.
- Only admins create and manage widgets, the same rule as share links.
- A widget shows a whole dashboard. Embedding a single card is out of scope for this feature.
- Everyone who can see the host page may see the whole dashboard. Showing each visitor only their
  own rows needs the host's server to vouch for the visitor and the report engine to lock filters,
  which today it does not; that is a separate, later feature and nothing here depends on it.
- The allowed-site list protects against other sites displaying the widget in a browser. It does
  not stop a person who copies the key from requesting the data by other means; the warning, the
  per-widget ceiling, replacement and revocation are the answers to that.
- The snippet is shown once, like a share link today. A lost snippet is replaced, or copied back
  from the page that holds it.
- The widget reuses the shared dashboard's behaviour for filters, periods, tables (064) and
  cross-filter (063); the AI narrative stays disabled, as on share links.
- Visitors' browsers are current versions of Chrome, Edge, Firefox and Safari, on desktop and
  phone.
- Share links (018) keep their current behaviour, limits and 90-day maximum.
