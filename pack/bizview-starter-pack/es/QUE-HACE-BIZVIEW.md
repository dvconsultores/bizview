# Qué hace BizView con tu proyecto

Este documento explica, en lenguaje llano, qué ocurre cuando subes el zip (importar) y qué
ocurre cuando lo pones en marcha (aplicar). Nada se ejecuta y nadie ve nada hasta que aplicas.

## Importar

1. BizView lee el zip en memoria, quita la carpeta que lo envuelve si la hay, y rechaza los
   ejecutables y los scripts escondidos en un SVG.
2. Mapea cada archivo al formato del proyecto y lista los que no lo son como ignorados: no se
   guardan y el proyecto se importa igual.
3. Comprueba los presupuestos antes de escribir nada: artefactos (400 archivos, 2 MB por archivo,
   20 MB en total) e imágenes (2 000 archivos, 300 KB por imagen, 25 MB en total). Un rechazo nombra
   el límite que se pasó.
4. Si el `slug` ya existe, el zip es una revisión nueva de ese proyecto; si quieres un proyecto
   aparte, pide una copia y BizView la crea con otro slug.
5. Valida el árbol completo con el mismo validador que la CLI: esquemas, SQL de forma estática,
   referencias entre archivos, datos personales contra la spec y si la spec está completa. Los
   problemas se muestran archivo por archivo, con una corrección propuesta.
6. Guarda el proyecto como borrador: nada corre y no lo ve ningún usuario.

## Aplicar

1. El borrador se compone con los demás proyectos aplicados en una versión nueva de la
   instalación y se vuelve a comprobar; los identificadores repetidos entre proyectos son errores de
   verdad.
2. Cada integración se registra con el worker: la primera ejecución es una carga completa y después
   corre la programación (`cron`), que hace la ventana incremental (`:window_start`/`:window_end`) o
   una recarga completa según `incremental.mode`.
3. Los datasets aterrizan en el esquema `ds_<integración>.<dataset>` con `_run_id` y `_loaded_at`.
4. Cada reporte se convierte en un tablero en `/r/<id>`, visible para los roles de `access`, con
   filtros, períodos, comparación, PDF/CSV y enlaces para compartir.
5. La aplicación queda en la auditoría y Volver a la versión anterior lo revierte todo.
6. Lo primero que conviene mirar: Integraciones para la última ejecución, Tableros para el
   tablero nuevo y Proyectos para los problemas pendientes.
