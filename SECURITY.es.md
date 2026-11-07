🇪🇸 Español · 🇬🇧 [English](SECURITY.md)

# Política de seguridad

Bizview es un producto autoalojado: el código, la CLI y las imágenes son nuestros; el servidor, la
base de datos y los datos son tuyos. Esta página explica cómo informar de un problema y qué protege
el producto por sí mismo.

## Informar de una vulnerabilidad

**No abras una incidencia pública.** Informa de forma privada a través de GitHub: pestaña
*Seguridad* → *Notificar una vulnerabilidad* en este repositorio. En el informe incluye:

- la versión afectada (el pie de página de la aplicación y `/api/health` la muestran),
- qué hiciste, qué ocurrió y qué esperabas,
- el impacto que observaste y la reproducción más pequeña que puedas preparar.

Acusamos recibo de los informes en **3 días hábiles** y procuramos publicar una corrección o una
mitigación en **30 días** para los problemas de gravedad alta confirmados, acreditando a quien
informa salvo que prefiera lo contrario. Un informe sobre la configuración de una instalación (una
contraseña débil, una base de datos expuesta) se responde con consejos, no con una corrección: esa
capa es responsabilidad de quien la opera.

Si necesitas un canal cifrado u otro contacto, escribe a **security@dvconsultores.com**.

## Versiones compatibles

| Versión | Compatible |
|---|---|
| 0.2.x | Sí — correcciones de seguridad y versiones normales |
| 0.1.x | Solo correcciones de seguridad, durante 60 días después de 0.2.0 |

Para actualizar se cambia `BIZVIEW_VERSION` en el `.env` de la instalación y se ejecuta
`docker compose pull && docker compose up -d`, o Watchtower lo hace automáticamente (consulta
[`docs/INSTALL.md`](./docs/INSTALL.md)). 0.2.0 retira el agente de autoría integrado en la
aplicación; su actualización copia los documentos de especificación de cada conversación aplicada a
la carpeta de su proyecto antes de eliminar las tablas del agente, y se niega a eliminar nada si
una copia no se puede verificar.

## Alcance

**Dentro del alcance** — el código de este repositorio: el backend y su API, el worker, la interfaz
web, la CLI (`cli/`), las imágenes de contenedor y el archivo compose, el formato del paquete de
autoría y sus esquemas, y la ruta de importación que los consume.

**Fuera del alcance** — los archivos de proyecto de cada cliente (su SQL y su YAML son suyos: una
consulta mal escrita es un defecto del proyecto, no una vulnerabilidad del producto), la
configuración de una instalación, las fuentes de datos que Bizview lee, los servicios de terceros y
la infraestructura de alojamiento.

Envíanos aquí una vulnerabilidad del producto aunque la hayas encontrado a través de una
instalación que no es tuya; dinos cuál es la instalación solo si tienes permiso para nombrarla.

## Protecciones incorporadas

- Las **credenciales** de las fuentes de datos y los secretos del inicio de sesión en dos pasos se cifran en reposo
  (AES-256-GCM) con `BIZVIEW_SECRET_KEY`, que nunca entra en la base de datos; en la API son de
  solo escritura — nunca se devuelven, se muestran ni se registran.
- **`SECURITY_PROFILE=internet`** exige HTTPS en todas partes e inicio de sesión en dos pasos para
  los administradores; los cambios sensibles exigen volver a introducir la contraseña; las
  direcciones de red de los administradores pueden incluirse en una lista de permitidas.
- **Límites de inicio de sesión**: por cuenta (5 fallos → 15 minutos) y por dirección de red
  (20 fallos cada 15 minutos).
- **Los orígenes son de solo lectura** para Bizview. Las conexiones rechazan loopback, link-local,
  las direcciones de metadatos en la nube y las internas, y se comprueban en cada conexión; no se
  siguen redirecciones; el XML se analiza sin DTD ni entidades. Las mismas reglas de direcciones se
  aplican a la **descarga de imágenes** que un reporte puede pedir por URL, que está acotada por
  tamaño, se inspecciona su contenido y se guarda en caché fuera del proyecto.
- **La importación valida antes de que se ejecute nada**: tipos de archivo, tamaños, recorrido de
  rutas, inspección del contenido de las imágenes, saneado de SVG (sin scripts, sin referencias
  externas) y los mismos esquemas JSON contra los que validó la CLI. Un archivo comprimido
  malformado no deja nada a medio importar.
- **Ninguna IA escribe dentro del producto.** El proveedor opcional sirve la página de ayuda de
  solo lectura; los paquetes de estructura que un cliente entrega a una IA externa contienen
  estructura, recuentos y formas — nunca credenciales, hosts ni valores de filas.

## Notas para quien opera la instalación

- Mantén privado el `.env` de la instalación (el instalador lo escribe con permisos 600): contiene
  la URL de la base de datos, la contraseña del superusuario, la clave secreta y cualquier clave de
  IA. Guarda una copia de `BIZVIEW_SECRET_KEY` por separado de la base de datos.
- Usa un dominio en `SITE_ADDRESS` en producción para que Caddy sirva HTTPS, y mantén
  `COOKIE_SECURE=true`.
- Prefiere un rol de base de datos que solo sea propietario de las tablas del producto antes que un
  superusuario de PostgreSQL.
- Las claves de IA nunca se devuelven por la API ni se escriben en los registros; rótalas en el
  proveedor si el `.env` de una instalación queda expuesto.
- El inicio de sesión con Google es opcional y está desactivado por defecto
  (`GOOGLE_AUTH_ENABLED=false`). Activarlo implica una ida y vuelta de autenticación con Google
  (`/api/auth/google/start` y después `/api/auth/google/callback`) en la que la instalación envía
  el código de autorización y los parámetros estándar de OAuth — ningún dato de negocio ni dato de
  reportes.
