# Geometry contract — mobile fixes, round 2 (062)

The Playwright suite asserts these numbers at 360 × 780 and 393 × 851, in both themes. A unit test may
assert a class; the geometry below is what a person actually sees.

## 1. Sign-in providers

| At | Assertion |
|---|---|
| 360 × 780 | two buttons, same `offsetWidth` within 1 px, equal to the form's width; `offsetHeight ≥ 44`; the second's `top` ≥ the first's `bottom` |
| 1280 × 900 | same: one per row, full width of the form column |
| one provider enabled | one full-width button, label `Continuar con Google` |

## 2. Sheet

| Measurement | Expected |
|---|---|
| `panel.offsetHeight` | `window.innerHeight` (a `< 2 px` difference for rounding) |
| drag handle (`[data-sheet-handle]`) | absent |
| footer visible | `footer.bottom ≤ innerHeight` and `footer.top ≥ 0` |
| last control at scroll end | `lastControl.bottom ≤ footer.top` |
| body scroll | `scrollHeight > clientHeight` when the content overflows |
| back button (`history.back()`) | the sheet is gone and focus is on the opener |

## 3. Maximized dialog

| Measurement | Expected |
|---|---|
| `<h2>` textContent | the metric label (KPI) / the component title (chart) — never `k_…` |
| `<h2>.offsetWidth / header.offsetWidth` | `≥ 0.5` at 360 px — the brief asked for 0.6, which five 44 px actions make impossible: the header is 328 px and three actions plus gaps take ~140 px, leaving 188 px (57 %) |
| `<h2>.scrollHeight` | `=== clientHeight` (one line) |
| each action button | `offsetWidth ≥ 44` and `offsetHeight ≥ 44` |
| chips row | `top` ≥ title `<h2>`'s `bottom` |

## 4. Pie / donut

| Measurement | Expected |
|---|---|
| dashboard svg `width` at 360 | `≥ 200` (and `≤ containerWidth − 32`, the card's gutter) |
| maximized svg `width` at 360 | `≥ 300` — the dialog body is already padded, so the ring may take its measured width (328 px at 360) |
| legend `<ul>` `top` at 360 | `≥` svg `bottom` (below the ring) |
| legend `<ul>` `top` at 1024 | beside the ring: same band as the svg |
| card with no data | card `offsetHeight ≥ 240` so nothing jumps |

## 5. Source form

| Measurement | Expected |
|---|---|
| any element inside the form with `position: sticky \| fixed` | none |
| `Guardar` `top` | `>` the last field's `bottom` (after it in document order) |
| action buttons at 360 | each `offsetWidth` equals the form width |
| `Eliminar fuente` | rendered after **Probar conexión** |
| bottom gap | `form.bottom` ≤ `innerHeight − 0` when scrolled to the end (nothing cut) |
