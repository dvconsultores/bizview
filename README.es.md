# Bizview AI Powered

[English](README.md) · **Español**

Los datos de tu negocio en tu teléfono, con un chat que arma los reportes.

Bizview es un producto de BI autoalojado y pensado primero para el móvil. Cada integración y cada
reporte es una **especificación declarativa** (YAML más SQL de solo lectura) que se valida antes de
correr: nada corre sin su spec. Un asistente de IA opcional escribe esas mismas specs a partir de una
petición en lenguaje natural; el código del producto las valida y las muestra, y el modelo nunca
genera código que el servidor ejecute.

Cada organización instala la misma versión publicada en su propio servidor. Marca, base de datos,
idioma e IA son configuración, nunca cambios de código.

<!-- captura: tablero en el teléfono + clip del chat (ver repo del sitio) -->

## Instalación (Docker Compose)

Requisitos: un servidor Linux con Docker y Docker Compose, y una base de datos **PostgreSQL** con
permisos de escritura (Bizview no incluye contenedor de base de datos; siempre es externa). Para un
servidor público, además un dominio que apunte a él.

```bash
mkdir -p /opt/bizview && cd /opt/bizview
curl -fsSLO https://raw.githubusercontent.com/dvconsultores/bizview/main/bizview.yml
curl -fsSL  https://raw.githubusercontent.com/dvconsultores/bizview/main/.env.example -o .env
```

No hace falta clonar: [`bizview.yml`](bizview.yml) es todo el stack (Caddy, backend, worker y
Watchtower) con las imágenes publicadas `dvconsultores/bizview-backend` y
`dvconsultores/bizview-web`. Edita `.env`; con cuatro valores alcanza para empezar:

```dotenv
DATABASE_URL_BI=postgresql://usuario:clave@host:5432/bizview
SUPER_USER_EMAIL=tu@empresa.com
SUPER_USER_PASSWORD=una-clave-larga              # solo en el primer arranque
BIZVIEW_SECRET_KEY=<openssl rand -hex 32>        # cifra las credenciales guardadas; respáldala
```

Luego:

```bash
mkdir -p projects attachments && sudo chown -R 10001:10001 projects attachments  # los contenedores corren como uid 10001
docker compose -f bizview.yml pull
docker compose -f bizview.yml up -d
```

(`projects/` y `attachments/` son las únicas carpetas del host; sin el `chown` la app puede leerlas
pero no escribir.) Para construir las imágenes desde el código, clona el repositorio y ejecuta
`docker compose -f bizview.yml up -d --build`.

- **Red local o privada**: abre `http://<servidor>:8081`. Deja `SECURITY_PROFILE=private`.
- **Servidor público**: pon `SITE_ADDRESS=bi.tuempresa.com`, `CADDY_ALLOWED_HOSTS=bi.tuempresa.com`,
  `SECURITY_PROFILE=internet`, `COOKIE_SECURE=true`, `HTTPS_PORT=443`. Caddy obtiene el certificado
  automáticamente. Abre `https://bi.tuempresa.com`.

Inicia sesión con el superusuario, agrega una fuente de datos y escribe una spec en un espacio de
trabajo o abre el **Asistente** y pide un reporte.

**Actualizar**: con `BIZVIEW_VERSION=latest` (el valor por defecto), Watchtower descarga las
imágenes nuevas solo (cada 5 minutos, únicamente los contenedores de Bizview). Para fijar una
versión, pon `BIZVIEW_VERSION=0.1.0` y actualiza cambiándola y ejecutando `docker compose -f
bizview.yml pull && docker compose -f bizview.yml up -d`. Puertos, TLS detrás de otro proxy,
Cloudflare, respaldos y marca: [docs/INSTALL.md](docs/INSTALL.md).

## Qué hace

| Capacidad | Spec |
|---|---|
| Integraciones declarativas (PostgreSQL, REST, SOAP, Supabase) ejecutadas por un worker según horario | [005](specs/005-vibe-reporting/spec.md), [016](specs/016-supabase-source/spec.md) |
| Reportes con métricas, dimensiones, vistas, filtros y períodos; reportes directos sobre una tabla existente | [005](specs/005-vibe-reporting/spec.md), [019](specs/019-direct-source-reports/spec.md) |
| **Asistente**: un chat que redacta, valida y previsualiza specs con los comandos de Spec Kit antes de aplicar nada | [014](specs/014-vibe-chat/spec.md), [017](specs/017-agentic-vibe-chat/spec.md), [021](specs/021-speckit-chat-commands/spec.md) |
| Layouts declarativos para tableros y PDF, dibujados por la app en pantalla y por ReportLab en el servidor | [026](specs/026-declarative-layouts/spec.md) |
| Proyectos BI: una carpeta por proyecto con specs numeradas, historial y editor en el navegador; exportación en zip | [020](specs/020-bi-projects/spec.md) |
| Compartir: enlaces de solo lectura con vencimiento, envío por correo, envíos programados | [018](specs/018-dashboard-sharing/spec.md) |
| Español e inglés, modo oscuro, exportación a PDF y CSV | [022](specs/022-i18n-en-es/spec.md), [006](specs/006-dark-mode/spec.md) |
| Administración: usuarios, roles, accesos, auditoría, perfil de seguridad `internet`, inicio de sesión con Google o Telegram | [002](specs/002-auth-admin-home/spec.md), [004](specs/004-data-sources-security/spec.md), [027](specs/027-google-sign-in/spec.md), [007](specs/007-telegram-sign-in/spec.md) |
| Guía dentro de la app, aviso de actualización, búsqueda de proyectos | [023](specs/023-chat-app-guide/spec.md), [025](specs/025-app-updates-and-search/spec.md) |

Móvil primero: cada pantalla funciona desde 320 px y cumple WCAG 2.2 AA. Cómo escribir reportes:
[docs/VIBE-REPORTING.md](docs/VIBE-REPORTING.md).

## Configuración

[`.env.example`](.env.example) es la lista completa. Los grupos que vas a tocar:

| Grupo | Variables |
|---|---|
| Base de datos | `DATABASE_URL_BI` |
| Sitio y TLS | `SITE_ADDRESS`, `CADDY_ALLOWED_HOSTS`, `HTTP_PORT` (8081), `HTTPS_PORT` (8443; `443` en un servidor público), `CADDY_TLS`, `TRUSTED_PROXIES` |
| Seguridad | `SECURITY_PROFILE` (`private` / `internet`), `COOKIE_SECURE`, `BIZVIEW_SECRET_KEY`, `SUPER_USER_EMAIL`, `SUPER_USER_PASSWORD` |
| Marca | `PRODUCT_NAME`, `ORGANIZATION_NAME`, `LOGO_URL`, `DEFAULT_LOCALE`, `TIMEZONE` |
| IA (opcional, apagada por defecto) | `AI_PROVIDER` (`none` / `anthropic` / `openai`), `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL` (cualquier endpoint compatible con OpenAI, incluidos modelos locales) |
| Correo y compartir | `SMTP_*`, `EMAIL_ALLOWED_DOMAINS`, `SHARE_LINKS_ENABLED` |
| Imágenes | `BIZVIEW_IMAGE_PREFIX`, `BIZVIEW_VERSION` |

## Cómo está hecho

```text
navegador ──HTTPS──▶ Caddy (SPA + /api + certificados) ──▶ backend FastAPI ──▶ PostgreSQL (externa)
                                                                ├──▶ worker (ETL, correo, horarios)
                                                                └──▶ proveedor de IA (opcional)
projects/ (specs, YAML, SQL) ──────────────────────────────▶ backend + worker ──▶ fuentes de datos
```

Python 3.12 / FastAPI / SQLAlchemy / Alembic / ReportLab; React 19 / Vite / Tailwind; Caddy. La
carpeta `cli/` contiene el comando `bizview` y los JSON Schemas y reglas SQL con los que validan
tanto la CLI como el backend. Las specs viven en [`specs/`](specs/) con
[Spec Kit](https://github.com/github/spec-kit); los principios, en
[`.specify/memory/constitution.md`](.specify/memory/constitution.md).

Entorno de desarrollo, pruebas y convenciones: [CONTRIBUTING.md](CONTRIBUTING.md).

## Seguridad

- `SECURITY_PROFILE=internet`: HTTPS en todo, verificación en dos pasos para administradores,
  límite de intentos de inicio de sesión y confirmación con contraseña para cambios sensibles.
- Las credenciales de las fuentes se cifran en reposo (AES-256-GCM) con `BIZVIEW_SECRET_KEY` y son
  de solo escritura: nunca se devuelven, muestran ni registran. Respalda la clave aparte de la base
  de datos.
- Las bases de datos de origen son de solo lectura para Bizview; las conexiones rechazan direcciones
  loopback, link-local y de metadatos de nube.
- La IA está apagada por defecto; al proveedor solo se envían estructura, agregados y metadatos,
  nunca filas, credenciales ni datos personales. Con un modelo local nada sale de tu servidor.

Reporta vulnerabilidades en privado desde la pestaña *Security* de GitHub: [SECURITY.md](SECURITY.md).

## Licencia

[GNU AGPL-3.0-or-later](LICENSE). Si ejecutas una versión modificada para terceros a través de la
red debes ofrecerles el código fuente; la app enlaza al código en cada página (`SOURCE_URL`). La
licencia no otorga derechos sobre el nombre ni el logo "Bizview".
