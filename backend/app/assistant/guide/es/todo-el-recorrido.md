# Todo el recorrido con un comando

## Para qué sirve

`/speckit-all` lleva una petición desde la idea hasta «Listo para aplicar» en un solo run: recorre
las ocho etapas de Spec Kit —especificar, aclarar, planificar, tareas, analizar, implementar,
converger y verificar— sin preguntarte nada, decidiendo en tu lugar y dejando cada decisión escrita.
Al terminar escribe `run-report.md` en la carpeta de la spec y te muestra el informe como tarjeta:
etapas, decisiones tomadas, verificación por historia de usuario y «Pendiente para el humano», que
solo nombra lo que de verdad necesita una persona (normalmente pulsar **Aplicar**). Cada etapa deja
su chip en la conversación con su posición (`Etapa 4/8`), y la barra de estado muestra el gasto del
contrato.

## Quién puede usarlo

Solo el **Superusuario**, en modo **Auto** con el contrato del run confirmado. En modo Preguntar o
Editar el comando no arranca: ofrece el botón «Pasar a Auto».

## Cómo se hace

- `/speckit-all <petición>`: si la petición no nombra una spec, la primera etapa crea la spec (o las
  dos que haga falta: la integración y su reporte). Si nombra una spec (`/speckit-all 002-ventas`),
  el run continúa desde la primera etapa que falte y no repite lo ya hecho.
- Cada etapa se abre con el comando que la posee, así que escribe solo lo suyo: la etapa que juzga
  (analizar, verificar) no escribe nada y, si algo falla, vuelve a la etapa que sí puede arreglarlo.
- La verificación ejecuta de verdad: validación, una comprobación por consulta o petición de la
  integración, una vista previa y el resultado por historia de usuario.

## Opciones

- `/speckit-all <petición> --until tasks`: el «dry run» documentado. Se detiene después de esa etapa
  (incluida) y escribe el informe con lo que hay.
- `--force`: no se fía de lo hecho y vuelve a recorrer las etapas desde el principio.
- `/speckit-all <spec>` sin nada más: reanuda el run donde se detuvo.
- `/speckit-verify <spec>`: repite solo la verificación de una spec ya implementada.

## Problemas frecuentes

El run solo se detiene por un conflicto de constitución que exige enmienda, una verificación que
sigue fallando tras tres ciclos, una acción que el contrato no permite o una fuente o credencial que
falta; el informe lo dice en una línea. Si se detiene por un límite del contrato, por «Detener» o por
un error del proveedor, todo lo escrito se conserva y `/speckit-all <spec>` continúa en la misma
etapa. Todo lo demás lo decide el agente y queda registrado en «Decisiones tomadas (modo autónomo)»
de la spec.
