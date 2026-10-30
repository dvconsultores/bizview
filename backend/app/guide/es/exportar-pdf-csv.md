# Exportar a PDF o CSV

## Para qué sirve

Descarga un reporte completo en PDF o los datos de una tarjeta en CSV, con los filtros que
tienes aplicados.

## Quién puede usarlo

Cualquier persona con acceso al tablero.

## Cómo se hace

1. Aplica los filtros y el período que quieras (ver Filtros y períodos).
2. Abre **Parámetros** y, en la sección **Exportar**, elige el **Formato**: **PDF** o **CSV**.
3. Pulsa **Generar reporte**. También puedes usar **Descargar PDF** en la parte superior del
   reporte.
4. Para una sola tarjeta, abre su menú (**Opciones de** …) y elige **Descargar CSV**.

## Opciones

- Se exporta la selección aplicada: los cambios sin aplicar no cuentan.
- El CSV usa punto y coma como separador y abre bien en Excel; su formato no cambia.
- La exportación a PDF la habilita el reporte con `pdf.enabled: true`.
- Cuando el reporte declara `layout.pdf`, el PDF arma sus bloques en el orden declarado: cabecera
  con el logo de la instalación, indicadores, gráficos, tablas y pie. Usa el tamaño de página, la
  orientación y los márgenes que declara (en milímetros); el logo sale de la marca de la
  instalación por su rol, nunca por una ruta.
- Una tabla que no entra continúa en la página siguiente con su cabecera repetida, o se corta y
  termina con una línea del tipo «y 5 filas más» que dice cuántas filas quedaron fuera: lo elige
  el reporte. El pie que declara el layout puede llevar la fecha de generación, el número de
  página y una línea legal.
- Sin `layout.pdf`, el PDF usa la plantilla de siempre: los reportes que nunca la declaran no
  cambian.
- El PDF muestra las mismas cifras que el tablero con los mismos filtros y período, porque los
  dos se arman con los mismos datos.

## Problemas frecuentes

- «Espera a que el reporte termine de cargar.»: la exportación se habilita cuando el reporte
  terminó de cargar.
- «No se pudo generar el PDF.»: inténtalo de nuevo en un momento.
