"""Command runs (feature 021, plan §6): one /speckit-… command executed in a conversation.

Lifecycle helpers (create, finish, end-of-turn mapping, files, tokens, resume) and the
deterministic preflight (prerequisites and confirmation gates, no provider call).
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.assistant.commands.registry import DOCS, CommandDef
from app.errors import ApiError
from app.i18n import M, t
from app.models import AssistantCommandRun
from app.projects.history import sha

RUNS_IN_SESSION = 20
ACTIVE = ("running", "waiting")
PREREQ_COMMAND = {"spec": "speckit-specify", "plan": "speckit-plan", "tasks": "speckit-tasks"}

_YES = re.compile(r"^\s*(s[ií]|yes|y|ok|vale|dale|contin[uú]a|continuar|continue|proceed)\b",
                  re.I)
_NO = re.compile(r"^\s*(no|n|cancela|cancelar|cancel|stop)\b", re.I)
# The third answer to the checklist gate (feature 030 follow-up, owner 2026-10-24): "fix them"
# instead of "proceed anyway" or "cancel".
_FIX = re.compile(r"^\s*(arregl\w*|corrig\w*|complet\w*|marc\w*|rellen\w*|resuelv\w*"
                  r"|fix\w*|complete\w*|tick\w*|check them|mark them)\b")
_STATUS = re.compile(r"^(\s*\*\*Status\*\*:[ \t]*)(.*)$", re.M)
_CHECK = re.compile(r"^\s*[-*] \[( |x|X)\]", re.M)
_TITLE = re.compile(r"^# .*$", re.M)


def _now() -> datetime:
    return datetime.now(UTC)


def active(db, session_id: int) -> AssistantCommandRun | None:
    """The conversation's running or waiting run."""
    return db.scalar(select(AssistantCommandRun)
                     .where(AssistantCommandRun.session_id == session_id,
                            AssistantCommandRun.status.in_(ACTIVE))
                     .order_by(AssistantCommandRun.id.desc()).limit(1))


def recent(db, session_id: int, limit: int = RUNS_IN_SESSION) -> list[AssistantCommandRun]:
    """The conversation's latest runs, newest first."""
    return list(db.scalars(select(AssistantCommandRun)
                           .where(AssistantCommandRun.session_id == session_id)
                           .order_by(AssistantCommandRun.id.desc()).limit(limit)))


def latest_for(db, session_id: int, command: str,
               spec: str | None) -> AssistantCommandRun | None:
    """Newest run of `command` on `spec` in the conversation."""
    query = select(AssistantCommandRun).where(AssistantCommandRun.session_id == session_id,
                                              AssistantCommandRun.command == command)
    query = query.where(AssistantCommandRun.spec.is_(None) if spec is None
                        else AssistantCommandRun.spec == spec)
    return db.scalar(query.order_by(AssistantCommandRun.id.desc()).limit(1))


def create(db, *, session_id: int, project_id: int, definition: CommandDef, arguments: str,
           locale: str, message_id: int | None = None, spec: str | None = None,
           resolved_from: str | None = None, forced: bool = False,
           reserved_number: int | None = None, status: str = "running",
           pending: dict | None = None, resumed_from: int | None = None,
           result: dict | None = None) -> AssistantCommandRun:
    """Insert a run; a second active run in the conversation is refused (409 command_active)."""
    run = AssistantCommandRun(
        session_id=session_id, project_id=project_id, message_id=message_id,
        command=definition.name, arguments=arguments, spec=spec,
        resolved_from=resolved_from, forced=forced,
        reserved_number=reserved_number, locale=locale, status=status, pending=pending,
        resumed_from=resumed_from, files=[], result=result, tokens=0)
    try:
        with db.begin_nested():
            db.add(run)
            db.flush()
    except IntegrityError:
        existing = active(db, session_id)
        command = existing.command if existing else definition.name
        raise ApiError(409, "command_active", M("commands.active", command=command),
                       extra={"command": command, "spec": existing.spec if existing else None,
                              "status": existing.status if existing else "running"}) from None
    return run


def finish(run, status: str, error: str | None = None) -> None:
    run.status = status
    run.error = error
    run.pending = None
    run.ended_at = _now()


def _complete(run) -> None:
    """A run that wrote nothing because its write went to another spec is `misrouted`."""
    stored = getattr(run, "result", None)
    result = stored if isinstance(stored, dict) else {}
    if not run.files and result.get("misrouted_to"):
        finish(run, "misrouted", result.get("error"))
    else:
        finish(run, "completed")


def end_from_activity(run, activity_status: str, definition: CommandDef, *,
                      finished: bool = False, error: str | None = None) -> None:
    """End-of-turn status of the running run from the 017 activity status (plan §6)."""
    if run is None or run.status != "running":
        return
    if finished or activity_status == "ready":
        _complete(run)
    elif activity_status == "done":
        if definition.interactive:
            run.status = "waiting"
        else:
            _complete(run)
    elif activity_status == "budget":
        finish(run, "budget")
    elif activity_status in ("stopped", "limit"):
        finish(run, "interrupted")
    elif activity_status == "error":
        finish(run, "failed", error or "error")


def mark_stale_interrupted(db, session_id: int, *, status: str = "interrupted",
                           error: str | None = None) -> None:
    """A run still `running` when its turn was lost (stale claim, stop) is interrupted;
    an unexpected worker error marks it `failed`."""
    db.execute(update(AssistantCommandRun)
               .where(AssistantCommandRun.session_id == session_id,
                      AssistantCommandRun.status == "running")
               .values(status=status, error=error, pending=None, ended_at=_now())
               .execution_options(synchronize_session="fetch"))


def add_tokens(run, tokens: int) -> None:
    run.tokens = (run.tokens or 0) + max(0, tokens)


def add_file(run, path: str, action: str, revision_id: int | None) -> None:
    """Record a file the run wrote (a new list, so the JSONB change is detected)."""
    run.files = [*(run.files or []),
                 {"path": path, "action": action, "revision_id": revision_id}]


def resume_info(db, run, notes: str | None) -> dict | None:
    """Files written by the interrupted chain this run resumes, and the working notes."""
    if run.resumed_from is None:
        return None
    paths: list[str] = []
    seen: set[int] = set()
    current = run.resumed_from
    while current is not None and current not in seen:
        seen.add(current)
        previous = db.get(AssistantCommandRun, current)
        if previous is None or previous.status != "interrupted":
            break
        for entry in previous.files or []:
            path = entry.get("path")
            if path and path not in paths:
                paths.append(path)
        current = previous.resumed_from
    return {"files": paths, "notes": notes or ""}


def _plain(text: str) -> str:
    """Lowercase without accents: «Arréglalas» reads as «arreglalas» for the gate words."""
    return "".join(char for char in unicodedata.normalize("NFD", text)
                   if unicodedata.category(char) != "Mn").lower()


def answer(text: str) -> str | None:
    """The user's reply to a confirmation gate: "fix", "yes", "no" or None.

    "fix" asks the product to repair what the gate complains about instead of skipping it —
    for the checklist gate that means running the command that owns the checklist write."""
    plain = _plain(text)
    if _FIX.match(plain):
        return "fix"
    if _YES.match(plain):
        return "yes"
    if _NO.match(plain):
        return "no"
    return None


def spec_status(text: str) -> str | None:
    """First word of the spec's `**Status**:` line."""
    match = _STATUS.search(text)
    value = match.group(2).strip() if match else ""
    return value.split()[0] if value else None


def approved_text(text: str) -> str:
    """spec.md with `**Status**: Approved` (the line is added after the title when missing)."""
    if _STATUS.search(text):
        return _STATUS.sub(lambda m: f"{m.group(1)}Approved", text, count=1)
    title = _TITLE.search(text)
    if title:
        return f"{text[:title.end()]}\n**Status**: Approved{text[title.end():]}"
    return f"**Status**: Approved\n{text}"


def approve_ops(spec: str, files: dict[str, str]) -> list[dict]:
    """The 020 write that approves the spec (base hash of the text that was read)."""
    path = f"specs/{spec}/spec.md"
    return [{"op": "write", "path": path, "content": approved_text(files[path]),
             "base_sha256": sha(files[path])}]


def checklist_table(spec: str, files: dict[str, str]) -> str:
    """Table of the spec's checklists when any has unchecked items, else ""."""
    prefix = f"specs/{spec}/checklists/"
    rows = []
    incomplete = False
    for path in sorted(files):
        if not path.startswith(prefix) or not path.endswith(".md"):
            continue
        marks = [m.group(1) for m in _CHECK.finditer(files[path])]
        done = sum(1 for mark in marks if mark in ("x", "X"))
        incomplete = incomplete or done < len(marks)
        rows.append(f"| {path[len(prefix):]} | {len(marks)} | {done} | {len(marks) - done} |")
    if not incomplete:
        return ""
    return "\n".join(["| Checklist | Total | Completed | Incomplete |", "|---|---|---|---|",
                      *rows])


@dataclass(frozen=True)
class Preflight:
    message: str | None = None   # product message (missing prerequisite or confirmation)
    missing: str | None = None   # missing document, e.g. "plan.md"
    command: str | None = None   # command that creates it, e.g. "speckit-plan"
    pending: dict | None = None  # confirmation gates: the run starts `waiting`


def gate_message(pending: dict, hint: str | None = None) -> str:
    """The gate's question; `hint` is the product's extra line (where the Auto switch is)."""
    gate = pending["gate"]
    if gate == "open_clarifications":
        text = t("commands.confirm_open_clarifications")
    elif gate == "unchecked_checklists":
        text = t("commands.confirm_unchecked_checklists", table=pending.get("table", ""))
    elif gate == "approve_spec":
        text = t("commands.confirm_approve_spec", status=pending.get("status") or "-")
    else:
        raise ValueError(f"unknown gate {gate}")
    return f"{text}\n\n{hint}" if hint else text


def preflight(definition: CommandDef, spec: str | None, files: dict[str, str]) -> Preflight:
    """Prerequisites of the command and its confirmation gates (deterministic)."""
    for key in definition.prereqs:
        doc = DOCS[key]
        if spec is None or f"specs/{spec}/{doc}" not in files:
            command = PREREQ_COMMAND[key]
            return Preflight(message=t("commands.missing_prereq", doc=doc, command=f"/{command}"),
                             missing=doc, command=command)
    spec_text = files.get(f"specs/{spec}/spec.md", "") if spec else ""
    gates: list[str] = []
    table = ""
    status = None
    if definition.name == "speckit-tasks" and "[NEEDS CLARIFICATION" in spec_text:
        gates.append("open_clarifications")
    if definition.name == "speckit-implement":
        table = checklist_table(spec or "", files)
        if table:
            gates.append("unchecked_checklists")
        status = spec_status(spec_text)
        if (status or "").lower() not in ("approved", "implemented"):
            gates.append("approve_spec")
    if not gates:
        return Preflight()
    pending = {"gates": gates, "gate": gates[0], "table": table, "status": status}
    return Preflight(message=gate_message(pending), pending=pending)


def advance(run, hint: str | None = None) -> str | None:
    """After a "yes": the next gate's message, or None when the run can start."""
    gates = list(run.pending["gates"])[1:]
    if gates:
        run.pending = {**run.pending, "gates": gates, "gate": gates[0]}
        return gate_message(run.pending, hint=hint)
    run.pending = None
    run.status = "running"
    return None
