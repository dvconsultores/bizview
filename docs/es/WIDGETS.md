# Tableros en otras webs

## Qué es un widget

Un widget es un permiso permanente para mostrar un tablero, en solo lectura, dentro de una página de
otro sitio. Quien lo visita no necesita cuenta de BizView, el tablero conserva sus filtros y periodos,
y el widget no vence salvo que un administrador ponga una fecha. Es un tablero por widget: insertar
una sola tarjeta no forma parte de esta funcionalidad.

Lo crea un **Administrador** o el **Superusuario** desde la pantalla de compartir del tablero
(**Compartir** → **Insertar en un sitio web**), y solo mientras la instalación tenga a la vez
`EMBED_WIDGETS_ENABLED` y `SHARE_LINKS_ENABLED` y el proyecto del reporte permita compartirlo. Un
tablero admite hasta 50 widgets activos, contados aparte de sus 20 enlaces compartidos.

## Qué pega el desarrollador

El producto muestra el fragmento una sola vez, al crear y al reemplazar (no se guarda en el navegador,
así que un fragmento perdido se reemplaza). Es un pequeño script en línea y un iframe: se pega tal
cual, sin ningún otro cambio en la página. El script solo ajusta la altura —recibe la altura del
contenido del widget y nada más— y acepta ese mensaje solo desde el origen de la propia instalación de
BizView. El iframe pide al navegador al menos el origen de la página anfitriona
(`referrerpolicy="origin"`), porque así sabe qué sitio lo enmarcó: conserva ese atributo y el
`data-bizview-widget`.

```html
<script>(function(){var m="bizview-widget-3",o=new URL("https://bi.example.com/w/KEY").origin;/* ajusta la altura del iframe */})();</script>
<iframe src="https://bi.example.com/w/KEY" title="Ventas" data-bizview-widget="bizview-widget-3" loading="lazy" style="width:100%;min-height:320px;border:0"></iframe>
```

La `KEY` es la dirección completa del widget: identifica al widget y no hace falta nada más. Si la
página tiene Content-Security-Policy, debe permitir `frame-src https://bi.example.com`.

## Qué ve el visitante

El tablero, con el tema, el idioma y los controles que el administrador eligió para ese widget: título,
filtros y periodo, y la descarga del PDF (apagada por defecto). Con los controles de filtro apagados,
editar la dirección del widget no cambia lo que sirve. El widget ocupa el ancho que le dan, crece
hasta la altura de su contenido para que la página anfitriona no muestre barra interna, y sigue
siendo legible a 375 px.

La vista previa dentro del producto (**Probar**) enmarca el mismo documento a ancho de teléfono,
tableta y escritorio, sin ningún sitio externo en la lista y sin contar como visita. Solo la ven los
administradores.

## Seguridad que conviene saber

Los sitios permitidos del widget son lo que aplica el navegador: el documento enmarcado responde
`Content-Security-Policy: frame-ancestors <los sitios de ese widget>` y no lleva `X-Frame-Options`,
mientras que todas las demás rutas de la instalación siguen negándose a ser enmarcadas. Un sitio debe
figurar con el esquema que usa de verdad (`http://localhost:5173` y `https://example.com` son sitios
distintos).

A la página nunca se le entrega la lista. Solo aprende una cosa: si el origen que la enmarcó está
permitido y, si lo está, cuál es ese origen, que es el único destino de su mensaje de altura. Un
widget que sirve a dos clientes no muestra a ninguno el dominio del otro, y el nombre interno que el
administrador le puso tampoco se publica (el `title` del iframe lo lleva en la página anfitriona,
donde el administrador eligió publicarlo). Una imagen, un logo o una imagen en caché no gastan el
techo de peticiones del widget: el techo cuenta las peticiones del reporte, que son las que usan la
base de datos.

La lista no impide que un programa que copia la clave pida los datos por otro medio: nada en un
navegador puede distinguir ese programa de un visitante. Por eso el producto mantiene además un techo
de peticiones por widget (`WIDGET_RATE_LIMIT`, 300 por minuto por defecto), un reemplazo que anula el
fragmento anterior al instante, una revocación que no se puede deshacer y una entrada de auditoría por
cada acción.

Un widget también se puede **eliminar**, en cualquier estado y aunque la inserción esté desactivada
en la instalación: sale de la lista del tablero, uno activo deja de funcionar en ese momento y la
entrada de auditoría (nombre, sitios, estado y visitas, nunca la clave) es el único registro que
queda. Revocar conserva el widget en la lista como historial; eliminar no.

El widget no usa nunca la sesión de quien mira: un administrador con sesión abierta que abre la página
anfitriona ve exactamente lo que ve un visitante anónimo. Cualquiera que pueda ver la página anfitriona
puede ver todo el tablero —los filtros son una comodidad para el visitante, no una restricción—, así
que díselo al cliente antes de activarlo. El documento enmarcado no se indexa ni se guarda en cachés,
y no ofrece ninguna ruta al resto del producto; las páginas legales de la instalación siguen
accesibles.

## Probarlo en local

Añade `http://localhost:5173` (o el puerto que use tu servidor de desarrollo) a los sitios permitidos
del widget, pega el fragmento en una página en blanco servida desde ahí y quita la entrada cuando
termines: una dirección local se muestra con la etiqueta **Desarrollo** para que no se olvide en la
lista.
