# Espacio de trabajo

## Para qué sirve

El espacio de trabajo es el conjunto de proyectos aplicados: define las integraciones y los
reportes que corren. Cada aplicación crea una versión nueva y siempre puedes volver a la anterior.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Abre [Abrir Espacio de trabajo](app:/admin/espacio) (ya no tiene tarjeta en Administración: se
   entra por esta dirección).
2. Si la instalación tiene una **Carpeta montada** (un repositorio Git), pulsa **Validar** y, si
   el resultado es **Válido**, **Aplicar** (se pide confirmar tu contraseña). Los proyectos de la
   aplicación se aplican desde su propia página (ver Aplicar un proyecto).
3. **Versión activa** muestra qué corre ahora y **Versión anterior**, la previa.
4. Antes de aplicar ves los cambios: **Nuevos**, **Modificados** y **Retirados**.

## Opciones

- **Volver a la versión anterior** restaura la versión previa en segundos; la actual queda
  archivada.
- **Especificaciones** guarda los documentos de cada versión, agrupados por proyecto: abre una
  spec y cambia entre **Especificación**, **Plan** y **Tareas**.
- **Reportes** indica el modo de cada reporte: **Dataset** o **Directo**.

## Problemas frecuentes

- Un error de validación nombra el archivo y cómo corregirlo; corrígelo en el repositorio o en el
  proyecto y vuelve a validar.
