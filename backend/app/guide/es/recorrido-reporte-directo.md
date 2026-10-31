# Un reporte directo paso a paso

## Para qué sirve

Crea un tablero sobre una tabla que ya existe (por ejemplo `bi_ventas`, preparada cada noche por
otro proceso), sin integración ni ETL.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Si la tabla está en una fuente PostgreSQL, abre la fuente en
   [Abrir Fuentes de datos](app:/admin/fuentes), marca **Permitir reportes directos** y guarda
   (se pide tu contraseña). Si está en la base BI de esta instalación, usa la fuente `bi`.
2. En [Abrir Proyectos](app:/proyectos) pulsa **Nuevo proyecto**, ponle nombre y pulsa
   **Crear proyecto**; se abre el editor.
3. Escribe la spec de **Reporte** con las líneas `**Modo**: directo`, `**Fuente**:` y
   `**Tablas**:`, y añade qué quieres ver (métricas, dimensiones, período).
4. Escribe `reports/<id>/report.yaml` con esas métricas, dimensiones y vistas.
5. Pulsa **Validar**: comprueba el YAML y la consulta de cada métrica.
6. Cuando diga **Listo para aplicar**, pulsa **Aplicar proyecto**, **Confirmar** y escribe tu
   contraseña.
8. En [Abrir Usuarios](app:/admin/usuarios), da **Acceso a tableros** a quienes deban verlo.
9. Abre el tablero: dirá «Datos en vivo · … · consultado …».

## Problemas frecuentes

- Si la consulta falla porque una columna no existe, la estructura de la tabla cambió: actualiza
  la spec y el reporte con las columnas nuevas y vuelve a validar.
