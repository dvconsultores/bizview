# Embed a dashboard in a website

## What it is for

Gives a developer a snippet that shows a dashboard, read-only, inside a page of another website. The
visitor needs no BizView account and never sees the rest of the product. The widget does not expire
unless you set a date.

## Who can use it

An **Administrator** or the **Superuser** creates it, when the installation has widgets turned on
(which also needs shared links) and the report's project allows sharing it.

## How to

1. Open the dashboard and press **Share** → **Embed in a website**.
2. Type a **Widget name**: it is for recognising it in the list.
3. In **Allowed sites** write one per line, with its scheme: `https://www.example.com`. No paths, no
   queries and no wildcards. A widget holds up to ten.
4. Optional: the theme, the language, whether the title, the filters and the PDF are shown, and an
   expiry date. The PDF is off by default.
5. Press **Create widget** and copy the snippet: it is never shown again and is not stored in the
   browser. Paste it into the page as it is; nothing else has to be written, and do not remove the
   iframe's `referrerpolicy="origin"`: that is how BizView knows which site is showing it.
6. Press **Test** to see it inside BizView, at phone, tablet and desktop widths.

## Options

- **Test** opens the widget in a frame, without the product's menu or header, and does not count as a
  visit. An administrator with a session open sees exactly what a visitor without an account sees.
  The snippet appears on that page only if you have just created or replaced the widget in the same
  session: it is not stored in the browser.
- **Edit** changes the name, the sites, the theme, the language, the controls and the date; the
  snippet keeps working.
- **Replace snippet** creates a new key: the previous snippet stops working and the name, the sites
  and the visits are kept.
- **Revoke** switches the widget off for ever; a page holding it shows a neutral message. Each
  dashboard holds 50 active widgets, counted apart from share links.
- A site starting with `http://localhost` or with a private address is marked **Development** so it is
  not forgotten in the list.
- No dashboard on the client's page usually means the site is not listed with the scheme it really
  uses.

## Common problems

- **Embed in a website** is missing, or refused with a reason: the installation has embedding off, or
  shared links off, or the project does not allow sharing this report.
- **Allowed sites**: when the client's page shows no dashboard, check the exact scheme, domain and
  port, that the widget is not revoked or expired, and that the dashboard is still available.
- When it says there are too many requests, the widget reached its per-minute ceiling: wait a few
  seconds. The installation sets the limit, and images do not spend it.
- If you lost the snippet, replace it: it is shown only when creating and when replacing.

## Related

- Share with a link
- Dashboards and reports
- Distributions
