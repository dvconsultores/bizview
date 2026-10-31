"""The working state validation, readiness and origin checks read from a project.

`WorkView(project)` answers the attributes those modules need: `draft` comes from the project
folder (read-only), while `validation` and `query_checks` live on the project row. Feature 045
removed the conversation and the draft preview that used to sit behind this adapter.
"""

from typing import ClassVar

from app.projects import fs

PROJECT_STATE = ("validation", "query_checks")


class WorkView:
    """The project's own working state."""

    def __init__(self, project) -> None:
        object.__setattr__(self, "project", project)
        object.__setattr__(self, "_files", None)

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

    @property
    def id(self):
        return self.project.id

    @property
    def description(self):
        return self.project.description

    # Without a conversation there is no working state and no run statistics to read.
    working_state: ClassVar[dict] = {}
    stats: ClassVar[dict] = {}

    def __getattr__(self, name):
        if name in PROJECT_STATE:
            return getattr(self.project, name)
        raise AttributeError(name)

    def __setattr__(self, name, value) -> None:
        if name in PROJECT_STATE:
            setattr(self.project, name, value)
            _persist(self.project.id, name, value)
        elif name == "draft":
            raise AttributeError("draft is read-only: write project files with fs.apply_ops")
        else:
            raise AttributeError(name)


def _persist(project_id: int, name: str, value) -> None:
    """Write one project-level state column in its own short transaction.

    The request's transaction never locks the project row: `fs.apply_ops` (own session) updates
    it on every write, and a lock held by the caller's open transaction would block it.
    """
    from sqlalchemy import update

    from app.db import get_sessionmaker
    from app.models import Project

    with get_sessionmaker()() as db:
        db.execute(update(Project).where(Project.id == project_id).values({name: value}))
        db.commit()


def real(obj):
    """The mapped Project behind a WorkView (or obj itself)."""
    return obj.project if isinstance(obj, WorkView) else obj
