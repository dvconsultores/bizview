# Bizview

[English](README.md) · **Español**

[![Bizview en el teléfono: un tablero de ventas](docs/assets/readme-phone.png)](docs/assets/readme-phone.png)

**Los datos de tu negocio en tu teléfono. Arma los reportes con la IA que quieras — Bizview los
valida, los ejecuta y los comparte.**

Bizview es un producto de BI autoalojado y pensado primero para el móvil. Cada integración y cada
reporte es una **especificación declarativa** (YAML más SQL de solo lectura). Esas specs se escriben
**fuera** de Bizview — a mano, en el editor del proyecto o con la IA que prefieras — contra un
contrato publicado, y el producto las valida, las importa, las ejecuta cada día y comparte el
resultado. El producto no escribe nada por su cuenta, y ningún modelo genera código que el servidor
ejecute.

[Instalar](#instalación-docker-compose) · [Producto alojado](https://bizview.com) · [Conectar mi ERP](docs/AUTHORING.md)

## Instalación (Docker Compose)

Requisitos: un servidor Linux con Docker y Docker Compose, y una base **PostgreSQL** donde puedas
escribir (Bizview nunca trae un contenedor de base de datos: siempre es externa). Para un servidor
público, además un dominio que apunte a él.

```bash
mkdir -p /opt/bizview && cd /opt/bizview
curl -fsSLO https://raw.githubusercontent.com/dvconsultores/bizview/main/bizview.yml
curl -fsSL  https://raw.githubusercontent.com/dvconsultores/bizview/main/.env.example -o .env
```

No hace falta clonar: [`bizview.yml`](bizview.yml) es todo el stack (Caddy, backend, worker y
Watchtower) corriendo las imágenes publicadas `dvconsultores/bizview-backend` y
`dvconsultores/bizview-web`. Con cuatro valores en `.env` alcanza para arrancar:

```dotenv
DATABASE_URL_BI=******host:5432/bizview
SUPER_USER_EMAIL=tu@ejemplo.com
SUPER_USER_PASSWORD=una-clave-larga        # solo en el primer arranque
BIZVIEW_SECRET_KEY=<openssl rand -hex 32>  # cifra las credenciales guardadas; hazle copia
```

Después:

```bash
mkdir -p projects image-cache && sudo chown -R 10001:10001 projects image-cache  # los contenedores corren como uid 10001
docker compose -f bizview.yml pull
docker compose -f bizview.yml up -d
```

(`projects/` e `image-cache/` son las carpetas del host que la aplicación escribe; sin el `chown`
puede leerlas pero no escribirlas.) Para construir las imágenes desde el código, clona el repositorio
y ejecuta `docker compose -f bizview.yml up -d --build`.

- **Red local o privada**: abre `http://<servidor>:8081`. Deja `SECURITY_PROFILE=private`.
- **Servidor público**: pon `SITE_ADDRESS=bi.tuempresa.com`, `CADDY_ALLOWED_HOSTS=bi.tuempresa.com`,
  `SECURITY_PROFILE=internet`, `COOKIE_SECURE=true`, `HTTPS_PORT=443`. Caddy obtiene el certificado
  automáticamente. Abre `https://bi.tuempresa.com`.

**Actualizar**: con `BIZVIEW_VERSION=latest` (el valor por defecto), Watchtower descarga las
imágenes nuevas solo (cada 5 minutos, únicamente los contenedores de Bizview). Para fijar una
versión, pon `BIZVIEW_VERSION=0.2.0` y actualiza cambiándola y ejecutando `docker compose -f
bizview.yml pull && docker compose -f bizview.yml up -d`. Puertos, TLS detrás de otro proxy,
Cloudflare, copias de seguridad y marca: [docs/INSTALL.md](docs/INSTALL.md).

## Cómo funciona

1. **Agrega una fuente** — **Fuentes de datos → Nueva**, con las credenciales y **Probar**.
2. **Descríbela** — `bizview describe <fuente>` imprime tablas, columnas y tipos (estructura y
   conteos, nunca filas).
3. **Descarga el paquete de autoría** — `bizview init workspace --name miempresa` escribe los
   presets, las reglas, los esquemas y un proyecto de ejemplo.
4. **Escribe la petición** — `REQUEST.md`: qué responde el tablero, para quién, con qué filtros.
5. **Constrúyelo con cualquier IA (o a mano)** — el `PROMPT.md` del paquete le dice al agente las
   reglas; la salida es `specs/NNN-nombre/spec.md`, `integrations/<id>/integration.yaml|queries/*.sql`
   y `reports/<id>/report.yaml`.
6. **Valida** — `bizview validate .` corre el mismo validador que el servidor y escribe
   `problems.json` con archivo, ruta JSON, mensaje y, cuando puede, el arreglo.
7. **Importa** — **Proyectos → Importar** recibe el zip, mapea las carpetas, informa colisiones,
   valida otra vez y muestra el árbol antes de aplicar nada.
8. **Aplica y comparte** — **Aplicar** crea una versión; **Compartir** genera un enlace de solo
   lectura, **Enviar por correo** programa el PDF.

El contrato, cada archivo y un ejemplo completo resuelto: [docs/AUTHORING.md](docs/AUTHORING.md). El
camino de importación: [docs/IMPORT.md](docs/IMPORT.md).

## Qué hace

| Capacidad | Spec |
|---|---|
| Integraciones declarativas (PostgreSQL, REST, SOAP, Supabase) ejecutadas por un worker con horario | [005](specs/005-vibe-reporting/spec.md), [016](specs/016-supabase-source/spec.md) |
| Reportes con métricas, dimensiones, vistas, filtros y períodos; reportes directos sobre una tabla existente | [005](specs/005-vibe-reporting/spec.md), [019](specs/019-direct-source-reports/spec.md) |
| Diseños declarativos para tableros y PDF, dibujados por la app en pantalla y por ReportLab en el servidor | [026](specs/026-declarative-layouts/spec.md) |
| Proyectos BI: una carpeta por proyecto con specs numeradas, historial y editor en el navegador; exportación en zip | [020](specs/020-bi-projects/spec.md) |
| Importación y exportación como puerta de entrada: subir → mapear → colisiones → validar → vista previa → aplicar | [020](specs/020-bi-projects/spec.md), [046](specs/046-release-docs-governance/spec.md) |
| El paquete de autoría: presets, reglas, esquemas, `PROMPT.md`, `REQUEST.md` y un ejemplo de oro | [043](specs/043-bizview-refactor-external-authoring/spec.md) |
| Paquetes de estructura: la estructura y los conteos de una fuente como documento que una IA externa puede leer | [043](specs/043-bizview-refactor-external-authoring/spec.md) |
| Componentes visuales: bloques gauge, index, share y asset, imágenes del proyecto y caché de imágenes por URL | [044](specs/044-visual-components-and-assets/spec.md) |
| Compartir: enlaces de solo lectura que expiran, envío por correo, envíos programados | [018](specs/018-dashboard-sharing/spec.md) |
| Español e inglés, modo oscuro, exportación a PDF y CSV | [022](specs/022-i18n-en-es/spec.md), [006](specs/006-dark-mode/spec.md) |
| Administración: usuarios, roles, acceso, auditoría, perfil `internet`, ingreso con Google o Telegram | [002](specs/002-auth-admin-home/spec.md), [004](specs/004-data-sources-security/spec.md), [027](specs/027-google-sign-in/spec.md), [007](specs/007-telegram-sign-in/spec.md) |
| Guía dentro de la app, aviso de actualización, búsqueda de proyectos | [023](specs/023-chat-app-guide/spec.md), [025](specs/025-app-updates-and-search/spec.md) |

Pensado para el móvil: cada pantalla funciona desde 320 px, WCAG 2.2 AA. Cómo escribir reportes:
[docs/AUTHORING.md](docs/AUTHORING.md).

## Configuración

[`.env.example`](.env.example) es la lista completa. Los grupos que vas a tocar:

| Grupo | Ajustes |
|---|---|
| Base de datos | `DATABASE_URL_BI` |
| Sitio y TLS | `SITE_ADDRESS`, `CADDY_ALLOWED_HOSTS`, `HTTP_PORT` (8081), `HTTPS_PORT` (8443; `443` en un servidor público), `CADDY_TLS`, `TRUSTED_PROXIES` |
| Seguridad | `SECURITY_PROFILE` (`private` / `internet`), `COOKIE_SECURE`, `BIZVIEW_SECRET_KEY`, `SUPER_USER_EMAIL`, `SUPER_USER_PASSWORD` |
| Marca | `PRODUCT_NAME`, `ORGANIZATION_NAME`, `LOGO_URL`, `DEFAULT_LOCALE`, `TIMEZONE` |
| Proyectos | `PROJECTS_DIR`, `PROJECT_MAX_MB`, `IMAGE_CACHE_DIR`, `IMAGE_CACHE_DAYS` |
| IA (opcional, apagada por defecto, **solo ayuda**) | `AI_PROVIDER` (`none` / `anthropic` / `openai_compatible`), `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL` (cualquier endpoint compatible con OpenAI, incluidos modelos locales) |
| Correo y compartir | `SMTP_*`, `EMAIL_ALLOWED_DOMAINS`, `SHARE_LINKS_ENABLED` |
| Imágenes | `BIZVIEW_IMAGE_PREFIX`, `BIZVIEW_VERSION` |

## Cómo está hecho

```text
navegador ──HTTPS──▶ Caddy (SPA + /api + certificados) ──▶ backend FastAPI ──▶ PostgreSQL (externa)
                                                               ├──▶ worker (ETL, correo, horarios, caché de imágenes)
                                                               └──▶ proveedor de IA (opcional, solo la ayuda)
projects/ (specs, YAML, SQL, assets) ────────────────────▶ backend + worker ──▶ fuentes de datos
                                        la autoría ocurre fuera ──▶ importar ──┘
```

Python 3.12 / FastAPI / SQLAlchemy / Alembic / ReportLab; React 19 / Vite / Tailwind; Caddy. La
carpeta `cli/` tiene el comando `bizview`, los esquemas JSON y las reglas SQL que leen la CLI, el
backend y el paquete de autoría: una sola fuente para el contrato. Las specs viven en
[`specs/`](specs/) con [Spec Kit](https://github.com/github/spec-kit); los principios en
[`.specify/memory/constitution.md`](.specify/memory/constitution.md).

Entorno de desarrollo, pruebas y convenciones: [CONTRIBUTING.md](CONTRIBUTING.md).

## Seguridad

- `SECURITY_PROFILE=internet`: HTTPS en todo, doble factor para administradores, límite de intentos
  de ingreso y confirmación con contraseña para los cambios sensibles.
- Las credenciales de las fuentes se cifran en reposo (AES-256-GCM) con `BIZVIEW_SECRET_KEY` y son
  de solo escritura: nunca se devuelven, se muestran ni se registran. Guarda la clave aparte de la
  base de datos.
- Las bases de origen son de solo lectura para Bizview; las conexiones rechazan direcciones de
  loopback, link-local y de metadatos de nube, y lo mismo las descargas de una imagen que un reporte
  pide por URL.
- La importación valida antes de que algo corra: tipos de archivo, tamaños, contenido comprobado por
  bytes y SVG saneado.
- Ninguna IA escribe dentro del producto. El proveedor opcional sirve la página de ayuda de solo
  lectura; los paquetes de estructura que le das a una IA externa llevan estructura, conteos y
  formas: nunca credenciales, hosts ni valores de filas.

Reporta vulnerabilidades en privado desde la pestaña *Security* de GitHub: [SECURITY.md](SECURITY.md).

## Contribuir

Los issues y pull requests son bienvenidos: lee [CONTRIBUTING.md](CONTRIBUTING.md) para el entorno de
desarrollo, el flujo de especificación y las comprobaciones que debe pasar un pull request, y
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) para el trato entre nosotros.

## Licencia

[GNU AGPL-3.0-or-later](LICENSE). Si ejecutas una versión modificada para otros por red, debes
ofrecerles su código fuente; la app enlaza al fuente en cada página (`SOURCE_URL`). La licencia no
concede derechos sobre el nombre ni el logo «Bizview».
