"""The `/speckit-all` pipeline (feature 039): the fixed plan, where a run is, and the report.

The command is a stage driver, not an engine (plan §1): its own run writes only the run report and
the decision log, and every stage is a real `assistant_command_run` opened through `run_command`
(028 FR-004). This module owns the stage list, the cursor, what counts as a finished stage, the
verify checks and the stop reasons. Nothing here calls a provider: the model drives, the product
enforces.

Cursor shape: `specs/039-speckit-all/data-model.md` §1.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.assistant.commands.resolve import strip_force
from app.errors import ApiError
from app.i18n import M, t

PIPELINE_KEY = "pipeline"
STAGES: tuple[str, ...] = ("specify", "clarify", "plan", "tasks", "analyze", "implement",
                           "converge", "verify")
STAGE_COMMANDS: dict[str, str] = {stage: f"speckit-{stage}" for stage in STAGES}
COMMAND_STAGES: dict[str, str] = {command: stage for stage, command in STAGE_COMMANDS.items()}
TOTAL = len(STAGES)
MAX_ROUNDS = 2                 # converge gaps, executed in the same run
MAX_VERIFY_CYCLES = 3          # fix-and-re-verify before stopping
REPORT_FILE = "run-report.md"
DECISIONS_HEADING = "## Decisiones tomadas (modo autónomo)"
MAX_STOP_REASON = 120

_DECISION = re.compile(r"^\s*[-*]\s*\[(?P<stage>[a-z]+)\]\s*(?P<text>\S.*)$")
_OPEN_TASK = re.compile(r"^\s*[-*]\s*\[\s\]\s*(?P<id>T\d+)\b", re.M)
_TASK_ID = re.compile(r"\bT\d{3,}\b")
_STORY = re.compile(r"^###\s+User Story\s+(?P<number>\d+)\s*[\u2014\u2013-]\s*"
                    r"(?P<title>.+?)"
                    r"(?:\s*\(Priority.*)?$", re.M)
_INDEPENDENT = re.compile(r"^\*\*Independent Test\*\*:\s*(?P<text>.+)$", re.M)


# --------------------------------------------------------------------------- arguments

@dataclass(frozen=True)
class Args:
    """What the composer typed, without the flags."""

    text: str
    until: str | None
    force: bool


def parse_args(arguments: str) -> Args:
    """Strip `--force` and `--until <stage>`; refuse an unknown stage with the catalogue message."""
    text, force = strip_force(arguments or "")
    kept: list[str] = []
    until = None
    tokens = text.split()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        lowered = token.lower()
        if lowered == "--until":
            until = _until_value(tokens[index + 1] if index + 1 < len(tokens) else "")
            index += 2
            continue
        if lowered.startswith("--until="):
            until = _until_value(token.split("=", 1)[1])
            index += 1
            continue
        kept.append(token)
        index += 1
    return Args(text=" ".join(kept), until=until, force=force)


def _until_value(value: str) -> str:
    stage = (value or "").strip().lower()
    if stage not in STAGES:
        raise ApiError(422, "until_invalid",
                       M("commands.until_invalid", value=stage or "-", stages=", ".join(STAGES)),
                       extra={"stages": list(STAGES), "value": stage})
    return stage


# --------------------------------------------------------------------------- state

def seed(run_id: int | None = None, args: Args | None = None,
         specs: tuple[str, ...] | list[str] = ()) -> dict[str, Any]:
    """A brand-new cursor for this run."""
    return {"id": run_id, "stages": list(STAGES), "cursor": 0,
            "until": args.until if args is not None else None,
            "specs": list(specs), "spec_index": 0, "round": 1, "verify_cycles": 0,
            "after_implement": None}


def state_of(db, session_id: int) -> dict[str, Any] | None:
    """The cursor of the conversation's newest runs that carry one (None when there is none)."""
    from sqlalchemy import select

    from app.models import AssistantCommandRun

    row = db.scalars(
        select(AssistantCommandRun)
        .where(AssistantCommandRun.session_id == session_id,
               AssistantCommandRun.result.isnot(None),
               AssistantCommandRun.result[PIPELINE_KEY].isnot(None))
        .order_by(AssistantCommandRun.id.desc()).limit(1)
    ).first()
    if row is None or not isinstance(row.result, dict):
        return None
    stored = row.result.get(PIPELINE_KEY)
    return _validated(stored) if isinstance(stored, dict) else None


def _validated(state: dict[str, Any]) -> dict[str, Any]:
    """Keep a stored cursor inside the invariants of data-model §1 (a wrong one is repaired)."""
    clean = seed(state.get("id"), None, state.get("specs") or [])
    clean["stages"] = list(STAGES)
    clean["cursor"] = _clamp(state.get("cursor"), 0, TOTAL)
    clean["spec_index"] = _clamp(state.get("spec_index"), 0, max(0, len(clean["specs"]) - 1))
    clean["round"] = _clamp(state.get("round"), 1, MAX_ROUNDS)
    clean["verify_cycles"] = _clamp(state.get("verify_cycles"), 0, MAX_VERIFY_CYCLES)
    after = state.get("after_implement")
    clean["after_implement"] = after if after in ("converge", "verify") else None
    until = state.get("until")
    clean["until"] = until if until in STAGES else None
    return clean


def _clamp(value: Any, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, number))


def advance(state: dict[str, Any], spec_index: int, stage_index: int) -> dict[str, Any]:
    """The cursor after `stage_index` of `spec_index` was opened; the next one is returned."""
    new = {**state, "specs": list(state.get("specs") or []),
           "stages": list(state.get("stages") or STAGES)}
    if stage_index + 1 < TOTAL:
        new["spec_index"], new["cursor"] = spec_index, stage_index + 1
    elif spec_index + 1 < len(new["specs"]):
        new["spec_index"], new["cursor"] = spec_index + 1, 0
        new["round"] = 1
        new["verify_cycles"] = 0
        new["after_implement"] = None
    else:
        new["spec_index"], new["cursor"] = spec_index, TOTAL
    return new


def finished(state: dict[str, Any] | None) -> bool:
    return state is None or state.get("cursor") == TOTAL


def position(state: dict[str, Any]) -> dict[str, Any]:
    """The pipeline as the conversation shows it (contract §6)."""
    index = int(state.get("cursor") or 0)
    specs = state.get("specs") or []
    spec_index = int(state.get("spec_index") or 0)
    return {"id": state.get("id"), "cursor": index, "total": TOTAL,
            "stage": STAGES[index] if index < TOTAL else None,
            "until": state.get("until"),
            "spec": specs[spec_index] if 0 <= spec_index < len(specs) else None,
            "spec_index": spec_index, "round": int(state.get("round") or 1)}


# --------------------------------------------------------------------------- completion

@dataclass(frozen=True)
class Facts:
    """What the artifacts and the conversation prove about one spec."""

    row: dict[str, Any] | None = None
    files: dict[str, str] | None = None
    clarified: bool = False
    converged: bool = False
    validation_ok: bool = False
    preview_ok: bool = False
    cursor: int = 0


def completed(spec: str, facts: Facts) -> set[str]:
    """The stages this spec can prove it already finished (data-model §4)."""
    files = facts.files or {}
    done: set[str] = set()
    text = files.get(f"specs/{spec}/spec.md")
    if text is None:
        return done
    done.add("specify")
    stage = (facts.row or {}).get("stage") or ""
    if facts.clarified and "[NEEDS CLARIFICATION" not in text:
        done.add("clarify")
    if f"specs/{spec}/plan.md" in files:
        done.add("plan")
    if f"specs/{spec}/tasks.md" in files:
        done.add("tasks")
    if facts.cursor > STAGES.index("analyze"):        # analyze writes nothing
        done.add("analyze")
    if stage in ("implementada", "aplicada"):
        done.add("implement")
        if not facts.converged:
            done.add("converge")
        if facts.validation_ok and facts.preview_ok:
            done.add("verify")
    # A stage is only complete when every earlier one is: an artifact alone does not skip ahead.
    done = {item for item in done
            if all(prior in done for prior in STAGES[:STAGES.index(item)])}
    return done


def detect(state: dict[str, Any], facts: dict[str, Facts]) -> dict[str, Any]:
    """Move the cursor to the first stage the artifacts do not prove finished (US3, resume)."""
    if state.get("until") is None and state.get("cursor") not in (0, TOTAL):
        return state
    spec_index, cursor = int(state.get("spec_index") or 0), int(state.get("cursor") or 0)
    specs = state.get("specs") or []
    while spec_index < len(specs):
        done = completed(specs[spec_index], facts.get(specs[spec_index], Facts()))
        while cursor < TOTAL and STAGES[cursor] in done:
            cursor += 1
        if cursor < TOTAL:
            break
        spec_index, cursor = spec_index + 1, 0
    if spec_index >= len(specs):
        # Every spec is done: the plan is over, not back at its first stage.
        return {**state, "spec_index": max(0, len(specs) - 1), "cursor": TOTAL}
    return {**state, "spec_index": spec_index, "cursor": cursor}


def next_position(state: dict[str, Any]) -> tuple[int, int] | None:
    """(spec_index, stage_index) to open next; None when `--until` or the plan ends."""
    specs = state.get("specs") or []
    index, cursor = int(state.get("spec_index") or 0), int(state.get("cursor") or 0)
    limit = TOTAL if state.get("until") is None else STAGES.index(state["until"]) + 1
    if not specs:
        # Before the plan owns a spec there is exactly one stage: the one that creates it.
        return (0, 0) if cursor == 0 and limit > 0 else None
    if index >= len(specs) or cursor >= limit:
        return None
    return index, cursor


def open_stage(state: dict[str, Any]) -> tuple[str | None, str] | None:
    """(spec, stage) to open next; the spec is None while the plan has not created it."""
    next_at = next_position(state)
    if next_at is None:
        return None
    spec_index, stage_index = next_at
    specs = state.get("specs") or []
    return (specs[spec_index] if spec_index < len(specs) else None), STAGES[stage_index]


def ordered_specs(rows: list[dict[str, Any]]) -> list[str]:
    """Integration specs before report specs, then by number (plan §6)."""
    def key(row: dict[str, Any]) -> tuple[int, int]:
        kind = 0 if (row.get("kind") or "") == "integracion" else 1
        return kind, int(row.get("number") or 0)

    return [row["folder"] for row in sorted(rows, key=key)]


# --------------------------------------------------------------------------- decisions

def decisions_section(text: str) -> str:
    """The body of the decisions section ("" when there is none)."""
    lines = (text or "").splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == DECISIONS_HEADING:
            start = index + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end]).strip("\n")


def without_decisions(text: str) -> str:
    """`text` with the decisions heading and its body removed (guard rule `decisions_append`)."""
    lines = (text or "").splitlines()
    kept: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == DECISIONS_HEADING:
            skipping = True
            continue
        if skipping and line.startswith("## "):
            skipping = False
        if not skipping:
            kept.append(line)
    return "\n".join(kept).strip("\n")


def decisions(text: str) -> list[dict[str, str]]:
    """The recorded decisions, one dict per line, with the stage that took it."""
    out = []
    for line in decisions_section(text).splitlines():
        match = _DECISION.match(line)
        if match and match.group("stage") in STAGES:
            out.append({"stage": match.group("stage"), "text": match.group("text").strip(),
                        "line": line.strip()})
    return out


def decisions_block(text: str) -> list[str]:
    """The decisions exactly as the spec carries them (the report mirrors them, FR-004)."""
    return [item["line"] for item in decisions(text)]


def is_decision(line: str) -> bool:
    """Whether a line is `- [stage] decision — why` with a known stage."""
    match = _DECISION.match(line or "")
    return bool(match) and match.group("stage") in STAGES


# --------------------------------------------------------------------------- verify

def _owned_by(files: dict[str, str], spec: str, artifact: str) -> bool:
    """Whether `artifact` declares this spec (`spec: specs/NNN-…` in its own yaml)."""
    for path in (f"integrations/{artifact}/integration.yaml",
                 f"reports/{artifact}/report.yaml"):
        declared = _declared_spec(files.get(path))
        if declared is not None:
            return declared == spec
    return False


def _declared_spec(text: str | None) -> str | None:
    import yaml

    if not text:
        return None
    try:
        loaded = yaml.safe_load(text)
    except Exception:
        return None
    value = loaded.get("spec") if isinstance(loaded, dict) else None
    if not isinstance(value, str):
        return None
    return value.strip().removeprefix("specs/").rstrip("/") or None


def _source_of(files: dict[str, str], artifact: str) -> str | None:
    import yaml

    text = files.get(f"integrations/{artifact}/integration.yaml")
    if not text:
        return None
    try:
        loaded = yaml.safe_load(text)
    except Exception:
        return None
    value = loaded.get("source") if isinstance(loaded, dict) else None
    return value.strip() if isinstance(value, str) else None


def stories(text: str) -> list[dict[str, Any]]:
    """The spec's user stories with their Independent Test (US4 AC1)."""
    found: list[dict[str, Any]] = []
    matches = list(_STORY.finditer(text or ""))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end():end]
        test = _INDEPENDENT.search(block)
        found.append({"story": f"US{match.group('number')}", "title": match.group("title").strip(),
                      "test": test.group("text").strip() if test else ""})
    return found


def verify(db, actor, session, spec: str, *, app_settings: Any,
           ip: str | None = None, preview_allowed: bool = True) -> dict[str, Any]:
    """Run the checks the product owns, without a provider call (US4, plan §3).

    Validation, one `check_query`/`check_request` per file of the spec's integrations, one preview
    (counted by the contract) and the per-story verdicts the evidence supports.
    """
    from app.assistant import origin, preview

    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    files = dict((session.draft or {}).get("files") or session.files())
    validation = session.validation or {}
    valid = bool(validation.get("valid"))
    checks.append({"check": "validation", "ok": valid,
                   "detail": "" if valid else t("pipeline.validation_failed")})
    if not valid:
        failures.append("validation")

    for path in sorted(files):
        match = origin.QUERY_FILE.match(path) or origin.REQUEST_FILE.match(path)
        if match is None or not _owned_by(files, spec, match.group(1)):
            continue
        source = _source_of(files, match.group(1))
        ok, detail = False, t("pipeline.source_missing")
        if source:
            try:
                result, _summary = origin.check_query(
                    db, actor, session, {"source": source, "path": path}, app_settings, ip)
                ok = bool(result.get("ok", True))
                detail = "" if ok else t("pipeline.check_failed")
            except origin.OriginToolError as exc:
                detail = exc.message
        checks.append({"check": f"check_query {path}", "ok": ok, "detail": detail})
        if not ok:
            failures.append(path)

    preview_ok = False
    detail = ""
    if not preview_allowed:
        detail = t("pipeline.preview_not_allowed")
    else:
        try:
            outcome = preview.run_draft_preview(db, session, time_limit_s=120)
            preview_ok = outcome.get("status") == "succeeded"
            detail = preview.summary_text(outcome)
            db.add(_real(session))
        except preview.PreviewBusy:
            detail = t("pipeline.preview_busy")
        except Exception:
            detail = t("pipeline.preview_failed")
    checks.append({"check": "preview", "ok": preview_ok, "detail": detail})
    if not preview_ok:
        failures.append("preview")

    integrations = (session.preview or {}).get("integrations", {}).values()
    row_counts = [data.get("rows") for item in integrations
                  for data in (item.get("datasets") or {}).values()]
    declared_rows = all(isinstance(count, int) and count > 0 for count in row_counts) \
        if row_counts else False
    story_rows = []
    for item in stories(files.get(f"specs/{spec}/spec.md", "")):
        ok = preview_ok and valid and declared_rows
        story_rows.append({**item, "ok": ok})
        if not ok:
            failures.append(item["story"])
    return {"spec": spec, "ok": not failures, "checks": checks, "stories": story_rows,
            "failures": failures}


def _real(session):
    """The mapped conversation behind the view the checks read."""
    from app.projects.workview import real

    return real(session)


# --------------------------------------------------------------------------- stop reasons

def stop_reason(kind: str, detail: str | None = None) -> str:
    """One line, ≤ MAX_STOP_REASON, from the closed set of contract §5."""
    value = f"{kind}:{detail}" if detail else kind
    return value[:MAX_STOP_REASON]


# --------------------------------------------------------------------------- report

def report_markdown(*, spec: str, state: dict[str, Any], rows: list[dict[str, Any]],
                    decisions_lines: list[str], verify_result: dict[str, Any] | None,
                    result: str, stop: str | None, tokens: int,
                    started: datetime | None, ended: datetime | None) -> str:
    """`specs/<spec>/run-report.md` (data-model §6). Same inputs, same bytes."""
    when = f"{_stamp(started)} → {_stamp(ended)}"
    head = [f"# Run report · {spec}", "",
            f"**Run**: {state.get('id')} · {when} · {len(rows)} stages · {tokens} tokens",
            f"**Result**: {result}" + (f" · {stop}" if stop else ""), "",
            "## Stages", "",
            "| # | Stage | Command run | Status | Files |",
            "|---|-------|-------------|--------|-------|"]
    for index, row in enumerate(rows, start=1):
        files = ", ".join(f"`{item.get('path')}`" for item in row.get("files") or []) or "—"
        head.append(f"| {index} | {row.get('stage')} | {row.get('run_id')} | "
                    f"{row.get('status')} | {files} |")
    if any(row.get("tokens") for row in rows):
        body = [*head, "", f"## {t('pipeline.tokens_per_stage')}", "",
                "| Spec | Stage | Tokens |", "|------|-------|--------|"]
        body += [f"| {row.get('spec') or '—'} | {row.get('stage')} | {row.get('tokens') or 0} |"
                 for row in rows]
    else:
        body = [*head]
    body += ["", "## Decisiones tomadas", ""]
    body += decisions_lines or ["—"]
    body += ["", "## Verificación", ""]
    if verify_result:
        body += ["| Check | Result | Detail |", "|-------|--------|--------|"]
        for check in verify_result.get("checks") or []:
            body.append(f"| {check.get('check')} | {'ok' if check.get('ok') else 'fail'} | "
                        f"{check.get('detail') or '—'} |")
        for story in verify_result.get("stories") or []:
            body.append(f"| {story.get('story')} Independent Test | "
                        f"{'pass' if story.get('ok') else 'fail'} | "
                        f"{story.get('test') or '—'} |")
    else:
        body.append("—")
    pending = pending_items(state, result)
    if pending:
        body += ["", "## Pendiente para el humano", ""] + [f"- {item}" for item in pending]
    return "\n".join(body).rstrip("\n") + "\n"


def pending_items(state: dict[str, Any], result: str) -> list[str]:
    """Only what a human must do; empty is the normal case (SC-003)."""
    if result == "ready":
        return [t("pipeline.pending_apply")]
    return []


def _stamp(value: datetime | None) -> str:
    if value is None:
        return "—"
    moment = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def runs_of(db, pipeline_id: int | None) -> list[Any]:
    """The stage runs of one pipeline, in the order they were opened."""
    from sqlalchemy import select

    from app.models import AssistantCommandRun

    if pipeline_id is None:
        return []
    rows = db.scalars(select(AssistantCommandRun)
                      .where(AssistantCommandRun.result.isnot(None))
                      .order_by(AssistantCommandRun.id)).all()
    found = []
    for row in rows:
        stored = (row.result or {}).get(PIPELINE_KEY) if isinstance(row.result, dict) else None
        if isinstance(stored, dict) and stored.get("id") == pipeline_id:
            found.append(row)
    return found


def stage_rows(db, state: dict[str, Any]) -> list[dict[str, Any]]:
    """The stage table of the report, deduplicated by (spec, stage) keeping the newest run."""
    newest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in runs_of(db, state.get("id")):
        stage = COMMAND_STAGES.get(row.command)
        if stage is None:
            continue
        key = (row.spec or "", stage)
        newest[key] = {"stage": stage, "run_id": row.id, "status": row.status,
                       "spec": row.spec, "files": list(row.files or []),
                       "tokens": int(row.tokens or 0)}
    return [newest[key] for key in
            sorted(newest, key=lambda item: (item[0], STAGES.index(item[1])))]


def specs_from_runs(db, pipeline_id: int | None) -> list[str]:
    """The spec folders this pipeline established (the `spec.md` its specify runs wrote)."""
    found: list[str] = []
    for row in runs_of(db, pipeline_id):
        for entry in row.files or []:
            match = re.match(r"^specs/(\d{3}-[a-z0-9-]+)/spec\.md$", entry.get("path") or "")
            if match and match.group(1) not in found:
                found.append(match.group(1))
    return found


def facts_for(db, session, view, rows: list[dict[str, Any]], cursor: int = 0) -> dict[str, Facts]:
    """The evidence of every spec of the project, for `completed`/`detect` (data-model §4)."""
    from app.projects import specs as project_specs

    files = view.files()
    validation_ok = bool((session.validation or {}).get("valid"))
    preview_ok = (session.preview or {}).get("status") == "succeeded"
    out: dict[str, Facts] = {}
    for row in rows:
        folder = row["folder"]
        stage = row.get("stage") or ""
        clarified = stage not in ("", "especificada") or project_specs.revised_by(
            db, view.project.id, f"specs/{folder}/spec.md", "speckit-clarify")
        out[folder] = Facts(row=row, files=files, clarified=bool(clarified),
                            converged=bool(row.get("converged")), validation_ok=validation_ok,
                            preview_ok=preview_ok, cursor=cursor)
    return out


def stage_runs(db, state: dict[str, Any], command: str,
               spec: str | None = None) -> list[Any]:
    """The runs of one stage of this pipeline, oldest first."""
    rows = [row for row in runs_of(db, state.get("id")) if row.command == command]
    return [row for row in rows if spec is None or row.spec == spec]


def verify_runs(db, state: dict[str, Any], spec: str | None = None) -> list[Any]:
    """The verify runs of this pipeline (one per cycle)."""
    return stage_runs(db, state, "speckit-verify", spec)


def last_verify(db, state: dict[str, Any], spec: str | None = None) -> dict[str, Any] | None:
    """The newest verify verdict of this pipeline, if it ran."""
    for row in reversed(verify_runs(db, state, spec)):
        stored = (row.result or {}).get("verify") if isinstance(row.result, dict) else None
        if isinstance(stored, dict):
            return stored
    return None


# --------------------------------------------------------------------------- state machine

def open_task_ids(text: str | None) -> list[str]:
    """The ids of the open tasks of a `tasks.md` (`- [ ] T025 …`), in order."""
    found: list[str] = []
    for match in _OPEN_TASK.finditer(text or ""):
        if match.group("id") not in found:
            found.append(match.group("id"))
    return found


def open_tasks(files: dict[str, str] | None, spec: str | None) -> list[str]:
    if not spec:
        return []
    return open_task_ids((files or {}).get(f"specs/{spec}/tasks.md"))


def task_ids(text: str | None) -> list[str]:
    """Every task id a text names, in order (the `--only` list is checked against these)."""
    return list(dict.fromkeys(_TASK_ID.findall(text or "")))


def routed_state(db, state: dict[str, Any] | None,
                 files: dict[str, str] | None) -> dict[str, Any] | None:
    """The 040 state machine: the only place that decides where the plan goes next.

    The 039 cursor was a one-way index, so after `converge` added the gap tasks T025-T028 the only
    reachable stage was `verify` and the run told the human to "open it in that order". These
    transitions are product code instead (spec A):

    - `converge` with open tasks → `implement` (the next convergence round) → `converge` again,
      at most `MAX_ROUNDS` convergence runs, then `verify`;
    - `verify` with open tasks → `implement` (a verify cycle) → `verify` again — never a failure
      and never a question (FR-003);
    - `verify` failed → `implement` (a verify cycle) → `verify`, at most `MAX_VERIFY_CYCLES`;
    - an `implement` opened by a verify cycle is followed by `verify`, not by `converge`.
    """
    if state is None:
        return None
    new = {**state, "specs": list(state.get("specs") or [])}
    specs = new["specs"]
    if not specs:
        return new
    index = _clamp(new.get("spec_index"), 0, len(specs) - 1)
    cursor = _clamp(new.get("cursor"), 0, TOTAL)
    new["spec_index"], new["cursor"] = index, cursor
    spec = specs[index]
    if cursor >= TOTAL:
        # The plan ended at `verify`: a failing verification still gets its fix cycles (US1 AC2).
        if new.get("until") is None and STAGES[-1] == "verify":
            verdict = last_verify(db, new, spec) or {}
            if ((open_tasks(files, spec) or verdict.get("ok") is False)
                    and len(verify_runs(db, new, spec)) < MAX_VERIFY_CYCLES):
                new["cursor"] = STAGES.index("implement")
                new["after_implement"] = "verify"
                new["verify_cycles"] = _clamp(int(new.get("verify_cycles") or 0) + 1,
                                              0, MAX_VERIFY_CYCLES)
        return new
    stage = STAGES[cursor]
    limit = TOTAL if new.get("until") is None else STAGES.index(new["until"]) + 1
    target: str | None = None
    after: str | None = None
    if stage == "verify":
        if open_tasks(files, spec):
            converges = len(stage_runs(db, new, STAGE_COMMANDS["converge"], spec))
            rounds = int(new.get("round") or 1)
            if converges and rounds < MAX_ROUNDS and STAGES.index("implement") < limit:
                target, after = "implement", "converge"
            elif len(verify_runs(db, new, spec)) < MAX_VERIFY_CYCLES \
                    and STAGES.index("implement") < limit:
                target, after = "implement", "verify"
        else:
            verdict = last_verify(db, new, spec) or {}
            if (verdict and verdict.get("ok") is False
                    and len(verify_runs(db, new, spec)) < MAX_VERIFY_CYCLES
                    and STAGES.index("implement") < limit):
                target, after = "implement", "verify"
    elif stage == "converge":
        if new.get("after_implement") == "verify" and STAGES.index("verify") < limit:
            target = "verify"
        new["after_implement"] = None
    if target is None:
        return new
    new["cursor"] = STAGES.index(target)
    new["after_implement"] = after
    if after == "converge":
        new["round"] = _clamp(int(new.get("round") or 1) + 1, 1, MAX_ROUNDS)
    elif after == "verify":
        new["verify_cycles"] = _clamp(int(new.get("verify_cycles") or 0) + 1,
                                      0, MAX_VERIFY_CYCLES)
    return new


def is_round_reentry(state: dict[str, Any] | None) -> bool:
    """Whether the plan is past its first convergence round (the chip shows «ronda N»)."""
    return bool(state) and int((state or {}).get("round") or 1) > 1


def rewind(db, state: dict[str, Any]) -> dict[str, Any]:
    """Point the cursor back at the stage whose run did not finish, so a resume repeats it.

    Once `run_command` opens a stage the cursor already points past it, so a stop in the middle of
    a stage would resume at the *next* one and silently skip the work that was cut short (US3 AC1
    says "resumes from the same stage"). The rewound cursor is stored on that run.
    """
    specs = state.get("specs") or []
    for row in reversed(runs_of(db, state.get("id"))):
        stage = COMMAND_STAGES.get(row.command)
        if stage is None:
            continue
        if row.status == "completed":
            return state
        if row.spec is None or row.spec not in specs:
            return state
        rewound = {**state, "spec_index": specs.index(row.spec),
                   "cursor": STAGES.index(stage)}
        row.result = {**(row.result or {}), PIPELINE_KEY: rewound}
        return rewound
    return state


def ends_here(state: dict[str, Any] | None) -> bool:
    """Whether the plan is over: every stage done, or `--until` reached (the report is due)."""
    if state is None:
        return False
    if state.get("cursor") == TOTAL:
        return True
    until = state.get("until")
    return until in STAGES and state.get("cursor") == STAGES.index(until) + 1


def write_report(db, session, spec: str, state: dict[str, Any], *, result: str,
                 stop: str | None = None, verify_result: dict[str, Any] | None = None,
                 actor: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Write `specs/<spec>/run-report.md` and return the card payload (None without a project)."""
    from app.projects import fs

    if session.project_id is None or not spec:
        return None
    files = session.files()
    spec_text = files.get(f"specs/{spec}/spec.md", "")
    rows = [row for row in stage_rows(db, state) if row.get("spec") in (spec, None)]
    started = min((row.started_at for row in runs_of(db, state.get("id")) if row.started_at),
                  default=None)
    ended = datetime.now(UTC)
    tokens = sum(int(row.tokens or 0) for row in runs_of(db, state.get("id")))
    markdown = report_markdown(spec=spec, state=state, rows=rows,
                              decisions_lines=decisions_block(spec_text),
                              verify_result=verify_result, result=result, stop=stop,
                              tokens=tokens, started=started, ended=ended)
    path = f"specs/{spec}/{REPORT_FILE}"
    if files.get(path) != markdown:
        fs.apply_ops(session.project_id, [{"op": "write", "path": path, "content": markdown}],
                     actor or {"kind": "agent", "user_id": None, "session_id": session.id,
                               "command": "/speckit-all", "command_run_id": state.get("id")})
        session.refresh()
    return {"spec": spec, "path": path, "result": result, "stop_reason": stop,
            "stages": [{"stage": row["stage"], "run_id": row["run_id"],
                        "status": row["status"]} for row in rows],
            "pending": pending_items(state, result),
            "decisions": decisions_block(spec_text),
            "verify": (verify_result or {}).get("checks") or [],
            "stories": (verify_result or {}).get("stories") or []}
