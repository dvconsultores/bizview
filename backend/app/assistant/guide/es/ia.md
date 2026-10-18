# Inteligencia artificial

## Para qué sirve

Muestra si la IA está activa, con qué proveedor y modelo, y permite probar la conexión.

## Quién puede usarlo

Solo el **Superusuario**. La IA es opcional.

## Cómo se hace

1. Abre [Abrir Inteligencia artificial](app:/admin/ia).
2. Revisa el **Estado** (**Activada**, **Desactivada** o **Configuración incompleta**), el
   **Proveedor**, el **Modelo**, la **Clave de API** (**Configurada** o **No configurada**) y el
   **Tiempo máximo**.
3. Pulsa **Probar conexión**. Verás **Conexión correcta** con el tiempo de respuesta o
   **La prueba falló** con el motivo.

## Opciones

**Cómo activarla**: la IA se configura en el archivo de ajustes de la instalación y requiere
reiniciar:

- Claude: `AI_PROVIDER=anthropic` y `AI_API_KEY`.
- Modelo local (los datos no salen de tu red): `AI_PROVIDER=openai_compatible`, `AI_BASE_URL` y
  `AI_MODEL`.

Solo se envían cifras agregadas; nunca registros detallados, contraseñas ni datos personales.

## Problemas frecuentes

- **La prueba falló**: revisa la clave, la dirección del modelo local o el tiempo máximo.
- **Configuración incompleta**: la pantalla lista los ajustes que faltan.
