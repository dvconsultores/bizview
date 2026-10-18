"""File revisions of BI projects and external changes (feature 020, plan section 3)."""

import hashlib
import uuid

from sqlalchemy import select

from app.models import ProjectFileRevision

# Actor dict keys: kind (user|agent|system|external|git), user_id, session_id, command
Actor = dict


def sha(text: str) -> str:
    """Return SHA-256 hex digest of UTF-8 encoded text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record(
    db,
    project_id: int,
    path: str,
    op: str,
    content: str | None,
    actor: dict,
    *,
    group_id: uuid.UUID,
    renamed_from: str | None = None,
    restored_from: int | None = None,
) -> ProjectFileRevision:
    """Create and flush a ProjectFileRevision row."""
    deleted = op == "delete"
    row = ProjectFileRevision(
        project_id=project_id,
        path=path,
        op=op,
        sha256=None if deleted else sha(content),
        content=None if deleted else content,
        size=0 if deleted else len(content.encode("utf-8")),
        renamed_from=renamed_from,
        restored_from=restored_from,
        actor_kind=actor["kind"],
        actor_id=actor.get("user_id"),
        command=(actor.get("command") or "edit")[:60],
        session_id=actor.get("session_id"),
        command_run_id=actor.get("command_run_id"),
        group_id=group_id,
    )
    db.add(row)
    db.flush()
    return row


def latest(db, project_id: int, path: str) -> ProjectFileRevision | None:
    """Return newest revision for a path."""
    return db.scalars(
        select(ProjectFileRevision)
        .where(ProjectFileRevision.project_id == project_id, ProjectFileRevision.path == path)
        .order_by(ProjectFileRevision.id.desc())
        .limit(1)
    ).first()


def file_map(db, project_id: int) -> dict[str, str]:
    """Return current live files {path: sha256} excluding deleted."""
    stmt = (
        select(ProjectFileRevision.path, ProjectFileRevision.op, ProjectFileRevision.sha256)
        .where(ProjectFileRevision.project_id == project_id)
        .order_by(ProjectFileRevision.path, ProjectFileRevision.id.desc())
        .distinct(ProjectFileRevision.path)
    )
    return {p: digest for p, op, digest in db.execute(stmt) if op != "delete"}


def sync_external(db, project) -> list[ProjectFileRevision]:
    """Detect and record revisions for external file changes; return new revisions."""
    from app.projects import fs

    files, _ = fs.list_files(project.slug)
    known = file_map(db, project.id)
    group = uuid.uuid4()
    actor = {"kind": "external", "user_id": None, "session_id": None, "command": "external"}
    new_revisions = []
    for path in sorted(files):
        if known.get(path) != files[path][1]:
            try:
                content = fs.read_text(project.slug, path)
            except fs.ProjectPathError:
                continue
            new_revisions.append(
                record(db, project.id, path, "external", content, actor, group_id=group))
    for path in sorted(known):
        if path not in files:
            new_revisions.append(
                record(db, project.id, path, "delete", None, actor, group_id=group))
    return new_revisions


HISTORY_EVENTS = ("project_applied", "project_withdrawn", "project_imported")


def _rev_json(rev, names: dict[int, str]) -> dict:
    return {"id": rev.id, "path": rev.path, "op": rev.op, "actor": rev.actor_kind,
            "actor_name": names.get(rev.actor_id) if rev.actor_kind == "user" else None,
            "command": rev.command, "session_id": rev.session_id,
            "command_run_id": rev.command_run_id,
            "restored_from": rev.restored_from, "renamed_from": rev.renamed_from,
            "size": rev.size, "sha256": rev.sha256, "time": rev.created_at.isoformat()}


def list_revisions(db, project_id: int, *, path: str | None = None, spec: str | None = None,
                   before_id: int | None = None, limit: int = 50) -> dict:
    """Newest-first revision groups (one per `apply_ops` call) merged with apply events."""
    from app.models import AppUser, AuditEvent

    limit = max(1, min(limit, 100))
    query = select(ProjectFileRevision).where(ProjectFileRevision.project_id == project_id)
    if path:
        query = query.where(ProjectFileRevision.path == path)
    if spec:
        query = query.where(ProjectFileRevision.path.like(f"specs/{spec}/%"))
    if before_id is not None:
        query = query.where(ProjectFileRevision.id < before_id)
    revisions = db.scalars(query.order_by(ProjectFileRevision.id.desc()).limit(limit)).all()

    events = select(AuditEvent).where(AuditEvent.kind.in_(HISTORY_EVENTS),
                                      AuditEvent.detail["project_id"].as_integer() == project_id)
    if len(revisions) == limit:
        events = events.where(AuditEvent.occurred_at >= revisions[-1].created_at)
    if before_id is not None:
        upper = db.scalar(select(ProjectFileRevision.created_at)
                          .where(ProjectFileRevision.id == before_id))
        if upper is not None:
            events = events.where(AuditEvent.occurred_at < upper)
    audit_rows = db.scalars(events).all() if not (path or spec) else []

    ids = {r.actor_id for r in revisions if r.actor_id} | {e.actor_id for e in audit_rows
                                                           if e.actor_id}
    names = ({u.id: u.full_name for u in db.scalars(select(AppUser).where(AppUser.id.in_(ids)))}
             if ids else {})
    groups: list[dict] = []
    for rev in revisions:
        if not groups or groups[-1]["group_id"] != str(rev.group_id):
            groups.append({"group_id": str(rev.group_id), "actor": rev.actor_kind,
                           "actor_name": names.get(rev.actor_id) if rev.actor_kind == "user"
                           else None,
                           "command": rev.command, "session_id": rev.session_id,
                           "command_run_id": rev.command_run_id,
                           "time": rev.created_at.isoformat(), "files": []})
        groups[-1]["files"].append(_rev_json(rev, names))
    items = groups + [{"event": e.kind, "time": e.occurred_at.isoformat(),
                       "actor_name": names.get(e.actor_id), "version": e.detail.get("version")}
                      for e in audit_rows]
    items.sort(key=lambda item: item["time"], reverse=True)
    return {"items": items,
            "next_before": revisions[-1].id if len(revisions) == limit else None}


def diff(a: str | None, b: str | None, *, context: int = 3, cap: int = 5000) -> dict:
    """Line hunks from `a` to `b` (None = empty), at most `cap` lines."""
    import difflib

    a_lines, b_lines = (a or "").splitlines(), (b or "").splitlines()
    matcher = difflib.SequenceMatcher(None, a_lines, b_lines, autojunk=False)
    hunks: list[dict] = []
    total = 0
    for group in matcher.get_grouped_opcodes(context):
        lines: list[dict] = []
        hunks.append({"a_start": group[0][1] + 1, "b_start": group[0][3] + 1, "lines": lines})
        for tag, i1, i2, j1, j2 in group:
            chunk = ([(" ", t) for t in a_lines[i1:i2]] if tag == "equal" else
                     [("-", t) for t in a_lines[i1:i2]] + [("+", t) for t in b_lines[j1:j2]])
            for kind, text in chunk:
                if total >= cap:
                    return {"hunks": hunks, "truncated": True}
                lines.append({"t": kind, "text": text})
                total += 1
    return {"hunks": hunks, "truncated": False}


def get_revision(db, project_id: int, revision_id: int) -> ProjectFileRevision | None:
    return db.scalar(select(ProjectFileRevision).where(
        ProjectFileRevision.project_id == project_id, ProjectFileRevision.id == revision_id))


def restore(db, project, revision_id: int, base_sha256: str | None, actor: dict) -> list[dict]:
    """Bring a file back to a revision (a delete revision deletes the file again)."""
    from app.i18n import M
    from app.projects import fs

    rev = get_revision(db, project.id, revision_id)
    if rev is None:
        raise fs.ProjectPathError("file_not_found",
                                  M("projects.file_not_found", path=str(revision_id)))
    actor = {**actor, "command": "restore"}
    if rev.op == "delete":
        return fs.apply_ops(project.id, [{"op": "delete", "path": rev.path,
                                          "base_sha256": base_sha256}], actor)
    return fs.apply_ops(project.id, [{"op": "write", "path": rev.path, "content": rev.content,
                                      "base_sha256": base_sha256, "force": False,
                                      "restored_from": rev.id}], actor)


def spec_timeline(db, project, folder: str) -> dict:
    """Stage dates of a spec folder from its revisions and versions, and its conversations."""
    from app.models import AssistantSession, WorkspaceVersion
    from app.projects import specs

    prefix = f"specs/{folder}/"
    revisions = db.scalars(select(ProjectFileRevision).where(
        ProjectFileRevision.project_id == project.id,
        ProjectFileRevision.path.like(f"{prefix}%")).order_by(ProjectFileRevision.id)).all()
    live = [r for r in revisions if r.op != "delete"]

    def first(path: str, test=lambda r: True):
        return next((r for r in live if r.path == f"{prefix}{path}" and test(r)), None)

    def clarified(rev) -> bool:
        return specs._command(rev.command) == "speckit-clarify" or (
            rev.content is not None and specs.parse_spec(rev.content)["clarified"])

    found = [
        ("especificada", first("spec.md")),
        ("aclarada", first("spec.md", clarified)),
        ("planificada", first("plan.md")),
        ("tareas", first("tasks.md")),
        ("implementada", first("tasks.md", lambda r: r.content is not None
                               and specs.open_tasks(r.content) == 0)),
    ]
    stages = [{"stage": name, "time": rev.created_at.isoformat()} for name, rev in found if rev]
    for version in db.scalars(select(WorkspaceVersion).order_by(WorkspaceVersion.applied_at)):
        files = ((version.projects or {}).get(project.slug) or {}).get("files") or {}
        if any(p.startswith(prefix) for p in files):
            stages.append({"stage": "aplicada", "time": version.applied_at.isoformat(),
                           "version": version.id})
    stages.sort(key=lambda s: s["time"])
    session_ids = {r.session_id for r in revisions if r.session_id is not None}
    sessions = db.scalars(select(AssistantSession).where(
        AssistantSession.id.in_(session_ids) | ((AssistantSession.project_id == project.id)
                                                & (AssistantSession.current_spec == folder))
    ).order_by(AssistantSession.id)).all()
    return {"folder": folder, "stages": stages,
            "conversations": [{"id": s.id, "title": s.title} for s in sessions]}
