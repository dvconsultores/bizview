---
description: Verifica una spec implementada con comprobaciones reales (validación, consultas y vista previa) y reporta el resultado por historia de usuario.
argument_hint: ""
source: speckit-verify
---
# /speckit-verify

## Goal
Probar la spec con las comprobaciones que el producto ya tiene, no con una opinión: validación del
borrador, `check_query`/`check_request` de cada consulta y petición de la integración de la spec, y
una vista previa. Al final, cada historia de usuario queda con pasado/fallado y el motivo.

## Command
- Al abrir esta etapa el producto ya ejecutó las comprobaciones y las publicó en la conversación
  (validación, una comprobación por archivo, vista previa y el veredicto por historia). Léelas.
- Esta etapa **no escribe archivos**: no tienes `propose_draft` ni `edit_draft`. Si algo falla, di
  qué archivo lo arregla y vuelve a la etapa que lo posee con
  `run_command` (`speckit-implement`, `speckit-converge`, `speckit-plan` o `speckit-tasks`).
- Cada vuelta cuenta como un ciclo: se permiten 3. Al tercero, detente y escribe el informe con el
  fallo; no inventes una comprobación que pase.
- Usa `check_query` o `run_preview` solo si necesitas repetir una comprobación concreta; la vista
  previa cuenta para el contrato.

## Qué reportas
- Una línea por comprobación con su resultado y el detalle, y una línea por historia de usuario
  (`US1`, `US2`, …) con su Independent Test y pasado/fallado.
- Cuando todo pasa: «Verificación completa» y la siguiente acción es aplicar (si el contrato lo
  permite) o «Pendiente para el humano: Aplicar».
