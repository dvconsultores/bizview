# Apariencia

## Para qué sirve

Elige la paleta de colores de todos los reportes de la instalación: cifras, series de los gráficos,
semáforos de variación y el PDF.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Abre [Abrir Apariencia](app:/admin/apariencia).
2. Cada tarjeta muestra una **Paleta** en tema claro y oscuro. Elige una y pulsa **Guardar**.
3. Desde ese momento todos los reportes que no declaren su propia paleta la usan, en pantalla y en
   el PDF.

## Opciones

- **Impacto** (por defecto): colores saturados, cifras grandes y tarjetas con más relieve en modo
  oscuro.
- **Clásico**: la apariencia de siempre.
- **Monocromo**: ocho tonos del color de la marca.
- **Contraste alto**: AA+ para televisores y proyectores.
- **Daltónico**: conjunto seguro para daltonismo.

## Problemas frecuentes

- El color principal de la marca sigue mandando en los botones y enlaces; las series de los gráficos
  vienen siempre de la paleta elegida.
- Un reporte puede declarar su propia paleta en su definición (`layout.theme.palette`); ese valor
  gana sobre el de la instalación y viaja con la versión del espacio de trabajo.
