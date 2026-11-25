# Insertar un tablero en una web

## Para qué sirve

Da a un desarrollador un fragmento que muestra un tablero, de solo lectura, dentro de una página de
otro sitio web. Quien visita esa página no necesita cuenta de BizView y no ve el resto del producto.
El widget no vence salvo que le pongas una fecha.

## Quién puede usarlo

Lo crea un **Administrador** o el **Superusuario**, cuando la instalación tiene los widgets activos
(lo que además exige los enlaces compartidos) y el proyecto del reporte permite compartirlo.

## Cómo se hace

1. Abre el tablero y pulsa **Compartir** → **Insertar en un sitio web**.
2. Escribe un **Nombre del widget**: es para reconocerlo en la lista.
3. En **Sitios permitidos** escribe uno por línea, con su esquema: `https://www.cliente.com`. Sin
   rutas, sin parámetros y sin comodines. Un widget admite hasta diez.
   El nombre y los sitios son obligatorios: si falta uno, el aviso aparece en ese mismo campo y el
   formulario no envía nada hasta que lo completes.
4. Opcional: el tema, el idioma, si se ven el título, los filtros y el PDF, y una fecha de
   vencimiento. El PDF está apagado por defecto.
5. Pulsa **Crear widget** y copia el fragmento: no se vuelve a mostrar y no se guarda en el navegador.
   Pégalo en la página tal cual; no hace falta escribir nada más, y conviene no quitarle el
   `referrerpolicy="origin"` del iframe: es lo que dice a BizView desde qué sitio se muestra.
6. Pulsa **Probar** para verlo dentro de BizView, a ancho de teléfono, tableta y escritorio.

## Opciones

- **Probar** abre el widget en un marco, sin el menú ni el encabezado del producto, y no cuenta como
  visita. Un administrador que tenga sesión abierta ve lo mismo que un visitante sin cuenta. El
  fragmento aparece en esa página solo si acabas de crear o reemplazar el widget en la misma sesión:
  no se guarda en el navegador.
- **Editar** cambia el nombre, los sitios, el tema, el idioma, los controles y la fecha; el fragmento
  sigue valiendo.
- **Reemplazar fragmento** crea una clave nueva: el fragmento anterior deja de funcionar y el nombre,
  los sitios y las visitas se conservan.
- **Revocar** apaga el widget para siempre; una página que lo tenga muestra un mensaje neutro. Cada
  tablero admite 50 widgets activos, contados aparte de los enlaces compartidos.
- **Eliminar** quita el widget de la lista, esté activo, revocado o vencido, y también cuando la
  inserción está desactivada en la instalación (así se puede limpiar). Si estaba activo deja de
  funcionar en ese momento. No se puede deshacer y solo queda su entrada en la auditoría.
- Un sitio que empiece por `http://localhost` o por una dirección privada se marca como **Desarrollo**
  para que no se olvide en la lista.
- Un icono de candado o la ausencia del tablero en la página del cliente casi siempre significa que el
  sitio no está en la lista con el esquema que realmente usa.

## Problemas frecuentes

- **Insertar en un sitio web** no aparece, o se niega con un motivo: la instalación tiene la
  inserción desactivada, o los enlaces compartidos, o el proyecto no permite compartir este reporte.
- **Sitios permitidos**: si la página del cliente no muestra el tablero, revisa el esquema, el dominio
  y el puerto exactos, que el widget no esté revocado ni vencido y que el tablero siga disponible.
- Si dice que hay demasiadas peticiones, el widget alcanzó su límite por minuto: espera unos segundos.
  El límite lo fija la instalación.
- Si perdiste el fragmento, reemplázalo: solo se muestra al crear y al reemplazar.

## Relacionados

- Compartir con un enlace
- Tableros y reportes
- Distribuciones
