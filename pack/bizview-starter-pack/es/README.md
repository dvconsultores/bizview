# {{name}} — paquete inicial de BizView

1. Rellena `REQUEST.md` (5 minutos).
2. Da esta carpeta a tu IA, o pega `PROMPT.md` + `REQUEST.md` (y `sources/…/structure.md` si lo hay)
   en el chat, y pide el proyecto.
3. Importa en BizView el zip que te devuelva: **Proyectos → Importar proyecto**.

```
REQUEST.md      lo que quieres, en tus palabras
PROMPT.md       las reglas para tu IA (las mismas para Claude Code, Codex o ChatGPT)
project.yaml    nombre, slug y fecha del proyecto
specs/001-…     la spec, el plan y las tareas
integrations/   la lectura del origen (solo si hay integración)
reports/        el tablero
.bizview/       los esquemas que valida BizView
```

Detalle de cada archivo: `CONTENIDO.md`. Qué pasa al importar y al aplicar: `QUE-HACE-BIZVIEW.md`.
Si prefieres otra herramienta, `CLAUDE.md` y `AGENTS.md` llevan el mismo texto que `PROMPT.md`.
