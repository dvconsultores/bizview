"""Applying a validator's deterministic fix to a project file (feature 035).

A problem that publishes `fix_data` (`{file, json_path, op, value}`) is fully understood by the
validator, so the product can correct it without an AI — which is the point: the session that cost
a working day could not be fixed because the only path to the fix ran through the provider that was
down.

Every write goes through `fs.apply_ops`, the manual-edit path, so it gets a revision, a base check
and the project's own bookkeeping; the audit keeps the problem code that motivated it.
"""
from __future__ import annotations

import yaml
from bizview_cli import fixops
from bizview_cli.fixops import FixError

from app.errors import ApiError
from app.i18n import M

MAX_FIXES = 50
SCOPE_CODES = ("path_outside_project", "path_not_allowed", "path_unsafe")


def _path_error(e) -> ApiError:
    """A path that is not this project's own: a client error, never «the file is gone» (037)."""
    status = 422 if e.code in SCOPE_CODES else 404
    return ApiError(status, e.code, e.message)


def _normalise(fixes: list[dict]) -> list[dict]:
    """Validate the shape of each requested fix (the client sends back what validation gave it)."""
    if not isinstance(fixes, list) or not fixes:
        raise ApiError(422, "validation", M("projects.fix_malformed"))
    if len(fixes) > MAX_FIXES:
        raise ApiError(422, "validation", M("projects.fix_too_many", max=MAX_FIXES))
    out = []
    for fix in fixes:
        if not isinstance(fix, dict):
            raise ApiError(422, "validation", M("projects.fix_malformed"))
        if not isinstance(fix.get("file"), str) or not fix["file"].strip():
            raise ApiError(422, "validation", M("projects.fix_malformed"))
        if fix.get("op") not in fixops.OPS:
            raise ApiError(422, "validation", M("projects.fix_malformed"))
        if not fixops.is_content_fix(fix):
            # Feature 040 (B): a fix changes content, never evidence — no fix marks a task or
            # rewrites `**Status**:`, not even one hand-crafted by a client.
            raise ApiError(422, "fix_not_content",
                           M("projects.fix_not_content", path=fix.get("json_path") or "/"))
        if not isinstance(fix.get("json_path"), str):
            raise ApiError(422, "validation", M("projects.fix_malformed"))
        problem = fix.get("problem_id")
        if isinstance(problem, str) and problem:
            # `problem_id` is `code:file:json_path`: a fix must carry the id of the problem it
            # belongs to, so an id of another file (or another project) cannot be attached (037).
            parts = problem.split(":", 2)
            if len(parts) != 3 or (parts[1] and parts[1] != fix["file"]):
                raise ApiError(422, "validation", M("projects.fix_malformed"))
        out.append({"file": fix["file"], "json_path": fix["json_path"], "op": fix["op"],
                    "value": fix.get("value"), "base_sha256": fix.get("base_sha256"),
                    "problem_id": fix.get("problem_id")})
    return out


def apply_fixes(db, actor, project, fixes: list[dict], ip: str | None,
                installation_palette: str | None = None) -> dict:
    """Apply the fixes and answer the new state: results, diffs, validation, readiness, project.

    Refuses (writing nothing) when a file no longer holds what validation saw: the reader ran
    «comprobar» on one version of the file and something changed it since.
    """
    from app.projects import fs, history
    from app.projects import service as projects
    from app.services.audit import record as audit_record

    wanted = _normalise(fixes)
    projects.ensure_editable(project)
    per_file: dict[str, list[dict]] = {}
    for fix in wanted:
        per_file.setdefault(fix["file"], []).append(fix)

    before_text: dict[str, str] = {}
    for path, items in per_file.items():
        # Feature 037: the path comes from a validation payload, so it is data, not a promise. It is
        # resolved from the project's own row and must be a path *of this project*: a composed
        # `projects/<other>/…` is refused as outside the project (it used to be reported as a
        # missing file, which is what «El archivo … ya no existe» said on the artemisa page).
        try:
            fs.resolve_project_path(project.id, path, db=db)
            text = fs.read_text(project.slug, path)
        except FileNotFoundError:
            raise ApiError(409, "fix_not_applicable", M("projects.fix_gone", file=path)) from None
        except fs.ProjectPathError as e:
            raise _path_error(e) from None
        except OSError:
            raise ApiError(409, "fix_not_applicable", M("projects.fix_gone", file=path)) from None
        current = history.sha(text)
        for item in items:
            if item["base_sha256"] and item["base_sha256"] != current:
                raise ApiError(409, "fix_stale", M("projects.fix_stale"))
        before_text[path] = text

    ops, diffs = [], []
    for path, items in per_file.items():
        text = before_text[path]
        try:
            document = yaml.safe_load(text)
        except yaml.YAMLError:
            raise ApiError(409, "fix_not_applicable", M("projects.fix_unreadable", file=path)) \
                from None
        if not isinstance(document, (dict, list)):
            raise ApiError(409, "fix_not_applicable", M("projects.fix_unreadable", file=path))
        for item in items:
            value = item["value"]
            if item.get("problem_id", "").startswith("layout_palette_missing") \
                    and installation_palette:
                value = installation_palette        # the installation's preset, not the product's
            try:
                fixops.apply_fix(document, item["json_path"], item["op"], value)
            except FixError as e:
                raise ApiError(409, "fix_not_applicable",
                               M("projects.fix_not_applicable", detail=str(e))) from None
        new_text = yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
        ops.append({"op": "write", "path": path, "content": new_text,
                    "base_sha256": history.sha(text)})
        diffs.append({"file": path, "before": text, "after": new_text,
                      "problems": [i.get("problem_id") for i in items]})

    try:
        written = fs.apply_ops(project.id, ops, {"kind": "user", "user_id": actor.id,
                                                 "session_id": None, "command": "fix"})
    except fs.ProjectPathError as e:
        raise ApiError(409, "fix_stale", M("projects.fix_stale")) from e

    for item, result in zip(written, ops, strict=False):
        audit_record(db, "project_fix_applied", actor_id=actor.id, ip=ip,
                     detail={"project": project.slug, "file": result["path"],
                             "revision": item.get("revision_id"),
                             "problems": [f.get("problem_id") for f in per_file[result["path"]]]})

    state = projects.revalidate(db, project)
    return {"results": [{"file": d["file"], "revision_id": w.get("revision_id"),
                         "diff": _diff(d["before"], d["after"]), "problems": d["problems"]}
                        for d, w in zip(diffs, written, strict=False)],
            **state}


def _diff(before: str, after: str, limit: int = 40) -> str:
    """A short unified diff for the interface (the applied change, not the whole file)."""
    import difflib

    lines = list(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                      lineterm="", n=2))[2:]
    if len(lines) > limit:
        lines = [*lines[:limit], "…"]
    return "\n".join(lines)
