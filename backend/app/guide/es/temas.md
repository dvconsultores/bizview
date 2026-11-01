# Escribir un tema

## Para qué sirve

Un tema es un archivo de datos —colores y unas pocas decisiones de forma— que cualquiera escribe
fuera de Bizview, con o sin una IA, y que entra por Apariencia o dentro de un proyecto. Nunca lleva
CSS, ni fuentes, ni marcado.

## Quién puede usarlo

Cualquier persona que prepare un proyecto; subirlo a la instalación lo hace el **Superusuario**.

## Cómo se hace

1. Copia `THEME.md` del proyecto: trae la forma exacta del archivo y las reglas que se comprueban.
2. Escribe `themes/<id>.yaml` con los tokens de `light` y de `dark`.
3. Valídalo sin servidor: `bizview theme validate themes/<id>.yaml`.
4. Míralo antes de subirlo: `bizview theme preview themes/<id>.yaml --out preview.svg`.
5. Súbelo en [Abrir Apariencia](app:/admin/apariencia) con **Subir tema**, o déjalo en `themes/`
   dentro del proyecto y entra al importarlo.

## Opciones

- `light` y `dark`: los mismos tokens en cada modo. Los colores son `#RRGGBB` y `series` lleva de
  3 a 8 entradas.
- `strategy`: `categorical` o `sequential` (una sola familia de color, que se comprueba por pasos
  de luminosidad).
- `shape`: `radius`, `density`, `kpi_scale`, `font` y `badge`, cada uno de una lista cerrada.

## Problemas frecuentes

- «no es un archivo legible»: el YAML tiene un error de sintaxis; casi siempre una comilla o una
  sangría.
- «… vs …: 3.9:1 (needs 4.5:1)»: ese par de tokens no alcanza el contraste mínimo. Cambia el color,
  no la regla.
- «series[1] vs series[2]: ΔE 4.0»: dos series se parecen demasiado; separa los tonos.
- El PDF siempre usa la variante clara del tema, aunque el informe esté en oscuro.
