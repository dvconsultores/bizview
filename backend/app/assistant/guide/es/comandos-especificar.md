# Comandos para especificar

## Para qué sirve

Estos comandos fijan los principios del proyecto y crean y aclaran cada spec.

## Quién puede usarlo

Solo el **Superusuario**, en el chat de un proyecto.

## Cómo se hace

- `/speckit-constitution <principios o cambios>`: actualiza la constitución del proyecto
  (`.specify/memory/constitution.md`). El bloque de reglas de la instalación no cambia: si pides
  debilitarlo, el agente explica por qué no.
- `/speckit-specify <descripción>`: crea una spec nueva `specs/NNN-nombre/` con su `spec.md`, la
  línea `**Tipo**:` (fuente, integración, reporte o distribución) y la lista de calidad
  `checklists/requirements.md`. Usa el siguiente número libre del proyecto, deja como mucho 3
  dudas marcadas `[NEEDS CLARIFICATION]` y la spec pasa a ser la **Spec actual** de la
  conversación.
- `/speckit-clarify`: hace hasta 5 preguntas, una a la vez, y anota cada respuesta en
  `## Clarifications` de `spec.md`.

## Opciones

- `/speckit-clarify` trabaja sobre la **Spec actual**; si no hay una, el chat te pide elegirla.
- Cada comando cambia solo sus archivos: si intenta otro, el servidor lo rechaza.
- Mientras un comando espera tu respuesta puedes contestar en el chat o pulsar **Terminar**.
