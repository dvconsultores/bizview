# Instalación y ajustes

## Para qué sirve

Resume cómo se configura una instalación de BizView, cómo se actualiza y qué hay que respaldar.

## Quién puede usarlo

Solo el **Superusuario** o quien administra el servidor.

## Cómo se hace

Los ajustes viven en el archivo `.env` de la carpeta de la instalación; después de cambiarlos,
reinicia la instalación. Por área:

- Marca: `ORGANIZATION_NAME` y `LOGO_URL`.
- Seguridad: `SECURITY_PROFILE` (`auto`, `private` o `internet`).
- IA: `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL` y `AI_BASE_URL`. No hay presupuesto de tokens: el
  asistente no se detiene por tokens.
- Idioma y hora: `DEFAULT_LOCALE` (`es` o `en`) y `TIMEZONE`.
- Proyectos: `PROJECTS_DIR` y `PROJECT_MAX_MB`.
- Reportes directos y ETL: `DIRECT_REPORTS_BI` y `TRANSFORM_MAX_ROWS`.
- Correo: ver Correo de la instalación.

## Opciones

- Actualizar: cambia `BIZVIEW_VERSION` en `.env` y vuelve a levantar la instalación.
- Respaldos: la base de datos, la carpeta `projects/` y la clave de cifrado; sin la clave, las
  credenciales guardadas no se pueden leer.
- Comandos del servidor: `rotate-secret-key` (rota la clave de cifrado) y `reset-superuser-mfa`
  (restablece el doble factor del **Superusuario**).
