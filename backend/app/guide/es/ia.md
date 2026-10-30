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

Cuando el proveedor falla, el chat y esta pantalla muestran un código corto con el significado y el
texto que devolvió el proveedor. Cada código tiene una sola salida:

- `not_configured` — **La IA no está configurada.** Completa `AI_PROVIDER`, `AI_API_KEY` y
  `AI_MODEL` y reinicia la instalación.
- `no_credit` — **La cuenta del proveedor de IA no tiene saldo.** Recarga la cuenta del proveedor.
  Mientras siga así el agente no llama al proveedor: cada intento se rechaza al instante y no gasta
  tokens. La franja **Bloqueada hasta que se arregle** lo indica en esta pantalla.
- `bad_key` — **La clave de API no es válida o no tiene permiso para este modelo.** Revisa
  `AI_API_KEY` (sin espacios ni comillas de más) y que la clave sea del mismo proveedor que
  `AI_BASE_URL`.
- `model_not_found` — **El modelo configurado no existe o no está disponible.** Compara `AI_MODEL`
  con **Modelos que anuncia el proveedor** más abajo: si el nombre no aparece, corrige
  `AI_MODEL`.
- `rate_limited` — **El proveedor limitó las solicitudes.** Espera y pulsa **Reintentar**: el
  agente respeta la espera que pida el proveedor (hasta 60 s) y reintenta una vez solo.
- `context_too_long` — **La conversación superó el contexto máximo del modelo.** Empieza una sesión
  nueva o resume el brief en menos texto.
- `provider_down` — **El proveedor de IA no responde o devuelve un error del servidor.** Reintenta
  en unos minutos; si sigue igual, revisa la página de estado del proveedor.
- `invalid_tool_call` — **El modelo devolvió una llamada a herramienta mal formada.** Reintenta; si
  se repite con el mismo modelo, cambia `AI_MODEL`.
- `refused` — **El proveedor rechazó la solicitud.** Reformula el mensaje; si insiste, cambia de
  modelo.
- `provider_error` — **El proveedor de IA devolvió un error.** El detalle está en el registro del
  servidor (abajo).

Si el agente se detiene solo, el resumen dice el motivo (`blocked:ai_<código>`): no es un corte de
red, es el proveedor. Un mensaje de «continúa» o «corrige» durante un bloqueo se rechaza igual, sin
llamar al proveedor, hasta que el código se arregle.

**La prueba falló** también aparece si **Configuración incompleta** lista ajustes que faltan. La
prueba hace dos cosas: una respuesta de un token y una llamada a herramienta; **Llamada a
herramienta** dice cuál de las dos falló.

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
