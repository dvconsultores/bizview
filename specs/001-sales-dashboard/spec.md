# Feature Specification: Sales Dashboard for Customers

> **Superseded (2026-09-29).** Reports and integrations are now defined per customer as specs in
> the customer's workspace ("vibe reporting", feature 005). The generic parts of this spec
> (periods, comparisons, freshness, PDF parity, 375 px) became engine requirements FR-013–FR-016
> of feature 005; the Customer B-specific parts become Customer B's workspace specs
> `erp-ventas` (integration) and `ventas` (report). Kept as reference.

**Feature Branch**: `001-sales-dashboard`

**Created**: 2026-09-28

**Status**: Superseded by [005 Vibe Reporting](../005-vibe-reporting/spec.md) (2026-09-29)

**Input**: User description: "Sales Dashboard for Customers — use spec-base.md at the repository root as the feature description (overview, four components, project structure), governed by .specify/memory/constitution.md. Run autonomously: where details are missing, choose the recommended answer a BI (business intelligence) expert would choose for a customer-facing mobile sales dashboard, record it as an assumption, and avoid [NEEDS CLARIFICATION] markers unless the choice is truly unguessable. Short name: sales-dashboard."

## Clarifications

### Session 2026-09-28

Answered autonomously with the recommended BI-practice option, at the user's request.

- Q: Which date decides the day a sale counts on? → A: The date the sale document (invoice
  or ticket) was completed in the origin, not the date the order was created.
- Q: What data volume must the first release handle? → A: Up to 100 customer accounts, 1,000
  users (200 at the same time), 2,000 products per account, 5 million historical sale lines, and
  20,000 new sale lines per day.
- Q: How long do users stay signed in, and what happens after failed sign-ins? → A: Signed in
  for up to 7 days of inactivity and 30 days at most; 5 failed attempts lock sign-in for 15
  minutes.
- Q: What availability is expected, and who hears about failed refreshes? → A: 99.5% monthly
  availability; operators are alerted after 2 consecutive failed refreshes.
- Q: What accessibility level must screens meet? → A: WCAG 2.2 level AA; up/down changes never
  shown by colour alone.
- Q: Which interface languages are needed? → A: Spanish only (confirmed by the user; replaces the
  earlier Spanish + English assumption).
- Q: Is a 30-minute refresh acceptable? → A: Yes (confirmed by the user).
- Q: Are the metric definitions accepted? → A: Yes, to be confirmed against the real origin
  tables when they are known (confirmed by the user).

## User Scenarios & Testing *(mandatory)*

The primary actor is a **customer user**: a person working for a business (the *customer
account*) whose sales are recorded in the existing origin system. Customer users only read data.
A secondary actor, the **internal administrator**, provisions customer accounts and their users.

### User Story 1 - See my sales summary on my phone (Priority: P1)

A customer user signs in from their phone and immediately sees the headline figures for their
business for the current period: net sales, number of orders, units sold, and average order
value, each compared with the previous comparable period. The screen also shows when the data
was last updated.

**Why this priority**: this is the core promise of the product — "how are my sales doing?"
answered in seconds on a phone. Without it nothing else has value.

**Independent Test**: provision one customer account with known sales in the origin data, sign
in on a 375px-wide phone screen, and verify the four headline figures and their comparisons
match hand-calculated values for month-to-date.

**Acceptance Scenarios**:

1. **Given** a signed-in customer user, **When** they open the dashboard, **Then** they see net
   sales, orders, units sold, and average order value for the default period (month-to-date),
   each with the absolute and percentage change versus the same number of days in the previous
   month.
2. **Given** a signed-in customer user, **When** they choose another period preset (Today,
   Yesterday, Last 7 days, Month-to-date, Last month, Quarter-to-date, Year-to-date, Last 12
   months) or a custom date range, **Then** all headline figures and comparisons recalculate for
   that period.
3. **Given** a signed-in customer user, **When** they switch the comparison from "previous
   period" to "same period last year", **Then** every change figure uses the prior-year period.
4. **Given** a user of customer A, **When** they try to view any data belonging to customer B
   (by any means, including editing an address or request), **Then** access is refused and no
   customer B data is revealed.
5. **Given** a person who is not signed in, **When** they open any dashboard screen, **Then**
   they are asked to sign in and see no sales data.
6. **Given** the dashboard is showing data, **When** the user looks at the summary, **Then** a
   "last updated" date and time is visible.

---

### User Story 2 - See how my sales move over time (Priority: P2)

A customer user views a trend chart of net sales for the selected period, grouped by day, week,
or month, with the comparison period drawn alongside, so they can spot growth, drops, and
seasonality.

**Why this priority**: after "how much", the next BI question is "is it going up or down, and
when did it change?". It builds on the same data as Story 1.

**Independent Test**: with known daily sales for a customer, select "Last 12 months" grouped by
month and verify each point equals the hand-calculated monthly net sales, readable at 375px.

**Acceptance Scenarios**:

1. **Given** a selected period, **When** the trend view opens, **Then** net sales are plotted
   with a grouping chosen automatically (day for ≤ 31 days, week for ≤ 13 weeks, month
   otherwise) and the user can switch grouping manually.
2. **Given** the trend chart, **When** the user taps a point, **Then** they see that point's
   exact net sales, orders, and the comparison value.
3. **Given** the trend chart, **When** the user switches the measure to orders or units sold,
   **Then** the chart redraws with that measure.
4. **Given** the period includes today, **When** the chart is shown, **Then** the current,
   incomplete day/week/month is visibly marked as partial.

---

### User Story 3 - See which products drive my sales (Priority: P3)

A customer user views a ranked list of their products for the selected period — by net sales or
by units — with each product's share of the total and its change versus the comparison period,
and can open one product to see its own trend.

**Why this priority**: product mix is the most common next question after totals and trends, and
the constitution calls out per-product aggregation explicitly.

**Independent Test**: with known product-level sales, verify the top 10 ranking, shares, and a
single product's trend against hand-calculated values.

**Acceptance Scenarios**:

1. **Given** a selected period, **When** the user opens the products view, **Then** they see the
   top 10 products by net sales with net sales, units, share of total (%), and change versus the
   comparison period, and can load more.
2. **Given** the products view, **When** the user switches the ranking to units sold, **Then** the
   list re-ranks by units.
3. **Given** the products view, **When** the user searches by product name or code, **Then** only
   matching products are listed.
4. **Given** the products view, **When** the user filters by product category, **Then** the list
   and totals only include that category.
5. **Given** a product in the list, **When** the user opens it, **Then** they see that product's
   headline figures and trend for the selected period.

---

### User Story 4 - Export a PDF summary (Priority: P4)

A customer user exports a PDF summary of what they are viewing — period, headline figures with
comparisons, trend chart, and top products — to share with colleagues or keep on file.

**Why this priority**: sharing is valuable but depends on Stories 1–3 existing first.

**Independent Test**: export a PDF for a known period and verify every figure equals the one on
screen and the PDF is legible when printed on A4/Letter.

**Acceptance Scenarios**:

1. **Given** a selected period and filters, **When** the user taps "Export PDF", **Then** a PDF
   is delivered to their phone containing the customer name, period, comparison basis,
   generation date and time, data "last updated" time, headline figures, trend chart, and top 10
   products.
2. **Given** an export has been requested, **When** it is being prepared, **Then** the user sees
   progress and can keep using the dashboard.
3. **Given** a period with no sales, **When** the user exports, **Then** the PDF states that
   there were no sales in the period rather than showing empty charts.

---

### User Story 5 - Provision customer access (Priority: P5)

An internal administrator creates a customer account linked to the matching customer in the
origin system, and adds or deactivates the users who may view it.

**Why this priority**: required before real customers can use the product, but it can start as a
minimal internal tool; Stories 1–4 can be tested with seeded accounts.

**Independent Test**: create a customer account and one user, sign in as that user, and see only
that customer's data; deactivate the user and verify they can no longer sign in.

**Acceptance Scenarios**:

1. **Given** an administrator, **When** they create a customer account and link it to an origin
   customer identifier, **Then** that account's users see that origin customer's sales only.
2. **Given** an administrator, **When** they add a user to a customer account, **Then** the user
   can set their credentials and sign in.
3. **Given** an administrator, **When** they deactivate a user, **Then** that user's active
   sessions end and further sign-ins are refused.

---

### Edge Cases

- **No sales in the period**: headline figures show zero, comparisons show "no prior data" where
  the comparison base is zero (no infinite or undefined percentages), charts show an empty state
  message.
- **New customer with no history**: dashboard shows a clear "no sales yet" state; year-over-year
  comparison is shown as unavailable.
- **Comparison base is zero**: percentage change is shown as "new" or "—", never as a division
  error.
- **Refresh failure / stale data**: if data has not been refreshed within twice the normal
  refresh interval, a visible "data may be out of date" notice appears next to the last-updated
  time; figures remain viewable.
- **Late corrections in the origin** (edited or cancelled orders, returns): corrections to sales
  from the previous 7 days appear in the dashboard within the normal freshness window; returns
  reduce net sales in the period in which the return happened.
- **Day boundaries**: a sale counts on the local day (customer account's timezone) its sale
  document was completed, so a sale completed at 23:30 local time counts for that day even if the
  order was created earlier.
- **Partial current period**: comparisons for a partial period compare like-for-like elapsed days
  (e.g., month-to-date on the 10th compares with days 1–10 of the previous month).
- **Short months**: when the previous month has fewer days (e.g., comparing 1–31 March with
  February), the comparison uses the whole previous month.
- **Very long product lists**: the product view loads in pages; search works across all products,
  not only loaded ones.
- **Products renamed or recategorised in the origin**: the dashboard shows the current name and
  category for all periods.
- **Custom range limits**: ranges outside available history are clipped to the available data
  with a notice; the end date cannot be before the start date.
- **Session expiry**: an expired session returns the user to sign-in and, after signing in, back
  to the view they were on.
- **Poor connectivity**: if a request fails, the user sees a retry option and the last
  successfully loaded figures stay on screen, clearly marked.
- **Screens narrower than 375px**: content stays usable without horizontal page scrolling.

## Requirements *(mandatory)*

### Functional Requirements

**Access and data isolation**

- **FR-001**: Users MUST sign in with individual credentials before seeing any sales data.
- **FR-002**: Each user MUST belong to exactly one customer account and MUST only ever see data
  of that account; this MUST be enforced for every screen, request, and export.
- **FR-003**: There MUST be no self-registration; customer accounts and users are created by
  internal administrators.
- **FR-004**: Administrators MUST be able to create customer accounts, link each to one origin
  customer identifier, set the account's timezone and currency, and add, deactivate, or
  reactivate its users.
- **FR-005**: Users MUST be able to recover access to their account if they forget their
  credentials, without administrator intervention.
- **FR-006**: The system MUST record sign-ins, failed sign-ins, and exports with user, time, and
  outcome.
- **FR-032**: A sign-in MUST remain valid for up to 7 days of inactivity and 30 days in total,
  after which the user signs in again; signing out MUST end the session immediately.
- **FR-033**: After 5 consecutive failed sign-in attempts for a user, sign-in for that user
  MUST be blocked for 15 minutes, and the block MUST be recorded as an audit event.

**Metrics**

- **FR-007**: The system MUST provide these measures, calculated consistently everywhere (screen
  and PDF). A sale belongs to the period in which its sale document (invoice or ticket) was
  completed in the origin; orders that are created but never completed are not counted.
  - *Net sales*: value of sold items after line and order discounts, excluding taxes and shipping,
    excluding cancelled orders, minus the value of returns processed in the period.
  - *Orders*: count of distinct completed, non-cancelled sale documents in the period.
  - *Units sold*: quantity of items sold minus quantity returned in the period.
  - *Average order value*: net sales ÷ orders (shown as "—" when orders is zero).
  - *Share of total*: a product's net sales ÷ total net sales for the same period and filters.
- **FR-008**: Each headline measure MUST show the value, the comparison value, and the absolute
  and percentage change, with a visual up/down indicator.

**Periods and comparisons**

- **FR-009**: Users MUST be able to choose the period from presets (Today, Yesterday, Last 7 days,
  Month-to-date, Last month, Quarter-to-date, Year-to-date, Last 12 months) or a custom date
  range; the default is Month-to-date.
- **FR-010**: Users MUST be able to compare against the previous comparable period (default) or
  the same period last year, following the like-for-like rules in Edge Cases.
- **FR-011**: Weeks MUST start on Monday; days, weeks, and months MUST follow the customer
  account's timezone.
- **FR-012**: The system MUST keep and show at least 24 full months of history plus the current
  year, so every year-over-year comparison in the presets is available.
- **FR-013**: The selected period, comparison, and filters MUST persist while the user moves
  between the summary, trend, and product views.

**Trends**

- **FR-014**: The system MUST show a trend of the chosen measure (net sales, orders, or units) for
  the selected period, with the comparison period overlaid.
- **FR-015**: The trend grouping MUST default by period length (day ≤ 31 days, week ≤ 13 weeks,
  month otherwise) and MUST be switchable by the user; the current incomplete bucket MUST be
  marked as partial.
- **FR-016**: Tapping a point on the trend MUST show its exact values.

**Products**

- **FR-017**: The system MUST list products ranked by net sales (default) or units sold, showing
  net sales, units, share of total, and change versus the comparison period, 10 at a time with
  "load more".
- **FR-018**: Users MUST be able to search products by name or code and filter by product
  category; totals and shares MUST reflect the active filter.
- **FR-019**: Users MUST be able to open a single product and see its headline figures and trend
  for the selected period.

**Export**

- **FR-020**: Users MUST be able to export a PDF summary of the current period, comparison, and
  filters containing: customer name, period and comparison basis, generation time, data
  last-updated time, headline figures with changes, trend chart, and top 10 products.
- **FR-021**: PDF figures MUST be identical to the figures shown on screen for the same selection.
- **FR-022**: The PDF MUST be produced by the service, not assembled on the user's device, and
  MUST be legible when printed on A4 and US Letter paper.

**Data freshness and accuracy**

- **FR-023**: The system MUST NOT write to or alter the origin system in any way.
- **FR-024**: The dashboard's data MUST be refreshed from the origin on a recurring schedule at
  least every 30 minutes; a refresh MUST be safe to repeat or interrupt without duplicating or
  losing data.
- **FR-025**: Every refresh MUST re-read at least the previous 7 days of origin data so late
  corrections are picked up.
- **FR-026**: Every screen showing figures MUST show the data's last-updated time, and MUST show a
  stale-data notice when the last successful refresh is older than twice the refresh interval.
- **FR-027**: Refresh runs MUST be recorded with start time, end time, outcome, and rows
  processed, so operators can see whether data is current.
- **FR-034**: Operators MUST be alerted when 2 consecutive refresh runs fail, and when the origin
  cannot be reached; while the origin is unavailable, users keep seeing the last refreshed data
  with the stale-data notice.

**Presentation**

- **FR-028**: All screens MUST be designed for phone screens first and remain fully usable at
  375px width without horizontal page scrolling; larger screens MAY use the extra space.
- **FR-029**: Money MUST be shown in the customer account's currency and numbers and dates in
  Spanish format; large values MUST be abbreviated on charts (e.g., 1.2M) and shown in
  full when tapped.
- **FR-030**: The interface, PDF, and emails MUST be in Spanish. There is no language selection in
  this release.
- **FR-031**: Empty, loading, error, and stale states MUST each have a clear message; failed
  loads MUST offer a retry.
- **FR-035**: Screens MUST meet WCAG 2.2 level AA (contrast, text scaling to 200%, screen-reader
  labels for figures and charts); increases and decreases MUST be shown with an arrow or sign as
  well as colour. The PDF MUST use real selectable text (no images of text), a logical reading
  order, AA contrast, the trend also given as a data table, and a document title and language;
  a fully tagged (PDF/UA) document is out of scope for this release.

### Key Entities *(include if feature involves data)*

- **Customer Account**: a business whose sales are shown. Links to one origin customer
  identifier; has a name, timezone, currency, and active flag.
- **User**: a person who can sign in; belongs to one customer account (or is an internal
  administrator); has an active flag.
- **Product**: an item the customer sells, identified by the origin's product code; has a current
  name and category.
- **Product Category**: a grouping of products taken from the origin.
- **Daily Sales Summary**: per customer account and day — net sales, orders, units, discounts,
  returns. Weekly and monthly summaries are derived from it.
- **Product Sales Summary**: per customer account, product, and day — net sales and units.
- **Refresh Run**: one execution of the data refresh — start, end, outcome, rows processed,
  period covered.
- **Audit Event**: a sign-in, failed sign-in, or export — user, time, outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a phone with a typical 4G connection, 95% of users see their sales summary
  within 2 seconds of opening the dashboard.
- **SC-002**: 95% of period, comparison, grouping, and filter changes show updated figures within
  1 second.
- **SC-003**: For every customer account and every completed day, dashboard totals for net sales,
  orders, and units match the origin system's figures exactly in an automated reconciliation.
- **SC-004**: Under normal operation, figures are never more than 60 minutes behind the origin
  system.
- **SC-005**: A complete rebuild of all dashboard data for the initial scope (100 customer
  accounts, 5 million historical sale lines) finishes within 5 minutes.
- **SC-006**: 95% of PDF exports are delivered within 10 seconds, and 100% match the on-screen
  figures.
- **SC-007**: In access testing, 0 requests by a user of one customer account return data of any
  other account.
- **SC-008**: In usability testing, at least 90% of first-time users find their month-to-date net
  sales and their top product within 1 minute without help.
- **SC-009**: Every screen passes a review at 375px width with no horizontal page scrolling and
  tap targets of at least 44×44 points.
- **SC-010**: The dashboard is available to customers at least 99.5% of each month (excluding
  announced maintenance).
- **SC-011**: SC-001 and SC-002 hold with 200 users active at the same time.
- **SC-012**: Every screen passes a WCAG 2.2 AA audit with no critical findings, and every PDF
  passes the PDF checks listed in FR-035.

## Assumptions

- **Architecture is fixed by the constitution**: the origin database is read-only and owned by
  another system; a background process transforms its data into the dashboard's own store; the
  dashboard never reads the origin while serving a user.
- **Metric definitions** (FR-007) follow standard retail BI practice. The exact origin fields for
  discounts, taxes, shipping, cancellations, and returns will be confirmed against the origin
  schema during planning; if a field is missing, the definition is adjusted and documented, not
  silently changed.
- **One currency per customer account**; no currency conversion in this release.
- **Timezone per customer account**, set by an administrator (default: the business's local
  timezone).
- **All users of a customer account see the same data**; there are no roles within a customer
  account (no per-branch or per-salesperson restrictions) in this release.
- **Product category exists in the origin data**; if it does not, the category filter is omitted
  and the rest of the product view is unaffected.
- **Interface language**: Spanish only; other languages are out of scope for this release.
- **History**: at least 24 full months plus the current year are available in the origin.
- **Scale of the first release**: up to 100 customer accounts, 1,000 users (200 at the same
  time), 2,000 products per account, 5 million historical sale lines, 20,000 new sale lines per
  day.
- **Refresh interval**: every 30 minutes (confirmed), with the stale-data notice after 60 minutes
  without a successful refresh.
- **Authentication method** is set by the constitution (v1.1.0) and the plan; this spec only
  requires individual credentials, self-service recovery, and strict per-account isolation.
- **Out of scope for this release**: editing or entering data, forecasts and targets, alerts and
  scheduled reports, dimensions other than time and product (branch, channel, salesperson,
  end-customer), multi-currency, offline mode, native mobile apps, and data export formats other
  than PDF.
- **Dependencies**: read-only access credentials to the origin database and documentation (or
  sample data) of its sales, order, return, and product tables.
