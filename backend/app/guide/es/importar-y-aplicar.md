# Qué pasa al importar y aplicar

## Para qué sirve

Explica, en lenguaje llano, qué hace BizView cuando subes el zip (importar) y cuando lo pones en marcha (aplicar). Nada se ejecuta y nadie ve nada hasta que aplicas.

## Quién puede usarlo

Solo el Superusuario para importar y aplicar. Después de aplicar, cada rol de `access` ve el tablero.

## Cómo se hace

### Importar

1. BizView lee el zip en memoria, quita la carpeta que lo envuelve si la hay, y rechaza los
   ejecutables y los scripts escondidos en un SVG.
2. Mapea cada archivo al formato del proyecto y lista los que no lo son como ignorados: no se
   guardan y el proyecto se importa igual.

### Aplicar

1. El borrador se compone con los demás proyectos aplicados en una versión nueva de la
   instalación y se vuelve a comprobar; los identificadores repetidos entre proyectos son errores de
   verdad.
2. Cada integración se registra con el worker: la primera ejecución es una carga completa y después
   corre la programación (`cron`), que hace la ventana incremental (`:window_start`/`:window_end`) o
   una recarga completa según `incremental.mode`.

## Opciones

- Importar un proyecto que ya existe propone una revisión, no un duplicado.
- El mismo texto está dentro de cada paquete, en `QUE-HACE-BIZVIEW.md` y `WHAT-BIZVIEW-DOES.md`.

## Relacionados

- Importar un proyecto
- Aplicar un proyecto
- Reimportar cambios
