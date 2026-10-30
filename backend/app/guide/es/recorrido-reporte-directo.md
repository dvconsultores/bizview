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
   **Crear proyecto**; se abre su chat.
3. Escribe `/speckit-specify Reporte directo sobre la tabla bi_ventas, sin ETL` y añade qué quieres
   ver (métricas, dimensiones, período). El agente crea la spec de **Reporte** con las líneas
   `**Modo**: directo`, `**Fuente**:` y `**Tablas**:` y te hace las preguntas que falten.
4. Ejecuta `/speckit-plan` y luego `/speckit-tasks`.
5. Ejecuta `/speckit-implement`. Responde «sí» si pregunta por aprobar la spec. El agente escribe
   `reports/<id>/report.yaml`, comprueba la consulta y corre la vista previa.
6. Revisa la vista previa (y su PDF) en el editor.
7. Cuando diga **Listo para aplicar**, pulsa **Aplicar proyecto**, **Confirmar** y escribe tu
   contraseña.
8. En [Abrir Usuarios](app:/admin/usuarios), da **Acceso a tableros** a quienes deban verlo.
9. Abre el tablero: dirá «Datos en vivo · … · consultado …».

## Problemas frecuentes

- Si la consulta falla porque una columna no existe, la estructura de la tabla cambió: pide al
  agente revisar la spec con `/speckit-clarify` o actualiza el reporte.
