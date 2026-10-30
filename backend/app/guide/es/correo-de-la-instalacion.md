# Correo de la instalación

## Para qué sirve

Explica cómo se configura el correo que usan los envíos y los enlaces compartidos.

## Quién puede usarlo

Solo el **Superusuario** (o quien administra el servidor): el correo se configura en el archivo
de ajustes de la instalación, no en pantallas.

## Cómo se hace

1. En el archivo `.env` de la instalación define `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`
   (`starttls`, `ssl` o `none`), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` y, opcional,
   `SMTP_FROM_NAME`.
2. Para permitir correos externos, lista sus dominios en `EMAIL_ALLOWED_DOMAINS` (separados por
   comas).
3. Para permitir enlaces compartidos, pon `SHARE_LINKS_ENABLED=true`. Los enlaces usan la
   dirección pública de la instalación (`SITE_ADDRESS`).
4. Reinicia la instalación y prueba el envío con el comando `mail-test` del servidor.

## Problemas frecuentes

- Sin correo configurado, **Enviar por correo** y **Envíos programados** muestran que el envío
  por correo no está disponible; el resto de la aplicación funciona igual.
