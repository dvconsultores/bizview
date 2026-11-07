# Enviar por correo

## Para qué sirve

Envía un tablero por correo con su PDF y, si quieres, un enlace para verlo en línea.

## Quién puede usarlo

Cualquier persona con acceso al tablero, cuando la instalación tiene el correo configurado.
**Incluir enlace** es solo para administradores.

## Cómo se hace

1. Abre el tablero y pulsa **Enviar por correo**.
2. En **Destinatarios** elige usuarios de la instalación y **Listas de correo**; el contador dice
   cuántas personas alcanza el envío.
3. Para direcciones sueltas escribe un **Correo externo** y pulsa **Agregar**, o pega varias en
   **Pegar lista** separadas por coma, punto y coma, espacio o salto de línea. También se acepta el
   formato `Nombre <correo>`.
4. Escribe el **Asunto** (si lo dejas vacío se usa el nombre del tablero) y un
   **Mensaje (opcional)**.
5. Marca **Adjuntar PDF del período y filtros actuales**.
6. Administradores: marca **Incluir enlace** y elige los **Días de vigencia del enlace**.
7. Si quieres reutilizar las direcciones escritas, escribe un nombre en
   **Guardar estos destinatarios como lista**.
8. Pulsa **Enviar**.

## Opciones

- **Envíos** muestra el estado de cada envío: **En cola**, **Enviando**, **Enviado**,
  **Enviado en parte** o **Falló**, con el estado de cada destinatario.
- **Reenviar los fallidos** vuelve a enviar solo las direcciones que fallaron, con el mismo asunto,
  mensaje y adjuntos.
- Una dirección no válida se muestra en rojo y detiene el envío: corrígela o quítala.
- No hay tope de destinatarios ni de envíos por hora: el correo sale por lotes, al ritmo que
  permita el proveedor de la instalación. El PDF no puede pasar de 10 MB.
- Si la instalación tiene el correo en pausa, el envío queda **En cola** y sale al reanudarse.
- Si la instalación restringe las direcciones sueltas a los administradores, un usuario normal
  sigue enviando a usuarios y a listas.

## Problemas frecuentes

- «El envío por correo no está disponible en esta instalación.»: el **Superusuario** debe
  configurar el correo.
- «Solo se permiten estos dominios»: la instalación limita las direcciones externas; usa una
  dirección de esos dominios o una lista con miembros permitidos.

## Relacionados

- Listas de correo
- Compartir con un enlace
- Exportar a PDF o CSV
- Envíos programados
