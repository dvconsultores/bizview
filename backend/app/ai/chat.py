"""The structure chat of one source (feature 052, FR-004/FR-005, US2).

What it is: a question about a source's *structure*, answered from the structure pack only. What it
is not: a data path. The chat receives no connector, runs no query, writes no file and exposes no
tool — the provider is called with `complete()`, like the connection test.

Three guards stand between a question and the provider:

1. **The budget.** A per-user, per-source, per-UTC-day token cap (`AI_STRUCTURE_CHAT_DAILY_TOKENS`).
2. **The refusal.** A data or action request is refused by product code *before* the call, so a
   prompt change can never reopen the hole SC-005 measures.
3. **The names.** Every object an answer mentions is checked against the pack; the ones that are not
   there come back in `unknown` and the interface chips them.
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import AIError, AIReply, get_provider, state
from app.config import Settings
from app.errors import ApiError
from app.i18n import M, t
from app.models import AppUser, DataSource, SourceChatMessage

log = logging.getLogger("app.ai")

PROMPT_FILE = Path(__file__).parent / "prompts" / "source_structure.md"
#: Characters of structure sent to the provider: ~15 k tokens, under every model's window.
MAX_CONTEXT_CHARS = 60_000
MAX_ANSWER_TOKENS = 900
HISTORY_TURNS = 10
RETENTION_DAYS = 30

#: A data request: the person wants rows, numbers or an action, not a description.
_DATA = re.compile(
    r"(\bfilas\b|\bregistros\b|\brows\b|\brecords\b|\bselect\s+[\w*]+\s+from\b|"
    r"\b(dame|damel[oa]s|mu[eé]strame|ens[eé][ñn]ame|show me|give me|list me)\b|"
    r"\bcu[aá]nto[s]?\s+(vend|factur|ingres|gast|compr)|"
    r"how much (did|have) (we|you|they)\s+(sell|sold|bill|spend))", re.I)
_WRITE = re.compile(
    r"\b(ejecut\w*|corre|correr|insert\w*|update|actualiz\w*\s+(el|los|la|las)\s+datos|"
    r"borr\w*|elimin\w*|drop|truncate|delete|remove|create\s+table|alter\s+table|run)\b", re.I)


def system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


def refusal(question: str) -> bool:
    """Whether the question asks for data or for an action rather than for the structure."""
    text = question or ""
    return bool(_DATA.search(text) or _WRITE.search(text))


def _index(structure: dict) -> dict:
    """Names and sizes only: what a question can be matched against when the pack does not fit."""
    if structure.get("kind") == "postgresql":
        schemas: dict[str, list] = {}
        for table in structure.get("tables") or []:
            schemas.setdefault(str(table.get("schema")), []).append(
                {"name": table.get("name"), "columns": len(table.get("columns") or [])})
        return {"kind": "postgresql", "schemas": schemas}
    if structure.get("kind") in ("rest", "supabase"):
        shape = structure.get("shape")
        return {"kind": structure.get("kind"),
                "samples": [{"name": s.get("name"), "path": s.get("path"),
                             "records": s.get("records")} for s in structure.get("samples") or []],
                "path": structure.get("path"),
                "keys": list(shape) if isinstance(shape, dict) else []}
    return {"kind": structure.get("kind"),
            "services": [s.get("name") for s in structure.get("services") or []]}


def _named(structure: dict, question: str) -> dict | None:
    """The one table the question names, with its columns — the internal "fetch" of R7."""
    text = (question or "").lower()
    if structure.get("kind") != "postgresql":
        return None
    for table in structure.get("tables") or []:
        name = str(table.get("name") or "")
        if name and re.search(rf"\b{re.escape(name.lower())}\b", text):
            return table
    return None


def context(pack: dict, question: str) -> str:
    """The structure as the provider sees it: all of it, or an index plus what is named."""
    import json

    structure = pack.get("structure") or {}
    body = json.dumps(structure, ensure_ascii=False, sort_keys=False)
    notes = str((pack.get("pack") or {}).get("notes") or "").strip()
    header = f"Fuente «{pack['pack']['source']}» ({pack['pack']['kind']})"
    if notes:
        header += f". Observaciones del superusuario: {notes}"
    if len(body) <= MAX_CONTEXT_CHARS:
        return f"{header}\n\n{body}"
    named = _named(structure, question)
    kept = {"index": _index(structure), "detalle": named,
            "nota": "La estructura completa no cabe: se envía el índice y el detalle de lo que la "
                    "pregunta nombra. Si hace falta otra tabla, dilo."}
    return f"{header}\n\n{json.dumps(kept, ensure_ascii=False)}"


def _known_names(pack: dict) -> set[str]:
    """Every object name the pack knows, lowercased, plus `schema.table` pairs."""
    names: set[str] = set()

    def add(value) -> None:
        text = str(value or "").strip().lower()
        if text:
            names.add(text)

    for table in (pack.get("structure") or {}).get("tables") or []:
        add(table.get("name"))
        add(table.get("schema"))
        add(f"{table.get('schema')}.{table.get('name')}")
        for column in table.get("columns") or []:
            add(column.get("name"))
    structure = pack.get("structure") or {}
    for sample in structure.get("samples") or []:
        add(sample.get("name"))
        for column in (sample.get("fields") or {}):
            add(column)
            add(str((sample.get("fields") or {}).get(column)).lstrip("$."))
    shape = structure.get("shape")
    if isinstance(shape, dict):
        names.update(str(k).lower() for k in shape)
    for service in structure.get("services") or []:
        add(service.get("name"))
        for port in service.get("ports") or []:
            for operation in port.get("operations") or []:
                add(operation.get("name"))
    return names


_BACKTICK = re.compile(r"`([^`\n]{1,80})`")
#: A file the answer talks about is not an object of the source.
_FILE = re.compile(r"\.(md|json|ya?ml|sql|csv|txt|zip)$", re.I)
_OBJECTISH = re.compile(
    r"\b([A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+|[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*)\b")


def unknown_names(answer: str, pack: dict) -> list[dict]:
    """Objects the answer mentions that the pack does not know (SC-003), in appearance order."""
    known = _known_names(pack)
    found: list[dict] = []
    seen: set[str] = set()
    candidates = [(m.group(1), "backtick") for m in _BACKTICK.finditer(answer or "")]
    candidates += [(m.group(1), "bare") for m in _OBJECTISH.finditer(answer or "")]
    for token, _kind in candidates:
        if _FILE.search(token.strip()):
            continue
        for part in _split(token):
            key = part.lower()
            if key in known or key in seen:
                continue
            seen.add(key)
            found.append({"name": part, "kind": _object_kind(part, pack)})
    return found


def _split(token: str) -> list[str]:
    """`$.data.total_count` and `orders.customer_email` are several names, not one."""
    cleaned = token.strip().strip("`").lstrip("$.").rstrip(":")
    parts = [p for p in re.split(r"[.\s()\[\]{}]+", cleaned) if p]
    return parts or ([cleaned] if cleaned else [])


def _object_kind(name: str, pack: dict) -> str:
    structure = pack.get("structure") or {}
    for table in structure.get("tables") or []:
        if str(table.get("name")).lower() == name.lower():
            return "table"
        for column in table.get("columns") or []:
            if str(column.get("name")).lower() == name.lower():
                return "column"
    return "unknown"


def spent_today(db: Session, source: DataSource, user: AppUser, day: date | None = None) -> int:
    """Tokens this user spent on this source since 00:00 UTC today.

    The window is an explicit UTC range, not `date(created_at)`: the database's own timezone must
    not decide when somebody's day starts."""
    start = datetime.combine(day or datetime.now(UTC).date(), time.min, tzinfo=UTC)
    total = db.scalar(
        select(func.coalesce(func.sum(SourceChatMessage.tokens_in + SourceChatMessage.tokens_out),
                             0))
        .where(SourceChatMessage.source_id == source.id,
               SourceChatMessage.user_id == user.id,
               SourceChatMessage.created_at >= start,
               SourceChatMessage.created_at < start + timedelta(days=1)))
    return int(total or 0)


def turns(db: Session, source: DataSource, user: AppUser, limit: int = HISTORY_TURNS) -> list[dict]:
    # `id` breaks the tie: several turns can share the transaction timestamp, and a history whose
    # order is arbitrary would hand the provider a shuffled conversation.
    rows = db.scalars(select(SourceChatMessage)
                      .where(SourceChatMessage.source_id == source.id,
                             SourceChatMessage.user_id == user.id)
                      .order_by(SourceChatMessage.created_at.desc(), SourceChatMessage.id.desc())
                      .limit(limit)).all()
    return [{"role": row.role, "text": row.body, "at": row.created_at} for row in reversed(rows)]


def clear(db: Session, source: DataSource, user: AppUser) -> int:
    rows = db.scalars(select(SourceChatMessage)
                      .where(SourceChatMessage.source_id == source.id,
                             SourceChatMessage.user_id == user.id)).all()
    for row in rows:
        db.delete(row)
    return len(rows)


def _estimate(text: str) -> int:
    return max(1, len(text) // 4)


def history_prompt(db: Session, source: DataSource, user: AppUser, question: str) -> str:
    past = turns(db, source, user, limit=HISTORY_TURNS * 2)
    lines = [f"{'Pregunta' if turn['role'] == 'question' else 'Respuesta'}: {turn['text']}"
             for turn in past if turn["text"]]
    body = "\n\n".join(lines)
    head = f"Conversación anterior:\n{body}\n\n" if body else ""
    return head + f"Pregunta: {question}"


def ask(db: Session, *, source: DataSource, user: AppUser, question: str,
        pack_factory, settings: Settings) -> dict:
    """One question, one answer — or a refusal, or the typed error of the contract.

    `pack_factory` is called only when the provider is actually going to be asked: a refusal and a
    spent budget must not cost a structure read."""
    cap = settings.ai_structure_chat_daily_tokens
    spent = spent_today(db, source, user)
    usage = {"cap": cap, "spent_today": spent}
    if refusal(question):
        return {"answer": t("sourceChat.refused"), "refused": True, "unknown": [],
                "model": None, "usage": usage, "tokens_in": 0, "tokens_out": 0,
                "created_at": datetime.now(UTC)}
    if not settings.ai_enabled:
        raise ApiError(409, "ai_not_configured", M("sourceChat.not_configured"),
                       extra={"ai": {"action": "admin_ai"}})
    if cap <= 0:
        raise ApiError(429, "ai_chat_cap", M("sourceChat.cap_off"),
                       extra={"ai": {"cap": cap, "spent_today": spent}})
    if spent >= cap:
        raise ApiError(429, "ai_chat_cap", M("sourceChat.cap", cap=cap),
                       extra={"ai": {"cap": cap, "spent_today": spent}})
    pack = pack_factory()
    system = f"{system_prompt()}\n\n## Estructura de la fuente\n\n{context(pack, question)}"
    prompt = history_prompt(db, source, user, question)
    try:
        reply: AIReply = get_provider(settings).complete(
            prompt, system=system, max_tokens=MAX_ANSWER_TOKENS)
    except AIError as e:
        log.warning("structure chat failed: %s (%s)", e.code, e.detail or "-")
        state.record_error(e.code, e.detail, settings.ai_model_effective)
        raise ApiError(502, f"ai_{e.code}", M(f"ai.error.{e.code}"),
                       extra={"ai": {"code": e.code, "action": e.action,
                                     "detail": e.detail}}) from None
    state.record_ok(reply.model)

    tokens_in = reply.tokens_in or _estimate(system) + _estimate(prompt)
    tokens_out = reply.tokens_out or _estimate(reply.text)
    keep = settings.ai_structure_chat_store_questions
    db.add(SourceChatMessage(source_id=source.id, user_id=user.id, role="question",
                             body=question[:2000] if keep else None, tokens_in=tokens_in))
    db.add(SourceChatMessage(source_id=source.id, user_id=user.id, role="answer",
                             body=reply.text[:8000] if keep else None, tokens_out=tokens_out))
    usage = {"cap": cap, "spent_today": spent + tokens_in + tokens_out}
    return {"answer": reply.text, "refused": False, "unknown": unknown_names(reply.text, pack),
            "model": reply.model, "usage": usage, "tokens_in": tokens_in,
            "tokens_out": tokens_out, "created_at": datetime.now(UTC)}


def purge_older_than(db: Session, days: int = RETENTION_DAYS) -> int:
    from sqlalchemy import delete

    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = db.execute(delete(SourceChatMessage).where(SourceChatMessage.created_at < cutoff))
    return result.rowcount or 0
