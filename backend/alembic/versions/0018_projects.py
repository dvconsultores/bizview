"""BI projects: a folder per project, file revisions, conversations bound to projects (feature 020).

Revision ID: 0018_projects
Revises: 0017_user_locale
Create Date: 2026-10-11
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0018_projects"
down_revision = "0017_user_locale"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"  # see 0003/0011/0013

KINDS_017 = (
    "login_ok", "login_failed", "login_locked", "logout",
    "user_created", "user_updated", "user_deactivated", "user_reactivated", "role_changed",
    "password_changed", "password_reset",
    "dashboard_granted", "dashboard_revoked",
    "superuser_created", "superuser_promoted", "superuser_recovered",
    "source_created", "source_updated", "source_deleted", "source_tested", "source_enabled",
    "source_disabled", "source_imported", "mfa_enabled", "mfa_disabled", "mfa_reset",
    "recovery_code_used", "recovery_codes_regenerated", "reauth_ok", "reauth_failed",
    "login_rate_limited", "admin_address_refused", "secret_key_rotated",
    "workspace_validated", "workspace_applied", "workspace_rolled_back",
    "integration_run_requested", "token_created", "token_revoked", "source_described",
    "telegram_settings_updated", "telegram_checked", "telegram_enabled", "telegram_disabled",
    "telegram_linked", "telegram_unlinked",
    "integration_paused", "integration_resumed", "integration_schedule_changed",
    "integration_run_stopped",
    "assistant_draft_applied", "assistant_session_archived", "assistant_budget_extended",
    "share_link_created", "share_link_revoked", "sharing_toggled",
    "email_settings_updated", "email_test_sent", "email_sent",
    "email_subscription_created", "email_subscription_updated", "email_subscription_deleted",
    "source_direct_reports_changed",
)
KINDS_018 = (
    *KINDS_017,
    "project_created", "project_updated", "project_deleted", "project_purged",
    "project_applied", "project_withdrawn", "project_imported", "project_exported",
    "project_converted",
)
NEW_KINDS = KINDS_018[len(KINDS_017):]

SLUG_RE = "^[a-z][a-z0-9-]{1,49}$"
SPEC_RE = "^[0-9]{3}-[a-z0-9][a-z0-9-]{0,59}$"
ORIGINS = ("app", "git")
OPS = ("create", "update", "delete", "rename", "restore", "import", "external", "git")
ACTORS = ("user", "agent", "system", "external", "git")


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_018)}")

    op.create_table(
        "project",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("origin", sa.Text(), server_default="app", nullable=False),
        sa.Column("spec_seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column("validation", pg.JSONB(), nullable=True),
        sa.Column("query_checks", pg.JSONB(), nullable=True),
        sa.Column("preview", pg.JSONB(), nullable=True),
        sa.Column("first_applied_at", TS, nullable=True),
        sa.Column("withdrawn_at", TS, nullable=True),
        sa.Column("imported_at", TS, nullable=True),
        sa.Column("deleted_at", TS, nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("last_activity_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"slug ~ '{SLUG_RE}'", name="slug"),
        sa.CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 80", name="name_len"),
        sa.CheckConstraint("char_length(description) <= 500", name="description_len"),
        sa.CheckConstraint(f"origin IN {_in(ORIGINS)}", name="origin"),
        sa.CheckConstraint("spec_seq >= 0", name="spec_seq"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_project_created_by"),
        sa.PrimaryKeyConstraint("id", name="pk_project"),
    )
    op.create_index("uq_project_slug_live", "project", ["slug"], unique=True,
                    postgresql_where=sa.text("deleted_at IS NULL"))

    op.create_table(
        "project_file_revision",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("op", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("size", sa.Integer(), server_default="0", nullable=False),
        sa.Column("renamed_from", sa.Text(), nullable=True),
        sa.Column("restored_from", sa.BigInteger(), nullable=True),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.Column("group_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"op IN {_in(OPS)}", name="op"),
        sa.CheckConstraint(f"actor_kind IN {_in(ACTORS)}", name="actor_kind"),
        sa.CheckConstraint("char_length(command) BETWEEN 1 AND 60", name="command_len"),
        sa.CheckConstraint("size >= 0", name="size"),
        sa.CheckConstraint("(op = 'delete') = (sha256 IS NULL)", name="sha_on_delete"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"],
                                name="fk_project_file_revision_project_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["app_user.id"],
                                name="fk_project_file_revision_actor_id"),
        sa.ForeignKeyConstraint(["session_id"], ["assistant_session.id"],
                                name="fk_project_file_revision_session_id", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_project_file_revision"),
    )
    op.create_index("ix_project_file_revision_path", "project_file_revision",
                    ["project_id", "path", sa.text("id DESC")])
    op.create_index("ix_project_file_revision_project", "project_file_revision",
                    ["project_id", sa.text("id DESC")])
    op.create_index("ix_project_file_revision_group", "project_file_revision",
                    ["project_id", "group_id"])

    op.add_column("assistant_session", sa.Column("project_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(op.f("fk_assistant_session_project_id"), "assistant_session",
                          "project", ["project_id"], ["id"], ondelete="CASCADE")
    op.add_column("assistant_session", sa.Column("current_spec", sa.Text(), nullable=True))
    op.create_check_constraint(op.f("ck_assistant_session_current_spec"), "assistant_session",
                               f"current_spec IS NULL OR current_spec ~ '{SPEC_RE}'")
    op.add_column("assistant_session",
                  sa.Column("read_only", sa.Boolean(), server_default=sa.text("false"),
                            nullable=False))
    op.create_index("ix_assistant_session_project", "assistant_session",
                    ["project_id", sa.text("updated_at DESC")])

    op.add_column("workspace_version",
                  sa.Column("projects", pg.JSONB(), server_default=sa.text("'{}'::jsonb"),
                            nullable=False))

    op.add_column("email_subscription", sa.Column("project_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(op.f("fk_email_subscription_project_id"), "email_subscription",
                          "project", ["project_id"], ["id"], ondelete="SET NULL")
    op.add_column("email_subscription", sa.Column("distribution_id", sa.Text(), nullable=True))
    op.add_column("email_subscription",
                  sa.Column("distribution_index", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        op.f("ck_email_subscription_distribution"), "email_subscription",
        "(project_id IS NULL) = (distribution_id IS NULL) "
        "AND (distribution_id IS NULL) = (distribution_index IS NULL)")
    op.create_unique_constraint(op.f("uq_email_subscription_distribution"), "email_subscription",
                                ["project_id", "distribution_id", "distribution_index"])

    # Backfill (research R10): existing conversations and the applied workspace become the
    # project "principal"; old conversations are kept read-only.
    bind = op.get_bind()
    has_sessions = bind.execute(sa.text("SELECT EXISTS (SELECT 1 FROM assistant_session)")).scalar()
    active = bind.execute(
        sa.text("SELECT id, commit FROM workspace_version WHERE state = 'active'")).fetchone()
    if has_sessions or active:
        superuser_id = bind.execute(
            sa.text("SELECT id FROM app_user WHERE is_superuser ORDER BY id LIMIT 1")).scalar()
        origin = "git" if active and active.commit else "app"
        pid = bind.execute(
            sa.text("INSERT INTO project (slug, name, origin, created_by) "
                    "VALUES ('principal', 'Principal', :origin, :uid) RETURNING id"),
            {"origin": origin, "uid": superuser_id}).scalar()
        bind.execute(sa.text("UPDATE assistant_session SET project_id = :pid, read_only = true"),
                     {"pid": pid})
    op.alter_column("assistant_session", "project_id", nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT count(*) FROM project WHERE slug <> 'principal'")).scalar()
    count += bind.execute(
        sa.text(f"SELECT count(*) FROM audit_event WHERE kind IN {_in(NEW_KINDS)}")).scalar()
    count += bind.execute(sa.text("SELECT count(*) FROM project_file_revision")).scalar()
    if count:
        raise RuntimeError(
            "Hay proyectos adicionales o datos de proyecto; elimínalos antes de bajar de 0018")

    op.drop_constraint(op.f("uq_email_subscription_distribution"), "email_subscription",
                       type_="unique")
    op.drop_constraint(op.f("ck_email_subscription_distribution"), "email_subscription",
                       type_="check")
    op.drop_constraint(op.f("fk_email_subscription_project_id"), "email_subscription",
                       type_="foreignkey")
    op.drop_column("email_subscription", "distribution_index")
    op.drop_column("email_subscription", "distribution_id")
    op.drop_column("email_subscription", "project_id")

    op.drop_column("workspace_version", "projects")

    op.drop_index("ix_assistant_session_project", table_name="assistant_session")
    op.drop_constraint(op.f("ck_assistant_session_current_spec"), "assistant_session",
                       type_="check")
    op.drop_constraint(op.f("fk_assistant_session_project_id"), "assistant_session",
                       type_="foreignkey")
    op.drop_column("assistant_session", "read_only")
    op.drop_column("assistant_session", "current_spec")
    op.drop_column("assistant_session", "project_id")

    op.drop_index("ix_project_file_revision_group", table_name="project_file_revision")
    op.drop_index("ix_project_file_revision_project", table_name="project_file_revision")
    op.drop_index("ix_project_file_revision_path", table_name="project_file_revision")
    op.drop_table("project_file_revision")

    op.drop_index("uq_project_slug_live", table_name="project")
    op.drop_table("project")

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_017)}")
