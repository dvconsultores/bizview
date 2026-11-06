# Proyectos

## Para qué sirve

Un proyecto BI es una carpeta con sus specs, integraciones, reportes y distribuciones. Se escribe
fuera de BizView, con la herramienta que prefieras, y aquí se importa, se descarga y se ve su
estado.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Abre [Abrir Proyectos](app:/proyectos).
2. Pulsa **Importar proyecto** y elige el archivo .zip (se pide confirmar tu contraseña).
   BizView lee lo que trae el zip antes de subirlo y muestra los dos límites: artefactos (los
   archivos del proyecto) e imágenes (las de `assets/`). Si uno se pasa, no lo sube y dice cuál.
3. El proyecto se crea con lo que trajo el zip y se abre su editor. No hay un botón para crear un
   proyecto vacío: un proyecto entra siempre por importación.

## Opciones

- Cada proyecto muestra sus specs y su estado: **Borrador** (nunca aplicado), **Aplicado**,
  **Cambios sin aplicar** o **Retirado**.
- **Descargar** baja el proyecto como .zip.
- **Eliminar proyecto** (solo si no está aplicado) lo lleva a la papelera 30 días.
- Tras actualizar BizView, lo que ya estaba aplicado aparece como el proyecto `principal`.
- El **Identificador** no se puede cambiar después de aplicar el proyecto.
- Escribe en **Buscar proyectos** para filtrar la lista por nombre, identificador o descripción
  (da igual mayúsculas y tildes); el contador dice cuántas coincidencias hay.

## Relacionados

- Importar un proyecto
- Editor de proyecto
- Aplicar un proyecto
- Estructura de un proyecto
