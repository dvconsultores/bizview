🇪🇸 Español · 🇬🇧 [English](CONTRIBUTING.md)

# Contribuir a Bizview

¡Gracias por ayudar! Bizview es software libre bajo la licencia [GNU AGPL-3.0-or-later](LICENSE). Al
contribuir aceptas que tu contribución se publica con los mismos términos: no hay CLA ni cesión de
derechos de autor; tu trabajo sigue siendo tuyo, publicado con la misma licencia que el resto.

## Reglas básicas

- **Un solo producto para todos los clientes.** Nunca añadas nombres de clientes, logotipos,
  direcciones ni credenciales al repositorio. Todo lo que cambia de un cliente a otro es un ajuste
  (consulta [`docs/INSTALL.md`](./docs/es/INSTALL.md)).
- **Bizview no escribe proyectos.** El producto valida, importa, ejecuta y comparte proyectos
  escritos fuera de él. Un cambio que haga que el producto escriba un proyecto, una spec o una
  consulta queda fuera de alcance por diseño (consulta la constitución, principio IX).
- **El contrato tiene una sola fuente.** Los esquemas JSON y las reglas SQL de
  `cli/bizview_cli/schemas/` los leen la CLI, el backend y el paquete de autoría. Nunca valides lo
  mismo dos veces en dos sitios.
- **La base de datos es siempre externa.** No añadas contenedores de base de datos; las pruebas se
  ejecutan en un esquema temporal `app_test_*` de la base de datos de `DATABASE_URL_BI` y lo
  eliminan después.
- **La IA es opcional y privada.** Una función que llame a un proveedor debe funcionar con la IA
  desactivada, enviar solo agregados o metadatos y documentar exactamente qué envía. Dentro de
  0.2.0 eso es la página de ayuda de solo lectura.
- **Primero el móvil.** Cada pantalla funciona a 320 px sin desplazamiento horizontal, cumple
  WCAG 2.2 AA y funciona en iOS/Safari 14+.
- Las reglas del proyecto están en [`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## Ejecutarlo en local

Requisitos: Python 3.12+ con [uv](https://docs.astral.sh/uv/), Node.js 20+ y una base de datos
PostgreSQL en la que puedas escribir.

```bash
cp .env.example .env        # define DATABASE_URL_BI, SUPER_USER_EMAIL, SUPER_USER_PASSWORD
python starter.py           # instala dependencias, migra y arranca el backend + el frontend
# abre http://localhost:5173
```

## Pruebas y comprobaciones

```bash
sh scripts/gates/all.sh                                   # vocabulario, código muerto, dependencias, rutas, versión, markdown
sh scripts/gates/05-migration.sh                          # requiere DATABASE_URL_BI: rescate verificado, tablas eliminadas
cd backend  && uv run ruff check app tests alembic && uv run pytest
cd cli      && uv run ruff check . && uv run pytest       # CLI de bizview, esquemas, reglas SQL
cd frontend && npx tsc --noEmit -p . && npm test && npm run build && npm run check:compat
cd frontend && npx playwright install && npm run e2e      # Chromium/Firefox/WebKit, 320/375 px
bash deploy/tests/test_install.sh                         # instalador (REAL_DOCKER=1 para comprobar compose)
```

Ejecútalas antes de proponer un cambio: son las comprobaciones que pasan los mantenedores, y la CI
ejecuta los mismos comandos. Las pruebas del backend usan la base de datos PostgreSQL de
`DATABASE_URL_BI` y crean y eliminan allí esquemas temporales `app_test_*`.

## Flujo de especificación

Las funciones del producto se especifican antes de construirse, con
[Spec Kit](https://github.com/github/spec-kit):

```text
/speckit.specify    → specs/NNN-name/spec.md (historias de usuario, requisitos, criterios de éxito)
/speckit.clarify    → las partes poco especificadas, respondidas en la spec
/speckit.plan       → plan.md, research.md, data-model.md, contracts/, quickstart.md
/speckit.tasks      → tasks.md (ordenadas, una casilla por tarea)
/speckit.implement  → el código, las pruebas, las tareas marcadas
/speckit.converge   → lo que aún le falta al árbol, añadido como tareas
```

Estas habilidades son del **repositorio** (`.claude/skills/`), no del producto. Una especificación
es parte del cambio: a una solicitud de cambio que modifica el comportamiento sin su spec (o sin
actualizar la existente) se le pide que la incluya. `/speckit.all` ejecuta toda la secuencia para
una sola función.

Toda especificación que añade una superficie de cara al lector lleva una sección `## Docs`: qué
documento de `docs/` la describe y qué tema de ayuda (ver abajo) encuentra la persona usuaria en la
aplicación.

## Documentación y temas de ayuda

- **Todos los documentos se publican en los dos idiomas.** El inglés vive en la ruta canónica y el
  español a su lado: `docs/es/<name>.md` dentro de `docs/`, `<NAME>.es.md` en la raíz del
  repositorio, y `es/` y `en/` en la guía y en el paquete inicial. Una traducción conserva la forma
  de su original — los mismos encabezados en el mismo orden, los mismos bloques de código y tablas,
  los mismos enlaces — y la prosa se traduce, nunca se resume.
  `python3 scripts/check_docs_parity.py`, que ejecutan `make check` y la CI, falla ante un par
  ausente o desincronizado e imprime qué difiere.
- Los documentos para lectores viven en `docs/`: [`AUTHORING.md`](./docs/es/AUTHORING.md) (el contrato
  y el ejemplo completo), [`IMPORT.md`](./docs/es/IMPORT.md) (la puerta de entrada),
  [`REPORTS.md`](./docs/es/REPORTS.md) (la referencia campo por campo),
  [`RENDERING.md`](./docs/es/RENDERING.md) (qué hace el motor con un `report.yaml`),
  [`INSTALL.md`](./docs/es/INSTALL.md) (instalaciones).
- La ayuda dentro de la aplicación es `backend/app/guide/`: `index.yaml` contiene los metadatos de
  los temas (`id`, `section`, `title`, `summary`, `roles`, `routes`, `tiles`, `commands`, `aliases`,
  `related`) y `es/<topic>.md` + `en/<topic>.md` contienen los cuerpos. **Un tema nuevo necesita los
  dos idiomas**, los mismos cinco encabezados en cada uno (`Para qué sirve` / `Quién puede usarlo` /
  `Cómo se hace` / `Opciones` / `Problemas frecuentes`), y una entrada en `index.yaml`.
  `backend/tests/test_guide.py` impone la paridad, los ids, los roles y que las palabras en negrita
  de un tema sean etiquetas reales de la interfaz.
- Una página a la que enlaza la ayuda debe existir (`routes:`), y una ruta a la que la persona
  usuaria puede llegar debería tener un tema: `frontend/tests/unit/guide-drift.test.ts` comprueba
  ambas direcciones.

## Proponer un cambio de esquema

Los esquemas de los artefactos se versionan junto con el producto:

1. Cambia el esquema en `cli/bizview_cli/schemas/` y sube su `format_version` cuando el cambio no
   sea compatible hacia atrás.
2. Actualiza el validador de `cli/bizview_cli/validate.py` y las reglas que aplica, además de las
   pruebas de la CLI y [`docs/REPORTS.md`](./docs/es/REPORTS.md) (la referencia de campos).
3. Si los proyectos existentes dejarían de validarse, añade una nota de migración a la
   especificación y di en el registro de cambios qué tiene que cambiar quien escribe.
4. Regenera el paquete de autoría para que los espacios de trabajo nuevos reciban el nuevo esquema
   (`cli/bizview_cli/workspace_template/`) y vuelve a ejecutar `bizview validate` sobre el proyecto
   de ejemplo.
5. Actualiza el ejemplo de referencia (`backend/tests/fixtures/projects/coinmarketcap/`) si el
   cambio lo deja inválido; la suite del backend lo dibuja en cada ejecución.

## Solicitudes de cambio

1. Abre una incidencia primero para cualquier cosa mayor que una corrección pequeña, para que
   podamos acordar el enfoque.
2. Mantén los cambios acotados; incluye pruebas para los cambios de comportamiento.
3. Actualiza `CHANGELOG.md` en *Unreleased*.
4. Firma tus commits (`git commit -s`) para certificar el
   [Developer Certificate of Origin](https://developercertificate.org/).
5. El texto de la interfaz está en español y vive en `frontend/src/i18n/es.ts` y
   `backend/app/i18n/es.py`; el código, los comentarios y la documentación están en inglés.
6. Ejecuta `sh scripts/gates/all.sh` antes de subir los cambios; las mismas puertas se ejecutan en
   la CI.

## Versiones (mantenedores)

`VERSION` en la raíz del repositorio es la única fuente de verdad: súbelo, alinea
`backend/pyproject.toml`, `frontend/package.json`, `cli/pyproject.toml` y
`cli/bizview_cli/__init__.py`, y `sh scripts/gates/07-version.sh` demuestra que coinciden. Mueve las
notas de *Unreleased* de `CHANGELOG.md` bajo la nueva versión y luego etiqueta `v<VERSION>`: la
etiqueta debe ser igual al archivo. Las imágenes se construyen y se suben desde la máquina de un
mantenedor con `./deploy.sh` (Docker Hub: `bizview-backend` y `bizview-web`). Una versión publicada
en GitHub lleva las notas, no artefactos de compilación.

## Código de conducta

Todas las personas que participan deben seguir el [Código de conducta](CODE_OF_CONDUCT.md).
