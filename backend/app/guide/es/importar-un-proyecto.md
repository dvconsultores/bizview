# Importar un proyecto

## Para qué sirve

Un proyecto entra en BizView de una sola forma: se escribe fuera (con Claude Code, Codex, DeepSeek,
un editor o a mano) y se importa como archivo `.zip`. No hay un botón que cree un proyecto vacío.

## Quién puede usarlo

Solo el **Superusuario**, y se pide confirmar la contraseña.

## Cómo se hace

1. Prepara la carpeta del proyecto con su `project.yaml`, sus specs y sus reportes, y comprímela:
   `zip -r proyecto.zip proyecto/`.
2. Abre [Abrir Proyectos](app:/proyectos) y pulsa **Importar proyecto**.
3. Elige el `.zip`. Antes de subirlo, BizView lee su contenido y muestra **Artefactos** e
   **Imágenes** con lo que traen y su límite. Si uno se pasa, **Importar ahora** queda deshabilitado
   y el aviso dice cuál se pasó y por qué.
4. Escribe tu contraseña y el proyecto se crea con lo que trajo el zip; se abre su editor.

Los dos límites se cuentan por separado, para que un juego de logos no gaste el espacio que
necesitan las specs:

| Límite | Qué cuenta | Archivos | Por archivo | Total |
|---|---|---|---|---|
| Artefactos | `project.yaml`, `specs/`, `integrations/`, `reports/`, `themes/`, `distributions/` | 400 | 2 MB | 20 MB |
| Imágenes | `assets/` | 2 000 | 300 KB | 25 MB |

El zip puede pesar la suma de los dos (45 MB). El aviso siempre nombra un límite, sus carpetas y
sus números.

## Opciones

- **Archivos ignorados (fuera del formato del proyecto)**: lo que no es del proyecto (`PROMPT.md`, `REQUEST.md`, `request/`,
  `sources/`, `.bizview/`, `README.md`, `.DS_Store`) no se guarda y se lista al terminar. El
  proyecto se importa igual.
- Un archivo que parece un programa (`.js`, `.sh`, `.exe`…) cancela la importación y se nombra: no
  es ruido.
- **Límites de importación**: al pie de la tarjeta de Proyectos, el superusuario puede cambiarlos.
  Un campo vacío significa el predeterminado de la instalación. El cambio queda en la auditoría.
- Si un límite te queda corto y ya cambiaste el de la instalación, vuelve a elegir el zip: la
  lectura se hace con los límites vigentes.
- Los comandos `bizview validate` y `bizview import --dry-run proyecto.zip` dicen los mismos números
  desde tu equipo, sin subir nada.

## Relacionados

- Proyectos
- Proyectos en VS Code y Git
- Aplicar un proyecto
- Estructura de un proyecto
