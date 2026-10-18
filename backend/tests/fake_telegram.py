"""Fake Telegram Bot API for tests (feature 007): no network, records what the bot sends."""

from __future__ import annotations

import json

import httpx


class FakeTelegram:
    def __init__(
        self, *, username: str = "BizviewPruebaBot", token: str = "123456:TEST-TOKEN-MARKER"
    ) -> None:
        self.bot_username = username
        self.token = token
        self.mode = "ok"   # ok | unauthorized | conflict | timeout | network
        self.webhook_url = ""
        self.updates: list[dict] = []
        self.sent: list[dict] = []
        self.edited: list[dict] = []
        self.answered: list[dict] = []
        self._update_id = 1000
        self._message_id = 1

    def start(
        self,
        token: str,
        *,
        user_id: int = 7001,
        first_name: str = "Ana",
        last_name: str | None = "Pérez",
        username: str | None = "ana_p",
    ) -> dict:
        update = {
            "update_id": self._update_id,
            "message": {
                "message_id": 1,
                "from": {
                    "id": user_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "username": username,
                },
                "chat": {"id": user_id, "type": "private"},
                "date": 0,
                "text": f"/start {token}",
            },
        }
        self._update_id += 1
        self.updates.append(update)
        return update

    def press(self, data: str, *, user_id: int = 7001, message_id: int = 1) -> dict:
        update = {
            "update_id": self._update_id,
            "callback_query": {
                "id": f"cbq-{self._update_id}",
                "from": {
                    "id": user_id,
                    "first_name": "Ana",
                    "last_name": "Pérez",
                    "username": "ana_p",
                },
                "message": {
                    "message_id": message_id,
                    "chat": {"id": user_id, "type": "private"},
                    "date": 0,
                    "text": "...",
                },
                "data": data,
            },
        }
        self._update_id += 1
        self.updates.append(update)
        return update

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if not path.startswith(f"/bot{self.token}/"):
                return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

            method = path.rsplit("/", 1)[-1]
            payload = json.loads(request.content) if request.content else {}
            if self.mode == "unauthorized":
                return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})
            if self.mode == "timeout":
                raise httpx.ReadTimeout("read timed out", request=request)
            if self.mode == "network":
                raise httpx.ConnectError("connection refused", request=request)
            if self.mode == "conflict" and method == "getUpdates":
                return httpx.Response(409, json={"ok": False, "description": "Conflict"})

            if method == "getMe":
                return httpx.Response(
                    200, json={"ok": True, "result": {"username": self.bot_username}})
            if method == "getWebhookInfo":
                return httpx.Response(200, json={"ok": True, "result": {"url": self.webhook_url}})
            if method == "getUpdates":
                offset = int(payload.get("offset", 0))
                result = [u for u in self.updates if u["update_id"] >= offset]
                return httpx.Response(200, json={"ok": True, "result": result})
            if method == "sendMessage":
                self.sent.append(payload)
                self._message_id += 1
                return httpx.Response(
                    200, json={"ok": True, "result": {"message_id": self._message_id - 1}})
            if method == "editMessageText":
                self.edited.append(payload)
                return httpx.Response(
                    200, json={"ok": True, "result": {"message_id": payload["message_id"]}})
            if method == "answerCallbackQuery":
                self.answered.append(payload)
                return httpx.Response(200, json={"ok": True, "result": True})
            return httpx.Response(404, json={"ok": False, "description": "Not Found"})

        return httpx.MockTransport(handler)
