"""One place that turns a conversation into provider messages (feature 036).

Nothing else may build a provider payload: the same rows are replayed on every turn, and a single
mismatched pair makes the provider answer `400` for the rest of the conversation's life (the report
that opened this feature: `tool_use_id call_00_g9JN… found in tool_result blocks` — the tool's own
note had been written between the `tool_use` and its result).

The rules this module keeps, and why:

R1  **A result belongs to its `tool_use`, by call id — never by adjacency.** Any row written between
    an assistant turn and its results (a tool's note, the run-contract line, a preview outcome) is
    emitted after the exchange instead of splitting it.
R2  **Results travel in the single user turn right after their assistant turn.** A result with no
    owner is dropped (it cannot be replayed); a `tool_use` with no result becomes a short text note
    in its assistant turn, so the context is not lost silently.
R3  **The window cuts at a user-text boundary**, so an exchange is never half inside it. Older
    exchanges keep their blocks (their ids are present) but travel with the stored one-line summary
    instead of the whole data block, which is what keeps a long run affordable.
R4  **Roles alternate, ids are unique, no message is empty** — checked by
    `app.ai.history_rules.validate_messages` before every call.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from app.ai import ChatMessage, ToolCall
from app.ai.history_rules import HistoryInvalid, validate_messages

log = logging.getLogger("app.assistant.history")

HISTORY_WINDOW = 30       # rows replayed: the loop's own HISTORY_LIMIT default


@dataclass
class StoredMessage:
    """One stored row, in the only shape the builder needs."""
    id: int
    role: str
    content: str = ""
    tool_name: str | None = None
    call_id: str | None = None                    # tool rows: the call it answers
    calls: tuple[ToolCall, ...] = ()              # assistant rows: what it asked for
    owner_id: int | None = None                   # tool rows: assistant_message_id
    orphan: bool = False
    reasoning: str | None = None
    data: str = ""                                # tool rows: the data block, for the newest turn


@dataclass
class Built:
    """What to send, and what had to be left out to be able to send it."""
    messages: list[ChatMessage] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)      # "tool:<id>:<call id>"
    noted: list[str] = field(default_factory=list)        # tool_use ids turned into a note
    repaired: bool = False

    @property
    def clean(self) -> bool:
        return not self.dropped and not self.noted and not self.repaired


def from_rows(rows: Sequence[Any]) -> list[StoredMessage]:
    """`AssistantMessage` ORM rows → stored messages (no query, no side effects)."""
    out: list[StoredMessage] = []
    for row in rows:
        payload = getattr(row, "tool_payload", None) or {}
        calls: tuple[ToolCall, ...] = ()
        if row.role == "assistant" and payload.get("calls"):
            calls = tuple(
                ToolCall(**{key: value for key, value in call.items()
                            if key in {"id", "name", "args", "args_error"}})
                for call in payload["calls"]
            )
        out.append(StoredMessage(
            id=row.id,
            role=row.role,
            content=row.content or "",
            data=_wrapped(row, payload) if row.role == "tool" else "",
            tool_name=getattr(row, "tool_name", None),
            call_id=payload.get("call_id") or getattr(row, "call_id", None),
            calls=calls,
            owner_id=getattr(row, "assistant_message_id", None),
            orphan=bool(getattr(row, "orphan", False)),
        ))
    return out


def from_chat(messages: Sequence[ChatMessage]) -> list[StoredMessage]:
    """The turn's in-memory history → the same shape, so one builder serves both paths."""
    return [
        StoredMessage(
            id=index,
            role=message.role,
            content=message.content or "",
            data=message.content or "",
            call_id=message.tool_call_id,
            calls=tuple(message.tool_calls),
            reasoning=message.reasoning,
        )
        for index, message in enumerate(messages)
    ]


def load(db, session_id: int, window: int = HISTORY_WINDOW) -> list[StoredMessage]:
    """The replayed rows of a conversation: the newest window, oldest first."""
    from sqlalchemy import select

    from app.models import AssistantMessage

    rows = list(
        db.scalars(
            select(AssistantMessage)
            .where(AssistantMessage.session_id == session_id)
            .order_by(AssistantMessage.id.desc())
            .limit(window)
        )
    )
    rows.reverse()
    return from_rows(rows)


def window_start(rows: Sequence[StoredMessage], window: int | None = None) -> int:
    """Index where the replayed window begins: a user message with text, never inside an exchange.

    The oldest user message *inside* the window is preferred, so the window keeps its size; when the
    window holds no user message at all (one very long turn) it widens back to the previous one —
    a payload cannot start with a result whose `tool_use` was cut.
    """
    size = len(rows)
    if window is None or size <= window:
        return 0
    cut = size - window
    for index in range(cut, size):
        if rows[index].role == "user" and rows[index].content.strip():
            return index
    for index in range(cut - 1, -1, -1):
        if rows[index].role == "user" and rows[index].content.strip():
            return index
    return 0


def compact_args(name: str, args: dict) -> dict:
    if name == "propose_draft":
        files = args.get("files")
        return {
            "files": sorted(files) if isinstance(files, dict) else files,
            "summary": args.get("summary"),
        }
    if name == "edit_draft":
        ops = args.get("ops")
        return {
            "ops": [
                {"op": o.get("op"), "path": o.get("path")}
                for o in ops
                if isinstance(o, dict)
            ]
            if isinstance(ops, list)
            else [],
            "summary": args.get("summary"),
        }
    return dict(args)


def build(rows: Sequence[StoredMessage], *, window: int | None = None,
          repair: bool = False, summaries: dict[str, str] | None = None) -> Built:
    """Rows → provider-ready messages. `repair=True` also drops what the rules forbid.

    `summaries` (call id → one line) is what an older exchange keeps when it is replayed from the
    turn's own history, which carries the data block but not the stored summary.
    """
    summaries = summaries or {}
    kept = list(rows)
    kept = kept[window_start(kept, window):]
    kept = _trim_leading(kept)

    built = Built()
    if not kept:
        return built

    owner_of: dict[str, StoredMessage] = {}
    for row in kept:
        for call in row.calls:
            owner_of.setdefault(call.id, row)
    by_id = {row.id: row for row in kept}

    results: dict[int, list[StoredMessage]] = {}
    for row in kept:
        if row.role != "tool":
            continue
        owner = by_id.get(row.owner_id) if row.owner_id is not None else None
        if owner is not None and (not row.call_id
                                  or not any(call.id == row.call_id for call in owner.calls)):
            owner = None          # the stored pointer disagrees with the stored turn
        if owner is None and row.call_id:
            owner = owner_of.get(row.call_id)
        if row.orphan or owner is None or not row.call_id:
            built.dropped.append(f"tool:{row.id}:{row.call_id or '-'}")
            continue
        results.setdefault(owner.id, []).append(row)

    newest = max((row.id for row in kept if row.calls), default=None)
    out: list[ChatMessage] = []
    emitted: set[str] = set()               # ids may not repeat in one conversation (R4)
    for row in kept:
        if row.role == "user":
            if not row.content.strip():
                continue
            out.append(ChatMessage(role="user", content=row.content))
        elif row.role == "assistant":
            calls: list[ToolCall] = []
            notes: list[str] = []
            answered = {result.call_id for result in results.get(row.id, [])}
            for call in row.calls:
                if row.id != newest:
                    # An older exchange keeps its ids but not its payload: the arguments of a
                    # draft are worth one line, not a whole file tree (015 FR-012/013).
                    call = dataclasses.replace(call, args=compact_args(call.name, call.args))
                if call.id in emitted:
                    # Same id asked twice: the provider sees one block, so one of them must go.
                    built.dropped.append(f"duplicate:{call.id}")
                    notes.append(_no_result(call.name))
                    built.noted.append(call.id)
                    continue
                if call.id in answered:
                    calls.append(call)
                    emitted.add(call.id)
                else:
                    notes.append(_no_result(call.name))
                    built.noted.append(call.id)
            content = "\n\n".join(part for part in [row.content, *notes] if part.strip())
            if not content.strip() and not calls:
                continue
            out.append(ChatMessage(role="assistant", content=content, tool_calls=tuple(calls),
                                   reasoning=row.reasoning))
            for result in results.get(row.id, []):
                # The newest exchange carries the data the model is working with; older ones
                # carry their stored one-line summary (the same rows, nothing re-fetched).
                if row.id == newest:
                    text = result.data or result.content
                else:
                    text = (summaries.get(result.call_id or "") or result.content
                            or result.data)
                out.append(ChatMessage(role="tool", content=text or result.data,
                                       tool_call_id=result.call_id))
        # a tool row is emitted with its owner; anything left over was dropped above

    built.messages = _merge(out)
    if repair:
        built.messages, extra = _repair(built.messages)
        built.repaired = bool(extra)
    return built


def for_provider(rows: Sequence[StoredMessage], provider: str, *,
                 window: int | None = None,
                 session_id: int | None = None,
                 summaries: dict[str, str] | None = None,
                 repair: bool = True) -> Built:
    """Build, validate, and repair once. Raises `HistoryInvalid` when it still cannot be sent."""
    built = build(rows, window=window, summaries=summaries)
    problems = validate_messages(built.messages, provider)
    if not problems:
        _log_if_dirty(built, session_id)
        return built
    log.warning("assistant history unusable (session %s, %s): %s",
                session_id if session_id is not None else "-", provider, "; ".join(problems))
    if not repair:
        raise HistoryInvalid(problems)
    built = build(rows, window=window, repair=True, summaries=summaries)
    problems = validate_messages(built.messages, provider)
    if problems:
        raise HistoryInvalid(problems)
    _log_if_dirty(built, session_id)
    return built


def _log_if_dirty(built: Built, session_id: int | None) -> None:
    """A drop is a repair nobody asked for: say it, with ids only (never content, 035 rule)."""
    if built.clean:
        return
    log.warning(
        "assistant history rebuilt (session %s): dropped=%s noted=%s repaired=%s",
        session_id if session_id is not None else "-",
        ",".join(built.dropped) or "-", ",".join(built.noted) or "-", built.repaired,
    )


def _wrapped(row: Any, payload: dict) -> str:
    """The tool result as the model reads it: the untrusted-data block of feature 021."""
    from app.assistant.commands import scope

    result = payload.get("result", {})
    return scope.wrap_data(f"herramienta:{getattr(row, 'tool_name', None) or ''}",
                           json.dumps(result, ensure_ascii=False))


def _no_result(tool_name: str) -> str:
    from app.i18n import t

    return t("assistant.history.no_result", name=tool_name or "-")


def _trim_leading(rows: list[StoredMessage]) -> list[StoredMessage]:
    """A payload starts with the user: anything before the first user message cannot be sent."""
    for index, row in enumerate(rows):
        if row.role == "user":
            return rows[index:]
    return []


def _merge(messages: list[ChatMessage]) -> list[ChatMessage]:
    """One turn per role: two `user` or two `assistant` messages in a row are invalid."""
    merged: list[ChatMessage] = []
    for message in messages:
        if not merged or merged[-1].role != message.role or message.role == "tool":
            merged.append(message)
            continue
        previous = merged[-1]
        if message.role == "user":
            text = "\n\n".join(part for part in (previous.content, message.content)
                               if part.strip())
            merged[-1] = ChatMessage(role="user", content=text,
                                     images=previous.images or message.images)
        else:
            calls = {call.id: call for call in (*previous.tool_calls, *message.tool_calls)}
            text = "\n\n".join(part for part in (previous.content, message.content)
                               if part.strip())
            merged[-1] = ChatMessage(role="assistant", content=text,
                                     tool_calls=tuple(calls.values()),
                                     reasoning=previous.reasoning or message.reasoning)
    return merged


def _repair(messages: list[ChatMessage]) -> tuple[list[ChatMessage], list[str]]:
    """Drop what cannot be sent and say what: orphan results, repeated ids, empty turns."""
    extra: list[str] = []
    out: list[ChatMessage] = []
    seen: set[str] = set()
    for message in messages:
        if message.role == "tool":
            previous = out[-1] if out else None
            owner_ids = {call.id for call in previous.tool_calls} if previous else set()
            if previous is None or message.tool_call_id not in owner_ids:
                extra.append(f"tool:{message.tool_call_id or '-'}")
                continue
            out.append(message)
            continue
        if message.role == "assistant" and message.tool_calls:
            calls = []
            for call in message.tool_calls:
                if call.id in seen:
                    extra.append(f"repeated:{call.id}")
                    continue
                seen.add(call.id)
                calls.append(call)
            if not calls and not message.content.strip():
                extra.append("empty:assistant")
                continue
            out.append(dataclasses.replace(message, tool_calls=tuple(calls)))
            continue
        if not message.content.strip() and not message.images:
            extra.append(f"empty:{message.role}")
            continue
        out.append(message)
    return _merge(out), extra


# --------------------------------------------------------------------------- compaction

# Kept verbatim at the tail of one turn: the exchanges the model is still working on, bounded by
# both a message count and a size (four results of 60 KB would otherwise fill the window alone).
COMPACT_KEEP = 8
COMPACT_TAIL_CHARS = 60_000
COMPACT_TEXT_CHARS = 400


def _message_chars(message: ChatMessage) -> int:
    total = len(message.content or "")
    for call in message.tool_calls or ():
        total += len(json.dumps(call.args or {}, ensure_ascii=False, default=str))
    return total


def estimate_chars(messages: Sequence[ChatMessage]) -> int:
    """Rough size of a payload in characters (about tokens x 4), tool args included."""
    return sum(_message_chars(message) for message in messages)


def compress(messages: Sequence[ChatMessage], summaries: dict[str, str] | None = None,
             *, keep: int = COMPACT_KEEP, tail_chars: int = COMPACT_TAIL_CHARS,
             text_chars: int = COMPACT_TEXT_CHARS) -> tuple[list[ChatMessage], int]:
    """Compact one turn's history without dropping a message: only what it *carries* shrinks.

    Like the compaction of other coding agents, the last exchanges stay verbatim and the older ones
    keep their meaning: a tool result keeps its stored one-line summary, an assistant turn keeps its
    first line, and a call keeps its identity (name, `op`/`path`) instead of the file contents it
    wrote. Nothing is reordered or removed, so the `tool_use`/`tool_result` pairing that 036
    validates still holds and the model keeps the thread of the turn.

    Returns the compacted list and the characters saved (0 when there was nothing to do).
    """
    summaries = summaries or {}
    before = estimate_chars(messages)
    cut = len(messages)
    kept = 0
    total = 0
    while cut > 0 and kept < keep:
        size = _message_chars(messages[cut - 1])
        if total + size > tail_chars and kept > 0:
            break
        total += size
        kept += 1
        cut -= 1
    while cut > 0 and messages[cut].role == "tool":
        cut -= 1                       # never start the verbatim tail with an orphan result
    if cut <= 0:
        return list(messages), 0
    out: list[ChatMessage] = []
    for index, message in enumerate(messages):
        if index >= cut:
            out.append(message)
            continue
        text = (message.content or "").strip()
        content = text.splitlines()[0][:text_chars] if text else ""
        if message.role == "tool":
            content = summaries.get(message.tool_call_id or "") or _no_result("")
        calls = tuple(replace(call, args=compact_args(call.name, call.args))
                      for call in message.tool_calls or ())
        out.append(replace(message, content=content, tool_calls=calls))
    return out, max(0, before - estimate_chars(out))
