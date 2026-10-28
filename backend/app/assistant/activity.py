"""Agent map: activity of the current/last assistant run (feature 017, Phase 15)."""

import copy
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.errors import not_found
from app.i18n import M, t
from app.models import AssistantPreviewRequest, AssistantSession

ACTIVITY_ROUNDS = 60
ACTIVITY_TOOLS = 25
RUNS_KEPT = 10
LABEL_CHARS = 120


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _clip(text: str) -> str:
    if len(text) <= LABEL_CHARS:
        return text
    return text[: LABEL_CHARS - 1] + "…"


def tool_label(name: str, args: dict | None) -> str:
    args = args or {}

    if name == "list_sources":
        return t("activity.list_sources")

    if name == "describe_source":
        source_name = args.get("name")
        if isinstance(source_name, str) and source_name.strip().lower() == "bi":
            label = t("activity.dataset_structure_bi")
        elif isinstance(source_name, str) and source_name:
            label = t("activity.dataset_structure_named", source_name=source_name)
        else:
            label = t("activity.dataset_structure_unnamed")
        path = args.get("path")
        if isinstance(source_name, str) and source_name.strip().lower() != "bi":
            if isinstance(path, str) and path:
                label += f" · {path}"
        return _clip(label)

    if name == "profile_source":
        source_name = args.get("name")
        if isinstance(source_name, str) and source_name.strip().lower() == "bi":
            label = t("activity.source_profile_bi")
            table = args.get("table")
            if isinstance(table, str) and table:
                label += f" · {table}"
            return _clip(label)
        if isinstance(source_name, str) and source_name:
            label = t("activity.source_profile_named", source_name=source_name)
        else:
            label = t("activity.source_profile_unnamed")
        table = args.get("table")
        if isinstance(table, str) and table:
            label += f" · {table}"
        return _clip(label)

    if name == "check_query":
        path = args.get("path")
        if isinstance(path, str) and path:
            report_match = re.match(r"^reports/([^/]+)/report\.yaml$", path)
            if report_match:
                return _clip(t("activity.check_named_metric", path=report_match.group(1)))
            return _clip(t("activity.check_path", path=path))
        return t("activity.check_query")

    if name == "get_workspace":
        return t("activity.active_workspace")

    if name == "get_authoring_guide":
        topic = args.get("topic")
        topic = topic if isinstance(topic, str) and topic else "index"
        return _clip(t("activity.authoring_guide_topic", topic=topic))

    if name == "propose_draft":
        return t("activity.propose_draft")

    if name == "edit_draft":
        return t("activity.edit_draft")

    if name == "read_draft":
        paths = args.get("paths")
        if isinstance(paths, list):
            str_paths = [p for p in paths if isinstance(p, str)]
            if str_paths:
                return _clip(t("activity.read_draft_paths", paths=", ".join(str_paths[:3])))
        return t("activity.read_draft")

    if name == "run_preview":
        return t("activity.preview")

    if name == "update_notes":
        return t("activity.working_notes")

    if name == "finish_command":
        return t("activity.finish_command")

    if name == "get_app_guide":
        return t("activity.app_guide")

    if name == "get_project_overview":
        return t("activity.project_overview")

    if name == "suggest_command":
        return t("activity.suggest_command")

    return _clip(name)


def _get_run(session: Any) -> dict | None:
    working = session.working_state or {}
    run = working.get("run")
    if isinstance(run, dict):
        return copy.deepcopy(run)
    return None


def _put_run(session: Any, run: dict) -> None:
    working = dict(session.working_state or {})
    working["run"] = run
    session.working_state = working


def begin_run(session: Any, command: str | None = None) -> None:
    old = _get_run(session)
    if old is not None and old.get("status") == "running":
        end_run(session, "error")
        old = _get_run(session)

    new_id = int(old.get("id") or 0) + 1 if old else 1
    now = _now()
    _put_run(
        session,
        {
            "id": new_id,
            "started_at": _iso(now),
            "finished_at": None,
            "status": "running",
            "round": 0,
            "tokens": 0,
            "tools": 0,
            "current": None,
            "rounds": [],
            "command": command,
        },
    )


def add_tokens(session: Any, amount: int) -> None:
    run = _get_run(session)
    if run is None or run.get("status") != "running":
        return
    run["tokens"] = int(run.get("tokens") or 0) + int(amount)
    _put_run(session, run)


def begin_round(session: Any, n: int, *, tools: int | None = None,
                chars: int | None = None, stage: str | None = None) -> None:
    """Start round `n`; `tools`, `chars` and `stage` are what the round cost (feature 040)."""
    run = _get_run(session)
    if run is None or run.get("status") != "running":
        return
    run["round"] = n
    rounds = [r for r in run.get("rounds", []) if isinstance(r, dict)]
    rounds.append({"n": n, "tools": [], "tool_count": tools, "chars": chars, "stage": stage})
    run["rounds"] = rounds[-ACTIVITY_ROUNDS:]
    _put_run(session, run)


def start_tool(session: Any, name: str, args: dict | None) -> None:
    run = _get_run(session)
    if run is None or run.get("status") != "running":
        return

    rounds = [r for r in run.get("rounds", []) if isinstance(r, dict)]
    if not rounds:
        rounds.append({"n": run.get("round", 0), "tools": []})

    label = tool_label(name, args)
    now = _iso(_now())
    tools = [t for t in rounds[-1].get("tools", []) if isinstance(t, dict)]
    tools.append({"name": name, "label": label, "status": "running", "started_at": now, "ms": None})
    rounds[-1]["tools"] = tools[-ACTIVITY_TOOLS:]
    run["rounds"] = rounds
    run["tools"] = int(run.get("tools") or 0) + 1
    run["current"] = {"tool": name, "label": label, "since": now}
    _put_run(session, run)


def end_tool(session: Any, ok: bool) -> None:
    run = _get_run(session)
    if run is None or run.get("status") != "running":
        return

    rounds = [r for r in run.get("rounds", []) if isinstance(r, dict)]
    if not rounds:
        return

    tools = [t for t in rounds[-1].get("tools", []) if isinstance(t, dict)]
    for tool in reversed(tools):
        if tool.get("status") == "running":
            tool["status"] = "ok" if ok else "error"
            started_at = tool.get("started_at")
            if isinstance(started_at, str):
                try:
                    started_dt = datetime.fromisoformat(started_at)
                    tool["ms"] = max(0, int((_now() - started_dt).total_seconds() * 1000))
                except ValueError:
                    tool["ms"] = None
            break

    rounds[-1]["tools"] = tools
    run["rounds"] = rounds
    run["current"] = None
    _put_run(session, run)


def end_run(session: Any, status: str) -> None:
    run = _get_run(session)
    if run is None or run.get("status") != "running":
        return

    rounds = [r for r in run.get("rounds", []) if isinstance(r, dict)]
    for round_data in rounds:
        tools = [t for t in round_data.get("tools", []) if isinstance(t, dict)]
        for tool in tools:
            if tool.get("status") == "running":
                tool["status"] = "error"
                started_at = tool.get("started_at")
                if isinstance(started_at, str):
                    try:
                        started_dt = datetime.fromisoformat(started_at)
                        tool["ms"] = max(0, int((_now() - started_dt).total_seconds() * 1000))
                    except ValueError:
                        tool["ms"] = None
        round_data["tools"] = tools

    run["rounds"] = rounds
    run["status"] = status
    run["finished_at"] = _iso(_now())
    run["current"] = None
    _put_run(session, run)

    stats = dict(session.stats or {})
    runs = stats.get("runs")
    if not isinstance(runs, list):
        runs = []
    runs = list(runs)
    runs.append(
        {
            "id": run.get("id"),
            "started_at": run.get("started_at"),
            "finished_at": run.get("finished_at"),
            "status": status,
            "rounds": run.get("round"),
            "tokens": run.get("tokens"),
            "tools": run.get("tools"),
        }
    )
    stats["runs"] = runs[-RUNS_KEPT:]
    session.stats = stats


def activity_json(db: Any, session_id: int, owner_id: int, settings: Any) -> dict:
    stmt = (
        select(
            AssistantSession.created_by,
            AssistantSession.busy_since,
            AssistantSession.working_state["run"],
            AssistantSession.stats["runs"],
        )
        .where(AssistantSession.id == session_id)
    )
    row = db.execute(stmt).first()

    if row is None or row[0] != owner_id:
        raise not_found(M("assistant.conversation_not_found"))

    _, busy_since, run_value, runs_value = row
    now = _now()
    busy = busy_since is not None and busy_since > now - timedelta(
        seconds=settings.ai_chat_busy_stale_seconds
    )

    run = run_value if isinstance(run_value, dict) else None
    runs = runs_value if isinstance(runs_value, list) else []

    run_out = None
    rounds_out = []

    if run is not None:
        status = run.get("status") or "error"
        if status == "running" and not busy:
            status = "error"

        for round_data in run.get("rounds", []):
            if not isinstance(round_data, dict):
                continue
            tools_out = []
            for tool in round_data.get("tools", []):
                if not isinstance(tool, dict):
                    continue
                tool_status = tool.get("status")
                tool_ms = tool.get("ms")
                if tool_status == "running":
                    if status == "running":
                        started_at = tool.get("started_at")
                        if isinstance(started_at, str):
                            try:
                                started_dt = datetime.fromisoformat(started_at)
                                tool_ms = max(0, int((now - started_dt).total_seconds() * 1000))
                            except ValueError:
                                tool_ms = None
                    else:
                        tool_status = "error"
                tools_out.append(
                    {
                        "name": tool.get("name"),
                        "label": tool.get("label"),
                        "status": tool_status,
                        "started_at": tool.get("started_at"),
                        "ms": tool_ms,
                    }
                )
            rounds_out.append({"n": round_data.get("n"), "tools": tools_out,
                               "tool_count": round_data.get("tool_count"),
                               "chars": round_data.get("chars"),
                               "stage": round_data.get("stage")})

        run_out = {
            "id": run.get("id"),
            "started_at": run.get("started_at"),
            "finished_at": run.get("finished_at"),
            "status": status,
            "round": run.get("round"),
            "tokens": run.get("tokens"),
            "tools": run.get("tools"),
            "current": run.get("current") if status == "running" else None,
        }

    preview_stmt = (
        select(AssistantPreviewRequest.requested_at, AssistantPreviewRequest.taken_at)
        .where(
            AssistantPreviewRequest.session_id == session_id,
            AssistantPreviewRequest.finished_at.is_(None),
        )
        .order_by(AssistantPreviewRequest.id.desc())
        .limit(1)
    )
    preview_row = db.execute(preview_stmt).first()

    background = []
    if preview_row is not None:
        background.append(
            {
                "kind": "preview",
                "status": "running" if preview_row.taken_at else "pending",
                "since": _iso(preview_row.taken_at or preview_row.requested_at),
            }
        )

    return {
        "busy": busy,
        "model": settings.ai_model_effective,
        "run": run_out,
        "rounds": rounds_out,
        "background": background,
        "runs": runs,
    }
