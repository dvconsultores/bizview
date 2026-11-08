# MySQL, SQL Server, SQLite, BigQuery y Google Sheets

## Para qué sirve

Además de PostgreSQL, un REST y un SOAP, BizView lee cinco tipos más de fuente. Todos se registran
igual —**Nueva fuente**, **Probar conexión**, **Guardar**— y todos son de solo lectura: la fuente es
del sistema que la usa, BizView nunca escribe en ella.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Abre [Abrir Fuentes de datos](app:/admin/fuentes) y pulsa **Nueva fuente**.
2. Elige el tipo y escribe el **Nombre**.
3. Completa la conexión y pulsa **Probar conexión**: verás **Conexión correcta** o el motivo del
   error. Si la cuenta puede escribir, la tarjeta lo avisa con un aviso.
4. Pulsa **Guardar** y después mira la pestaña **Estructura**.

## Opciones


| Tipo | Credencial de solo lectura | Nota |
|---|---|---|
| MySQL / MariaDB | un usuario con `GRANT SELECT` | el puerto es 3306 |
| SQL Server | un inicio de sesión con `db_datareader` | el puerto es 1433; no admite Azure AD |
| SQLite | ninguno: es un archivo | solo aparecen los archivos de la carpeta de la instalación |
| Google BigQuery | una cuenta de servicio con BigQuery Data Viewer y Job User | se le pega el JSON; hay un tope de bytes por consulta |
| Google Sheets | una cuenta de servicio, con la hoja compartida con su correo | cada pestaña es una tabla |



- Conexiones simultáneas: cuántas conexiones puede abrir BizView a la vez en esa fuente.
- **Estructura**: muestra las tablas, las columnas y sus tipos; se guarda en un paquete que la IA
  de fuera lee para escribir la integración.
- En Sheets, cada pestaña es una tabla y la primera fila son los encabezados.
- En BigQuery, la consulta se ejecuta primero en seco: si leería más bytes que el tope, no se
  ejecuta y el run dice cuánto habría leído.

## Problemas frecuentes

- **No disponible en esta instalación**: falta el controlador de ese tipo o la carpeta de archivos.
  Lo resuelve quien administra el servidor.
- **La fuente no admite más conexiones ahora**: el origen está lleno; la carga queda en ámbar y se
  reintenta. Baja las conexiones simultáneas de la fuente o mueve la hora de la carga.
- Comparte la hoja con este correo: el mensaje trae la dirección exacta de la cuenta de
  servicio; comparte la hoja con permiso de lectura.
