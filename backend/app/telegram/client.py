"""Telegram Bot API client (feature 007). The token lives only inside the client: errors are
redacted and never chain the httpx exception (its request URL contains the token)."""

from __future__ import annotations

from typing import Any

import httpx

from app.ai import redact
from app.security.netguard import Policy, guarded_client

API = "https://api.telegram.org"
CODES = ("invalid_credential", "webhook_conflict", "timeout", "unreachable", "telegram_error")
Button = tuple[str, str]


class TelegramError(Exception):
    """Raised for any Telegram API failure with a machine-readable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        assert code in CODES, f"unknown TelegramError code: {code}"
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


class BotClient:
    """Thin synchronous wrapper around the Telegram Bot API."""

    def __init__(
        self,
        token: str,
        *,
        timeout: float = 35.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._token = token
        if transport is not None:
            self._client = httpx.Client(
                transport=transport,
                base_url=f"{API}/bot{token}/",
                timeout=timeout,
            )
        else:
            # Public-API policy: refuse private IPs to defend against DNS tampering.
            self._client = guarded_client(
                policy=Policy(allow_private=False),
                timeout=timeout,
                base_url=f"{API}/bot{token}/",
            )

    def _call(
        self,
        method: str,
        payload: dict | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        try:
            response = self._client.post(
                method, json=payload or {},
                timeout=timeout if timeout is not None else httpx.USE_CLIENT_DEFAULT,
            )
        except httpx.TimeoutException:
            raise TelegramError("timeout") from None
        except httpx.TransportError as exc:
            raise TelegramError("unreachable", redact(str(exc), self._token)) from None

        if response.status_code in (401, 404):
            raise TelegramError("invalid_credential")
        if response.status_code == 409:
            raise TelegramError("webhook_conflict")

        try:
            body = response.json()
        except ValueError:
            raise TelegramError("telegram_error", f"HTTP {response.status_code}") from None
        if response.status_code < 200 or response.status_code >= 300 or not body.get("ok"):
            description = str(body.get("description", f"HTTP {response.status_code}"))
            raise TelegramError("telegram_error", redact(description, self._token))
        return body["result"]

    def get_me(self) -> dict:
        return self._call("getMe")

    def get_webhook_info(self) -> dict:
        return self._call("getWebhookInfo")

    def get_updates(self, offset: int, timeout: int = 25) -> list[dict]:
        # Add 10s slack for Telegram's long-polling timeout.
        return self._call(
            "getUpdates",
            {
                "offset": offset,
                "timeout": timeout,
                "allowed_updates": ["message", "callback_query"],
            },
            timeout=timeout + 10,
        )

    def send_message(
        self, chat_id: int, text: str, buttons: list[list[Button]] | None = None
    ) -> dict:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if buttons:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": label, "callback_data": data} for label, data in row]
                    for row in buttons
                ]
            }
        return self._call("sendMessage", payload)

    def edit_message(self, chat_id: int, message_id: int, text: str) -> None:
        try:
            self._call(
                "editMessageText",
                {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                    # Remove inline buttons after a choice is made.
                    "reply_markup": {"inline_keyboard": []},
                },
            )
        except TelegramError as exc:
            if exc.code == "telegram_error" and "message is not modified" in exc.detail:
                return  # Idempotent edit: no visual change.
            raise

    def answer_callback(self, callback_query_id: str, text: str | None = None) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text is not None:
            payload["text"] = text
        self._call("answerCallbackQuery", payload)

    def close(self) -> None:
        self._client.close()
