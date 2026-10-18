"""Scripted provider for tests and the e2e suite (feature 014).

Never contacts a network. Selectable as AI_PROVIDER=fake only when BIZVIEW_TEST_HOOKS=1 (never in
images).
"""
import dataclasses
import json
import math
import os
import threading
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from app.ai import AIReply, ChatMessage, ChatReply, ChatUsage, ToolSpec

Step = ChatReply | Callable[[list[ChatMessage], tuple[ToolSpec, ...], str | None], ChatReply]
DEFAULT_TEXT = "Respuesta de prueba."


def enabled() -> bool:
    return os.environ.get("BIZVIEW_TEST_HOOKS") == "1"


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4)) if text else 0


class FakeProvider:
    name = "fake"
    model = "fake"

    def __init__(self, script: Iterable[Step] = ()):
        self._script: deque[Step] = deque(script)
        self.requests: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def queue(self, *steps: Step) -> None:
        with self._lock:
            self._script.extend(steps)

    def reset(self) -> None:
        with self._lock:
            self._script.clear()
            self.requests.clear()

    def payloads(self) -> list[str]:
        """Every request "sent", serialised: SC-002 audits search these strings."""
        return [json.dumps(r, ensure_ascii=False, sort_keys=True) for r in self.requests]

    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 1024,
                 effort: str | None = None) -> AIReply:
        request = {"kind": "complete", "system": system, "prompt": prompt,
                   "max_tokens": max_tokens}
        with self._lock:
            self.requests.append(request)
            step = self._script.popleft() if self._script else None
        if step is None:
            return AIReply("OK", self.model)
        if isinstance(step, ChatReply):
            return AIReply(step.text, step.model or self.model)
        reply = step([ChatMessage("user", prompt)], (), system)
        return AIReply(reply.text, reply.model or self.model)

    def chat(self, messages: Sequence[ChatMessage], *,
             tools: Sequence[ToolSpec] = (), system: str | None = None,
             max_tokens: int = 4096, context: str | None = None) -> ChatReply:
        request: dict[str, Any] = {
            "kind": "chat",
            "system": system,
            "messages": [
                {**dataclasses.asdict(m),
                 "images": [(i.media_type, len(i.data)) for i in m.images]}
                for m in messages
            ],
            "tools": [dataclasses.asdict(t) for t in tools],
            "max_tokens": max_tokens,
            "context": context,
        }
        with self._lock:
            self.requests.append(request)
            step = self._script.popleft() if self._script else None
        if step is None:
            reply = ChatReply(DEFAULT_TEXT, (), ChatUsage(), self.model)
        elif isinstance(step, ChatReply):
            reply = step
        else:
            reply = step(list(messages), tuple(tools), system)
        if reply.usage.total == 0:  # deterministic usage, so token budgets are testable
            calls = json.dumps([dataclasses.asdict(c) for c in reply.tool_calls],
                               ensure_ascii=False)
            reply = dataclasses.replace(reply, usage=ChatUsage(
                input=estimate_tokens(json.dumps(request, ensure_ascii=False, sort_keys=True)),
                output=estimate_tokens(reply.text + (reply.reasoning or "") + calls)))
        if reply.tool_calls and reply.stop_reason == "end":
            reply = dataclasses.replace(reply, stop_reason="tool_use")
        if not reply.model:
            reply = dataclasses.replace(reply, model=self.model)
        return reply


SHARED = FakeProvider()  # the instance returned by get_provider; the e2e test hooks script it
