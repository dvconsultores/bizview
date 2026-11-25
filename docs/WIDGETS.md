# Dashboards in other websites

## What a widget is

A widget is a standing permission to show one dashboard, read-only, inside a page of another site.
Visitors need no BizView account, the dashboard keeps its filters and periods, and the widget does not
expire unless an administrator sets a date. It is one dashboard per widget: embedding a single card
is not part of this feature.

A widget is created from the dashboard's sharing screen (**Compartir** → **Insertar en un sitio web**)
by an **Administrator** or the **Superuser**, and only while the installation has both
`EMBED_WIDGETS_ENABLED` and `SHARE_LINKS_ENABLED` and the report's project allows sharing. A dashboard
holds up to 50 active widgets, counted apart from its 20 share links.

## What the developer pastes

The product shows the snippet once, at creation and at replacement (it is not kept in the browser, so
a lost snippet is replaced). It is a short inline script and an iframe: paste it as it is, with no
other change to the page. The script only sizes the frame — it receives the widget's content height
and nothing else — and it accepts that message only from the BizView installation's own origin. The
iframe asks the browser for at least the origin of the host page (`referrerpolicy="origin"`), because
that is how the widget knows which site framed it: keep that attribute and the `data-bizview-widget`
one.

```html
<script>(function(){var m="bizview-widget-3",o=new URL("https://bi.example.com/w/KEY").origin;/* sizes the iframe */})();</script>
<iframe src="https://bi.example.com/w/KEY" title="Ventas" data-bizview-widget="bizview-widget-3" loading="lazy" style="width:100%;min-height:320px;border:0"></iframe>
```

The `KEY` is the whole address of the widget: it identifies the widget and nothing else is needed. The
page's Content-Security-Policy, if it has one, must allow `frame-src https://bi.example.com`.

## What the visitor sees

The dashboard, with the theme, the language and the controls the administrator chose for that widget:
title, filters and period, and the PDF download (off by default). With the filter controls switched
off, editing the widget's address cannot change what it serves. The widget fills the width it is
given, grows to the height of its content so the host page shows no inner scrollbar, and stays
readable at 375 px.

The preview inside the product (**Probar**) frames the same document at phone, tablet and desktop
widths, without any external site listed and without counting as a visit. It works for administrators
only.

## Security you should know

The widget's allowed sites are what a browser enforces: the framed document answers
`Content-Security-Policy: frame-ancestors <that widget's sites>` and no `X-Frame-Options`, while every
other route of the installation keeps refusing to be framed. A site must be listed with the scheme it
really uses (`http://localhost:5173` and `https://example.com` are different sites).

The page itself is never told the list. It learns one thing: whether the origin that framed it is
allowed — and, if it is, that origin, which is the only place its height message is sent to. One
widget serving two customers' sites therefore shows neither of them the other's domain, and the
administrator's internal name for the widget is not published either (the iframe's `title` carries
it in the host page, where the administrator chose to publish it). An image, logo or cached picture
does not spend the widget's request ceiling: the ceiling counts the report requests, which are the
ones that use the database.

The list does not stop a program that copies the key from requesting the data by other means: nothing
in a browser can tell that program from a visitor. That is why the product also keeps a per-widget
request ceiling (`WIDGET_RATE_LIMIT`, 300 per minute by default), a replacement that stops the old
snippet at once, revocation that cannot be undone, and an audit entry for each action.

The widget never uses the viewer's session: an administrator who is signed in and opens the host page
sees exactly what an anonymous visitor sees. Anyone who can see the host page can see the whole
dashboard — filters are a convenience for the visitor, not a restriction — so say so to the customer
before enabling it. The framed document is never indexed and never cached, and it offers no route into
the rest of the product; the installation's legal pages stay reachable.

## Testing it locally

Add `http://localhost:5173` (or whichever port your development server uses) to the widget's allowed
sites, paste the snippet into a blank page served from there, and remove the entry when you are done:
a local address is shown with a **Development** badge so it is not forgotten in the list.
