# Seguridad

## Para qué sirve

Muestra el perfil de seguridad de la instalación, qué controles están activos y qué requiere
atención.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Abre [Abrir Seguridad](app:/admin/seguridad).
2. Arriba ves el perfil: **Perfil privado** (red privada: se permite HTTP y el doble factor es
   opcional) o **Perfil internet** (HTTPS obligatorio en todo y doble factor para
   administradores). Puede ser **automático** o **configurado**.
3. Revisa la lista de controles: cada uno dice **Correcto** o **Requiere atención**.

## Opciones

- El perfil se cambia en el archivo de ajustes de la instalación (`SECURITY_PROFILE`) y requiere
  reiniciar.
- **Lecturas directas (24 h)** cuenta las consultas de reportes directos por fuente.
- La tarjeta **Ingreso con Telegram** configura el bot de Telegram.
- Si aparece un aviso sobre `DATABASE_URL_ORIGIN`, esa variable ya no se usa: elimínala del
  archivo de ajustes tras revisar la fuente importada.

## Problemas frecuentes

- Un control en **Requiere atención** explica qué falta; corrígelo en la instalación. BizView no
  ofrece formas de desactivar la confirmación de contraseña ni el doble factor obligatorio.
