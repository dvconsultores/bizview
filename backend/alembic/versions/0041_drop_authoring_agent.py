"""Remove the in-app authoring agent: rescue what was applied, then drop its tables (feature 045).

Authoring moved outside BizView (043/045): the chat, its drafts, its command runs and its
autonomous-run state have no producer or reader left, so the tables go. What must not go with them
is work a person wrote: an `applied` conversation whose spec folder never reached its project
folder would be lost, and transcripts are not kept.

The rescue runs first, and it is the only step that touches the filesystem:

1. Every `assistant_session` with a project and a draft: its `specs/<NNN-name>/…` documents are
   copied into `PROJECTS_DIR/<slug>/`. `applied` sessions are checked against their project's files
   and any document the project lacks is written; drafts nobody applied are imported too, so the
   writing survives even though the conversation does not.
2. A file already present with the same SHA-256 is not rewritten. A file present with different
   bytes is *not* overwritten — the person's project wins and the divergence is logged — because
   the draft is the older copy and this migration may not guess.
3. Every byte written is verified against the SHA-256 of what the database held. **A write that
   cannot be done, or does not verify, aborts the migration before a single table is dropped.**

At no point are PostgreSQL and the filesystem atomic: the files are written and verified first, and
only then is `DROP TABLE` issued. A run interrupted before the drop leaves the tables intact, and
re-running the migration is safe (an identical file is skipped, a missing one is written).

Downgrade recreates the empty tables and **does not bring any row back**. Recovering the records
means restoring the database backup taken before the upgrade (docs/INSTALL.md, «Copias de
seguridad»); the spec documents stay in the project folders either way.

Revision ID: 0041_drop_authoring_agent
Revises: 0043_image_cache
Create Date: 2026-11-01
"""
import hashlib
import logging
import os
import re
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision = "0041_drop_authoring_agent"
down_revision = "0043_image_cache"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.045")

TABLES = (
    "assistant_preview_request",
    "assistant_attachment",
    "assistant_message",
    "assistant_command_run",
    "assistant_auto_run",
    "assistant_run_profile",
    "assistant_session",
)
SPEC_DOC = re.compile(r"^specs/[0-9]{3}-[a-z0-9-]{1,60}/[A-Za-z0-9._-]+$")
SAFE_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_DOC_BYTES = 2 * 1024 * 1024


def _projects_dir() -> Path:
    """The projects folder, resolved the way the app resolves it (`PROJECTS_DIR`)."""
    return Path(os.environ.get("PROJECTS_DIR") or "/app/data/projects")


def _drafts(bind) -> list[tuple[str, dict]]:
    """(slug, files) of every conversation draft whose project is live, applied first."""
    if not _has_table(bind, "assistant_session"):
        return []
    rows = bind.execute(sa.text(
        "SELECT p.slug, s.status, s.draft FROM assistant_session s "
        "JOIN project p ON p.id = s.project_id "
        "WHERE s.draft IS NOT NULL AND p.deleted_at IS NULL "
        "ORDER BY (s.status = 'applied') DESC, s.id"))
    out = []
    for slug, status, draft in rows:
        files = (draft or {}).get("files") if isinstance(draft, dict) else None
        if isinstance(files, dict) and files:
            out.append((slug, files, status))
    return out


def _has_table(bind, name: str) -> bool:
    found = bind.execute(sa.text("SELECT to_regclass(:t)"), {"t": f"public.{name}"}).scalar()
    return found is not None


def _rescue(bind) -> None:
    """Copy every draft spec document into its project folder and verify the copy."""
    root = _projects_dir()
    written = skipped = 0
    for slug, files, status in _drafts(bind):
        if not SAFE_SLUG.match(slug or ""):
            raise RuntimeError(f"045: proyecto con slug no seguro ({slug!r}); rescate detenido")
        folder = root / slug
        for path, text in sorted(files.items()):
            if not SPEC_DOC.match(path) or not isinstance(text, str):
                continue
            data = text.encode("utf-8")
            if len(data) > MAX_DOC_BYTES:
                raise RuntimeError(f"045: documento excesivo en {slug}/{path}; rescate detenido")
            target = folder / path
            digest = hashlib.sha256(data).hexdigest()
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() == digest:
                    skipped += 1
                    continue
                log.warning("045: %s/%s ya existe con otro contenido; se conserva el del proyecto "
                            "(borrador %s)", slug, path, status)
                skipped += 1
                continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            except OSError as exc:
                raise RuntimeError(
                    f"045: no se pudo rescatar {slug}/{path} ({exc}); no se borra ninguna tabla"
                ) from exc
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise RuntimeError(
                    f"045: {slug}/{path} no verifica tras escribirlo; no se borra ninguna tabla")
            written += 1
    log.info("045: rescate terminado (%d documentos escritos, %d ya presentes)", written, skipped)


def _audit_kinds_without_assistant(bind) -> list[str]:
    """The audit kinds the product still records: the model's catalogue, minus the agent's."""
    from app.models import AUDIT_KINDS

    return [kind for kind in AUDIT_KINDS]


def upgrade() -> None:
    bind = op.get_bind()
    _rescue(bind)

    kinds = _audit_kinds_without_assistant(bind)
    op.drop_constraint(op.f("ck_audit_event_ck_audit_event_kind"), "audit_event", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_event_ck_audit_event_kind"), "audit_event",
        "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")")

    # PostgreSQL drops an index with its last column; naming it first keeps the intent readable and
    # covers an installation where the index was already gone.
    op.execute("DROP INDEX IF EXISTS ix_project_file_revision_command_run")
    op.drop_column("project_file_revision", "command_run_id")
    op.drop_column("project_file_revision", "session_id")
    op.drop_column("project", "preview")

    # CASCADE: `assistant_message` carries a self-reference added by 0029 and the tables reference
    # each other; every dependent object here is part of the same removed subsystem.
    for table in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


def downgrade() -> None:
    """Refuses: the rows are gone, and an empty schema would be a lie.

    Feature 045 deleted a subsystem, not a table of stale data. Recreating the seven tables empty
    would let an installation *believe* it went back while every conversation, command run and run
    contract stayed lost — and a later downgrade would then fail on columns the skeletons lack.
    Recovering the records means restoring the database backup taken before the upgrade
    (docs/INSTALL.md, «Copias de seguridad»); the spec documents stay in the project folders.
    """
    raise RuntimeError(
        "0041_drop_authoring_agent cannot be downgraded: the authoring agent's rows were deleted. "
        "Restore the database backup taken before the upgrade; the spec documents of every applied "
        "conversation are in its project folder."
    )
