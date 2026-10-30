# De la fuente a la distribución

## Para qué sirve

Es el recorrido completo para un tablero nuevo con datos de un sistema operativo, desde la fuente
hasta que llega por correo.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Registra y prueba la fuente en [Abrir Fuentes de datos](app:/admin/fuentes).
2. Crea un proyecto en [Abrir Proyectos](app:/proyectos) y abre su chat.
3. Spec de **Fuente**: `/speckit-specify` describiendo la fuente; se cumple cuando la fuente
   existe y su prueba es correcta.
4. Spec de **Integración**: `/speckit-specify` con qué datos cargar y cada cuánto; luego
   `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks` e `/speckit-implement`.
5. Spec de **Reporte**: igual, con las métricas, dimensiones y vistas del tablero.
6. Spec de **Distribución** (opcional): los envíos programados por rol.
7. Cuando el editor diga **Listo para aplicar**, pulsa **Aplicar proyecto**.
8. Revisa la primera carga en [Abrir Integraciones](app:/admin/integraciones) (puedes usar
   **Ejecutar ahora**).
9. Da acceso al tablero en **Acceso a tableros** de cada usuario
   ([Abrir Usuarios](app:/admin/usuarios)).
10. Compártelo con **Compartir** o **Enviar por correo** si hace falta.
