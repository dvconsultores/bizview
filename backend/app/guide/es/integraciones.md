# Integraciones

## Para qué sirve

Muestra las cargas de datos de la versión activa: cuándo corren, si terminaron bien y permite
pausarlas, ejecutarlas a mano o cambiar su frecuencia.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Abre [Abrir Integraciones](app:/admin/integraciones).
2. Cada integración muestra su estado (**Activa**, **Pausada** o **Ejecutando**), la
   **Próxima ejecución** y la **Última carga correcta**.
3. Acciones: **Pausar** / **Reanudar**, **Ejecutar ahora** (carga incremental), **Carga completa**
   (recarga todo) y **Detener** una ejecución en curso.
4. **Cambiar frecuencia** abre el formulario: elige **Cada 15 minutos**, **Cada 30 minutos**,
   **Cada hora**, **Diaria** o **Personalizada** con una **Expresión cron** (como máximo una vez
   cada 5 minutos). Opcional: un **Horario permitido** para empezar y una **Recarga completa**
   periódica.
5. **Usar la programación del spec** vuelve a la frecuencia que dice la spec.

## Opciones

- **Historial** lista las ejecuciones: **Programada**, **Manual** o **Manual completa**, con su
  resultado (**Correcta**, **Falló**, **Omitida** o **En curso**) y la ruta usada: **COPY**,
  **COPY + Polars**, **filas** o **filas + Polars**.

## Problemas frecuentes

- **Fuente deshabilitada**: la integración no corre hasta que su fuente vuelva a estar
  **Habilitada**.
- «No hay integraciones activas»: aplica un proyecto o un espacio de trabajo con specs de
  integración.
