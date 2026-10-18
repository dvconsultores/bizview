# Fuentes de datos

## Para qué sirve

Una fuente es un sistema del que BizView lee datos: una base PostgreSQL, un servicio SOAP o REST,
o un proyecto Supabase. Las credenciales se guardan cifradas y nunca se muestran.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Abre [Abrir Fuentes de datos](app:/admin/fuentes) y pulsa **Nueva fuente**
   ([Abrir Nueva fuente](app:/admin/fuentes/nueva)).
2. Elige el **Tipo de fuente** (no se puede cambiar después) y escribe el **Nombre**.
3. Completa la **Conexión**: dirección, base o servicio, modo de cifrado, tipo de autenticación,
   encabezados y credenciales.
4. Pulsa **Probar conexión**: verás **Conexión correcta** con el tiempo de respuesta o el motivo
   del error.
5. Pulsa **Guardar**.

## Opciones

- Estados en la lista: **Sin probar**, **Conectada**, **Error**, **Deshabilitada** e
  **Importada: revisa**.
- **Habilitada**: desmarcarla detiene las integraciones de esa fuente.
- **Eliminar fuente** borra la fuente y sus credenciales cifradas.
- En PostgreSQL, **Permitir reportes directos** deja que un reporte lea la fuente en vivo (ver
  Reportes directos).
- Las credenciales son de solo escritura: para cambiarlas usa **Reemplazar**.

## Problemas frecuentes

- «Dirección no permitida (local, interna o de metadatos)»: BizView no se conecta a direcciones
  internas del propio servidor.
- Con el perfil internet solo se permiten conexiones cifradas (HTTPS/TLS).
