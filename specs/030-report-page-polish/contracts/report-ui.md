# Contract — report page UI (container, meta line, actions, sheet, chips)

The reader-facing contract of the report page and the shared view (US1–US3, FR-001…FR-005, FR-012).

## 1. Container

| Viewport | Content |
|---|---|
| ≥1024 px | the app container: `mx-auto w-full max-w-screen-2xl` + `px-4 sm:px-5 lg:px-4` — identical to the Tableros list |
| 375 px | same container, 16 px gutters, no horizontal scroll |
| TV mode | full width, chrome hidden (existing behaviour) |
| Shared view | same container, in its own header + main (it lives outside the shell) |

There is exactly one definition (`frontend/src/lib/layout.ts` → `APP_CONTAINER`, `APP_GUTTER`) and
`PageContainer` is the only component that composes it.

## 2. Header order

```text
breadcrumbs
title                                        [ Filtros ] [ Parámetros ] [ PDF ] [ Compartir ] …
description
meta line:  Año en curso · 1 ene – 23 oct 2026 · vs 2025 · Datos 23 oct 20:00
chips:      Estatus: pagada ×   Zona: norte ×   +2 más
auto-refresh status line
KPIs …
```

- No "Parámetros del reporte" card exists anywhere.
- "Consultado por" is never rendered on screen (PDF footer + audit only).
- The meta line truncates in the middle, never inside a date; on phones the period keeps the first
  line and the rest wraps to a second.
- Chips wrap to two lines, then "+N más" opens the sheet on its Filtros tab.

## 3. Actions

| Action | ≥1024 px | 640–1023 px | <640 px | Condition (unchanged) |
|---|---|---|---|---|
| Filtros (count) | icon + label | icon + label | icon + label | always |
| Parámetros | icon + label | icon + label | icon + label | always |
| Descargar PDF | icon + label | icon + `title` | inside "⋯" | `def.pdf` |
| Compartir | icon + label | icon + `title` | inside "⋯" | admin + dashboard code |
| Enviar por correo | icon + label | icon + `title` | inside "⋯" | dashboard code + email available |
| Envíos programados | icon + label | icon + `title` | inside "⋯" | admin + dashboard code |
| Modo TV | icon + label | icon + `title` | inside "⋯" | always |

The "⋯" button is `aria-haspopup="menu"` with `aria-expanded`, roving focus, Esc closes and returns
focus (the `CardMenu` pattern). Every control is ≥44×44 px (`min-h-tap min-w-tap`) and has an
accessible name in the active language.

## 4. `ReportSheet`

| Aspect | Behaviour |
|---|---|
| Desktop ≥1024 px | right side sheet, 360 px, no backdrop, dashboard scrollable and clickable behind; 200 ms slide |
| <1024 px | bottom sheet, drag handle, `max-height: 70vh`, dashboard visible above; swipe-down closes |
| Semantics | `role="dialog"`, `aria-modal="false"`, `aria-labelledby` = active tab title |
| Focus | moves into the sheet on open; Tab cycles inside while open; Esc closes; focus returns to the opener; trap released on close |
| Outside click | closes on desktop |
| Tabs | "Filtros" (default when opened from Filtros) · "Parámetros" (default when opened from Parámetros) |
| Filtros tab | one control per declared filter, search inside long lists, "Limpiar", "Listo" |
| Parámetros tab | period, comparison, custom range, auto-refresh, export format, "Paleta" |
| Applying | live, debounced 250 ms; the URL is the state (`?period=…&compare=…&filter=…`); charts update with the sheet open |
| Unknown filter in URL | ignored, one-line notice inside the sheet |
| Reduced motion | no slide, no chart transition |

## 5. Shared view

Header: `Logo · organization name` … `[ Español | English ] [ ☀ | ☾ ]` — the theme toggle uses the
same roving-radio pattern as the language switcher, defaults to the device appearance, persists in
`localStorage` (`bizview.theme`) and re-themes without a reload. A PDF downloaded from the shared view
is always light.
