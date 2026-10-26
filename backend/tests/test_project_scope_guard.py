"""Feature 037 FR-012: a query on a project-scoped model filters by its project.

The incident was not a single wrong line: it was a payload that carried another project's rows
because nothing forced a query to name its project. This guard reads the backend with `ast` and
fails when a `select(<project-scoped model>)` is written without `project_id` or `session_id` in
the statement. The allowlist lists the call sites that are installation-wide by definition — each
with the reason — so a new one has to be justified here, in the code review, not forgotten.
"""
from __future__ import annotations

import ast
from pathlib import Path

import app

APP_DIR = Path(app.__file__).parent
SCOPED = {
    "AssistantSession",
    "AssistantPreviewRequest",
    "AssistantCommandRun",
    "AssistantAutoRun",
    "AssistantRunProfile",
    "ProjectFileRevision",
}

# file (relative to app/) → function → why the scope is not a project.
ALLOWED = {
    ("api/assistant.py", "list_sessions"):
        "the caller's own conversations across projects (the history page); `?project=` filters",
    ("api/assistant.py", "list_run_profiles"):
        "run profiles are installation-wide contract prefills (stages, limits, source names)",
    ("api/assistant.py", "create_run_profile"):
        "the unique-name check of an installation-wide profile",
    ("api/assistant.py", "update_run_profile"):
        "the unique-name check of an installation-wide profile",
    ("projects/importer.py", "import_open_drafts"):
        "feature 020 migration: turns pre-020 conversations into projects, across all of them",
    ("assistant/preview.py", "cleanup_stale"):
        "hourly housekeeping of every project's preview schema",
    ("worker.py", "take_preview_requests"):
        "the worker's queue is installation-wide: it takes work orders, it does not act on a page",
    ("worker.py", "_resolve_auto_watch"):
        "the scheduler reacts to a new version for every project watching an integration",
}


def _segments(src: str):
    """Every call to `select(<scoped model>)` with its source statement and enclosing function."""
    tree = ast.parse(src)
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def enclosing(node) -> tuple[ast.stmt, str | None]:
        statement, function = None, None
        while node in parents:
            node = parents[node]
            if statement is None and isinstance(node, ast.stmt):
                statement = node
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function = node.name
                break
        return statement, function

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "select"):
            continue
        target = node.args[0]
        if not (isinstance(target, ast.Name) and target.id in SCOPED):
            continue
        statement, function = enclosing(node)
        yield target.id, statement, function


def _offending() -> list[str]:
    bad = []
    for path in sorted(APP_DIR.rglob("*.py")):
        rel = path.relative_to(APP_DIR).as_posix()
        src = path.read_text(encoding="utf-8")
        for model, statement, function in _segments(src):
            segment = ast.get_source_segment(src, statement) if statement is not None else ""
            segment = segment or ""
            if "project_id" in segment or "session_id" in segment:
                continue
            if (rel, function) in ALLOWED:
                continue
            bad.append(f"{rel}:{getattr(statement, 'lineno', '?')} {function}() selects {model} "
                       "without a project filter")
    return bad


def test_no_project_scoped_query_is_written_without_its_project():
    bad = _offending()
    assert bad == [], "\n".join(bad)


def test_the_allowlist_does_not_rot():
    """Every allowlisted site still exists: a renamed function must be reviewed, not ignored."""
    seen = set()
    for path in sorted(APP_DIR.rglob("*.py")):
        rel = path.relative_to(APP_DIR).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                seen.add((rel, node.name))
    missing = sorted(site for site in ALLOWED if site not in seen)
    assert missing == [], missing
