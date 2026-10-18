# Usuarios

## Para qué sirve

Crea las cuentas de las personas, decide qué tableros ve cada una y restablece contraseñas.

## Quién puede usarlo

Un **Administrador** gestiona las cuentas de **Usuario**. Solo el **Superusuario** gestiona a
los administradores.

## Cómo se hace

1. Abre [Abrir Usuarios](app:/admin/usuarios). Busca con **Buscar por nombre o correo** o
   filtra por **Rol** y **Estado**.
2. Para crear una cuenta, pulsa **Nuevo usuario**
   ([Abrir Nuevo usuario](app:/admin/usuarios/nuevo)): escribe nombre, correo y rol, pulsa
   **Generar** para la **Contraseña temporal** y luego **Crear usuario**. Entrega la contraseña
   temporal a la persona: se muestra una sola vez y deberá cambiarla al ingresar.
3. Abre un usuario para ver sus **Datos** y su **Acceso a tableros**: marca los tableros que
   puede ver y guarda.

## Opciones

- **Desactivar usuario**: ya no puede ingresar y sus sesiones abiertas se cierran.
  **Reactivar usuario** lo devuelve.
- **Restablecer contraseña**: cierra sus sesiones y le da una contraseña temporal.
- **Restablecer doble factor**: la persona configura de nuevo la verificación en dos pasos.
- **Quitar vínculo de Telegram**: ya no podrá ingresar con Telegram hasta vincularlo otra vez.

## Problemas frecuentes

- «No puedes modificar a este usuario.»: es un **Administrador** o el **Superusuario**; solo el
  **Superusuario** los cambia.
- Tus propios datos se cambian desde tu perfil, no aquí.
