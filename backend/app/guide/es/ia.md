# Inteligencia artificial

## Para qué sirve

Muestra si la IA está activa, con qué proveedor y modelo, y permite probar la conexión. La IA del
producto solo sirve para la ayuda: no escribe specs, ni consultas, ni reportes.

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

La ayuda no envía tus datos: solo el índice de temas y la página que abres. Los paquetes de
estructura que le das a una IA externa llevan estructura, conteos y formas: nunca credenciales,
hosts ni valores de filas.

## Problemas frecuentes

Cuando el proveedor falla, la ayuda y esta pantalla muestran un código corto con el significado y
el texto que devolvió el proveedor. Cada código tiene una sola salida:

- `not_configured` — **La IA no está configurada.** Completa `AI_PROVIDER`, `AI_API_KEY` y
  `AI_MODEL` y reinicia la instalación.
- `no_credit` — **La cuenta del proveedor de IA no tiene saldo.** Recarga la cuenta del proveedor.
  Mientras siga así no se llama al proveedor: cada intento se rechaza al instante. La franja **Bloqueada hasta que se arregle** lo indica en esta pantalla.
- `bad_key` — **La clave de API no es válida o no tiene permiso para este modelo.** Revisa
  `AI_API_KEY` (sin espacios ni comillas de más) y que la clave sea del mismo proveedor que
  `AI_BASE_URL`.
- `model_not_found` — **El modelo configurado no existe o no está disponible.** Compara `AI_MODEL`
  con **Modelos que anuncia el proveedor** más abajo: si el nombre no aparece, corrige
  `AI_MODEL`.
- `rate_limited` — **El proveedor limitó las solicitudes.** Espera y pulsa **Reintentar**: el
  espera la que pida el proveedor (hasta 60 s) y reintenta una vez sola.
- `context_too_long` — **La conversación superó el contexto máximo del modelo.** Abre un tema más
  corto o pide la página en otro momento.
- `provider_down` — **El proveedor de IA no responde o devuelve un error del servidor.** Reintenta
  en unos minutos; si sigue igual, revisa la página de estado del proveedor.
- `invalid_tool_call` — **El modelo devolvió una llamada a herramienta mal formada.** Reintenta; si se
  repite con el mismo modelo, cambia `AI_MODEL`.
- `refused` — **El proveedor rechazó la solicitud.** Reformula el mensaje; si insiste, cambia de
  modelo.
- `provider_error` — **El proveedor de IA devolvió un error.** El detalle está en el registro del
  servidor (abajo).

El código queda en `Administración → IA` y en `GET /api/health` (`healthy`, `blocking_code`), así
que un bloqueo se ve también desde fuera de la aplicación, y la ayuda lo reporta al lector.

**La prueba falló** también aparece si **Configuración incompleta** lista ajustes que faltan.

### Dónde está el detalle

**Detalles técnicos**, debajo de cada error y de la prueba, muestra cuándo ocurrió, el modelo y una
referencia para buscarla. El texto completo está en el registro del backend, no en el del proxy
(Caddy):

```sh
docker logs --tail 200 bizview-backend | grep -i "AI"
```

### Arreglos que no necesitan la IA

Si el problema es del proyecto y no del proveedor (falta un `joins`, falta `date`, un tipo de vista
desconocido), el panel **Problemas** ofrece **Aplicar arreglo** en ese aviso, y en la cabecera el
botón para aplicar todos los arreglos de una vez. Funciona en cualquier modo, incluso con la IA
caída: no llama al proveedor, edita el borrador, vuelve a validar y deja el cambio en la auditoría.
