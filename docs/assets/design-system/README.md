# Design-system evidence

Playwright writes the screenshots for feature 050 here, one per screen and viewport:

```
01-apariencia-{phone,desktop}-{light,dark}.png      evidence 1 — the theme library uses the width
02-cuenta-{phone,desktop}-{light,dark}.png          evidence 3 — the account dropdown, grouped
03-perfil-{phone,desktop}-{light,dark}.png          evidence 4 — appearance choices on one row
05-ayuda-lista-{phone,desktop}-{light,dark}.png     evidence 5 — bounded topic navigation
06-ayuda-tema-{phone,desktop}-{light,dark}.png      evidence 6 — the article scrolls on its own
```

The names without a colour suffix (`01-apariencia-desktop.png`, …) are the same six screens captured
against the **deployed installation** (`bi.getbizview.com`) after the release, in the light theme.

Regenerate the local ones with:

```bash
cd frontend && npx playwright test tests/e2e/design-system.spec.ts
```

The images in this folder are the record for feature 050's closure report (the diff a reviewer would
otherwise have to reproduce). The assertions are the gate; the images are refreshed only when a
reviewed change alters what a screen looks like.
