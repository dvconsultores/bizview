# Generar estructura con IA

## Para qué sirve

Lee una fuente, entiende lo que contiene y guarda el paquete de estructura: las tablas o
endpoints con sus campos, tipos, claves, fecha de carga, relaciones, datos personales y notas sobre
qué es una fila. Ese paquete es lo que le entregas a la IA que construye el tablero fuera de
BizView. No escribes nada: pulsas un botón.

## Quién puede usarlo

Solo el **Superusuario**, y necesita un proveedor de IA configurado en Administración → IA.

## Cómo se hace

1. Abre la fuente y entra en la pestaña **Estructura** (ver Estructura de una fuente).
2. Revisa **Peticiones de muestra**: son los endpoints que la generación va a leer.
3. Pulsa **Generar estructura con IA** y espera: la línea de progreso dice en qué paso va (escaneo,
   IA, verificación).
4. Lee el resultado: cada tabla con su «qué es una fila», su clave, su fecha y sus campos; abajo, las
   relaciones, las métricas sugeridas y lo que la verificación descartó (**Descartado por la
   verificación**).
5. Pulsa **Descargar estructura (.md)** o la de JSON para llevarte el paquete.

## Opciones

- **Actualizar** vuelve a leer la fuente sin IA; lo generado se queda guardado hasta que generes otra
  vez.
- **Qué cambió** aparece tras una generación y nombra las tablas y campos que entraron o salieron
  respecto del paquete anterior.
- **Descartado por la verificación** lista lo que el modelo mencionó y la fuente no tiene: no está en
  el paquete y no debe usarse en un spec.
- **Descargar el escaneo (.md)** da la lectura cruda de la fuente, sin IA.
- **Cancelar** deja de esperar; si la corrida termina igualmente, el paquete queda guardado.

## Problemas frecuentes

- El botón está desactivado: falta el proveedor de IA o la corrida tiene el tope en cero
  (Administración → IA).
- «La respuesta del modelo no formó un paquete válido»: vuelve a intentarlo; el escaneo sigue
  disponible y no se perdió el paquete anterior.
- Una fuente SOAP no genera: su estructura es la operación del WSDL, no hay campos que inferir.

## Relacionados

- Estructura de una fuente
- Inteligencia artificial
- Peticiones de muestra
