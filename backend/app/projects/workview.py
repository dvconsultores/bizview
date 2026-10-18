"""Project-level working state seen by the 017 assistant modules (feature 020, research R4).

`WorkView(project, session)` answers the attributes readiness/origin/preview/tools read from a
conversation: `draft` comes from the project folder (read-only), `validation`, `query_checks` and
`preview` live on the project (shared by every conversation of the project), everything else is the
conversation's (`working_state`, `stats`, `id`, `status`, ...). Use `real(obj)` where the ORM needs
the mapped session object (`db.add`, `object_session`).
"""

from app.projects import fs

PROJECT_STATE = ("validation", "query_checks", "preview")


class WorkView:
    """Adapter (project, conversation) with the attributes of an AssistantSession."""

    def __init__(self, project, session) -> None:
        object.__setattr__(self, "project", project)
        object.__setattr__(self, "session", session)
        object.__setattr__(self, "_files", None)
        object.__setattr__(self, "command_run", None)   # feature 021: the running command

    def files(self) -> dict[str, str]:
        """Layout files of the project folder {path: text} (cached until refresh())."""
        if self._files is None:
            listed, _ = fs.list_files(self.project.slug)
            files = {}
            for path in sorted(listed):
                try:
                    files[path] = fs.read_text(self.project.slug, path)
                except (OSError, fs.ProjectPathError):
                    continue
            object.__setattr__(self, "_files", files)
        return self._files

    def refresh(self) -> None:
        """Forget the cached files (after a write)."""
        object.__setattr__(self, "_files", None)

    def next_spec(self) -> int:
        """Next spec number (`spec_seq + 1`), read fresh: writes bump it in their own session."""
        from sqlalchemy import select

        from app.db import get_sessionmaker
        from app.models import Project

        with get_sessionmaker()() as db:
            seq = db.scalar(select(Project.spec_seq).where(Project.id == self.project.id))
        return (seq or 0) + 1

    @property
    def draft(self) -> dict | None:
        files = self.files()
        return {"files": files, "summary": self.project.name} if files else None

    def __getattr__(self, name):
        if name in PROJECT_STATE:
            return getattr(self.project, name)
        return getattr(self.session, name)

    def __setattr__(self, name, value) -> None:
        if name in PROJECT_STATE:
            setattr(self.project, name, value)
            _persist(self.project.id, name, value)
        elif name == "command_run":
            object.__setattr__(self, name, value)
        elif name == "draft":
            raise AttributeError("draft is read-only: write project files with fs.apply_ops")
        else:
            setattr(self.session, name, value)


def _persist(project_id: int, name: str, value) -> None:
    """Write one project-level state column in its own short transaction.

    The conversation's transaction never locks the project row: `fs.apply_ops` (own session)
    updates it on every write, and a lock held by the caller's open transaction would block it.
    """
    from sqlalchemy import update

    from app.db import get_sessionmaker
    from app.models import Project

    with get_sessionmaker()() as db:
        db.execute(update(Project).where(Project.id == project_id).values({name: value}))
        db.commit()


def real(obj):
    """The mapped AssistantSession behind a WorkView (or obj itself)."""
    return obj.session if isinstance(obj, WorkView) else obj


def for_session(db, session) -> WorkView:
    """WorkView of a conversation and its project (the project is detached from `db`)."""
    from app.models import Project

    project = db.get(Project, session.project_id)
    if project is not None:
        db.expunge(project)
    return WorkView(project, session)
