# Validar antes de importar

## Para qué sirve

La importación valida siempre. Validar antes, en tu equipo, solo sirve para ver los problemas sin
subir nada y para corregirlos con la misma lista que verá BizView después.

## Quién puede usarlo

Solo el **Superusuario**, y solo si tiene la CLI instalada. No es obligatorio: el paso 5 de
**Importar proyecto** hace exactamente la misma comprobación.

## Cómo se hace

1. Instala la CLI: `uv tool install bizview-cli`.
2. Descomprime el proyecto dentro de un espacio de trabajo, en `projects/<identificador>/`.
3. Abre esa carpeta en la terminal.
4. Ejecuta `bizview validate`.
5. Corrige lo que aparezca y repite hasta que no quede ningún error.
6. Con `--write-lock` se escribe `bizview.lock`, la huella de lo validado.

La CLI y el servidor leen los mismos esquemas, así que un proyecto que valida aquí aplica allí.

## Opciones

- `--describe <nombre>=<archivo.json>` comprueba contra una estructura ya descargada, sin conectarse.
- `--live` ejecuta además cada consulta contra la fuente, si la instalación deja alcanzarla.
- `bizview import --dry-run proyecto.zip` mide el zip contra los dos presupuestos sin subirlo.

## Problemas frecuentes

- Un error de `schema_error` en un YAML suele ser una clave mal escrita o una indentación de dos
  espacios en lugar de cuatro.
- `missing_spec` significa que el `spec:` del artefacto no apunta a una carpeta que existe.
- Si el comando no encuentra `bizview.yaml`, la carpeta no es un espacio de trabajo: el proyecto va
  dentro de `projects/`.

## Relacionados

- Corregir los problemas
- Importar un proyecto
- Estructura de un proyecto
