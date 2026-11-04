# Ingreso con Google

## Para qué sirve

Entrar con la cuenta de Google de la organización, sin otra contraseña, y dejar que la instalación
decida con qué rol y con qué tableros se entra.

## Quién puede usarlo

Cualquier persona cuyo correo de Google pertenezca a un dominio permitido. La política se configura
con el rol **Superusuario**, en Administración → Seguridad → **Ingreso con Google**.

## Cómo se hace

1. Abre [Abrir la página de ingreso](app:/ingresar).
2. Pulsa **Continuar con Google** y elige tu cuenta.
3. Si es tu primera vez y la instalación tiene el alta automática activa, BizView crea tu usuario
   con el rol y el acceso que fijó la política. Si ya tenías cuenta, entras con ella.
4. Si tu cuenta tiene verificación en dos pasos, escribe el código de 6 dígitos.

## Opciones

- **Dominios permitidos**: los dominios que pueden entrar. Mientras no guardes la lista, es la que
  trae la instalación (GOOGLE_ALLOWED_DOMAINS); el primer guardado la convierte en configuración.
- **Alta automática**: con el interruptor activo, una cuenta desconocida de un dominio permitido se
  crea al ingresar. Elige el rol por defecto —nunca **Superusuario**— y el acceso por defecto:
  ninguno, todos los tableros públicos o una lista de tableros.
- **Reglas de rol**: se evalúan de arriba abajo y gana la primera que coincida. Cada regla mira el
  dominio o una lista de correos, y decide el rol y el acceso. La condición por grupo llegará cuando
  la instalación tenga una cuenta de servicio de Workspace.
- **Vincular por correo**: un usuario que ya existe se reconoce por su correo y conserva su rol. Una
  regla solo lo cambia si activas «aplicar reglas también a usuarios existentes», y cada cambio
  queda en la auditoría.
- El botón y estos ajustes solo existen cuando la instalación tiene el ingreso con Google activo.

## Problemas frecuentes

- «No se pudo iniciar sesión con Google. Inténtalo de nuevo.»: el mensaje es siempre el mismo. El
  motivo real —dominio no permitido, cuenta sin usuario, cuenta desactivada— queda en
  [Consultar la auditoría](app:/admin/auditoria).
- No aparece el botón: la instalación no tiene el ingreso con Google configurado.
- Cambiar el rol de una cuenta creada automáticamente: hazlo en **Usuarios**. Los siguientes
  ingresos conservan lo que fijó el administrador, salvo que las reglas se apliquen también a
  usuarios existentes.
- Desvincular una cuenta de Google: un **Administrador** desactiva el usuario o le asigna una
  contraseña; desde ese momento entra con correo y contraseña.
