"""Autonomous mode of the Asistente (feature 028): the run contract, the mode gate and the
per-run counters.

The mode is a property of the conversation (`assistant_session.mode`) and the contract is one row of
`assistant_auto_run` per run. Both are enforced here, in product code, and never by asking the model
to behave (FR-003): `offered_tool_specs`/`run_tool` in `tools.py` consult this module on every call.

Contract shape: `specs/028-autonomous-mode/contracts/run-contract.schema.json`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.i18n import t

Mode = Literal["ask", "edit", "auto"]
Stage = Literal["draft", "preview", "apply"]

LIVE_STATUSES = ("confirmed", "running")
# Stages that may only run with an `auto` mode and a live contract.
AUTO_ONLY_TOOLS = frozenset({"run_command", "apply_draft"})
# Reads allowed in `ask`: the discovery set of `tools.py` (list_sources, describe_source,
# profile_source, get_authoring_guide, get_workspace) plus the app guide, the project overview and
# the draft reader. `check_query` is allowed only without `path` (the `is_discovery()` split:
# reading a source, not checking a draft). A test asserts the parity with `DISCOVERY_TOOLS`.
DISCOVERY_NAMES = frozenset({"list_sources", "describe_source", "profile_source",
                             "get_authoring_guide", "get_workspace"})
ASK_TOOLS = frozenset(DISCOVERY_NAMES | {"get_app_guide", "get_project_overview", "read_draft"})
MAX_STOP_REASON = 120


class ContractError(ValueError):
    """A contract that the product refuses (mapped to `422 contract_invalid`)."""


class SourceAllow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    tables: list[str] = Field(default_factory=list, max_length=200)


class ContractLimits(BaseModel):
    """Optional caps of one run. `None` means "no cap": the owner asked for an Auto run that is not
    stopped by the contract ("do not limit ever"). With no caps the run ends by applying, by
    "Detener", by switching the mode down or by the round cap; there is no token budget at all.
    """

    model_config = ConfigDict(extra="forbid")

    tokens: int | None = Field(default=None, ge=10_000, le=5_000_000)
    previews: int | None = Field(default=None, ge=0, le=20)
    applies: int | None = Field(default=None, ge=0, le=5)
    wall_clock_seconds: int | None = Field(default=None, ge=60, le=7200)


class RunContract(BaseModel):
    """One authorised run: what the agent may read, do and spend before stopping."""

    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=2000)
    sources: list[SourceAllow] = Field(default_factory=list, max_length=20)
    stages: list[Stage] = Field(default_factory=lambda: ["draft", "preview", "apply"],
                                min_length=1, max_length=3)
    limits: ContractLimits = Field(default_factory=ContractLimits)
    modify_existing: bool = False
    auto_rollback: bool = True
    visible_to: list[Literal["admin", "user"]] = Field(default_factory=list, max_length=2)
    profile_id: int | None = None

    @field_validator("stages")
    @classmethod
    def _stage_order(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("stages repeats a value")
        order = {"draft": 0, "preview": 1, "apply": 2}
        return sorted(value, key=lambda stage: order[stage])

    @model_validator(mode="after")
    def _apply_needs_preview(self) -> RunContract:
        # An apply without a preview would skip the readiness gate of 014/017.
        if "apply" in self.stages and "preview" not in self.stages:
            raise ValueError("stages: apply requires preview")
        return self

    def allows_stage(self, stage: str) -> bool:
        return stage in self.stages

    def source_entry(self, name: str) -> SourceAllow | None:
        wanted = (name or "").strip().casefold()
        return next((item for item in self.sources if item.name.strip().casefold() == wanted), None)

    def summary(self) -> str:
        """The transcript line of a confirmed contract."""
        return t("assistant.contract.confirmed", stages=", ".join(self.stages))


def parse_contract(payload: Any) -> RunContract:
    """Validate a contract payload, raising `ContractError` carrying the offending fields."""
    try:
        return RunContract.model_validate(payload or {})
    except Exception as exc:  # pydantic ValidationError: report the fields, not the traceback
        fields: dict[str, str] = {}
        errors = getattr(exc, "errors", None)
        if callable(errors):
            for item in errors():
                key = ".".join(str(part) for part in item.get("loc") or ("contract",))
                fields[key] = item.get("msg") or "invalid"
        err = ContractError(t("assistant.contract.invalid"))
        err.fields = fields            # type: ignore[attr-defined]
        raise err from exc


def _contract_error(fields: dict[str, str]) -> ContractError:
    err = ContractError(t("assistant.contract.invalid"))
    err.fields = fields            # type: ignore[attr-defined]
    return err


def live_contract(session: Any) -> Any:
    """The `assistant_auto_run` row authorising this turn, or None.

    Read through the relationship-free session so the tools do not need a second query per call:
    the service loads it once into `session.auto_run`.
    """
    run = getattr(session, "auto_run", None)
    if run is None:
        return None
    return run if getattr(run, "status", None) in LIVE_STATUSES else None


def contract_of(session: Any) -> RunContract | None:
    run = live_contract(session)
    if run is None:
        return None
    try:
        return RunContract.model_validate(run.contract or {})
    except Exception:  # a stored contract always parses; never break a turn on it
        return None


def mode_of(session: Any) -> str:
    """The mode of the conversation: `ask`, `auto`, or the legacy `edit`."""
    return getattr(session, "mode", None) or "auto"


@dataclass(frozen=True)
class Refusal:
    code: str
    message: str
    limit: str | None = None

    def payload(self) -> dict[str, Any]:
        data: dict[str, Any] = {"error": self.message, "code": self.code}
        if self.limit:
            data["limit"] = self.limit
        return data


def mode_gate(session: Any, tool: str, args: dict[str, Any],
              contract: RunContract | None = None) -> Refusal | None:
    """What the current mode and contract allow for this tool call, or None when allowed."""
    mode = mode_of(session)
    if mode == "auto" and tool == "suggest_command":
        return Refusal("assistant.auto.use_run_command", t("assistant.auto.use_run_command"))
    if mode == "ask":
        allowed = tool in ASK_TOOLS
        if tool == "check_query":
            path = args.get("path")
            allowed = not (isinstance(path, str) and path.strip())
        if not allowed:
            return Refusal("assistant.mode.ask_refused", t("assistant.mode.ask_refused"))
        return None
    if tool == "apply_draft":
        if contract is None:
            return Refusal("assistant.contract.required", t("assistant.contract.required"))
        if not contract.allows_stage("apply"):
            return Refusal("assistant.contract.stage_not_allowed",
                           t("assistant.contract.stage_not_allowed"))
        return None
    if tool == "run_preview":
        if mode != "auto":
            return None            # the human button keeps its own rules (014/017)
        if contract is None:
            return Refusal("assistant.contract.required", t("assistant.contract.required"))
        if not contract.allows_stage("preview"):
            return Refusal("assistant.contract.stage_not_allowed",
                           t("assistant.contract.stage_not_allowed"))
        return None
    if tool in AUTO_ONLY_TOOLS and (mode != "auto" or contract is None):
        return Refusal("assistant.contract.required", t("assistant.contract.required"))
    if tool == "run_command":
        if contract is None or not contract.allows_stage("draft"):
            return Refusal("assistant.contract.stage_not_allowed",
                           t("assistant.contract.stage_not_allowed"))
        return None
    return None


def source_refusal(contract: RunContract | None, name: str | None,
                   table: str | None = None) -> Refusal | None:
    """The contract's source/table allow-list; an empty list means "no extra restriction"."""
    if contract is None or not contract.sources or not name:
        return None
    entry = contract.source_entry(name)
    if entry is None:
        return Refusal("assistant.contract.source_not_allowed",
                       t("assistant.contract.source_not_allowed", source=name))
    if table and entry.tables:
        allowed = {item.strip().casefold() for item in entry.tables}
        if table.strip().casefold() not in allowed:
            return Refusal("assistant.contract.source_not_allowed",
                           t("assistant.contract.source_not_allowed", source=name))
    return None


def limit_refusal(contract: RunContract | None, run: Any, *,
                  previews: int | None = None, applies: int | None = None,
                  tokens: int | None = None, wall_clock: bool = False,
                  settings: Any = None) -> Refusal | None:
    """Whether a contract limit is already reached (checked before the action, not after)."""
    if contract is None or run is None:
        return None
    limits = contract.limits
    if previews is not None and limits.previews is not None and previews > limits.previews:
        return _limit("previews")
    if applies is not None and limits.applies is not None and applies > limits.applies:
        return _limit("applies")
    if tokens is not None and limits.tokens is not None and tokens >= limits.tokens:
        return _limit("tokens")
    if wall_clock and settings is not None and limits.wall_clock_seconds is not None:
        if _elapsed_seconds(run) >= limits.wall_clock_seconds:
            return _limit("wall_clock")
    return None


def _limit(name: str) -> Refusal:
    return Refusal("assistant.contract.limit_reached",
                   t("assistant.contract.limit_reached", limit=name), limit=name)


def _elapsed_seconds(run: Any) -> float:
    started = getattr(run, "confirmed_at", None) or getattr(run, "started_at", None)
    if started is None:
        return 0.0
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - started).total_seconds())


def used_json(run: Any) -> dict[str, int]:
    """The counters the status bar shows."""
    return {
        "tokens": int(getattr(run, "tokens", 0) or 0),
        "previews": int(getattr(run, "previews", 0) or 0),
        "applies": int(getattr(run, "applies", 0) or 0),
        "elapsed_seconds": int(_elapsed_seconds(run)),
    }


def run_json(run: Any, contract: RunContract | None = None) -> dict[str, Any] | None:
    """The public face of a run for `session_json` (see contracts/auto-mode-api.md §5)."""
    if run is None:
        return None
    parsed = contract
    if parsed is None:
        try:
            parsed = RunContract.model_validate(run.contract or {})
        except Exception:
            parsed = None
    return {
        "id": run.id,
        "status": run.status,
        "stop_reason": run.stop_reason,
        "stage": run.stage,
        "limits": parsed.limits.model_dump() if parsed else {},
        "used": used_json(run),
        "stages": list(parsed.stages) if parsed else [],
        "sources": [item.model_dump() for item in parsed.sources] if parsed else [],
        "modify_existing": bool(parsed.modify_existing) if parsed else False,
        "auto_rollback": bool(parsed.auto_rollback) if parsed else True,
        "visible_to": list(parsed.visible_to) if parsed else [],
        "version_id": run.version_id,
        "summary": run.summary,
        "watch_state": run.watch_state,
    }


def pill(session: Any) -> str:
    """`contract_status` of `session_json`: none | confirmed | running | applied | stopped |
    failed (a spent contract is what the UI renders as "Auto · sin contrato")."""
    run = getattr(session, "auto_run", None)
    return run.status if run is not None else "none"


def offered_names(mode: str, contract: RunContract | None, base: frozenset[str]) -> frozenset[str]:
    """The tools the model is offered for a mode, derived from the command guard's own set."""
    if mode == "ask":
        return frozenset(base & ASK_TOOLS)
    if mode != "auto":
        return base
    base = base - {"suggest_command"}
    extra = {"run_command", "set_current_spec"}
    if contract is not None and contract.allows_stage("preview"):
        extra.add("run_preview")
    if contract is not None and contract.allows_stage("apply"):
        extra.add("apply_draft")
    if contract is None:
        extra = {"set_current_spec"}
    return frozenset(base | extra)
