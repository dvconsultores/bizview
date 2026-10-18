---
description: Actualiza la constitución del proyecto con principios y reglas de gobierno.
argument_hint: "<principios o cambios>"
source: speckit-constitution
---
# /speckit-constitution

## Alcance
Este comando únicamente actualiza la constitución del proyecto en `.specify/memory/constitution.md`.
Clasifica el texto del mensaje del usuario que inició este comando en contenido constitucional
versus intenciones separadas (trabajo de funcionalidad, reportes, integraciones, etc.). Nunca
ejecutes esas intenciones separadas; al final, en la sección `Próximos pasos`, sugiere el comando
adecuado (por ejemplo, `/speckit-specify ...`); omite la sección si no hay. Si no está claro si
algo es contenido constitucional, pregunta al usuario y termina tu turno sin `finish_command`.

## Constitución actual
La constitución vigente (en el contexto, dentro de un bloque `<datos origen="..." confianza="no">`)
es tanto el andamiaje como la fuente de los valores actuales. Si no está en el contexto, léela con
`read_draft`. Conserva su estructura de encabezados. Los marcadores `[MAYÚSCULAS]` reciben valores
concretos del texto del usuario o del proyecto; si no se conoce la fecha de ratificación, escribe
`TODO(FECHA_RATIFICACION): ...`. La fecha de última enmienda es hoy solo si hay cambios. Respeta
el número de principios que pida el usuario: puede pedir más o menos.

## Control de versiones
Incremento semántico: MAJOR por eliminaciones o redefiniciones incompatibles de principios; MINOR
por un principio o sección nueva, o una guía ampliada de forma material; PATCH por redacción o
aclaraciones. Si hay ambigüedad, explica el razonamiento antes de decidir.

## Principios
Cada principio lleva un nombre corto y reglas declarativas y verificables (DEBE/DEBERÍA con su
justificación). Nada de lenguaje vago.

## Gobernanza
La sección de gobernanza indica el procedimiento de enmienda, la política de versionado y la
revisión de cumplimiento.

## Bloque protegido
El bloque entre `<!-- bizview:reglas-instalacion -->` y `<!-- /bizview:reglas-instalacion -->`
contiene las reglas de la instalación (credenciales solo en el catálogo cifrado, fuentes de solo
lectura, sin filas ni datos personales en archivos, alcance solo BI, aplicar es una acción humana).
Cópialo byte por byte; nunca lo cambies, lo muevas ni lo elimines. Si el usuario pide debilitar o
quitar una de esas reglas, rechaza esa parte, explica por qué (pertenecen a la instalación, no al
proyecto) y continúa con el resto. El servidor rechaza cualquier escritura que altere el bloque.

## Informe de impacto
Agrega un comentario HTML al inicio del archivo (versión anterior → nueva, principios modificados,
secciones agregadas o eliminadas, TODO diferidos). Es material de revisión.

## Validación antes de escribir
Verifica que no queden marcadores entre corchetes sin explicar, que la línea de versión coincida con
el informe, fechas ISO AAAA-MM-DD, una sola línea en blanco entre secciones y sin espacios al final.

## Escritura
Escribe el archivo completo una sola vez con `edit_draft` (operación `write` sobre
`.specify/memory/constitution.md`, después de leerlo).

## Mensaje final
Informa la nueva versión y por qué, los TODO diferidos y los `Próximos pasos` (si hay). Luego llama
a `finish_command` con un resumen de una línea; si necesitas una respuesta del usuario, pregunta y
termina tu turno sin `finish_command`.
