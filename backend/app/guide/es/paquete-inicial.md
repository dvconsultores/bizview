# Descargar el paquete inicial

## Para qué sirve

Es la carpeta que tu IA necesita para escribir un proyecto de BizView: las reglas, la petición, la
spec, los esqueletos de los artefactos y los esquemas que valida BizView. Se descarga hecha y se
entrega tal cual.

## Quién puede usarlo

Solo el **Superusuario**, desde Proyectos.

## Cómo se hace

1. Abre [Proyectos](app:/proyectos) y pulsa **Nuevo proyecto** (o **Descargar paquete inicial** si
   todavía no hay ninguno).
2. Escribe el nombre. También decide el identificador: minúsculas, dígitos y guiones.
3. Elige la fuente si el proyecto leerá una. Añade su estructura, nunca una credencial ni una fila.
4. Elige el idioma de los documentos y el tipo de la primera spec.
5. Pulsa **Descargar paquete inicial**: baja `bizview-starter-<identificador>.zip`.

Dentro del zip están `PROMPT.md` (las reglas), `REQUEST.md` (la petición que rellenas), `project.yaml`,
`specs/001-…`, `integrations/…`, `reports/…` y `.bizview/`. `CONTENIDO.md` explica cada archivo y
`QUE-HACE-BIZVIEW.md`, qué ocurre al importar y al aplicar.

## Opciones

- **Descargar plantilla general**: el mismo paquete con marcadores, sin nombre ni fuente, para
  reutilizarlo o repartirlo.
- La plantilla general también está en el repositorio y en cada release.
- Desde un equipo con la CLI: `bizview init project "Ventas"` escribe el mismo paquete.

## Problemas frecuentes

- Un nombre solo con símbolos: el identificador no se puede formar y el aviso nombra el campo.
- La fuente no responde: el zip se descarga igual, sin su estructura, y el aviso lo dice.

## Relacionados

- Escribir la petición
- Pasarlo a tu IA
- Los cinco pasos
