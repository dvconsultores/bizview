# Proyectos en VS Code y Git

## Para qué sirve

Un proyecto también se puede trabajar fuera de la aplicación, en VS Code con los mismos comandos
de Spec Kit, y volver a traerlo o publicarlo en un repositorio Git.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. En el editor del proyecto pulsa **Descargar**: el .zip trae el proyecto con su carpeta
   `.specify/` y las plantillas de Spec Kit.
2. Ábrelo en VS Code y trabaja con los comandos `/speckit-…` de tu agente.
3. Valida desde la terminal con `bizview validate`. Para leer la estructura de las fuentes usa
   `bizview describe` con un token de [Abrir Tokens de acceso](app:/admin/tokens).
4. Para traerlo de vuelta, comprímelo y usa **Importar proyecto** en
   [Abrir Proyectos](app:/proyectos).

## Opciones

- Espacio Git: un repositorio con `projects/<slug>/` por proyecto se valida y aplica en
  [Abrir Espacio de trabajo](app:/admin/espacio). Un repositorio con el formato anterior se trata
  como el proyecto `principal`.
- `bizview project new` agrega un proyecto a un espacio Git.
- `BIZVIEW_LANG` elige el idioma de la línea de comandos.
- Un proyecto que viene de Git es de solo lectura en la aplicación: se cambia en el repositorio.
