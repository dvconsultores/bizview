"""The shape a provider payload must have, and the check that proves it (feature 036).

A conversation is replayed on every turn, so one structurally wrong pair poisons it for good: the
provider answers `400` and the reader sees the same error whatever they type. The rules below are
what both providers require; `validate_messages` checks the neutral history the loop builds and
`check_payload` checks the exact body each converter produced, right before it is sent.

Anthropic Messages API
  * `messages[0]` is `user`; roles alternate, `user` turn by `user` turn.
  * every `tool_result` block answers a `tool_use` of the **previous** message, and all results of
    one assistant turn travel in that single user turn, as its **first** blocks.
  * `tool_use` ids are unique in the conversation; no message is empty.

OpenAI-compatible `/chat/completions`
  * every `{"role": "tool"}` message answers the `tool_calls` of the assistant message right
    before it (`tool_call_id` present in that message's `tool_calls`).
  * assistant `tool_calls` ids are unique; no message is empty.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class HistoryInvalid(Exception):
    """The built conversation cannot be sent: it would be rejected before the model reads it.

    `problems` names the offending index and the call ids, never the message content.
    """

    def __init__(self, problems: Sequence[str]):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems) or "invalid history")


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def validate_messages(messages: Sequence[Any], provider: str = "anthropic") -> list[str]:
    """Problems of a neutral history (`ChatMessage` list); empty means it can be sent."""
    problems: list[str] = []
    if not messages:
        return ["historial vacío"]
    if messages[0].role != "user":
        problems.append(f"[0] la conversación debe empezar por user, no por {messages[0].role}")
    seen: dict[str, int] = {}
    index = 0
    while index < len(messages):
        message = messages[index]
        if message.role == "tool":
            problems.append(f"[{index}] resultado sin turno de asistente que lo pidiera "
                            f"({message.tool_call_id or '-'})")
            index += 1
            continue
        if message.role == "user":
            if index and messages[index - 1].role == "user":
                problems.append(f"[{index}] dos mensajes user seguidos")
            if not _text(message.content).strip() and not message.images:
                problems.append(f"[{index}] mensaje user vacío")
            index += 1
            continue
        calls = [call.id for call in message.tool_calls]
        for call_id in calls:
            if call_id in seen:
                problems.append(f"[{index}] id de herramienta repetido: {call_id} "
                                f"(ya en [{seen[call_id]}])")
            seen[call_id] = index
        if not _text(message.content).strip() and not calls:
            problems.append(f"[{index}] mensaje assistant vacío")
        index += 1
        results = []
        while index < len(messages) and messages[index].role == "tool":
            results.append(messages[index])
            index += 1
        if results and not calls:
            problems.extend(
                f"[{index - len(results) + offset}] resultado {result.tool_call_id or '-'} tras "
                "un turno sin tool_use"
                for offset, result in enumerate(results)
            )
            continue
        answered = [result.tool_call_id for result in results]
        for call_id in calls:
            if call_id not in answered:
                problems.append(f"la herramienta {call_id} no tiene resultado")
        for call_id in answered:
            if call_id not in calls:
                problems.append(f"el resultado {call_id or '-'} no lo pidió este turno")
        for result in results:
            if not _text(result.content).strip():
                problems.append(f"el resultado {result.tool_call_id or '-'} está vacío")
    return problems


def check_payload(payload: Sequence[dict], provider: str) -> list[str]:
    """Problems of the converted body; the providers call it right before sending."""
    if provider == "openai_compatible":
        return _check_openai(payload)
    return _check_anthropic(payload)


def _check_anthropic(payload: Sequence[dict]) -> list[str]:
    problems: list[str] = []
    if not payload:
        return ["payload vacío"]
    if payload[0].get("role") != "user":
        problems.append(f"[0] el primer mensaje debe ser user, no {payload[0].get('role')}")
    use_ids: dict[str, int] = {}
    for index, message in enumerate(payload):
        role = message.get("role")
        blocks = message.get("content")
        if not isinstance(blocks, list) or not blocks:
            problems.append(f"[{index}] mensaje sin bloques")
            continue
        if index and role == payload[index - 1].get("role"):
            problems.append(f"[{index}] dos mensajes {role} seguidos")
        uses = {block.get("id") for block in blocks if block.get("type") == "tool_use"}
        results = [block for block in blocks if block.get("type") == "tool_result"]
        for block in blocks:
            if block.get("type") == "tool_use":
                call_id = block.get("id")
                if call_id in use_ids:
                    problems.append(f"[{index}] id de herramienta repetido: {call_id}")
                use_ids[call_id] = index
        if results:
            if role != "user":
                problems.append(f"[{index}] tool_result en un mensaje {role}")
            if blocks[0].get("type") != "tool_result":
                problems.append(f"[{index}] tool_result no es el primer bloque")
            if index == 0:
                problems.append(f"[{index}] tool_result sin turno anterior")
                continue
            previous = payload[index - 1]
            previous_uses = {b.get("id") for b in (previous.get("content") or [])
                             if isinstance(b, dict) and b.get("type") == "tool_use"}
            if previous.get("role") != "assistant" or not previous_uses:
                problems.append(f"[{index}] tool_result tras un mensaje sin tool_use")
                continue
            for block in results:
                call_id = block.get("tool_use_id")
                if call_id not in previous_uses:
                    problems.append(f"[{index}] tool_result {call_id} no lo pidió el mensaje "
                                    "anterior")
            if uses:
                problems.append(f"[{index}] tool_use y tool_result en el mismo mensaje")
    return problems


def _check_openai(payload: Sequence[dict]) -> list[str]:
    problems: list[str] = []
    if not payload:
        return ["payload vacío"]
    seen: dict[str, int] = {}
    for index, message in enumerate(payload):
        role = message.get("role")
        if role == "tool":
            # Several results may answer one assistant turn: walk back to the turn that asked.
            owner = index - 1
            while owner >= 0 and payload[owner].get("role") == "tool":
                owner -= 1
            if owner < 0:
                problems.append(f"[{index}] tool sin mensaje anterior")
                continue
            previous = payload[owner]
            previous_ids = {call.get("id") for call in (previous.get("tool_calls") or [])
                            if isinstance(call, dict)}
            if not previous_ids:
                problems.append(f"[{index}] tool tras un mensaje sin tool_calls")
            elif message.get("tool_call_id") not in previous_ids:
                problems.append(f"[{index}] tool {message.get('tool_call_id')} no está en los "
                                "tool_calls anteriores")
            continue
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            call_id = call.get("id")
            if call_id in seen:
                problems.append(f"[{index}] id de herramienta repetido: {call_id}")
            seen[call_id] = index
        empty = message.get("content") in (None, "") and not message.get("tool_calls")
        if empty and role != "system":
            problems.append(f"[{index}] mensaje {role} vacío")
    return problems


def assert_valid(payload: Sequence[dict], provider: str) -> None:
    problems = check_payload(payload, provider)
    if problems:
        raise HistoryInvalid(problems)
