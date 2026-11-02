"""The import allowances of this installation (feature 049).

The measurement itself lives in `cli/bizview_cli/budgets.py`, which the CLI, the ZIP importer and
the file writer all call: the constitution makes the layout the single source of the authoring
contract, and two answers to "how big may this be" is exactly how the reported defect happened.
This module adds the one thing the CLI cannot know — which numbers *this installation* uses.

Resolution is a chain, most specific first:

    the stored row (`project_limits`)  →  `Settings` (the deployment defaults)  →  the package
    default

A NULL column means "inherit", so an operator who raised `PROJECT_MAX_MB` in `.env` keeps that
value until a super user writes an explicit number in the app.
"""

from __future__ import annotations

from bizview_cli import budgets as shared
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ApiError
from app.i18n import M
from app.models import ProjectLimits
from app.services import audit

#: Column → the `Settings` field it inherits from when the column is NULL.
FIELDS = {
    "artifact_max_files": "project_max_files",
    "artifact_max_kb": "project_max_kb",
    "artifact_max_mb": "project_max_mb",
    "asset_max_files": "project_asset_max_files",
    "asset_max_kb": "project_asset_max_kb",
    "asset_max_mb": "project_asset_max_mb",
}


def _row(db: Session) -> ProjectLimits:
    row = db.get(ProjectLimits, 1)
    if row is None:                       # a database restored from before 0047, or a test truncate
        row = ProjectLimits(id=1)
        db.add(row)
        db.flush()
    return row


def stored(db: Session) -> dict:
    """The raw overrides, `None` where this installation inherits."""
    row = _row(db)
    return {column: getattr(row, column) for column in FIELDS}


def effective(db: Session) -> dict[str, shared.Budget]:
    """Both allowances as this installation applies them, overrides resolved."""
    overrides = stored(db)
    settings = get_settings()
    values = {name: {} for name in (shared.layout.ARTIFACTS, shared.layout.ASSETS)}
    for column, setting in FIELDS.items():
        name = shared.layout.ASSETS if column.startswith("asset_") else shared.layout.ARTIFACTS
        chosen = overrides[column]
        values[name][column.split("_", 1)[1]] = (
            chosen if chosen is not None else getattr(settings, setting))
    return {name: shared.as_budget(name, fields) for name, fields in values.items()}


def zip_max_mb(limits: dict[str, shared.Budget]) -> int:
    """The archive may carry both allowances: anything smaller is not the zip's fault."""
    return sum(budget.max_mb for budget in limits.values())


def json(limits: dict[str, shared.Budget], overrides: dict) -> dict:
    """The `GET /api/projects/limits` body: what applies, and what is stored."""
    return {
        "artifacts": limits[shared.layout.ARTIFACTS].as_json(),
        "assets": limits[shared.layout.ASSETS].as_json(),
        "zip_max_mb": zip_max_mb(limits),
        "stored": overrides,
    }


def validate(values: dict) -> dict:
    """Field problems for a `PUT`: the user reads a field error instead of a 500 from the CHECK."""
    problems: dict[str, str] = {}
    for column in FIELDS:
        value = values.get(column)
        if value is not None and value < 1:
            problems[column] = "must_be_positive"
    for prefix in ("artifact", "asset"):
        kb, mb = values.get(f"{prefix}_max_kb"), values.get(f"{prefix}_max_mb")
        if kb is not None and mb is not None and kb > mb * 1024:
            problems[f"{prefix}_max_kb"] = "greater_than_total"
    return problems


def store(db: Session, values: dict, actor) -> dict:
    """Write the six overrides (a `None` clears one) and audit the change."""
    problems = validate(values)
    if problems:
        raise ApiError(422, "invalid", M("projects.limits_invalid"), fields=problems)
    row = _row(db)
    before = stored(db)
    for column in FIELDS:
        setattr(row, column, values.get(column))
    row.updated_by = actor.id
    db.flush()
    after = stored(db)
    audit.record(db, "project_limits_changed", actor_id=actor.id, target_id=None,
                 detail={"before": before, "after": after})
    return json(effective(db), after)
