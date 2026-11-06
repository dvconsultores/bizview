# Apariencia

## Para qué sirve

Administra los temas de la instalación: los cinco que trae el producto, los que subas tú y los que
llegaron con un proyecto. Un tema decide los colores de todos los reportes que no declaren el suyo:
cifras, series de los gráficos, píldoras de variación y el PDF.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Abre [Abrir Apariencia](app:/admin/apariencia).
2. La biblioteca muestra cada tema en claro y en oscuro. El que está **en uso** lleva el anillo y no
   se puede volver a aplicar.
3. **Usar en la instalación** deja ese tema como el de todos los reportes que no declaren otro.
4. **Subir tema** abre el diálogo: pega el YAML del tema o elige el archivo. Se valida antes de
   guardarlo y, si algo falla, verás cada problema con su ruta.

## Opciones

- **Del producto**: Impacto, Clásico, Monocromo, Contraste alto y Daltónico. No se pueden reemplazar
  ni eliminar; **Duplicar** abre una copia para editarla.
- **Subido**: lo que subiste tú. Se puede reemplazar (con confirmación) o eliminar.
- **De un proyecto**: llegó con un proyecto importado; se va con él.
- **Descargar** devuelve el archivo tal como se subió.
- **Eliminar** se rechaza mientras un reporte use el tema: el mensaje nombra los reportes.

## Problemas frecuentes

- «Ya existe un tema con el id»: el identificador está tomado. Confirma el reemplazo o cambia el
  `id` del archivo.
- «El tema no se puede usar»: cada línea dice el token y la medida, por ejemplo
  `light.text vs light.surface: 3.9:1 (needs 4.5:1)`. Aclara u oscurece ese color.
- El color principal de la marca sigue mandando en los botones y enlaces; las series de los gráficos
  vienen siempre del tema.
- Un reporte puede declarar su propio tema en su definición (`layout.theme.id`); ese valor gana
  sobre el de la instalación.

## Relacionados

- Administración
- Definir un reporte
- Escribir un tema
