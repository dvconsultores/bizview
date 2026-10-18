# Bot contract: Telegram conversation

The worker's `TelegramPoller` handles two update types. Every text is Spanish; `{product}` is
`PRODUCT_NAME` (+ ` · ORGANIZATION_NAME` when set).

## `/start <token>` (message, private chat)

1. Hash the token; find a `pending`, unexpired request. None → reply
   "Este enlace ya no es válido. Vuelve a intentarlo desde {product}." and stop.
2. Bind `telegram_id = message.from.id`, `chat_id`, set `started`.
3. **sign_in**:
   - Telegram id not linked → request `refused/not_linked`; reply
     "Esta cuenta de Telegram no está vinculada a {product}. Ingresa con tu correo y vincúlala
     desde tu perfil."
   - else reply (store `message_id`):
     "Solicitud de ingreso a {product}\nNavegador: {browser} · IP {ip}\nVence a las {HH:MM}.\n
     Elige el código que ves en la pantalla. Si no fuiste tú, toca Cancelar."
     Inline keyboard: three codes (the request's `match_code` + two distinct random 10–99, shuffled)
     `c:<id>:<code>`, and `x:<id>` "Cancelar".
4. **link**: reply "Vincular tu Telegram a {masked email} en {product}. Vence a las {HH:MM}."
   with buttons `ok:<id>` "Confirmar" and `x:<id>` "Cancelar".

## Callback query

- Only if `callback_query.from.id == request.telegram_id` and the request is `started` and
  unexpired; otherwise answer "Esta solicitud ya no es válida." and stop.
- `c:<id>:<code>`: equal to `match_code` → `approved` (user_id = linked user); else
  `refused/wrong_code`. `x:<id>` → `refused/cancelled`. `ok:<id>` (link) → `approved`.
- Always `answerCallbackQuery`, then edit the message to the final state without buttons:
  "✔ Ingreso aprobado. Vuelve a {product}." / "✖ Solicitud cancelada." /
  "✔ Telegram vinculado." / "✖ Código incorrecto: solicitud cancelada."
- Inactive or locked users are refused at the status step (API), so the message can say
  "Aprobado" while the browser shows the refusal reason; the bot never reveals account state.

## Polling

`getUpdates?offset={update_offset}&timeout=25&allowed_updates=["message","callback_query"]`;
after handling each update, `update_offset = update_id + 1` (committed per update). Errors:
401 → stop polling and record `last_check_ok=false, reason=invalid_credential`; 409 → reason
`webhook_conflict`; network errors → retry with backoff (1 s → 60 s). Other chats (groups) and
other commands get no reply.
