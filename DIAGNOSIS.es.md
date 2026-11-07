🇪🇸 Español · 🇬🇧 [English](DIAGNOSIS.md)

# Diagnóstico — por qué `/speckit-all` no puede terminar `001-mercado-cripto` (041-speckit-all-root-cause)

Fecha: 2026-10-28. Método: primero lectura del código de principio a fin, después la evidencia y
después las pruebas que fallan. Todas las referencias a archivos son a la `main` actual (f7feae3).

## 0. Situación de la evidencia

- `tmp/evidence/bizview-chats.json` (procedente de ~/Downloads, exportado el 2026-10-19) es una
  **conversación distinta** (proyecto `artemisa`, spec `001-integracion-facturas`). No contiene
  ninguna de las firmas del fallo (ni mensaje de la guarda, ni `FileChanged`, ni "sin cambios desde
  la lectura anterior"). NO es el registro principal que el encargo daba por supuesto.
- `tmp/evidence/backend.log` (docker logs dashboard-backend-1, 676 862 líneas): ni `FileChanged` ni
  `IntegrityError` — coherente con el código: `_post_error` convierte `FileChanged` en un mensaje
  del chat y `log.exception` va al logger del hilo worker dentro del contenedor que sirvió realmente
  la conversación. El registro reciente del contenedor local está dominado por errores de
  conectividad con la base de datos hacia 190.120.249.37:5432.
- `tmp/evidence/coinmarketcap-project/` (zip del 2026-10-24): el proyecto **antes** de la ronda de
  convergencia atascada — solo existe `requests/listings.yaml`; `global-metrics.yaml`,
  `fear-greed.yaml` y las tareas T025–T028 se crearon después, en el borrador de la conversación.
- Conclusión: la transcripción de producción citada en el encargo es el registro de comportamiento;
  cada causa de abajo está demostrada **en el código** y se reproducirá con pruebas guionizadas de
  FakeProvider.

## 1. Qué hace cada pieza (paso 1 del método)

- `app/assistant/service.py` — un hilo worker por turno (`run_turn` → `_attempt_turn` → `_turn`). El
  bucle de rondas (service.py:2452) sigue hasta que no hay llamadas a herramientas, hasta un
  presupuesto de etapa, hasta una llamada fallida idéntica repetida o hasta `max_rounds` — que en
  modo Auto es **None** (propietario, 2026-10-27: "nunca porque se agote un contador de rondas").
  Cualquier excepción que escape de `_turn` llega a `_post_error`, que escribe «Ocurrió un error
  inesperado; lo hecho hasta la última ronda se guardó. (TypeName)» (`_error_text`,
  service.py:2166).
- `app/assistant/tools.py` — despacho de herramientas con guardas de ámbito de ejecución y
  memoización (`run_tool`, tools.py:922). Todas las escrituras del agente pasan por `_write_ops`
  (tools.py:1879), que llama a `_requests_checked` (la guarda de `fields`, tools.py:1849), después
  a `fs.apply_ops` y convierte `fs.FileChanged` en un ToolError recuperable.
- `app/assistant/origin.py` — `check_query` maneja archivos SQL, YAML de petición **y** reportes
  directos (una sola herramienta para los tres; no hay ninguna herramienta `check_request` en el
  repositorio). `run_check` (origin.py:1046) comprueba el **contenido actual del borrador** y
  guarda `session.query_checks[path] = {sha256, ok, columns, error, at}` — atención: **sin
  `keys`**.
- `app/assistant/commands/pipeline.py` — la máquina de estados de `/speckit-all`; `write_report`
  (pipeline.py:738) escribe `specs/<spec>/run-report.md` mediante `fs.apply_ops` **sin
  `base_sha256` y sin `force`**.
- `app/projects/fs.py` — `apply_ops` es la única vía de escritura; `base_check` (fs.py:423) lanza
  `FileChanged` siempre que el `base_sha256` de la operación difiera de la revisión registrada —
  incluso cuando la operación no envía **ninguna base** para un archivo que ya existe
  (`None != sha`).
- `app/engine/extract.py` — ejecuta peticiones REST/Supabase; `_records` (extract.py:386) mapea
  `fields` con `text_value(json_path(...))`, el valor en bruto a texto. **`timestamp_units` no
  aparece en ninguna parte del motor.**
- `cli/bizview_cli/validate.py` — acepta `timestamp_units` y solo rechaza una unidad que no nombra
  ningún campo mapeado (`_timestamp_units`, validate.py:689).
- `app/assistant/history.py` — el historial reproducido conserva los datos completos de las
  herramientas solo para el intercambio más reciente; los anteriores viajan como el resumen de una
  línea que se guardó.
- `app/assistant/preview.py` — mapea la familia «date/time field value out of range» de Postgres a
  `preview.timestamp_unit_mismatch`, cuyo texto le dice al agente que defina `timestamp_units`.

## 2. Causas demostradas

### C1 (H1, reformulada) — la guarda de `fields` es insatisfacible justo para los archivos para los que existe

`_requests_checked` (tools.py:1849) rechaza cualquier `write` de un YAML de petición durante
`speckit-implement`/`fix` salvo que `session.query_checks[path]["ok"] is True`.

Pero `check_query` solo puede comprobar el contenido **actual** del borrador (`run_check`,
origin.py:1051: `text = files.get(path)`; no hay forma de pasarle un contenido propuesto), y para un
archivo de petición `ok = not missing and not missing_columns and not mismatched` (`_shape_result`,
origin.py:840) — es decir, `ok` significa "el archivo actual ya coincide con la respuesta en vivo y
con el conjunto de datos".

Así que cuando un archivo de petición está mal — la única situación en la que el agente tiene que
escribirlo —, `check_query` registra necesariamente `ok: false`, y la guarda rechaza entonces la
escritura corregida con «Antes de escribir `fields` … ejecuta `check_query`». Volver a ejecutar
`check_query` no puede cambiar el resultado (mismo archivo, misma respuesta); la memoización
(`_check_query_deps`, tools.py:840) incluso reproduce el fallo en caché («Usó la estructura ya
consultada de "coinmarketcap"»). **Bloqueo mutuo.** El agente vuelve a leer («sin cambios desde la
lectura anterior» ×5), vuelve a planificar, reintenta — y, como el modo Auto no tiene tope de
rondas, el bucle corre hasta `ai_stage_token_budget`.

Dos defectos adyacentes en la misma guarda (afinados después de la ejecución de reproducción):

- Las `keys` SÍ se guardan cuando el agente llama a la **herramienta** `check_query` sobre una ruta
  de petición: el envoltorio 040 `_check_query` (tools.py:2199–2208) fusiona `{ok, keys}` en la
  entrada. Pero la guarda nunca llega a ellas: primero se bloquea con `ok is not True`
  (tools.py:1864). Y `origin.run_check` construye por sí mismo una entrada de **reemplazo** sin
  `keys` (origin.py:1093–1104), así que cualquier otro llamador (`recheck_draft`, la vía del
  reporte directo) borra las claves guardadas.
- El docstring dice `check_request`; la herramienta real es `check_query` (el mensaje de i18n es
  correcto).

Esto reproduce exactamente la transcripción: mensaje de la guarda → comprobación memoizada → nuevas
lecturas → repetir. T026 (`fields` de `global-metrics.yaml`) y T028 (discrepancia del endpoint) son
interminables.

### C2 (H2, reformulada) — `write_report` escribe sin base: el segundo reporte siempre tumba el turno

`pipeline.write_report` (pipeline.py:759) envía `{"op": "write", "path": "specs/<spec>/run-report.md",
"content": …}` sin `base_sha256` y sin `force`. `fs.base_check` trata una base ausente sobre un
archivo existente como un conflicto y lanza `FileChanged`. El contenido del reporte incluye tokens y
marcas de tiempo, así que un segundo reporte para la misma spec siempre son bytes distintos →
siempre una escritura → siempre `FileChanged`.

Ningún llamador lo captura: `end()` (service.py:2381) → `_report_at_end` → `write_report` → la
excepción se desenrolla por `_turn` hasta `_post_error` → «Ocurrió un error inesperado; lo hecho
hasta la última ronda se guardó. (FileChanged)».

La primera parada de una ejecución de `/speckit-all` escribe el reporte sin problema; **toda parada
o finalización posterior de la misma spec muere**, y por eso la conversación no puede terminar nunca
— incluso la parada por presupuesto del propio bucle C1 queda abortada por C2 al salir. (El
comentario de `_report_on_stop`, service.py:1854, declara la semántica de reemplazo que se
pretendía; la vía de escritura no puede reemplazar.)

La forma original de H2 (hash `seen` obsoleto de `read_draft`) queda descartada: `edit_draft`
calcula `base_sha256` a partir del contenido actual del archivo (tools.py:2047,2080), y un `seen`
obsoleto produce un ToolError recuperable («léelo con read_draft»), no una excepción; `_write_ops`
captura `fs.FileChanged` (tools.py:1888).

### C3 (H4) — `timestamp_units` existe en el comprobador y en el validador, no en el motor

La detección de `check_request` (origin.py:811–849), la regla del validador (validate.py:689) y el
texto del error de la vista previa (`preview.timestamp_unit_mismatch`, es.py:562 — "revisa
`timestamp_units` en la petición") existen desde 040 (E). El motor no: `extract._records` copia el
valor en bruto (`text_value`), y `timestamp_units` no se lee en ninguna parte bajo `app/engine/`. Un
epoch de fear & greed (`1730000000`) copiado con COPY a `snapshot_at timestamptz` falla en Postgres
con la familia de fuera de rango — y el mensaje de error manda al agente a declarar una perilla que
**no tiene efecto en tiempo de ejecución**. T025 (el mapeo de `snapshot_at` de `fear_greed`) es
interminable; el agente declara la unidad, la validación pasa, la vista previa vuelve a fallar,
bucle.

### C4 — no hay detector de ausencia de progreso por ronda (la corrección 5 del encargo, confirmada necesaria)

El único freno de repetición del bucle es `last_failed == signature` (service.py:2687): la *misma*
llamada fallando dos veces *consecutivas*. Un `read_draft` con éxito entre medias lo reinicia
(service.py:2683) — que es justo el patrón de producción (leer ×5, luego escribir, luego el error de
la guarda). Con `max_rounds = None` en Auto, nada más detiene los bucles C1/C3 antes del presupuesto
de etapa (`blocked:stage_budget`, service.py:2613).

### C5 — el bloqueo mutuo de la guarda sobrevivió a la primera corrección cuando la comprobación no lee NINGUNA forma (ejecución 133)

Evidencia de la base de datos de producción (sesión 24; ejecuciones 129 `FileChanged`,
130/132/133 `blocked:stage_budget`, ~600k tokens cada una, todavía en imágenes anteriores a la
corrección). Transcripción de la ejecución 133 (mensajes 7546–7594): el agente comprueba
`fear-and-greed.yaml`, el comprobador responde `'$.data' no es una lista en la respuesta` con
`keys: []` (origin.py devuelve el error **antes** de leer forma alguna cuando `records` resuelve a
un objeto), y a partir de ahí todo `edit_draft` correctivo — incluidos los que arreglan `records:` —
se rechaza con «Antes de escribir `fields`…» hasta que el presupuesto de etapa mata la ejecución. La
primera corrección de la guarda de 041 aceptaba una comprobación fallida **con claves**; un fallo
estructural guarda una entrada sin claves, que la guarda trataba como si no hubiera comprobación.
Insatisfacible otra vez: solo un archivo ya arreglado podía producir claves, y solo las claves
permitían arreglar el archivo. Corrección: una entrada de comprobación guardada para la ruta — sea
cual sea lo que encontró — autoriza la escritura; las claves, cuando existen, siguen validando los
tokens de campo simples.

### C6 — la plataforma no puede leer un endpoint con forma de objeto (la causa más profunda)

Los dos endpoints que necesita esta spec devuelven `data` como un único objeto JSON. El motor
(`extract._records`) y el comprobador (`origin._run_check_request`, las dos apariciones) rechazaban
cualquier ruta `records` que resolviera a un dict — así que los conjuntos de datos `global_metrics` y
`fear_greed` eran **imposibles de implementar** escribiera lo que escribiera el agente; cada
ejecución solo podía dar vueltas hasta que la detuviera un presupuesto o una guarda. Corrección: un
dict en la ruta de records cuenta como una lista de un solo registro en el motor y en el
comprobador, y la descripción del esquema `records` lo dice. Con C6 corregido, el comprobador lee
las claves reales del objeto, lo que además da a la guarda C5 la información que quiere.

### C7–C10 (encontradas el 2026-10-29 por el E2E local en vivo, cada una con la prueba primero y luego corregida)

Un E2E completo de `/speckit-all` sobre un proyecto nuevo (`panorama-cripto`, esquema aislado
`app_test_041dev`, código corregido, proveedor real de DeepSeek y API real de CoinMarketCap) sacó a
la luz cuatro causas más, cada una reproducida fallando antes de su corrección:

- **C7 — historial vacío más allá de la ventana de 30 filas.** Una conversación en Auto tiene un
  solo mensaje de usuario; `_scoped_history` buscaba el ancla solo dentro de las 30 filas más
  recientes, así que a partir de la tercera etapa el historial estaba vacío y la etapa moría con
  `blocked:ai_history_invalid`. Corrección: obtener directamente la fila de usuario más reciente ≤
  `history_from` cuando el escaneo por ventana no la encuentra (service.py).
- **C8 — archivos de petición imposibles de crear.** La guarda C5 rechazaba toda escritura no
  comprobada, mientras que `check_query` solo acepta archivos que existen: bloqueo mutuo en la
  creación. Corrección: un esqueleto sin `fields` se escribe libremente; declarar `fields` sigue
  exigiendo que se haya ejecutado una comprobación (tools.py).
- **C9 — una referencia a una carpeta bloquea su tarea para siempre.** `tasks_ticks` exigía que toda
  referencia entre comillas invertidas fuera una clave de archivo; «Crear la carpeta
  `integrations/x/`» nunca se marca, y una sola línea así anula un marcado en bloque — el muro de
  producción «hay N tareas sin completar». Corrección: una referencia terminada en barra queda
  probada por cualquier archivo que haya debajo (commands/guard.py).
- **C10 — fallos de vista previa a ciegas.** La línea de resultado de la IA omitía todo detalle de la
  comprobación, así que el agente quemaba ventanas de etapa enteras adivinando («comprobación
  contract no superada en altcoin_season»). Corrección: una clave `run.check.*` se reconstruye a
  partir de sus parámetros — columnas, recuentos, límites declarados, nunca valores de filas — y se
  añade a la línea (assistant/preview.py).

**Resultado del E2E (2026-10-29):** con C1–C10 en su sitio, el pipeline completó implement para
001-mercado-cripto con las 36 tareas marcadas y una **vista previa en verde contra la API en vivo**
(assets=100, global_metrics=1, fear_greed=1, altcoin_season=1 — los dos endpoints con forma de
objeto se extraen gracias a C6). Se usó un mensaje de dirección con la propia corrección del
validador `/speckit-implement … --only T001,…` para centrar una ventana, imitando el botón
«Implementar tareas pendientes» del producto.

### C12 (observada el 2026-10-29, CORREGIDA 8aa22e8 — el cursor respeta los artefactos ausentes) — una etapa vacía aun así avanza el cursor

Una ejecución de etapa puede completarse sin haber escrito nada (el modelo la cierra o salta con
`run_command`), y el cursor del pipeline en curso avanza entonces; cuando más tarde el modelo intenta
reabrir la etapa saltada, se le rechaza («La etapa 4/8 del plan es /speckit-tasks, no
/speckit-plan: ábrela en ese orden») aunque el artefacto de la etapa (plan.md) no exista. `detect()`
repara el cursor a partir de los artefactos solo en un `/speckit-all` nuevo. Dirección de la
corrección: el cursor de la ejecución debería consultar la misma prueba de artefacto que usa
`completed()` antes de rechazar una reapertura, o una finalización sin artefacto de specify/plan/tasks
no debería avanzar el cursor.

### C15 (observada el 2026-10-29 en producción, CORREGIDA f5a4677) — el reporte de ejecución vuelve a ensuciar un proyecto aplicado

El pipeline aplica (se toma la instantánea) y solo después escribe `run-report.md` y la contabilidad
del estado de la spec en el borrador — así que un proyecto recién aplicado vuelve a mostrar «Cambios
sin aplicar» de inmediato. Cosmético, pero corroe la confianza. Dirección de la corrección: escribir
el reporte y los cambios de estado antes de la instantánea de aplicación, o excluir los archivos
generados de la comparación de cambios pendientes.

### C14 (observada el 2026-10-29 en producción, CORREGIDA 8aa22e8 — alcance del encargo de converge) — converge añade tareas que implement no puede completar

Converge añadió T026–T030 a 002-panorama-cripto; T030 pide editar una línea de contenido de la spec
(`**Uses**`) y T028 pide verificar o corregir el archivo de la OTRA spec — pero las reglas de
escritura de la etapa implement solo permiten marcar tareas, cambiar `**Status**` y escribir los
artefactos de la propia spec. El agente se niega con razón a marcar lo que no pudo hacer, así que
`verify` falla para siempre («hay 5 tareas sin completar»). Dirección de la corrección: converge solo
debe añadir tareas cuya evidencia pueda producir implement (artefactos de la propia spec, archivos de
reporte o de integración), y una tarea que nombra una línea de un documento de spec debería
ejecutarla converge mismo (es quien añade a tasks.md) o dirigirse a la etapa que es dueña del
archivo.

### C11 (observada el 2026-10-29, CORREGIDA 4efc4e8 — la parada reintenta el bloqueo mutuo) — «Detener» puede dar un 500 en un bloqueo mutuo de Postgres

`POST /sessions/{id}/stop` → `service.stop` → `runs.mark_stale_interrupted` actualiza cada fila
`running` de `assistant_command_run` mientras la transacción del turno en vivo está actualizando esa
misma fila: ciclo de ShareLock, `DeadlockDetected`, sin manejar → 500. Visto en el E2E local mientras
la etapa implement estaba confirmando una ronda. Dirección de la corrección: reintentar una vez la
actualización de la parada ante `DeadlockDetected` (o con skip-locked), y mapear el fallo a la
respuesta normal de "parada solicitada" — el propio commit del turno ya registra la marca de parada.

## 3. Descartado

- **H1 tal como estaba planteada** (la guarda exige una herramienta que no existe para REST):
  `check_query` acepta rutas `requests/*.yaml` (origin.py:1076–1081) y el mensaje de i18n nombra
  `check_query`. Lo insatisfacible es el requisito `ok is True` (C1), no el nombre de la herramienta.
- **H2 tal como estaba planteada** (hash obsoleto de la caché de lectura enviado como revisión): ver
  C2; las bases de `edit_draft` están frescas y `_write_ops` captura el conflicto. El `FileChanged`
  que escapa viene de la escritura sin base de `write_report`.
- **H3** (la forma corta de lectura sin cambios sigue enviando contenido): nota de regresión
  deliberada y fechada en tools.py:2129–2133 — una corrección del 2026-10-26 hizo corta la forma
  corta y el modelo perdió el archivo («no puedo leer el contenido real», 20M tokens). Entre turnos,
  `history.build` ya reproduce los resultados antiguos de herramientas como resúmenes de una línea
  (history.py:243–246), así que las lecturas no se acumulan entre turnos; dentro de un mismo turno
  largo de Auto sí lo hacen, pero la cura es detener el bucle (C4), no volver a truncar las lecturas.
- **H5** (estado guardado incoherente tras las caídas): el fallo del `tool_result` huérfano está
  corregido — los resultados se escriben una vez por ronda, emparejados por
  `call_id`/`assistant_message_id` (service.py:2728–2731); `IntegrityError` pasó a ser una parada con
  nombre `StateConflict` (040 paso 0, service.py:2138); `rewind` devuelve el cursor a la etapa sin
  terminar (pipeline.py:705). La conversación atascada puede reanudarse una vez corregidas C1–C3;
  nada del estado guardado vuelve a entrar en el callejón sin salida por sí solo (el callejón era
  código vivo, no estado).

## 4. Diseño de la corrección (forma aprobada, ajustada a lo demostrado)

1. **Guarda (C1)** — `run_check` guarda `keys` (y mantiene `skipped`) en `query_checks[path]`.
   `_requests_checked` acepta una escritura cuando la última comprobación **leyó la forma** (`keys` no
   vacío, o `skipped`, o `ok is True`) y después valida los `fields` del contenido **nuevo** contra
   esas `keys`. Una comprobación que dio error (sin forma) sigue bloqueando. El docstring nombra
   `check_query`. Afinamiento encontrado al revivir la comprobación muerta de 040 (E): comparaba
   **nombres de columna** de salida con las claves de la respuesta, lo que da falsos positivos en
   cualquier columna renombrada (`snapshot_at: snapshot`). La comprobación viva juzga en cambio la
   **ruta** mapeada, y solo cuando es una clave simple de primer nivel — las rutas anidadas o
   indexadas las juzga la propia comprobación.
2. **Escritura del reporte (C2)** — `write_report` envía `force: True` (el reporte de ejecución es
   generado, determinista y propiedad del pipeline; la revisión se sigue registrando para auditoría).
   La constitución IX no se toca: el reporte nunca marca tareas como hechas.
3. **Motor (C3)** — `extract._records` convierte los valores mapeados cuya columna está declarada en
   `timestamp_units`: `seconds`/`milliseconds` → ISO-8601 en UTC (`iso8601` pasa tal cual); los
   valores no numéricos pasan tal cual para que Postgres siga nombrando los datos malos. Además NO se
   añade una comprobación de rango en la vista previa: el error de Postgres existente ya se mapea al
   mensaje con nombre y, con esta corrección, la unidad declarada se aplica de verdad.
4. **Parada por falta de progreso (C4)** — en el bucle de rondas: tras 3 rondas consecutivas con el
   mismo conjunto de firmas de llamadas a herramientas y sin escribir ningún archivo, terminar la
   etapa con `blocked:no_progress`, nombrando las herramientas que se repiten y el último error.
   Respeta la regla del propietario de "sin contador de rondas": se detiene ante una falta de
   progreso demostrada, no ante un recuento.

## 5. Verificación (ejecutada el 2026-10-28)

- `tests/test_assistant_root_cause_041.py` (7 pruebas): cada causa se reprodujo fallando por el
  motivo alegado primero (ToolError de la guarda `check_request_first`; `fs.FileChanged` desde el
  segundo `write_report`; epoch en bruto saliendo de `_records`; 6 rondas de proveedor en vez de una
  parada) y después en verde tras las correcciones. Dos son guardas de regresión que ya pasaban (las
  claves que guarda el envoltorio de herramientas de 040; una petición **sin comprobar** sigue
  bloqueando).
- C5/C6 (añadidas tras la evidencia de la ejecución 133, mismo archivo, ahora 10 pruebas): la entrada
  de fallo estructural bloqueaba la corrección de `records` (ToolError, C5), `extract._records`
  reventaba con un objeto (C6) y `check_query` no leía claves de una respuesta con forma de objeto —
  las tres fallaron por el motivo alegado primero y luego quedaron en verde tras las correcciones de
  la guarda, el motor y el comprobador.
- `tests/test_assistant_root_cause_041_e2e.py`: la transcripción de producción reproducida en el
  bucle real de `/speckit-implement` — la escritura sin comprobar se rechaza, la comprobación fallida
  lee la forma, la misma escritura entra entonces, la ejecución queda `completed`, sin «error
  inesperado», con los `fields` corregidos y `timestamp_units` en disco.
- Afinamiento del detector que encontraron las suites: las rondas *exitosas* idénticas son un patrón
  de trabajo (la propia prueba del límite de descubrimiento guioniza tres), así que solo cuenta una
  ronda idéntica que además falló y no escribió nada; `blocked:no_progress` tras tres.
- Suites afectadas en verde: test_assistant_request_shape, test_assistant_guard, test_assistant_loop,
  test_assistant_speckit_all, test_assistant_commands_guard, test_assistant_preview — salvo tres
  fallos que también fallan en la main limpia f7feae3 (preexistentes, NO de 041; verificados en un
  worktree en ese commit):
  `test_assistant_guard.py::test_discovery_limit_restricts_then_returns_after_draft`,
  `test_assistant_loop.py::test_context_too_long_retries_with_latest_round`,
  `test_assistant_loop.py::test_context_too_long_twice_reports_error` (las dos pruebas de contexto
  esperan el mensaje antiguo del proveedor; el código ahora responde con el texto de reanudación de
  etapa de 040).
- Suite del frontend: en verde (vitest, salida 0). Suite completa del backend: el resultado se
  registra abajo cuando termine.

## 6. Pasos en producción

- Despliegue: reconstruir la imagen del backend; ninguna migración de base de datos (`query_checks` es
  JSONB; no hay cambio de esquema). La imagen del worker comparte el código del motor
  (`timestamp_units`), así que hay que reconstruirla también.
- La conversación atascada SÍ se puede reanudar tras el despliegue: `/speckit-all 001-mercado-cripto`.
  El cursor rebobinado repite la etapa sin terminar; las escrituras antes imposibles pasan a ser
  posibles (la guarda acepta un archivo comprobado sea cual sea lo que encontró la comprobación;
  `timestamp_units` se respeta al extraer; los dos endpoints con forma de objeto —
  `global-metrics/quotes/latest` y `fear-and-greed/latest` — ahora se extraen como un solo registro).
  El estado guardado es coherente (resultados emparejados por ronda, 036), así que nada vuelve a
  entrar en el callejón sin salida.
- Nota sobre el borrador actual: `fear-and-greed.yaml` lleva un escalar inválido
  `timestamp_units: seconds` (el esquema quiere un mapa). El motor ignora lo que no es un dict y el
  validador lo señala, así que al agente se le dirá y podrá corregirlo — no hace falta editarlo a
  mano.
- Si el presupuesto de tokens de la conversación está agotado, empieza una conversación nueva sobre
  el mismo proyecto: los archivos y las specs se conservan.
