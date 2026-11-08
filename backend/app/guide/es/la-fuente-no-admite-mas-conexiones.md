# La fuente no admite más conexiones

## Para qué sirve

Explica qué hacer cuando una integración termina en ámbar con «La fuente no admite más conexiones
ahora». No es un defecto de BizView ni de los datos: el servidor de origen se quedó sin conexiones
libres y rechazó la nuestra.

## Quién puede usarlo

El **Superusuario** y quien administre la base de datos de origen.

## Cómo se hace

1. Es el límite del origen, no el de BizView. El dueño de esa base de datos es otro sistema (el ERP,
   por ejemplo) y sus propios clientes ocuparon todos los cupos. BizView abre una conexión por
   fuente (o las que diga Conexiones simultáneas en la fuente) y la cierra al terminar.
2. En el origen, mira el techo y quién lo ocupa:

   ```sql
   SHOW max_connections;
   SELECT application_name, state, count(*) FROM pg_stat_activity GROUP BY 1, 2;
   ```

   Las sesiones de BizView aparecen como `bizview-engine:<integración>`.
3. Elige uno de los cuatro remedios reales:
   - poner un PgBouncer (pooling por transacción) delante del origen;
   - pedir al proveedor del ERP que suba `max_connections`;
   - apuntar BizView a una réplica de lectura;
   - mover la programación a una hora tranquila o alargar la ventana en lugar de correr cada
     hora (o usar `materialize: daily` en los reportes).
4. Mientras lo resuelves, no hay nada que reparar: los tableros siguen mostrando los últimos datos
   cargados, con su hora de «Datos actualizados». La siguiente ejecución vuelve a intentarlo.

## Opciones

- Una ejecución en ámbar trae el número de intentos y la espera (4 intentos, 7 min) y este
  enlace. BizView espera y reintenta solo antes de darse por vencido.
- Si el origen estuvo lleno tres veces seguidas, el superusuario recibe un solo aviso, no uno por
  cada intento.
- Cuando la integración acumula varias ejecuciones así en el día, su página sugiere la hora en la
  que el origen estuvo más libre.
- **Probar conexión**, en la fuente, muestra las conexiones máximas del origen y cuántos
  clientes tiene ahora, si el usuario de BizView puede leer la lista de sesiones; si no, dice
  «Sin permiso para verlo».

## Problemas frecuentes

- «Sin permiso para verlo»: el usuario de la fuente no puede leer `pg_stat_activity`. La conexión
  funciona; los números los mira quien administre el origen.
- El error nombra el host de BizView, no el del origen: entonces es otra cosa — la base de datos del
  producto se quedó sin conexiones. Sube `DB_POOL_SIZE` o `DB_POOL_OVERFLOW` y revisa
  `docker compose logs backend`.
- «No se pudo conectar con la fuente» en rojo: eso no es este caso. La red o el servidor no
  responden, y reintentar no lo arregla.

## Relacionados

- Integraciones
- Envíos programados
- Fuentes de datos
