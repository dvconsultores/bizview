---
description: Recorre una spec entera —especificar, aclarar, planificar, tareas, analizar, implementar, converger y verificar— sin preguntar y termina con el informe del run.
argument_hint: "<petición o NNN-nombre> [--until <etapa>] [--force]"
source: speckit-all
---
# /speckit-all

## Goal
Llevar una petición (o una spec que ya existe) desde la idea hasta «Listo para aplicar» en un solo
run, sin intervención del humano después del contrato. Cada etapa es un comando real de Spec Kit;
este comando solo decide el orden, registra las decisiones y escribe el informe.

## Command
El bloque `Pipeline` de `## Comando` dice en qué etapa estás (`Etapa i/8`), sobre qué spec y cuáles
faltan. La siguiente etapa se abre **siempre** con `run_command`:

```text
specify → clarify → plan → tasks → analyze → implement → converge → verify
```

- No escribas artefactos en esta etapa: los escribe la etapa que los posee. Este run solo escribe
  líneas en «Decisiones tomadas (modo autónomo)» de `specs/<spec>/spec.md`; el `run-report.md` lo
  escribe el producto al terminar.
- Si el plan tiene dos specs (integración y reporte), termina las ocho etapas de la integración
  antes de empezar el reporte. Cambia de spec con `set_current_spec`.
- `--until <etapa>`: el run se detiene después de esa etapa (incluida) y escribe el informe.
  `--until tasks` es el «dry run» documentado.
- `--force`: no te fíes de lo ya hecho; vuelve a recorrer las etapas desde el principio.
- Una etapa que ya está completa se salta: no repitas trabajo hecho.

## Qué haces en cada etapa
- **specify**: escribe la spec completa (y su checklist) con lo que pide el usuario. Si la petición
  necesita una fuente que no existe, detente y dilo en una línea: no inventes una spec sin fuente.
- **clarify**: genera como máximo 5 preguntas de la taxonomía de aclaraciones, respóndelas tú con
  la opción mejor sostenida y aplícalas como haría el comando (sección de aclaraciones y textos).
- **plan**: plan técnico y artefactos (`integrations/…`, `reports/…`).
- **tasks**: tareas ordenadas y verificables.
- **analyze**: revisa coherencia spec/plan/tareas. Si hay CRITICAL/HIGH, vuelve a la etapa que posee
  el archivo (`run_command`) una vez; lo MEDIUM/LOW se registra como decisión.
- **implement**: escribe los artefactos y marca las tareas.
- **converge**: si faltan piezas, añade la fase de convergencia a `tasks.md` y ejecútala en el
  mismo run (máximo 2 rondas).
- **verify**: el producto ya ejecutó las comprobaciones; léelas y arregla lo que falle volviendo a
  `implement`/`converge` (máximo 3 ciclos).

<!-- bizview:contrato-autonomo -->
- No preguntas: ninguna etapa termina pidiendo al humano una decisión ni una confirmación. Una duda
  se resuelve con esta precedencia —constitución, el texto de la spec, otras specs del proyecto,
  los valores por defecto del paquete de autoría— y se registra como decisión.
- Toda decisión se escribe como `- [etapa] decisión — porqué` bajo
  «## Decisiones tomadas (modo autónomo)» en `specs/<spec>/spec.md`. Nunca cambies otra línea de
  ese archivo.
- El orden de etapas es fijo y se avanza solo con `run_command`; una etapa no se salta ni se repite.
- Un artefacto ya escrito no se reescribe igual: la misma etapa dos veces no produce cambios salvo
  que cambien sus entradas.
- Solo te detienes por: un conflicto de constitución que exige enmienda, la verificación que sigue
  fallando tras 3 ciclos, una acción que el contrato no permite, o una fuente o credencial que
  falta. Cualquier otra cosa es una decisión, no una parada.
- Al terminar escribes el informe y, en «Pendiente para el humano», solo lo que de verdad lo
  necesita (Aplicar si el contrato no lo permite). Nunca des instrucciones de cómo seguir.
<!-- /bizview:contrato-autonomo -->
