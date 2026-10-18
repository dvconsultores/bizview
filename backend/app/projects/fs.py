"""Safe file access inside project folders (feature 020, research R2)."""

import hashlib
import logging
import os
import secrets
import stat
from pathlib import Path

from bizview_cli import layout

from app.config import get_settings
from app.i18n import M

MAX_FILE_BYTES = 512 * 1024
MAX_FILES = 400
MAX_PATH = 240
CONSTITUTION = ".specify/memory/constitution.md"
TRASH = ".papelera"


class ProjectPathError(Exception):
    """Error raised for invalid or unsafe project paths."""

    def __init__(self, code: str, message: "M"):
        self.code = code
        self.message = message
        super().__init__(code)

    def __str__(self) -> str:
        return str(self.message)


def _unsafe(path: str) -> ProjectPathError:
    return ProjectPathError("path_unsafe", M("projects.path_unsafe", path=path))


def projects_dir() -> Path:
    """Return the configured projects directory, refusing symlinks."""
    path = Path(get_settings().projects_dir)
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return path
    if stat.S_ISLNK(mode):
        raise _unsafe("PROJECTS_DIR")
    return path


def project_root(slug: str) -> Path:
    """Return the root path for a project slug, refusing unsafe slugs and symlinks."""
    if not layout.ID_RE.match(slug):
        raise _unsafe(slug)
    root = projects_dir() / slug
    try:
        mode = os.lstat(root).st_mode
    except FileNotFoundError:
        return root
    if stat.S_ISLNK(mode):
        raise _unsafe(slug)
    return root


def check_rel(rel: str) -> list[str]:
    """Validate a project-relative path and return its parts."""
    if not rel or rel.startswith("/") or "\\" in rel or "\x00" in rel or len(rel) > MAX_PATH:
        raise _unsafe(rel)
    parts = rel.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise _unsafe(rel)
    if any(part.startswith(".") for part in parts) and rel not in (
        CONSTITUTION,
        ".specify",
        ".specify/memory",
    ):
        raise _unsafe(rel)
    return parts


def resolve(slug: str, rel: str, *, folder: bool = False) -> Path:
    """Resolve a project-relative path, enforcing safety and layout rules."""
    parts = check_rel(rel)
    allowed = layout.is_allowed_folder(rel) if folder else layout.is_allowed(rel)
    if not allowed:
        raise ProjectPathError(
            "path_not_allowed",
            M("projects.path_not_allowed", path=rel, allowed=layout.ALLOWED_TEXT),
        )
    root = project_root(slug)
    for component in [
        root,
        *[root.joinpath(*parts[:i]) for i in range(1, len(parts) + 1)],
    ]:
        try:
            mode = os.lstat(component).st_mode
        except FileNotFoundError:
            break
        if stat.S_ISLNK(mode):
            raise _unsafe(rel)
        if not stat.S_ISDIR(mode) and component != root.joinpath(*parts):
            raise _unsafe(rel)
    target = root.joinpath(*parts)
    if (
        os.path.commonpath([os.path.realpath(root), os.path.realpath(target)])
        != os.path.realpath(root)
    ):
        raise _unsafe(rel)
    return target


def _read_bytes(target: Path) -> bytes:
    """Read a regular file without following a final symlink."""
    fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        return f.read()


def read_text(slug: str, rel: str) -> str:
    """Read a UTF-8 text file safely from a project."""
    target = resolve(slug, rel)
    fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
    f = os.fdopen(fd, "rb")
    with f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode):
            raise _unsafe(rel)
        if st.st_size > MAX_FILE_BYTES:
            raise ProjectPathError(
                "too_large", M("projects.too_large", path=rel, max="512 KB")
            )
        data = f.read()
    if b"\x00" in data:
        raise ProjectPathError("not_text", M("projects.not_text", path=rel))
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ProjectPathError("not_text", M("projects.not_text", path=rel)) from None


def list_files(slug: str) -> tuple[dict[str, tuple[int, str]], list[str]]:
    """List project files with sizes and hashes, ignoring symlinks and the trash folder."""
    root = project_root(slug)
    if not root.is_dir():
        return ({}, [])
    files: dict[str, tuple[int, str]] = {}
    ignored: list[str] = []
    for dirpath, dirnames, _filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != TRASH or Path(dirpath) != root]
        for entry in os.scandir(dirpath):
            rel_path = Path(entry.path).relative_to(root).as_posix()
            if entry.is_symlink():
                ignored.append(rel_path)
                continue
            if entry.is_dir(follow_symlinks=False):
                continue
            if entry.is_file(follow_symlinks=False):
                if layout.is_allowed(rel_path):
                    try:
                        data = _read_bytes(Path(entry.path))
                        files[rel_path] = (len(data), hashlib.sha256(data).hexdigest())
                    except OSError:
                        ignored.append(rel_path)
                else:
                    ignored.append(rel_path)
    return (files, sorted(ignored))


def check_limits(slug: str, rel: str, data: bytes, current: dict[str, tuple[int, str]]) -> None:
    """Check file size, content, and project limits before writing."""
    if len(data) > MAX_FILE_BYTES:
        raise ProjectPathError("too_large", M("projects.too_large", path=rel, max="512 KB"))
    if b"\x00" in data:
        raise ProjectPathError("not_text", M("projects.not_text", path=rel))
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        raise ProjectPathError("not_text", M("projects.not_text", path=rel)) from None
    max_mb = get_settings().project_max_mb
    too_large = ProjectPathError(
        "project_too_large", M("projects.project_too_large", max_mb=max_mb, max_files=MAX_FILES))
    if rel not in current and len(current) >= MAX_FILES:
        raise too_large
    total = sum(size for p, (size, _) in current.items() if p != rel) + len(data)
    if total > max_mb * 1024 * 1024:
        raise too_large


def _mkdirs(root: Path, parts: list[str]) -> None:
    """Create project directories safely without following symlinks."""
    projects_dir()
    os.makedirs(root, mode=0o750, exist_ok=True)
    if stat.S_ISLNK(os.lstat(root).st_mode):
        raise _unsafe(root.name)
    current = root
    for i, part in enumerate(parts, start=1):
        current = current / part
        try:
            os.mkdir(current, 0o750)
        except FileExistsError:
            pass
        mode = os.lstat(current).st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise _unsafe("/".join(parts[:i]))


def write_atomic(slug: str, rel: str, text: str) -> tuple[bytes | None, str]:
    """Atomically write a UTF-8 text file to a project; returns (previous bytes, new sha256)."""
    target = resolve(slug, rel)
    data = text.encode("utf-8")
    previous = _read_bytes(target) if target.exists() else None
    parts = check_rel(rel)
    _mkdirs(project_root(slug), parts[:-1])
    tmp = target.parent / f".{parts[-1]}.{secrets.token_hex(6)}.tmp"
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except OSError as e:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise ProjectPathError("not_writable", M("projects.not_writable")) from e
    return (previous, hashlib.sha256(data).hexdigest())


def restore_bytes(slug: str, rel: str, previous: bytes | None) -> None:
    """Best-effort restore of a file after a failed transaction."""
    logger = logging.getLogger("app")
    try:
        target = resolve(slug, rel)
        if previous is None:
            if target.exists():
                target.unlink()
                prune(slug, str(Path(rel).parent) if "/" in rel else "")
        else:
            tmp = target.parent / f".{Path(rel).name}.{secrets.token_hex(6)}.tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
            with os.fdopen(fd, "wb") as f:
                f.write(previous)
                os.fsync(f.fileno())
            os.replace(tmp, target)
    except Exception:
        logger.exception("Failed to restore a project file (%s)", slug)


def remove(slug: str, rel: str) -> bytes | None:
    """Remove a file from a project and prune empty parent directories."""
    target = resolve(slug, rel)
    previous = None
    if target.exists():
        previous = _read_bytes(target)
        try:
            os.unlink(target)
        except OSError as e:
            raise ProjectPathError("not_writable", M("projects.not_writable")) from e
    root = project_root(slug)
    current = target.parent
    while current != root:
        try:
            os.rmdir(current)
        except OSError:
            break
        current = current.parent
    return previous


def make_folder(slug: str, rel: str) -> None:
    """Create a folder inside a project."""
    resolve(slug, rel, folder=True)
    _mkdirs(project_root(slug), check_rel(rel))


def remove_folder(slug: str, rel: str) -> list[str]:
    """Return the list of project-relative files under a folder (caller deletes)."""
    resolve(slug, rel, folder=True)
    files, _ = list_files(slug)
    prefix = rel.rstrip("/") + "/"
    return sorted(p for p in files if p.startswith(prefix))


def prune(slug: str, rel: str) -> None:
    """Remove empty directories from rel upwards, never the project root."""
    root = project_root(slug)
    target = root.joinpath(*check_rel(rel)) if rel else root
    current = target
    while current != root:
        try:
            if current.is_symlink() or not current.is_dir():
                break
            os.rmdir(current)
        except OSError:
            break
        current = current.parent


def check_dir() -> bool:
    """Ensure the projects directory exists and is writable."""
    try:
        path = projects_dir()
        os.makedirs(path, mode=0o750, exist_ok=True)
        return os.access(path, os.W_OK)
    except (OSError, ProjectPathError):
        return False


class FileChanged(ProjectPathError):
    """Raised when base_sha256 does not match the current revision (research R5)."""

    def __init__(self, path: str, current: dict):
        super().__init__(
            "file_changed",
            M("projects.file_changed", path=path, author=current.get("author") or "?",
              time=current.get("time") or "?"),
        )
        self.current = dict(current)


def _spec_folder(path: str) -> str | None:
    """Return the spec folder name if path is inside a spec folder."""
    parts = path.split("/")
    if len(parts) >= 2 and parts[0] == "specs" and layout.SPEC_FOLDER_RE.match(parts[1]):
        return parts[1]
    return None


def apply_ops(project_id: int, ops: list[dict], actor: dict) -> list[dict]:
    """Apply ordered file operations atomically, recording history (research R5, R6)."""
    import uuid
    from datetime import UTC, datetime

    from sqlalchemy import text as sql_text

    from app.db import get_sessionmaker, lock_key
    from app.models import AppUser, Project
    from app.projects import history

    with get_sessionmaker()() as db:
        db.execute(
            sql_text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": lock_key("project", project_id)},
        )
        project = db.get(Project, project_id)
        if project is None or project.deleted_at is not None:
            raise _unsafe(str(project_id))
        slug = project.slug

        history.sync_external(db, project)
        current = history.file_map(db, project.id)
        sizes, _ = list_files(slug)

        specs_dir = project_root(slug) / "specs"
        existing_folders = {f for f in (_spec_folder(p) for p in sizes) if f}
        if specs_dir.is_dir():
            existing_folders |= {d.name for d in specs_dir.iterdir()
                                 if d.is_dir() and not d.is_symlink()}

        group = uuid.uuid4()
        done: list[tuple[str, bytes | None]] = []
        out = []

        def base_check(path: str, base: str | None, force: bool = False) -> None:
            if force or current.get(path) == base:
                return
            last = history.latest(db, project.id, path)
            author = last.actor_kind if last else None
            if last and last.actor_id:
                user = db.get(AppUser, last.actor_id)
                author = user.full_name if user else last.actor_kind
            raise FileChanged(path, {
                "revision_id": last.id if last else None,
                "sha256": current.get(path),
                "author": author,
                "time": last.created_at.isoformat() if last else None,
            })

        # Files that come from a zip or Git keep their numbers, gaps included (numbers are never
        # reused, FR-017/FR-018); a spec created here takes the next number.
        keep_numbers = (actor.get("command") in ("import", "git")
                        or actor.get("kind") in ("git", "system"))

        def new_folder_check(path: str) -> None:
            folder = _spec_folder(path)
            if folder and folder not in existing_folders:
                number = int(folder[:3])
                if keep_numbers:
                    if any(int(f[:3]) == number for f in existing_folders):
                        raise ProjectPathError("spec_number_duplicate", M(
                            "projects.spec_number_duplicate", number=f"{number:03d}"))
                    project.spec_seq = max(project.spec_seq, number)
                else:
                    expected = project.spec_seq + 1
                    if number != expected:
                        raise ProjectPathError(
                            "spec_number", M("projects.spec_number", number=f"{expected:03d}"))
                    project.spec_seq = expected
                existing_folders.add(folder)

        def note(kind: str, path: str, rev) -> None:
            out.append({"op": kind, "path": path, "revision_id": rev.id if rev else None,
                        "sha256": rev.sha256 if rev else None})

        try:
            for op in ops:
                kind = op["op"]
                if kind == "write":
                    path = op["path"]
                    resolve(slug, path)
                    base_check(path, op.get("base_sha256"), op.get("force", False))
                    new_folder_check(path)
                    data = op["content"].encode("utf-8")
                    check_limits(slug, path, data, sizes)
                    previous, digest = write_atomic(slug, path, op["content"])
                    done.append((path, previous))
                    sizes[path] = (len(data), digest)
                    restored_from = op.get("restored_from")
                    rev_op = "create" if path not in current else "update"
                    if restored_from is not None:
                        rev_op = "restore"
                    rev = history.record(db, project.id, path, rev_op, op["content"], actor,
                                         group_id=group, restored_from=restored_from)
                    current[path] = digest
                    note(kind, path, rev)
                elif kind == "delete":
                    path = op["path"]
                    resolve(slug, path)
                    base_check(path, op.get("base_sha256"))
                    previous = remove(slug, path)
                    done.append((path, previous))
                    sizes.pop(path, None)
                    current.pop(path, None)
                    rev = history.record(db, project.id, path, "delete", None, actor,
                                         group_id=group)
                    note(kind, path, rev)
                elif kind == "rename":
                    src, dst = op["from"], op["to"]
                    resolve(slug, src)
                    resolve(slug, dst)
                    base_check(src, op.get("base_sha256"))
                    if dst in current:
                        raise _unsafe(dst)
                    new_folder_check(dst)
                    text = read_text(slug, src)
                    data = text.encode("utf-8")
                    check_limits(slug, dst, data, sizes)
                    previous_dst, digest = write_atomic(slug, dst, text)
                    done.append((dst, previous_dst))
                    previous_src = remove(slug, src)
                    done.append((src, previous_src))
                    rev_dst = history.record(db, project.id, dst, "rename", text, actor,
                                             group_id=group, renamed_from=src)
                    rev_src = history.record(db, project.id, src, "delete", None, actor,
                                             group_id=group)
                    sizes.pop(src, None)
                    current.pop(src, None)
                    sizes[dst] = (len(data), digest)
                    current[dst] = digest
                    note(kind, dst, rev_dst)
                    note("delete", src, rev_src)
                elif kind == "mkdir":
                    path = op["path"]
                    resolve(slug, path, folder=True)
                    parts = path.split("/")
                    if (len(parts) == 2 and parts[0] == "specs"
                            and layout.SPEC_FOLDER_RE.match(parts[1])):
                        new_folder_check(path + "/spec.md")
                    make_folder(slug, path)
                    note(kind, path, None)
                elif kind == "rmdir":
                    path = op["path"]
                    for f in remove_folder(slug, path):
                        previous = remove(slug, f)
                        done.append((f, previous))
                        sizes.pop(f, None)
                        current.pop(f, None)
                        rev = history.record(db, project.id, f, "delete", None, actor,
                                             group_id=group)
                        note("delete", f, rev)
                    prune(slug, path)
                else:
                    raise _unsafe(str(kind))

            now = datetime.now(UTC)
            project.last_activity_at = now
            project.updated_at = now
            db.commit()
        except Exception:
            db.rollback()
            for path, previous in reversed(done):
                restore_bytes(slug, path, previous)
            raise
        return out
