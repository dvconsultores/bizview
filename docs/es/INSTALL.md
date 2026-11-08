🇪🇸 Español · 🇬🇧 [English](../INSTALL.md)

# Instalar Bizview para un cliente

Bizview es un solo producto de código abierto. Cada cliente recibe una **instalación**: una carpeta
en su servidor con los ajustes y un archivo compose que ejecuta las imágenes publicadas de una
versión del producto. No se copia ni se cambia código por cliente.

```text
/opt/bizview/                 una instalación (un cliente)
├── bizview.yml               imágenes de backend + web fijadas a BIZVIEW_VERSION
└── .env                      todos los ajustes (modo 600: base de datos, superusuario, IA)
```

Una carpeta del servidor solo necesita `bizview.yml` y `.env`: la SPA y el logo están dentro de la
imagen `bizview-web`, así que no hay carpeta `branding/`, y nada monta un checkout del cliente, así
que no hay carpeta `workspace/`. Las únicas carpetas del host son `projects/` y `attachments/` (los
datos de la aplicación), que crea el archivo compose. `deploy/install.sh` escribe exactamente este
par y lo arranca; si copias los archivos de este repositorio, esos mismos dos archivos son todo lo
que necesitas.

## 1. Requisitos

- Servidor Linux (amd64 o arm64) con [Docker Engine](https://docs.docker.com/engine/install/) y
  Docker Compose v2 (`docker compose version`).
- Una base de datos PostgreSQL para el producto (la «base de datos BI»), accesible desde el
  servidor. El producto crea sus tablas en el esquema `public` de la base de datos. Recomendado: una
  base de datos dedicada y un rol que sea su dueño, no el superusuario `postgres`.
- Para HTTPS: un nombre de dominio que apunte al servidor, y el puerto 443 o el 80 del host libres
  para el certificado automático (más abajo, cuando ambos pertenecen a otro servicio).

### Cuando el 80 y el 443 ya pertenecen a otro servicio

El HTTPS automático necesita libre uno de esos dos puertos del host: el desafío TLS-ALPN corre en el
443 y el desafío HTTP en el 80. En un servidor compartido donde ambos están ocupados, publica otro
puerto del host (`HTTPS_PORT=8443`) y elige el origen del certificado con `CADDY_TLS`:

| `CADDY_TLS` | Qué hace Caddy | Qué más hace falta |
|---|---|---|
| `auto` (por defecto) | obtiene y renueva un certificado | el 443 o el 80 del host accesibles |
| `internal` | sirve un certificado de su propia CA local | un proxy delante que lo acepte, por ejemplo Cloudflare con modo SSL **Full** (no *Full (strict)*) |
| `file` | sirve el par de certificados de `CADDY_TLS_DIR` (`origin.pem` + `origin-key.pem`, por defecto `./deploy/caddy/certs`) | un par válido, por ejemplo un certificado Cloudflare Origin CA; necesario para **Full (strict)** |

Esos dos modos no emiten nada, así que no hace falta ningún puerto del host para los certificados; el
contenedor sigue escuchando en el 443 por dentro y tú publicas lo que diga `HTTPS_PORT`. Si hay una
CDN delante, apúntala a ese puerto: Cloudflare acepta los puertos HTTPS de origen 443, 2053, 2083,
2087, 2096 y 8443, configurados por nombre de host en una **Origin Rule** (Rules → Origin Rules →
*Destination Port*). Con Cloudflare haciendo de proxy para un nombre que no es accesible en el
origen, los visitantes ven **525** (fallo del handshake TLS): esa es esta situación, no un error de la
aplicación.

Si el plan no ofrece **Destination Port** en una Origin Rule (el selector falta en la sección
«Then…»), el edge solo puede alcanzar el origen en sus puertos estándar. Termina el TLS en el proxy,
como se describe a continuación: el proxy escucha en el 443 y reenvía a `HTTPS_PORT`.

### Detrás de Nginx Proxy Manager (o de cualquier proxy que termine el TLS)

Mantén `SITE_ADDRESS` como **dominio** y `CADDY_TLS=internal`: el proxy termina el certificado
público y Bizview sigue respondiendo HTTPS en su puerto publicado, así que el perfil `internet` y las
direcciones construidas a partir de `SITE_ADDRESS` siguen siendo correctas. En Nginx Proxy Manager,
**Hosts → Proxy Hosts → Add Proxy Host**:

| Campo | Valor |
|---|---|
| Domain Names | `bi.example.com` |
| Scheme | `https` |
| Forward Hostname / IP | el host de Docker (`172.17.0.1`, o la IP de LAN del host), o el nombre del contenedor de Caddy si ambos comparten una red |
| Forward Port | el `HTTPS_PORT` publicado (`9443` en este ejemplo) |
| Block Common Exploits | activado |
| Websockets Support | activado (sin uso hoy, inofensivo) |

En la pestaña **Advanced**:

```nginx
proxy_ssl_server_name on;                  # nginx no envía SNI por defecto …
proxy_ssl_name bi.example.com;             # … y Caddy rechaza una conexión TLS sin él
proxy_ssl_verify off;                      # la CA interna de Caddy no está en el almacén de confianza del proxy
client_max_body_size 100m;                 # iguala CADDY_MAX_REQUEST_BODY (adjuntos, zips de proyecto)
proxy_read_timeout 300s;
```

Las dos primeras líneas no son opcionales: con `SITE_ADDRESS` fijado a un nombre, Caddy tiene un
certificado solo para ese nombre y responde a una conexión sin SNI con `tlsv1 alert internal error`,
que el proxy informa como **502**. Por eso tampoco ayuda apuntar el proxy a `HTTP_PORT`: allí Caddy
redirige el HTTP en claro a HTTPS.

En la pestaña **SSL**, solicita un certificado (Let's Encrypt necesita el dominio accesible en el
puerto 80) o sube uno, y luego activa **Force SSL** y **HTTP/2**. No hace falta nada más: la
aplicación no usa WebSockets ni eventos enviados por el servidor, y uvicorn ya corre con
`--proxy-headers`.

Por último, dile a Caddy que confíe en el proxy, o cada cliente parecerá la dirección del proxy (el
límite de peticiones, la auditoría y `ADMIN_ALLOWED_NETWORKS` verán una sola IP). Usa la red del
contenedor del proxy cuando Nginx Proxy Manager esté delante, o los rangos de Cloudflare cuando la CDN
alcance el origen directamente; se acepta una lista separada por espacios. Los rangos publicados por
Cloudflare a la fecha de este escrito (vuelve a copiarlos de
<https://www.cloudflare.com/ips/> si cambian):

```dotenv
TRUSTED_PROXIES=103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 104.16.0.0/13 104.24.0.0/14 108.162.192.0/18 131.0.72.0/22 141.101.64.0/18 162.158.0.0/15 172.64.0.0/13 173.245.48.0/20 188.114.96.0/20 190.93.240.0/20 197.234.240.0/22 198.41.128.0/17 2400:cb00::/32 2405:8100::/32 2405:b500::/32 2606:4700::/32 2803:f800::/32 2a06:98c0::/29 2c0f:f248::/32
```

La cabecera `Host` debe llegar a Caddy sin cambios (`proxy_set_header Host $host`, el valor por
defecto de NPM), o `CADDY_ALLOWED_HOSTS` responde **421**.

### Cloudflare o NPM muestra un error en lugar de la aplicación

La dirección funciona desde el servidor pero no desde fuera, así que el edge no puede alcanzar la
aplicación. Cada error de Cloudflare nombra una falla distinta; revísalo antes de cambiar nada:

| Código | Significado | Normalmente |
|---|---|---|
| **521** | el origen rechazó la conexión | no hay nada escuchando en el puerto al que apunta el edge (stack caído, `HTTPS_PORT` equivocado) |
| **525** | falló el handshake TLS con el origen | el edge apunta a un puerto **HTTP en claro** (`HTTP_PORT`, p. ej. `8090`) en lugar del puerto TLS (`HTTPS_PORT`, `9443`), o el proxy host **no tiene certificado** |
| **526** | el certificado del origen no es válido | Cloudflare en **Full (strict)** mientras Caddy usa `CADDY_TLS=internal`; cambia a **Full** o entrega un par Cloudflare Origin CA con `CADDY_TLS=file` |
| **502** | el proxy alcanzó la aplicación, que no respondió | el proxy **no envía SNI** (`proxy_ssl_server_name on;` + `proxy_ssl_name <dominio>;`), no puede verificar la CA interna de Caddy (`proxy_ssl_verify off;`), o apunta al puerto equivocado |
| **421** | la aplicación rechazó el `Host` | el proxy reescribió `Host`, o el nombre falta en `CADDY_ALLOWED_HOSTS` |

Dos comandos separan «la aplicación está bien» de «el edge está mal configurado»; ejecútalos en el
servidor:

```bash
# la aplicación sobre TLS, con el SNI correcto (un -H Host pelado no basta: el TLS necesita el nombre)
curl -sk -o /dev/null -w '%{http_code}\n' \
  --resolve bi.example.com:9443:127.0.0.1 https://bi.example.com:9443/api/health
# un certificado para el nombre en el puerto que usa el edge (salida vacía = no hay TLS ahí)
echo | openssl s_client -connect 127.0.0.1:443 -servername bi.example.com 2>&1 | grep -E 'subject=|issuer='
```

Que el primero devuelva `200` y el segundo no devuelva nada significa que la aplicación está sana y
que el proxy que termina el TLS no tiene certificado: añade uno al proxy host (pestaña **SSL** de
NPM), o apunta el edge directamente a `HTTPS_PORT` y usa el modo SSL **Full**.

Un `tlsv1 alert internal error` del primer comando significa que el nombre usado en él no coincide con
`SITE_ADDRESS`; Caddy solo tiene un certificado para ese nombre.

Para probar el origen mientras el registro está proxied, pon el registro DNS en **DNS only** (nube
gris) de forma temporal y dirígete al origen por IP con el nombre como SNI:

```bash
curl -k --resolve bi.example.com:9443:<origin-ip> https://bi.example.com:9443/api/health
```

## 2. Instalar

Una instalación es el archivo compose más sus ajustes, nada más: copia [`bizview.yml`](../../bizview.yml)
y un `.env` relleno en una carpeta, crea las dos carpetas de datos propiedad del usuario de los
contenedores, y arráncala:

```bash
mkdir -p projects attachments
sudo chown -R 10001:10001 projects image-cache   # los contenedores corren como uid 10001
docker compose -f bizview.yml up -d
```

Los contenedores corren como **uid 10001** (`app`), así que `projects/` y `image-cache/` deben ser
suyas. Docker las crearía como root, y la aplicación podría leerlas pero no escribir en ellas: los
proyectos BI y las imágenes de los reportes fallan entonces en el primer uso, y el log dice
`PROJECTS_DIR … is not writable`.

[`deploy/install.sh`](../../deploy/install.sh) hace eso por ti. Ejecútalo con `sudo bash`. De forma
interactiva (pregunta las respuestas que falten):

```bash
sudo bash deploy/install.sh
```

Sin intervención (las respuestas van en la línea de comandos):

```bash
sudo bash deploy/install.sh \
  --yes --dir /opt/bizview \
  --version 0.1.0 \
  --image-prefix andresdom2004/bizview \
  --db-url '******db.internal:5432/bizview' \
  --admin-email admin@customer.com \
  --site dashboard.customer.com \
  --org-name 'Customer Inc.' \
  --start
```

Una copia tomada de este repositorio está **sin sellar**: sus marcadores de versión, prefijo de
imágenes y URL de origen no están rellenos, así que `--version X.Y.Z` y
`--image-prefix <registry/owner/bizview>` son obligatorios con `--yes` (una ejecución interactiva los
pregunta). Una copia sellada puede adjuntarse a mano a un release de GitHub; nada se adjunta
automáticamente.

El instalador comprueba Docker, escribe la carpeta de la instalación y, con `--start`, la arranca y
espera hasta que esté sana. Cuando no se da `--admin-password` **genera una y la imprime una sola
vez** (también queda guardada en `.env`). Todas las opciones: `install.sh --help`.

Entra en la dirección impresa con el superusuario. El primer arranque crea las tablas y el
superusuario; los arranques posteriores solo aplican las migraciones nuevas.

## 3. Ajustes (`.env`)

| Ajuste | Significado |
|---|---|
| `BIZVIEW_VERSION` | versión del producto que se ejecuta (actualizar = cambiarla) |
| `BIZVIEW_IMAGE_PREFIX` | de dónde vienen las imágenes: `<prefix>-backend` y `<prefix>-web`. `./deploy.sh` publica en Docker Hub (`andresdom2004/bizview-backend`, `andresdom2004/bizview-web`), así que ese prefijo es `andresdom2004/bizview`; sirve cualquier registro que guarde esas mismas dos imágenes. Un `install.sh` sin sellar exige `--image-prefix`. |
| `DATABASE_URL_BI` | la base de datos PostgreSQL del producto |
| `SUPER_USER_EMAIL`, `SUPER_USER_PASSWORD` | solo se usan para crear el superusuario en el primer arranque, y por el comando de recuperación |
| `PRODUCT_NAME`, `ORGANIZATION_NAME`, `LOGO_URL` | nombres que ven los usuarios; el logo viaja en la imagen `bizview-web`, y `LOGO_URL` apunta a otro |
| `FOOTER_CREDIT` | quién publica esta instalación, mostrado tras la licencia en cada pie de página (por defecto `GlobalDV`) |
| `SITE_ADDRESS` | `:80` para HTTP en claro, o un dominio para HTTPS automático; un dominio hace que los enlaces de tableros compartidos y los enlaces de los correos usen `https://<domain>/s/…` (ver «Correo y enlaces compartidos») |
| `HTTP_PORT`, `HTTPS_PORT` | puertos publicados (ver «Cuando el 80 y el 443 ya pertenecen a otro servicio») |
| `CADDY_TLS` | `auto` (por defecto), `internal` o `file`: de dónde obtiene Caddy su certificado |
| `CADDY_TLS_DIR` | carpeta del host con `origin.pem` + `origin-key.pem` cuando `CADDY_TLS=file` (por defecto `./deploy/caddy/certs`) |
| `COOKIE_SECURE` | `true` con HTTPS (obligatorio en producción) |
| `SOURCE_URL` | opcional: reemplaza el enlace al código fuente que se muestra a los usuarios |
| `DEFAULT_LOCALE` | la interfaz, los mensajes de la API, los correos y Telegram recurren a este idioma (`es` o `en`, por defecto `es`) cuando no lo decide ni la cuenta ni el navegador. NO afecta a la CLI `bizview`. |
| `TIMEZONE` | zona horaria de las programaciones de integraciones y de los periodos de los reportes (p. ej. `America/Caracas`) |
| `DIRECT_REPORTS_BI` | por defecto `true`: los reportes directos pueden leer tablas de la base de datos BI; `false` apaga `source: bi` |
| `DIRECT_REPORT_CONCURRENCY` | valor por defecto de la instalación, 1–20: consultas directas a la vez por cada fuente que no tenga declaración propia (función 048) |
| `DIRECT_REPORT_WARN_ROWS` | por defecto 5000000: por encima de este número estimado de filas una tabla directa necesita un índice encabezado por su columna de fecha |
| `DIRECT_BI_ROLE` | rol de base de datos de solo lectura opcional para `source: bi`; obligatorio en el perfil `internet` cuando `DIRECT_REPORTS_BI=true`; ver §5 |
| `AI_*` | proveedor de IA opcional (ver más abajo) |

Después de editar: `cd /opt/bizview && docker compose -f bizview.yml up -d`.

### Idioma (inglés / español)

La función 022 añade el inglés junto al español en todo el producto. El idioma activo de la interfaz
se resuelve en este orden:

1. El idioma guardado en la cuenta, elegido con el selector de idioma de la cabecera o de los ajustes.
   Si la cuenta está configurada para seguir al navegador, no existe idioma guardado.
2. La cabecera `Accept-Language` del navegador.
3. El valor por defecto de la instalación, `DEFAULT_LOCALE`, que puede ser `es` o `en` y vale `es`
   por defecto.

La página de ingreso y la página pública de tablero compartido tienen su propio selector. La elección
se recuerda en ese dispositivo y se guarda en la cuenta al entrar. Cambiar de idioma no recarga la
página y conserva los filtros del reporte.

Los errores de la API se devuelven en el idioma de la petición usando el mismo orden. Los correos y
sus PDF adjuntos se renderizan por destinatario: quien tiene idioma en su cuenta recibe ese; las
direcciones sin cuenta, o las cuentas sin idioma guardado, reciben `DEFAULT_LOCALE` porque al enviar
no hay navegador. Las respuestas del bot de Telegram usan el idioma de la cuenta vinculada, luego el
código de idioma de Telegram, luego `DEFAULT_LOCALE`.

Para cambiar el idioma por defecto, pon `DEFAULT_LOCALE=en` en `.env` y ejecuta
`docker compose -f bizview.yml up -d`.

Las specs de reporte pueden llevar etiquetas en inglés opcionales para títulos, descripciones,
métricas y dimensiones; consulta [REPORTS.md](REPORTS.md), sección «English labels (optional)».

## 4. Perfil de seguridad y clave secreta

- **`SECURITY_PROFILE`** — el instalador lo pregunta:
  - `private` — red local: se permite HTTP en claro para el producto y para las fuentes de datos;
    doble paso de ingreso opcional.
  - `internet` — accesible desde internet: HTTPS obligatorio para el producto y para cada fuente de
    datos, cookies seguras y **doble paso de ingreso obligatorio para los administradores**. Exige un
    dominio en `SITE_ADDRESS`; de lo contrario el producto se niega a arrancar.
  - `auto` — `internet` cuando `SITE_ADDRESS` es un dominio, `private` en caso contrario.
- **`BIZVIEW_SECRET_KEY`** cifra las credenciales de las fuentes de datos y los secretos del doble
  paso. El instalador la genera. **Respáldala en un gestor de contraseñas, aparte de los respaldos de
  la base de datos**: sin ella, las credenciales guardadas no se pueden descifrar (vuelve a
  introducirlas y vuelve a enrolar el doble paso de ingreso). El producto se niega a arrancar si
  existen datos cifrados y la clave falta o es incorrecta.
- **Rota la clave** (cada año, o si `.env` pudo filtrarse): pon la clave actual en
  `BIZVIEW_SECRET_KEY_PREVIOUS`, una nueva en `BIZVIEW_SECRET_KEY`
  (`python3 -c "import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"`),
  reinicia, ejecuta `docker compose -f bizview.yml run --rm backend python -m app.cli rotate-secret-key`, y luego quita
  `BIZVIEW_SECRET_KEY_PREVIOUS` y reinicia.
- Opcional: `ADMIN_ALLOWED_NETWORKS=10.0.0.0/8` (administración solo desde estas redes),
  `SOURCES_ALLOW_PRIVATE_NETWORKS=false` (fuentes de datos solo en direcciones públicas),
  `TRUSTED_PROXIES` (solo cuando hay un balanceador delante de este servidor).

## 5. Fuentes de datos

El superusuario registra los sistemas de origen en **Administración → Fuentes de datos**
(PostgreSQL, SOAP/SAP, REST). Las credenciales son de solo escritura y están cifradas. Usa cuentas de
solo lectura: la prueba de conexión avisa si no lo son. Las instalaciones actualizadas desde una
versión que usaba `DATABASE_URL_ORIGIN` la importan una vez como «Origen (importado)»; elimina la
variable después.

Estas tres (y `DIRECT_BI_ROLE`) son los **valores por defecto** de la instalación. Desde la función
048 cada fuente PostgreSQL lleva su propia declaración de caché, su tope de filas y su concurrencia,
así que se puede dar cinco segundos a un almacén y dos minutos a otro sin cambiar la instalación. Una
fuente sin declaración hereda lo que se configura aquí, y por eso actualizar no cambia nada hasta que
alguien declare una.

### Reportes directos sobre la base de datos BI (`DIRECT_BI_ROLE`)

**No necesitas esto.** Para reportar sobre tus propios datos, registra la base de datos en
**Administración → Fuentes de datos** y reporta desde esa fuente, o deja que una integración ponga
los datos en un dataset (`ds_<integration>`) y reporta desde él. Ambas cosas funcionan con
`DIRECT_REPORTS_BI=false`, no necesitan ningún rol de base de datos y son de solo lectura por
construcción. La fuente `bi` de más abajo existe solo para leer tablas de la base de datos **del
propio producto**, algo que una instalación expuesta a internet no debe permitir sin el rol de solo
lectura.

Los reportes directos con `source: bi` leen la base de datos BI a través de la conexión agrupada
normal, en solo lectura. Cuando `DIRECT_BI_ROLE` está definido, cada una de esas sesiones ejecuta
`SET LOCAL ROLE <role>` para la transacción de solo lectura de la sesión directa, así que solo tiene
los permisos que el DBA conceda a ese rol: USAGE en los esquemas que contienen las tablas permitidas y
SELECT en esas tablas, nada en las tablas del producto.

**Vistas y funciones (riesgo residual).** La validación y la primera lectura recorren las
dependencias de cada vista o vista materializada declarada y rechazan cualquiera que lea una tabla del
producto, pero ese recorrido no puede ver una tabla del producto alcanzada a través de una función
llamada dentro de una vista. PostgreSQL comprueba las tablas de una vista con los privilegios del
dueño de la vista (salvo que la vista se cree `WITH (security_invoker = true)`, PostgreSQL 15+), y una
función `SECURITY DEFINER` se ejecuta con los privilegios de su dueño; por eso el rol por sí solo no
ayuda cuando esos objetos pertenecen al usuario de la aplicación. Reglas: las vistas y funciones
alcanzables por el rol directo deben pertenecer a un rol sin privilegios sobre las tablas del producto
(p. ej. el rol del proceso que mantiene las tablas de reportes), nunca al usuario de la aplicación
(`bizview`); no concedas `EXECUTE` sobre funciones `SECURITY DEFINER` del usuario de la aplicación al
rol directo ni a `PUBLIC`; prefiere vistas `security_invoker`. Una conexión restringida aparte
(`DATABASE_URL_BI_DIRECT`) está prevista como trabajo posterior.

Este rol es **obligatorio** cuando `SECURITY_PROFILE=internet` y `DIRECT_REPORTS_BI=true`, y
recomendable siempre.

Un DBA debe ejecutar una vez lo siguiente; el ejemplo usa el usuario de base de datos de la
aplicación, `bizview`:

```sql
CREATE ROLE bizview_direct NOLOGIN;

-- tablas en public: un GRANT por cada tabla permitida, por nombre
GRANT USAGE ON SCHEMA public TO bizview_direct;
GRANT SELECT ON public.bi_ventas TO bizview_direct;  -- repite por cada tabla permitida

-- esquema de reportes dedicado (o ds_*): los permisos de todo el esquema están bien
GRANT USAGE ON SCHEMA reporting TO bizview_direct;
GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO bizview_direct;
ALTER DEFAULT PRIVILEGES FOR ROLE erp_loader IN SCHEMA reporting
    GRANT SELECT ON TABLES TO bizview_direct;

GRANT bizview_direct TO bizview;
```

En `public` nunca uses `GRANT SELECT ON ALL TABLES IN SCHEMA public` ni
`ALTER DEFAULT PRIVILEGES ... IN SCHEMA public`: cubrirían las tablas del producto. Nunca concedas
ningún privilegio sobre las tablas del producto a `bizview_direct`. Cuando una tabla permitida en
`public` se elimina y se vuelve a crear, vuelve a ejecutar su `GRANT SELECT`. En los esquemas `ds_*`
el dueño es el usuario de la aplicación `bizview`, así que usa `FOR ROLE bizview` en la línea
`ALTER DEFAULT PRIVILEGES`. Asegúrate también de que el pseudo-rol `PUBLIC` no tenga privilegios sobre
las tablas del producto (`REVOKE ALL ... FROM PUBLIC` en esas tablas si hace falta).

Nota: el motor elimina y vuelve a crear un esquema `ds_<id>` cuando se quita o se vuelve a aplicar una
integración, lo que pierde los permisos a nivel de esquema. Los permisos mostrados arriba deben
volver a ejecutarse tras una recreación así. Para una configuración estable, crea un esquema de
reportes dedicado mantenido por el proceso externo, aplica allí los permisos y mantén los esquemas
`ds_*` fuera de los reportes directos. Pon `DIRECT_BI_ROLE=bizview_direct` en `.env` y reinicia la
aplicación.

### Orígenes con pocas conexiones

La base de datos de origen es de otro sistema (un ERP, casi siempre), y ese sistema se queda primero
con su `max_connections`. Cuando no queda ningún cupo, PostgreSQL rechaza la **conexión** de BizView
—no se ejecuta ninguna consulta ni se lee ninguna fila— y la integración termina en ámbar con **«La
fuente no admite más conexiones ahora»**, después de esperar y reintentar por su cuenta
(`SOURCE_CONNECT_RETRIES`, 4 intentos por defecto, `SOURCE_CONNECT_BACKOFF_S`, 15 s por defecto →
15 s, 45 s, 2 min, 5 min). Los datos y su hora de «Datos actualizados» no cambian; la siguiente
ejecución programada vuelve a intentarlo.

BizView es deliberadamente pequeño: una sesión por fuente por defecto (dos en Supabase), reutilizada
entre los datasets de una ejecución, cerrada al terminar, nombrada `bizview-engine:<integración>` en
el `pg_stat_activity` del origen y limitada a 10 s para conectar, 30 s inactiva dentro de una
transacción y 60 s inactiva. **Conexiones simultáneas**, en la página de la fuente, sube el techo
(1–20) cuando el origen puede permitírselo; el techo es por proceso de la instalación, así que con
varias réplicas de la API cada una tiene el suyo (las ejecuciones sí quedan acotadas con exactitud,
mediante un bloqueo en la base de datos del producto).

Cuatro remedios, en el orden en que suelen funcionar:

1. **Un pooler** delante del origen (PgBouncer, pooling por transacción). BizView habla PostgreSQL
   normal, así que no cambia nada por su lado.
2. **Subir `max_connections`** con el proveedor dueño del origen.
3. **Leer de una réplica**, apuntando la fuente a ella.
4. **Mover la programación** a una hora tranquila (la página de la integración sugiere la hora más
   libre que ha observado), alargar la ventana en lugar de correr cada hora, o `materialize: daily`
   en los reportes que no necesitan una cifra viva.

`ALTER ROLE bizview CONNECTION LIMIT 2` **no** reserva cupos: un límite de conexiones solo acota,
nunca garantiza. Si el mensaje nombra el host de BizView en lugar del del origen, lo que se agotó fue
la base de datos del producto: sube `DB_POOL_SIZE` / `DB_POOL_OVERFLOW` y revisa
`docker compose logs backend`.

### MySQL, MariaDB, SQL Server, SQLite, BigQuery y Google Sheets

Los cinco tipos siguientes se comportan como PostgreSQL: **Probar conexión**, **Ver estructura**,
el paquete de estructura que lleva el zip inicial y la extracción de solo lectura son iguales en
todos. Cambian el controlador, el privilegio mínimo y, en dos casos, un ajuste.

La imagen publicada instala todos los controladores (`uv sync --extra sources`). Una imagen
construida sin uno muestra ese tipo en **Nueva fuente** con el motivo en lugar de fallar: añade el
extra (`bizview[mysql]`, `[mssql]`, `[bigquery]`, `[sheets]`) y reconstruye.

**MySQL / MariaDB** (`PyMySQL`). Un usuario de solo lectura y nada más:

```sql
CREATE USER 'bizview'@'%' IDENTIFIED BY '<contraseña>';
GRANT SELECT ON erp.* TO 'bizview'@'%';
-- la tarjeta de veredicto revisa los permisos: avisa si el usuario puede escribir
```

Puerto 3306 por defecto; TLS `require` (o `verify-full` con la CA del servidor pegada). La sesión se
abre `READ ONLY` y con `MAX_EXECUTION_TIME`, así que una consulta desbocada no puede escribir ni
colgar al worker. En Linux los nombres de tabla distinguen mayúsculas: escríbelos como los muestra
el catálogo.

**SQL Server** (`pymssql`, sin gestor ODBC en la imagen). Un inicio de sesión solo con
`db_datareader`:

```sql
CREATE LOGIN bizview WITH PASSWORD = '<contraseña>';
USE erp; CREATE USER bizview FOR LOGIN bizview;
ALTER ROLE db_datareader ADD MEMBER bizview;
```

Puerto 1433; `encrypt=yes` por defecto (una conexión `optional` se rechaza con el perfil de
seguridad `internet`). SQL Server no tiene un modo de solo lectura por sesión, así que las lecturas
se garantizan rechazando toda sentencia que no sea una lectura, y la tarjeta de veredicto ejecuta
`IS_MEMBER('db_datawriter')` y avisa si el inicio de sesión puede escribir. No se admite
autenticación de Azure AD: usa un inicio de sesión SQL.

**SQLite** (biblioteca estándar, no hay controlador que instalar). Deja la exportación del cliente
en una carpeta montada en el contenedor y apunta `SOURCES_FILES_DIR` a ella:

```env
SOURCES_FILES_DIR=/data/sources
```

```yaml
# docker-compose.yml, servicio backend
volumes:
  - /srv/bizview-fuentes:/data/sources:ro
```

El formulario lista solo los archivos de esa carpeta (`.sqlite`, `.sqlite3`, `.db`, `.db3`, hasta
4 GB) y la ruta se vuelve a comprobar al guardar la fuente: un `..`, un enlace simbólico que salga
de la carpeta o la base de datos del propio producto no se pueden guardar. El archivo se abre
`mode=ro`, nunca se crea ni se migra. Sin `SOURCES_FILES_DIR` el tipo no se ofrece.

**Google BigQuery** (`google-cloud-bigquery`). Crea una cuenta de servicio con **BigQuery Data
Viewer** y **BigQuery Job User** en el proyecto, descarga su clave JSON y pégala en el formulario:
se guarda cifrada y no se vuelve a mostrar. Indica el proyecto, la ubicación, los conjuntos de datos
que BizView puede ver y el **Máximo de bytes facturados por consulta** (1 GB por defecto). Cada
consulta se ejecuta primero en seco: la que leería más que el tope no se ejecuta y el run dice
cuánto habría leído. Una cuenta de servicio con rol de escritura se muestra con un aviso.

**Google Sheets** (`google-api-python-client`). Pega el enlace de la hoja y el mismo tipo de cuenta
de servicio, y **comparte la hoja** con la dirección que muestra el formulario (el `client_email` de
la cuenta; basta con permiso de lectura). Cada pestaña es una tabla; la primera fila es el
encabezado; los tipos se infieren al leer la estructura y se declaran en la integración, así que una
celda cambiada nunca cambia el tipo de una columna. `materialize: daily` es la programación
recomendada: una hoja es una fuente pequeña, y la cuota de lectura de Google se responde con una
pausa ámbar cuando se agota.

## 6. Proyectos

Las integraciones (ETL) y los reportes son **specs**, y viven en **proyectos BI**: una carpeta por
proyecto dentro de `PROJECTS_DIR`, escrita fuera del producto y traída a través de **Proyectos →
Importar** (ver [IMPORT.md](IMPORT.md)). Aplicar un proyecto crea una versión del espacio de
trabajo con él y con los demás proyectos aplicados, y esa versión es la que leen los reportes y las
integraciones. No hay nada que copiar al servidor ni nada que montar, y el archivo compose ya ejecuta
todo lo que el producto necesita, así que no hay ningún proceso extra que instalar ni programar.

El producto no escribe: no hay chat, ni comandos dentro de la aplicación, ni borrador. Lo que escribes
y validas en tu máquina (con la CLI, `bizview validate`) es lo que el servidor vuelve a validar y
aplica.

Un checkout de `bizview init` todavía se puede aplicar desde **Espacio de trabajo → Validar → Aplicar**
(`/admin/espacio`, que no tiene tarjeta en Administración desde el pulido de la 024); el `bizview.yml`
que se distribuye no monta ninguno. Aplicar copia la versión validada a la base de datos (el motor
nunca ejecuta archivos que cambiaron después de la validación); **Volver a la versión anterior**
revierte. **Administración → Integraciones** muestra las ejecuciones, comprobaciones y próxima
ejecución de cada integración, y ejecuta una a demanda. Las tablas de dataset viven en los esquemas
`ds_<integration>` de la base de datos del producto, propiedad del motor.

## 7. IA (opcional)

La IA está apagada por defecto y todo funciona sin ella. Se usa para el agente de ayuda de solo
lectura (033) y para **Generar estructura con IA**, el generador de estructura de cada fuente de datos
(052): la autoría ocurre fuera de Bizview (043/045). El proveedor nunca recibe registros detallados,
contraseñas ni datos personales.

Claude (Anthropic):

```ini
AI_PROVIDER=anthropic
AI_API_KEY=sk-ant-...
# AI_MODEL=claude-opus-5-5   (por defecto)
```

Un modelo local, para que ningún dato salga de la red del cliente (cualquier servidor compatible con
OpenAI, p. ej. [Ollama](https://ollama.com), vLLM, LM Studio):

```ini
AI_PROVIDER=openai_compatible
AI_BASE_URL=http://ollama.internal:11434/v1
AI_MODEL=llama3.1
# AI_API_KEY=   (solo si el servidor necesita una)
```

Reinicia, entra como superusuario → **IA** → **Probar conexión**. La página informa el éxito y el
tiempo de respuesta, o el motivo del fallo (clave inválida, modelo inexistente, inalcanzable, …). La
clave nunca se muestra.

**Generar estructura con IA** (Fuentes de datos → una fuente → **Estructura**) gasta el mismo
proveedor: una pulsación hace un escaneo, como mucho seis llamadas al modelo y una verificación, y
guarda el paquete de estructura que lee la IA externa. Un ajuste opcional limita una ejecución:

```ini
# AI_STRUCTURE_TOKENS=150000    # tokens que puede gastar una generación; 0 apaga el botón
```

El prompt interno es dato (`backend/app/ai/prompts/structure_enrich.md`) y Administración → IA lo
muestra en solo lectura, así que una instalación puede ver exactamente qué se le pide al proveedor.

### Proyectos (la sección Proyectos)

Un **proyecto BI** es una carpeta `projects/<slug>/` en el volumen del backend (`PROJECTS_DIR`, por
defecto `./projects` junto al archivo compose) con sus specs, integraciones, reportes y
distribuciones. **Proyectos** los lista; cada proyecto abre un editor en la nube (archivos, problemas,
historial, validación, aplicar y revertir). `PROJECT_MAX_MB` (por defecto 20) limita el tamaño de un
proyecto. Aplicar un proyecto crea una versión del espacio de trabajo con él y con los demás proyectos
aplicados; la versión registra qué proyecto es dueño de cada artefacto.

Un proyecto también puede incluir imágenes: la carpeta `assets/` dentro de la carpeta del proyecto
guarda los logos que muestra un reporte (`≤ 300 KB` cada uno, `≤ 25 MB` por proyecto), y viajan con la
exportación del proyecto. No necesitan ningún volumen extra, porque viven dentro de `projects/` y se
respaldan con ella.

Distintas son las imágenes que un reporte lee de una **columna de URL**: el worker descarga cada
dirección nueva una vez y guarda los bytes en `IMAGE_CACHE_DIR` (por defecto `./image-cache` junto al
archivo compose, montada como `IMAGE_CACHE_DIR_HOST`; `IMAGE_CACHE_DAYS`, por defecto 90, es la
ventana de retención). Los archivos se nombran por el hash de su contenido y los comparten todos los
proyectos que piden la misma dirección, así que calcula unos pocos megabytes por cada cien logos. La
escribe el worker y la lee el backend, así que ambos la necesitan, y va en los respaldos: sin ella los
tableros muestran el círculo de reserva hasta que la siguiente ejecución vuelva a descargar las
imágenes.

DeepSeek (o cualquier endpoint compatible con OpenAI) funciona con `AI_PROVIDER=openai_compatible`:

```ini
AI_PROVIDER=openai_compatible
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-chat
```

Una llamada fallida registra su código y un detalle redactado en `ai_status`, que `GET /api/health`
lee (`configured`, `provider`, `model`, `healthy`, `blocking_code`) y **Administración → IA** muestra
con las palabras del propio proveedor.

Desde la 0.2.0 la IA se usa **solo** en la página de ayuda de solo lectura: la autoría se mudó fuera
de Bizview (ver [AUTHORING.md](AUTHORING.md)) y ningún dato, proyecto ni consulta se envía jamás a
un proveedor.

### Ingreso con Telegram (opcional)

Apagado por defecto. Cuando está encendido, los usuarios que vinculan su cuenta de Telegram desde
**Perfil** pueden entrar aprobando una solicitud en Telegram y eligiendo el código que aparece en
pantalla; el correo y la contraseña siguen funcionando. Los administradores del perfil `internet`
siguen introduciendo su código de doble paso.

1. En Telegram, habla con [@BotFather](https://t.me/BotFather) → `/newbot`. Anota el nombre del bot
   (termina en `bot`) y su credencial. Usa un bot por instalación y no configures un webhook.
2. El stack debe alcanzar `https://api.telegram.org` (solo HTTPS saliente; no hace falta ninguna
   dirección pública).
3. Entra como superusuario → **Seguridad** → **Ingreso con Telegram**: introduce el nombre del bot y
   la credencial, **Guardar**, **Probar**, y luego activa **Activar ingreso con Telegram**.

La credencial se cifra con `BIZVIEW_SECRET_KEY`, no se vuelve a mostrar nunca y `rotate-secret-key` la
vuelve a cifrar. Cambiarla apaga la opción hasta que el bot se pruebe otra vez.

### Ingreso con Google (opcional)

Apagado por defecto. Con `GOOGLE_AUTH_ENABLED=true`, la pantalla de ingreso muestra **Continuar con
Google** junto al formulario de contraseña; el correo y la contraseña siguen funcionando. El navegador
va a `/api/auth/google/start` y Google vuelve a `/api/auth/google/callback`, así que el URI de
redirección autorizado del cliente es `https://<your-domain>/api/auth/google/callback`.

El id y el secreto del cliente pertenecen al proyecto de Google Cloud de **esta instalación**, nunca a
un cliente en manos del proveedor: dos instalaciones no comparten credencial, y revocar un cliente
solo afecta a esa instalación.

1. En la [consola de Google Cloud](https://console.cloud.google.com/), crea un proyecto (o elige uno
   existente) para esta instalación.
2. Configura la **pantalla de consentimiento de OAuth**: **Internal** cuando los usuarios pertenecen a
   un dominio de Google Workspace del cliente, o **External** con las personas listadas como usuarios
   de prueba mientras la aplicación no esté publicada.
3. **Credentials** → **Create credentials** → **OAuth client ID**, tipo de aplicación **Web
   application**. En **Authorised redirect URIs** añade exactamente
   `https://<your-domain>/api/auth/google/callback`, con el dominio de `SITE_ADDRESS`.
4. Copia el id y el secreto del cliente en el `.env` de la instalación (`GOOGLE_CLIENT_ID`,
   `GOOGLE_CLIENT_SECRET`), pon `GOOGLE_AUTH_ENABLED=true` y reinicia:
   `docker compose -f bizview.yml up -d`.
5. Opcional: `GOOGLE_ALLOWED_DOMAINS=cliente.com,socio.com` restringe qué dominios de correo pueden
   entrar (vacío = cualquier dominio). `GOOGLE_REDIRECT_URI` reemplaza el URI de redirección y es solo
   para configuraciones de proxy poco habituales; vacío lo deriva de `SITE_ADDRESS`.

Hay dos comportamientos que conviene entender antes de activarlo:

- **No crea cuentas.** Un ingreso con Google solo tiene éxito cuando el correo verificado de Google
  pertenece a un usuario existente y activo: invita primero a la persona (**Administración →
  Usuarios**) y luego podrá usar Google. Un correo desconocido recibe el mismo fallo que una
  contraseña incorrecta, así que el flujo no sirve para descubrir quién tiene cuenta, y el primer
  ingreso correcto vincula esa identidad de Google al usuario. Nunca crees ni asciendas un usuario a
  través de él.
- **Un usuario invitado igualmente define una contraseña en su primer ingreso.** Toda cuenta conserva
  una contraseña utilizable, así que conserva una vía de entrada que no depende de Google: un usuario
  nuevo entra por primera vez (con Google o con la contraseña temporal) y el producto le pide definir
  su propia contraseña antes de continuar. A partir de ahí Google es una alternativa, nunca un
  reemplazo.
- **Los administradores conservan su segundo factor.** Google prueba *quién* es la persona; no
  reemplaza el código de doble paso que el perfil `internet` exige a los administradores. Ambos
  métodos terminan en el mismo ingreso, así que un administrador sigue introduciendo (o enrolándose)
  su código.

El secreto del cliente solo lo lee el backend: nunca lo devuelve una respuesta de la API, nunca se
escribe en los logs y nunca se envía al navegador. Vive en `.env`, así que lo cubren los permisos de
ese archivo y no los ajustes cifrados del producto.

Solución de problemas:

- **Usa tu propio cliente.** Un cliente copiado de otra instalación falla en el callback, porque el URI
  de redirección no le pertenece; y un secreto filtrado expondría entonces todas las instalaciones que
  lo compartan.
- **`redirect_uri_mismatch`** significa que la entrada de la consola no es carácter por carácter
  `https://<your-domain>/api/auth/google/callback`: HTTPS, sin barra final, el dominio de
  `SITE_ADDRESS`. Corrige la entrada (o `GOOGLE_REDIRECT_URI`) y reinicia.
- **`access blocked`** significa que la pantalla de consentimiento es **External** y la persona no
  está listada como usuario de prueba, o que la aplicación no está publicada. Añádela como usuario de
  prueba, o usa una pantalla de consentimiento **Internal** en el dominio de Workspace del cliente.
- **Nadie queda bloqueado.** El ingreso con contraseña funciona en todos esos casos — y también con
  `GOOGLE_AUTH_ENABLED=false` —, así que el superusuario puede seguir entrando con correo y contraseña
  y corregir los ajustes (ver §10 para recuperar al superusuario).

### Correo y enlaces compartidos (opcional)

Ambos están apagados por defecto. El correo permite a los usuarios enviar el PDF de un tablero desde el
tablero y permite a los administradores programar envíos. Los enlaces compartidos permiten a los
administradores crear enlaces de solo lectura que caducan a los 1–90 días.

1. Pide al proveedor de correo del cliente una cuenta SMTP: host, puerto (normalmente `587` con
   STARTTLS o `465` con SSL/TLS), usuario, contraseña y una dirección desde la que puedas enviar.
2. El `.env` de la instalación (el mismo archivo que los ajustes de IA; no hay formulario en el
   producto) ya contiene estas variables comentadas. Descoméntalas y rellénalas:

   ```
   SMTP_HOST=smtp.cliente.com
   SMTP_PORT=587
   SMTP_SECURITY=starttls       # starttls | ssl | none; vacío = ssl en 465, si no starttls
   SMTP_USER=bizview@cliente.com
   SMTP_PASSWORD=...
   SMTP_FROM=bizview@cliente.com
   SMTP_FROM_NAME=Cliente Demo  # opcional; por defecto ORGANIZATION_NAME
   EMAIL_ALLOWED_DOMAINS=       # opcional: vacío = cualquier dominio (ver «Enviar a cualquier dirección»)
   SHARE_LINKS_ENABLED=true     # permite a los administradores pulsar Compartir en un tablero
   ```

   El correo está encendido cuando `SMTP_HOST` y `SMTP_FROM` están definidos. Tras cualquier cambio
   reinicia el stack (`docker compose -f bizview.yml up -d`); un valor inválido lo detiene al arrancar
   con un mensaje que nombra la variable.
3. El correo sale del stack, así que este debe poder alcanzar el host y el puerto SMTP (solo saliente;
   no hace falta ninguna dirección pública).
4. Comprueba la configuración con un correo de prueba (no hay opción de correo en
   **Administración**): `docker compose -f bizview.yml run --rm backend python -m app.cli mail-test <address>` envía un mensaje e
   imprime el éxito o un motivo saneado (nunca la contraseña).

Notas de seguridad. `SMTP_SECURITY=none` se rechaza al arrancar en el perfil `internet`, y STARTTLS
verifica el certificado. `SMTP_PASSWORD` queda en el entorno de la instalación: nunca se guarda en la
base de datos, ni lo devuelve la API, ni se muestra, ni se registra, y debe ser ASCII sin saltos de
línea. Los correos de prueba y los envíos quedan auditados.

Enviar a cualquier dirección (funcionalidad 058). Quien envía sigue siendo interno —solo un usuario
con sesión y con acceso al tablero puede enviar—, pero un envío puede llegar a **cualquier
dirección**: usuarios de la instalación, una **lista de correo** creada en **Listas de correo**, o
direcciones escritas o pegadas en el diálogo. El producto no impone **límites de volumen**: los pone
el proveedor. Lo que sí hace es dosificar y agrupar la entrega para que una lista grande no atasque
al worker ni dispare al proveedor:

```
EMAIL_BATCH_SIZE=50            # destinatarios por mensaje SMTP (CCO, el remitente en Para)
EMAIL_SEND_RATE=10             # mensajes por segundo; 0 = sin pausa
EMAIL_INDIVIDUAL_MESSAGES=false  # true = un mensaje por dirección (rebotes por dirección en SES)
EMAIL_SENDING_PAUSED=false     # true = retiene la cola; los envíos se siguen aceptando
EMAIL_FROM_MODE=installation   # installation = SMTP_FROM + Reply-To al remitente; user = desde el remitente
EMAIL_FREE_ADDRESSES_ROLE=user # admin = solo los administradores escriben direcciones sueltas
```

Qué necesita cada proveedor:

| Proveedor | Configuración |
|---|---|
| Amazon SES | verifica el dominio (DKIM), deja `EMAIL_FROM_MODE=installation` con `SMTP_FROM` en el dominio verificado y pon `EMAIL_INDIVIDUAL_MESSAGES=true` para que un rebote se atribuya a una dirección; mantén `EMAIL_SEND_RATE` en o por debajo de tu ritmo de envío (el de SES por defecto es 14/s) |
| Google Workspace | relay SMTP `smtp-relay.gmail.com:587` con STARTTLS, `SMTP_USER` una cuenta con contraseña de aplicación o la lista de IP del relay; `EMAIL_FROM_MODE=user` funciona cuando el tenant permite «enviar como» a sus usuarios |
| Microsoft 365 | `smtp.office365.com:587` con STARTTLS y SMTP AUTH activado en el buzón; un buzón compartido como `SMTP_FROM` mantiene el remitente estable, `EMAIL_FROM_MODE=installation` con `Reply-To` al remitente |

Un PDF de 10 MB sigue teniendo su propio límite: cuando lo supera con **Incluir enlace** marcado, el
correo lleva solo el enlace, y sin enlace el envío falla con el motivo «El PDF supera 10 MB y no se
pidió un enlace.». Las entregas fallidas se reintentan a los 1, 5 y 15 minutos, el estado de cada
destinatario se lista en **Envíos**, y **Reenviar los fallidos** encola solo las direcciones que
fallaron.

Enlaces. Quien tenga un enlace ve ese tablero en solo lectura hasta que caduque o se revoque
(**Revocar**), con un máximo de 20 enlaces activos por tablero. Los enlaces se guardan solo como hash,
así que un enlace perdido no se puede volver a mostrar: crea uno nuevo. Poner
`SHARE_LINKS_ENABLED=false` (y reiniciar) detiene todos los enlaces a la vez. La página pública no la
indexan los buscadores y tiene límite de peticiones por dirección.

Enlaces en los correos. Cuando un administrador marca **Incluir enlace** en **Enviar por correo**, el
correo saliente lleva un enlace privado válido N días (1–90), creado con la nota «Correo:
<asunto>». El remitente tiene un enlace por envío, no por destinatario, y el enlace cuenta para los
20 enlaces activos por tablero mientras está en cola o activo; en el límite se rechaza el envío con
enlace y el correo se puede enviar sin él. Los envíos programados (**Envíos programados**) reutilizan
un único enlace propiedad de cada suscripción y no cuentan para el límite; solo se crea un reemplazo
cuando el enlace actual caduca en menos de un día o se revoca. **Enlaces activos** dentro de
**Compartir** muestra el origen de cada enlace («Creado a mano», «Creado por un envío por correo»,
«Creado por un envío programado») y marca los enlaces de suscripción como no contados. Revocar el
enlace de una suscripción lo detiene de inmediato y la siguiente ejecución programada crea uno nuevo.
Cuando los enlaces compartidos están apagados (`SHARE_LINKS_ENABLED=false`) en el momento de la
ejecución, un envío programado va sin enlace (solo PDF) y el que solo tiene un enlace se omite en esa
ejecución. Los cifrados de los enlaces que se guardan para reintentos y reutilización están cifrados
con `BIZVIEW_SECRET_KEY` y `rotate-secret-key` los vuelve a cifrar.

Direcciones de los enlaces. Con un dominio en `SITE_ADDRESS`, los enlaces de la vista de compartir y
de los correos (incluidos los programados) son `https://<domain>/s/…`. Sin dominio (`:80`), un enlace
creado desde el navegador usa la dirección que está usando el administrador, y los correos
programados recurren a `http://localhost`: así que define un dominio en `SITE_ADDRESS` antes de
incluir enlaces en correos programados. Los destinatarios fuera de la red necesitan que el sitio sea
alcanzable desde donde abran el enlace.

Los envíos programados usan la zona horaria de la instalación (`TIMEZONE`).

## 8. Actualizar

```bash
cd /opt/bizview
sed -i "s/^BIZVIEW_VERSION=.*/BIZVIEW_VERSION='0.2.0'/" .env
docker compose -f bizview.yml pull && docker compose -f bizview.yml up -d
```

Las migraciones se ejecutan solas. Volver a una versión anterior no está soportado una vez que una más
nueva ha migrado la base de datos: restaura un respaldo en su lugar (siguiente sección). Lee las notas
del release antes de actualizar.

**Nunca ejecutes `alembic upgrade` desde un puesto de trabajo contra la base de datos de una
instalación.** Marca la base de datos con una revisión que las imágenes instaladas pueden no contener,
y entonces todos los contenedores fallan al arrancar con `Can't locate revision identified by '…'` (el
entrypoint ahora lo explica). El contenedor migra por su cuenta; si la base de datos ya está más
adelante, actualiza al release que la migró, o restaura un respaldo tomado antes de esa actualización.

El stack también ejecuta **`watchtower`** (contenedor `bizview-watchtower`): cada
`WATCHTOWER_POLL_INTERVAL` segundos (300 por defecto) descarga una imagen más nueva de la etiqueta de
`BIZVIEW_VERSION` y recrea solo los contenedores de esta instalación, un servicio a la vez, para que el
sitio siga en pie. Está acotado por etiqueta y nunca toca otros stacks del host. Dos consecuencias:

- con `BIZVIEW_VERSION=latest`, una publicación actualiza la instalación por sí sola: los comandos de
  arriba solo hacen falta entonces para fijar una versión;
- con una etiqueta fija como `0.1.0`, no pasa nada hasta que cambies la etiqueta, lo que convierte una
  actualización en un acto deliberado (el ajuste recomendado para un cliente).

Watchtower recrea un contenedor con **su propia configuración guardada**: aplica una imagen nueva,
nunca un cambio en `bizview.yml`. Un release que añade un servicio o renombra contenedores (0.1.0 → los
servicios ahora son `bizview-backend`, `bizview-worker`, `bizview-caddy` en lugar de `bizview-*-1`) deja
los contenedores viejos corriendo junto a los nuevos, todavía con sus puertos, y un release que añade un
**volumen** o una **variable de entorno** sigue corriendo sin él hasta que el archivo compose se aplique
una vez. Siempre que una actualización haya tocado `bizview.yml`, ejecuta esto en el servidor después de
descargar las imágenes:

```bash
docker compose -f bizview.yml up -d --build --remove-orphans
```

No hace falta `down`: `up -d` ya recrea solo lo que cambió, y el backend ejecuta las migraciones por sí
solo al arrancar.

Nunca mezcles los dos flujos: un `up -d --build` local reemplaza el contenedor pero no la imagen del
registro, así que el siguiente sondeo puede devolverlo a lo que tenga `:latest`. Publica con `deploy.sh`
(y deja que Watchtower lo aplique) o compila localmente y mantén Watchtower al margen (una etiqueta de
versión fija, o elimina el servicio mientras desarrollas).

Para comprobar de inmediato en lugar de esperar: `docker compose -f bizview.yml run --rm watchtower
--run-once`. Necesita el socket de Docker, que puede controlar todos los contenedores del host; quita el
servicio `watchtower` del archivo compose si eso no es aceptable, y actualiza con los comandos de
arriba.

**Confirma qué se está ejecutando de verdad.** `/api/health` responde con la versión del release y el
commit con el que se construyó la imagen (`deploy.sh` lo graba):

```bash
curl -sk https://bi.example.com/api/health
# {"status":"ok","version":"0.1.0","commit":"3fb5fff"}
```

Si `commit` no es el que publicaste, el servidor sigue ejecutando la imagen anterior: la etiqueta no se
movió, o Watchtower todavía no ha sondeado. Un checkout de desarrollo (sin `BIZVIEW_COMMIT`) responde
sin el campo `commit`.

## 9. Respaldo y restauración

La base de datos guarda todos los datos del producto (usuarios, accesos, auditoría, versiones del
espacio de trabajo aplicadas, historial de archivos de los proyectos, historial de ejecuciones y los
datasets `ds_*`, que también se pueden reconstruir con una ejecución completa); la carpeta de la
instalación guarda los ajustes, la **carpeta `projects/`** (los archivos de cada proyecto BI —respáldala
con la base de datos—) y la **carpeta `image-cache/`** (las imágenes que `IMAGE_CACHE_DIR` conserva para
los reportes que leen una columna de URL); el logo está dentro de la imagen `bizview-web`.

Desde la 045 no se guardan datos de conversación: el agente de autoría dentro de la aplicación y sus
tablas ya no existen, y los documentos de spec de cualquier conversación que se haya aplicado viven en la
carpeta de su proyecto. Restaurar un respaldo de la base de datos tomado *antes* de la actualización a la
045 es la única forma de recuperar esas filas: la degradación vuelve a crear las tablas vacías.

```bash
pg_dump --format=custom --file bizview-$(date +%F).dump "$DATABASE_URL_BI"   # base de datos
tar czf bizview-install-$(date +%F).tgz -C /opt bizview                        # ajustes + proyectos + caché de imágenes
```

Restaurar: `pg_restore --clean --dbname "$DATABASE_URL_BI" bizview-YYYY-MM-DD.dump`, devuelve la carpeta
a su sitio, `docker compose -f bizview.yml up -d`. Mantén los respaldos cifrados: contienen los secretos
de `.env`.

## 10. Recuperar al superusuario

Contraseña olvidada o sin acceso: pon la nueva contraseña en `SUPER_USER_PASSWORD` en `.env`, y luego

```bash
cd /opt/bizview && docker compose -f bizview.yml run --rm backend python -m app.cli reset-superuser-password
```

Cambiar la variable por sí sola no hace nada: una contraseña cambiada en la interfaz siempre gana.

Autenticador **y** códigos de recuperación perdidos: `docker compose -f bizview.yml run --rm backend python -m app.cli
reset-superuser-mfa`, luego entra y vuelve a enrolarte. Otros usuarios: el superusuario los restablece en
su página de usuario (*Restablecer doble factor*).

## 11. Desinstalar

```bash
cd /opt/bizview && docker compose -f bizview.yml down -v     # detiene los contenedores, elimina los volúmenes de certificados
```

La base de datos no se toca; elimínala aparte si el cliente ya no necesita los datos.

## Operar varios clientes

Mantén el repositorio del producto genérico. Si operas instalaciones para varios clientes, mantén un
**repositorio privado de operaciones** con una carpeta por cliente que contenga solo los archivos de
instalación de ese cliente, nunca código:

```text
ops-bizview/                       (privado)
├── acme/     .env.enc  bizview.yml
└── globex/   .env.enc  bizview.yml
```

Cifra los archivos `.env` (por ejemplo con [sops](https://github.com/getsops/sops) + age) y actualiza a
los clientes cambiando `BIZVIEW_VERSION` por carpeta. Las necesidades específicas de un cliente se
convierten en ajustes o puntos de extensión del producto, nunca en un fork.
