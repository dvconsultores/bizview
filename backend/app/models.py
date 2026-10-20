"""ORM models (see specs/002-auth-admin-home/data-model.md). Tables live in the database's
default schema, `public`; no schema is hard-coded."""
import uuid
from datetime import datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    SmallInteger,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

AUDIT_KINDS = (
    "login_ok", "login_failed", "login_locked", "logout",
    "user_created", "user_updated", "user_deactivated", "user_reactivated", "role_changed",
    "password_changed", "password_reset",
    "dashboard_granted", "dashboard_revoked",
    "superuser_created", "superuser_promoted", "superuser_recovered",
    # feature 004
    "source_created", "source_updated", "source_deleted", "source_tested", "source_enabled",
    "source_disabled", "source_imported", "mfa_enabled", "mfa_disabled", "mfa_reset",
    "recovery_code_used", "recovery_codes_regenerated", "reauth_ok", "reauth_failed",
    "login_rate_limited", "admin_address_refused", "secret_key_rotated",
    # feature 005
    "workspace_validated", "workspace_applied", "workspace_rolled_back",
    "integration_run_requested", "token_created", "token_revoked", "source_described",
    # feature 007
    "telegram_settings_updated", "telegram_checked", "telegram_enabled", "telegram_disabled",
    "telegram_linked", "telegram_unlinked",
    # feature 013
    "integration_paused", "integration_resumed", "integration_schedule_changed",
    "integration_run_stopped",
    # feature 014
    "assistant_draft_applied", "assistant_session_archived", "assistant_session_deleted",
    # feature 017
    "assistant_budget_extended",
    # feature 018
    "share_link_created", "share_link_revoked", "sharing_toggled",
    "email_settings_updated", "email_test_sent", "email_sent",
    "email_subscription_created", "email_subscription_updated",
    "email_subscription_deleted",
    # feature 019
    "source_direct_reports_changed",
    # feature 020
    "project_created", "project_updated", "project_deleted", "project_purged", "project_applied",
    "project_withdrawn", "project_imported", "project_exported", "project_converted",
    # feature 024
    "assistant_attachment_uploaded", "assistant_attachment_deleted",
    # feature 027
    "google_sign_in", "google_sign_in_refused", "google_linked",
    # feature 028
    "assistant_mode_changed", "assistant_contract_confirmed", "assistant_run_started",
    "assistant_run_applied", "assistant_run_stopped", "assistant_run_rolled_back",
    "assistant_profile_created", "assistant_profile_edited", "assistant_profile_deleted",
)
DIRECT_OUTCOMES = ("ok", "timeout", "unreachable", "busy", "structure_changed", "not_allowed",
                   "product_table", "error")
RUN_KINDS = ("incremental", "full", "manual_incremental", "manual_full")
RUN_STATUSES = ("running", "succeeded", "failed", "skipped", "stopped")
VERSION_STATES = ("active", "previous", "archived")
SOURCE_KINDS = ("postgresql", "soap", "rest", "supabase")
DASHBOARD_STATUSES = ("available", "coming_soon", "hidden")
ROLES = ("admin", "user")
THEMES = ("system", "light", "dark")
LOCALES = ("es", "en")
TELEGRAM_PURPOSES = ("sign_in", "link")
TELEGRAM_STATUSES = ("pending", "started", "approved", "refused", "expired", "consumed")
ASSISTANT_STATUSES = ("open", "applied", "archived")
ASSISTANT_ROLES = ("user", "assistant", "tool")
# Feature 028: the composer selector and the run contract of one autonomous run.
ASSISTANT_MODES = ("ask", "edit", "auto")
AUTO_RUN_STATUSES = ("confirmed", "running", "applied", "stopped", "failed")
AUTO_RUN_STAGES = ("discover", "specify", "clarify", "plan", "tasks", "implement", "converge",
                   "preview", "apply")
AUTO_WATCH_STATES = ("pending", "ok", "failed", "rolled_back")
# Feature 024: media types decided by magic bytes (app/assistant/attachments.py).
ATTACHMENT_TYPES = ("image/png", "image/jpeg", "image/webp", "image/gif")
EMAIL_SEND_STATUSES = ("queued", "sending", "sent", "partial", "failed")
EMAIL_DELIVERY_STATUSES = ("queued", "sent", "failed", "skipped")
SUBSCRIPTION_FREQUENCIES = ("daily", "weekly", "monthly")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "pk": "pk_%(table_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "ix": "ix_%(table_name)s_%(column_0_name)s",
        },
    )


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        CheckConstraint("email = lower(btrim(email))", name="email_normalised"),
        CheckConstraint("char_length(email) BETWEEN 3 AND 254 AND position('@' in email) > 1",
                        name="email_format"),
        CheckConstraint("char_length(btrim(full_name)) BETWEEN 1 AND 120", name="full_name_len"),
        CheckConstraint(_in("role", ROLES), name="role"),
        CheckConstraint("NOT is_superuser OR role = 'admin'", name="superuser_is_admin"),
        CheckConstraint(_in("theme", THEMES), name="theme"),
        CheckConstraint("locale IS NULL OR " + _in("locale", LOCALES), name="locale"),
        CheckConstraint("is_active OR NOT is_superuser", name="superuser_active"),
        Index("uq_app_user_single_superuser", text("(true)"), unique=True,
              postgresql_where=text("is_superuser")),
        Index("ix_app_user_role_active", "role", "is_active"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    full_name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    is_superuser: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    password_hash: Mapped[str] = mapped_column(Text)
    must_change_password: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    failed_attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    # Two-step sign-in (feature 004): secret encrypted with BIZVIEW_SECRET_KEY.
    totp_secret_ct: Mapped[bytes | None] = mapped_column(LargeBinary)
    totp_key_id: Mapped[str | None] = mapped_column(Text)
    totp_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger)
    # Dark mode (feature 006): "system" follows the device appearance.
    theme: Mapped[str] = mapped_column(Text, server_default=text("'system'"))
    locale: Mapped[str | None] = mapped_column(Text)
    # Feature 024: when this person accepted the one-time notice that an attached image
    # leaves the installation to the configured AI provider (null = not accepted yet).
    attachments_notice_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    __tablename__ = "user_session"

    id_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(INET)
    mfa_pending: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    reauth_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Dashboard(Base):
    __tablename__ = "dashboard"
    __table_args__ = (
        CheckConstraint("code ~ '^[a-z][a-z0-9-]{1,39}$'", name="code_format"),
        CheckConstraint("char_length(description) <= 200", name="description_len"),
        CheckConstraint(_in("status", DASHBOARD_STATUSES), name="status"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("100"))
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # feature 005: dashboards created from applied workspace reports
    report_id: Mapped[str | None] = mapped_column(Text, unique=True)
    managed_by: Mapped[str] = mapped_column(Text, server_default=text("'product'"))


class DashboardAccess(Base):
    __tablename__ = "dashboard_access"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    dashboard_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("dashboard.id", ondelete="CASCADE"), primary_key=True)
    granted_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (
        CheckConstraint(_in("kind", AUDIT_KINDS), name="kind"),
        Index("ix_audit_event_occurred_at", text("occurred_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    kind: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    target_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), index=True)
    ip: Mapped[str | None] = mapped_column(INET)
    detail: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class DataSource(Base):
    """Origin system (feature 004). Credentials live only in `secrets_ct`, encrypted."""
    __tablename__ = "data_source"
    __table_args__ = (
        CheckConstraint(_in("kind", SOURCE_KINDS), name="kind"),
        CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 80", name="name_len"),
        CheckConstraint("char_length(description) <= 300", name="description_len"),
        CheckConstraint("(secrets_ct IS NULL) = (secrets_key_id IS NULL)", name="secrets_pair"),
        CheckConstraint("direct_reports = false OR kind = 'postgresql'",
                        name="direct_reports_kind"),
        Index("uq_data_source_name_ci", text("lower(name)"), unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default=text("''"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    settings: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    secrets_ct: Mapped[bytes | None] = mapped_column(LargeBinary)
    secrets_key_id: Mapped[str | None] = mapped_column(Text)
    secret_fields: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    imported: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    direct_reports: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_test: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))


class SecurityState(Base):
    """Singleton: which key encrypts the data, and a known value to verify it at start."""
    __tablename__ = "security_state"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    key_id: Mapped[str] = mapped_column(Text)
    key_check: Mapped[bytes] = mapped_column(LargeBinary)
    key_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    legacy_origin_notice: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class RecoveryCode(Base):
    __tablename__ = "recovery_code"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(Text)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginThrottle(Base):
    __tablename__ = "login_throttle"

    ip: Mapped[str] = mapped_column(INET, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    limited_audited: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class WorkspaceVersion(Base):
    """An applied, validated workspace (feature 005). The engine runs from this copy."""
    __tablename__ = "workspace_version"
    __table_args__ = (
        CheckConstraint(_in("state", VERSION_STATES), name="state"),
        Index("uq_workspace_version_active", "state", unique=True,
              postgresql_where=text("state = 'active'")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    commit: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(Text)
    lock: Mapped[dict] = mapped_column(JSONB)
    artifacts: Mapped[dict] = mapped_column(JSONB)
    specs: Mapped[dict] = mapped_column(JSONB)
    projects: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    state: Mapped[str] = mapped_column(Text)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    applied_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))


class IntegrationRun(Base):
    __tablename__ = "integration_run"
    __table_args__ = (
        CheckConstraint(_in("kind", RUN_KINDS), name="kind"),
        CheckConstraint(_in("status", RUN_STATUSES), name="status"),
        Index("ix_integration_run_integration_started", "integration_id", text("started_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    integration_id: Mapped[str] = mapped_column(Text)
    version_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("workspace_version.id"))
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    checks: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    rollups: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    message: Mapped[str | None] = mapped_column(Text)
    message_key: Mapped[str | None] = mapped_column(Text)
    message_params: Mapped[dict | None] = mapped_column(JSONB)
    requested_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    stop_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_requested_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))


class IntegrationRunRequest(Base):
    __tablename__ = "integration_run_request"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    integration_id: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("integration_run.id"))


class IntegrationControl(Base):
    """Operational overrides of a workspace integration (feature 013).

    Keyed by integration id; kept when the integration disappears from the active version.
    """
    __tablename__ = "integration_control"
    __table_args__ = (
        CheckConstraint("(window_start IS NULL) = (window_end IS NULL)", name="window_pair"),
        CheckConstraint(
            "schedule IS NULL OR char_length(schedule) BETWEEN 9 AND 100",
            name="schedule_len",
        ),
        CheckConstraint(
            "full_rebuild_cron IS NULL OR char_length(full_rebuild_cron) BETWEEN 9 AND 100",
            name="full_rebuild_cron_len",
        ),
    )

    integration_id: Mapped[str] = mapped_column(Text, primary_key=True)
    paused: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    schedule: Mapped[str | None] = mapped_column(Text)
    full_rebuild_cron: Mapped[str | None] = mapped_column(Text)
    window_start: Mapped[time | None] = mapped_column(Time)
    window_end: Mapped[time | None] = mapped_column(Time)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportCache(Base):
    __tablename__ = "report_cache"

    report_id: Mapped[str] = mapped_column(Text, primary_key=True)
    selection_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    data_version: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, primary_key=True, server_default=text("'data'"))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportRollup(Base):
    """State of a report's daily rollup table (feature 005 amendment, FR-A06/FR-A07)."""
    __tablename__ = "report_rollup"
    __table_args__ = (
        CheckConstraint(_in("status", ("ready", "stale", "failed")), name="status"),
        CheckConstraint("rows IS NULL OR rows >= 0", name="rows"),
        CheckConstraint("refresh_ms IS NULL OR refresh_ms >= 0", name="refresh_ms"),
    )

    report_id: Mapped[str] = mapped_column(Text, primary_key=True)
    schema_name: Mapped[str] = mapped_column(Text)
    table_name: Mapped[str] = mapped_column(Text)
    definition_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    source_runs: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    columns: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    rows: Mapped[int | None] = mapped_column(BigInteger)
    built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DirectReadLog(Base):
    """One direct read session of a direct report (feature 019): no values, only the outcome."""
    __tablename__ = "direct_read_log"
    __table_args__ = (
        CheckConstraint(_in("outcome", DIRECT_OUTCOMES), name="outcome"),
        CheckConstraint("duration_ms >= 0", name="duration_ms"),
        CheckConstraint("rows >= 0", name="rows"),
        Index("ix_direct_read_log_occurred_at", text("occurred_at DESC")),
        Index("ix_direct_read_log_report_occurred_at", "report_id", text("occurred_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())
    report_id: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(Integer)
    rows: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    outcome: Mapped[str] = mapped_column(Text)
    stale_served: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class ApiToken(Base):
    """Personal access token (feature 005): hashed, scoped, revocable."""
    __tablename__ = "api_token"
    __table_args__ = (
        CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 60", name="name_len"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TelegramSettings(Base):
    """Telegram bot settings (feature 007): singleton row, token encrypted and write-only."""
    __tablename__ = "telegram_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("bot_username ~ '^[A-Za-z][A-Za-z0-9_]{1,28}[Bb][Oo][Tt]$'",
                        name="bot_username_format"),
        CheckConstraint("(token_ct IS NULL) = (token_key_id IS NULL)", name="token_pair"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    bot_username: Mapped[str | None] = mapped_column(Text)
    token_ct: Mapped[bytes | None] = mapped_column(LargeBinary)
    token_key_id: Mapped[str | None] = mapped_column(Text)
    token_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_check_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_check: Mapped[dict | None] = mapped_column(JSONB)
    update_offset: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    last_poll_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))


class TelegramLink(Base):
    """A user's own Telegram account (feature 007), by its permanent id."""
    __tablename__ = "telegram_link"
    __table_args__ = (
        CheckConstraint("username IS NULL OR char_length(username) <= 64", name="username_len"),
        CheckConstraint("char_length(display_name) BETWEEN 1 AND 128", name="display_name_len"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    linked_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))


class GoogleLink(Base):
    """A user's linked Google identity (feature 027), by its immutable subject id."""
    __tablename__ = "google_link"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_google_link_user"),
        CheckConstraint("char_length(google_sub) BETWEEN 1 AND 255", name="google_sub_len"),
        CheckConstraint("char_length(email) BETWEEN 3 AND 254", name="email_len"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False)
    google_sub: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TelegramRequest(Base):
    """Single-use, short-lived approval for a Telegram sign-in or link (feature 007)."""
    __tablename__ = "telegram_request"
    __table_args__ = (
        CheckConstraint("char_length(id) = 16", name="id_len"),
        CheckConstraint(_in("purpose", TELEGRAM_PURPOSES), name="purpose"),
        CheckConstraint("match_code IS NULL OR match_code BETWEEN 10 AND 99", name="match_code"),
        CheckConstraint(_in("status", TELEGRAM_STATUSES), name="status"),
        CheckConstraint("purpose <> 'link' OR user_id IS NOT NULL", name="link_has_user"),
        CheckConstraint(
            "purpose <> 'sign_in' OR (browser_hash IS NOT NULL AND match_code IS NOT NULL)",
            name="sign_in_has_browser"),
        Index("ix_telegram_request_status_expires", "status", "expires_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    purpose: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    browser_hash: Mapped[bytes | None] = mapped_column(LargeBinary, unique=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    match_code: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    reason: Mapped[str | None] = mapped_column(Text)
    chat_id: Mapped[int | None] = mapped_column(BigInteger)
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


PROJECT_ORIGINS = ("app", "git")
REVISION_OPS = ("create", "update", "delete", "rename", "restore", "import", "external", "git")
REVISION_ACTORS = ("user", "agent", "system", "external", "git")
SLUG_PATTERN = "^[a-z][a-z0-9-]{1,49}$"
SPEC_FOLDER_PATTERN = "^[0-9]{3}-[a-z0-9][a-z0-9-]{0,59}$"


class Project(Base):
    """A BI project: a folder under PROJECTS_DIR with numbered specs and artifacts (feature 020)."""

    __tablename__ = "project"
    __table_args__ = (
        CheckConstraint(f"slug ~ '{SLUG_PATTERN}'", name="slug"),
        CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 80", name="name_len"),
        CheckConstraint("char_length(description) <= 500", name="description_len"),
        CheckConstraint(_in("origin", PROJECT_ORIGINS), name="origin"),
        CheckConstraint("spec_seq >= 0", name="spec_seq"),
        Index("uq_project_slug_live", "slug", unique=True,
              postgresql_where=text("deleted_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    slug: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default=text("''"))
    origin: Mapped[str] = mapped_column(Text, server_default=text("'app'"))
    spec_seq: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    validation: Mapped[dict | None] = mapped_column(JSONB)
    query_checks: Mapped[dict | None] = mapped_column(JSONB)
    preview: Mapped[dict | None] = mapped_column(JSONB)
    first_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                       server_default=func.now())


class ProjectFileRevision(Base):
    """One recorded change of a project file (feature 020, plan section 3)."""

    __tablename__ = "project_file_revision"
    __table_args__ = (
        CheckConstraint(_in("op", REVISION_OPS), name="op"),
        CheckConstraint(_in("actor_kind", REVISION_ACTORS), name="actor_kind"),
        CheckConstraint("char_length(command) BETWEEN 1 AND 60", name="command_len"),
        CheckConstraint("size >= 0", name="size"),
        CheckConstraint("(op = 'delete') = (sha256 IS NULL)", name="sha_on_delete"),
        Index("ix_project_file_revision_path", "project_id", "path", text("id DESC")),
        Index("ix_project_file_revision_project", "project_id", text("id DESC")),
        Index("ix_project_file_revision_group", "project_id", "group_id"),
        Index("ix_project_file_revision_command_run", "command_run_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    project_id: Mapped[int] = mapped_column(BigInteger,
                                            ForeignKey("project.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(Text)
    op: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    size: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    renamed_from: Mapped[str | None] = mapped_column(Text)
    restored_from: Mapped[int | None] = mapped_column(BigInteger)
    actor_kind: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    command: Mapped[str] = mapped_column(Text)
    session_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("assistant_session.id", ondelete="SET NULL"))
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # Feature 021: the /speckit-… command run that wrote it (agent writes inside a command).
    command_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("assistant_command_run.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssistantSession(Base):
    """A stored vibe-reporting conversation (feature 014)."""
    __tablename__ = "assistant_session"
    __table_args__ = (
        CheckConstraint("char_length(btrim(title)) BETWEEN 1 AND 120", name="title_len"),
        CheckConstraint(_in("status", ASSISTANT_STATUSES), name="status"),
        CheckConstraint("tokens_used >= 0", name="tokens_used"),
        CheckConstraint("token_budget > 0", name="token_budget"),
        CheckConstraint("status <> 'applied' OR applied_version_id IS NOT NULL",
                        name="applied_has_version"),
        Index("ix_assistant_session_updated_at", text("updated_at DESC")),
        CheckConstraint("current_spec IS NULL OR current_spec ~ '" + SPEC_FOLDER_PATTERN + "'",
                        name="current_spec"),
        CheckConstraint(_in("mode", ASSISTANT_MODES), name="mode"),
        Index("ix_assistant_session_project", "project_id", text("updated_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    draft: Mapped[dict | None] = mapped_column(JSONB)
    validation: Mapped[dict | None] = mapped_column(JSONB)
    preview: Mapped[dict | None] = mapped_column(JSONB)
    working_state: Mapped[dict | None] = mapped_column(JSONB)
    query_checks: Mapped[dict | None] = mapped_column(JSONB)
    stats: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    project_id: Mapped[int] = mapped_column(BigInteger,
                                            ForeignKey("project.id", ondelete="CASCADE"))
    current_spec: Mapped[str | None] = mapped_column(Text)
    read_only: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Feature 028: the composer selector (ask | auto; `edit` stays for conversations created
    # before the simplification). The run contract is the newest `assistant_auto_run` row of this
    # conversation (no FK back: it would be a table cycle).
    mode: Mapped[str] = mapped_column(Text, server_default=text("'auto'"))
    applied_version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("workspace_version.id"))
    tokens_used: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    token_budget: Mapped[int] = mapped_column(Integer)
    busy_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AssistantMessage(Base):
    """One turn of a conversation (feature 014): user text, assistant reply, or tool result."""
    __tablename__ = "assistant_message"
    __table_args__ = (
        CheckConstraint(_in("role", ASSISTANT_ROLES), name="role"),
        CheckConstraint("role <> 'tool' OR tool_name IS NOT NULL", name="tool_has_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant_session.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, server_default=text("''"))
    tool_name: Mapped[str | None] = mapped_column(Text)
    tool_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssistantAttachment(Base):
    """An image attached to a chat message (feature 024): the brief, not the project's data.

    The bytes live on disk under `ATTACHMENTS_DIR/<session_id>/<sha256>.<ext>`, never inside
    PROJECTS_DIR, so no export, Git mirror or applied version can carry them (FR-008)."""
    __tablename__ = "assistant_attachment"
    __table_args__ = (
        CheckConstraint(_in("media_type", ATTACHMENT_TYPES), name="media_type"),
        CheckConstraint("byte_size > 0", name="byte_size"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        CheckConstraint("original_name IS NULL OR char_length(original_name) <= 120",
                        name="original_name_len"),
        Index("ix_assistant_attachment_sha256", "sha256"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant_session.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("assistant_message.id", ondelete="CASCADE"), index=True)
    media_type: Mapped[str] = mapped_column(Text)
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(Text)
    original_name: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssistantPreviewRequest(Base):
    """A super user's "Vista previa" request, processed by the worker (feature 014)."""
    __tablename__ = "assistant_preview_request"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant_session.id", ondelete="CASCADE"), index=True)
    requested_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ShareLink(Base):
    """An expiring read-only link to one dashboard; only the token's SHA-256 is stored."""

    __tablename__ = "share_link"
    __table_args__ = (
        CheckConstraint("note IS NULL OR char_length(note) <= 200", name="note_len"),
        CheckConstraint("expires_at > created_at", name="expiry"),
        CheckConstraint("visits >= 0", name="visits"),
        Index(
            "ix_share_link_active",
            "dashboard_id",
            "expires_at",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dashboard_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("dashboard.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id")
    )
    visits: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    last_visit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailSubscription(Base):
    """Scheduled delivery of a dashboard."""

    __tablename__ = "email_subscription"
    __table_args__ = (
        CheckConstraint(_in("frequency", SUBSCRIPTION_FREQUENCIES), name="frequency"),
        CheckConstraint("hour BETWEEN 0 AND 23", name="hour"),
        CheckConstraint(
            "(frequency = 'weekly') = (weekday IS NOT NULL) AND "
            "(weekday IS NULL OR weekday BETWEEN 0 AND 6)",
            name="weekday",
        ),
        CheckConstraint(
            "(frequency = 'monthly') = (monthday IS NOT NULL) AND "
            "(monthday IS NULL OR monthday BETWEEN 1 AND 28)",
            name="monthday",
        ),
        CheckConstraint("char_length(period) BETWEEN 1 AND 40", name="period_len"),
        CheckConstraint(
            "link_days IS NULL OR link_days BETWEEN 1 AND 90", name="link_days"
        ),
        Index(
            "ix_email_subscription_due",
            "next_due_at",
            postgresql_where=text("NOT paused"),
        ),
        CheckConstraint("(project_id IS NULL) = (distribution_id IS NULL) "
                        "AND (distribution_id IS NULL) = (distribution_index IS NULL)",
                        name="distribution"),
        UniqueConstraint("project_id", "distribution_id", "distribution_index",
                         name="uq_email_subscription_distribution"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dashboard_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("dashboard.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    recipients: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    frequency: Mapped[str] = mapped_column(Text)
    hour: Mapped[int] = mapped_column(SmallInteger)
    weekday: Mapped[int | None] = mapped_column(SmallInteger)
    monthday: Mapped[int | None] = mapped_column(SmallInteger)
    period: Mapped[str] = mapped_column(Text)
    attach_pdf: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    link_days: Mapped[int | None] = mapped_column(Integer)
    paused: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    last_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Feature 020: subscriptions owned by a project distribution (distributions/<id>.yaml).
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("project.id", ondelete="SET NULL"))
    distribution_id: Mapped[str | None] = mapped_column(Text)
    distribution_index: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmailSend(Base):
    """One requested or scheduled send of a dashboard."""

    __tablename__ = "email_send"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(subject)) BETWEEN 1 AND 200", name="subject_len"
        ),
        CheckConstraint(
            "message IS NULL OR char_length(message) <= 2000", name="message_len"
        ),
        CheckConstraint(
            "link_days IS NULL OR link_days BETWEEN 1 AND 90", name="link_days"
        ),
        CheckConstraint(_in("status", EMAIL_SEND_STATUSES), name="status"),
        Index("ix_email_send_requested_by_created", "requested_by", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dashboard_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("dashboard.id", ondelete="CASCADE"), index=True
    )
    requested_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id")
    )
    subscription_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("email_subscription.id", ondelete="SET NULL")
    )
    subject: Mapped[str] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    selection: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    attach_pdf: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    link_days: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default=text("'queued'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailDelivery(Base):
    """One recipient of a send."""

    __tablename__ = "email_delivery"
    __table_args__ = (
        CheckConstraint(
            "char_length(recipient) BETWEEN 3 AND 254", name="recipient_len"
        ),
        CheckConstraint(_in("status", EMAIL_DELIVERY_STATUSES), name="status"),
        CheckConstraint("attempts >= 0", name="attempts"),
        CheckConstraint(
            "error IS NULL OR char_length(error) <= 500", name="error_len"
        ),
        Index(
            "ix_email_delivery_due",
            "next_attempt_at",
            postgresql_where=text("status = 'queued'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    send_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("email_send.id", ondelete="CASCADE"), index=True
    )
    recipient: Mapped[str] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, server_default=text("'queued'"))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


COMMAND_RUN_STATUSES = (
    "running", "waiting", "completed", "misrouted", "budget", "interrupted", "failed",
)
RESOLVE_SOURCES = ("argument", "number", "title", "current")


class AssistantCommandRun(Base):
    """One /speckit-… (or /ayuda) command executed in a conversation (feature 021, plan §6)."""

    __tablename__ = "assistant_command_run"
    __table_args__ = (
        CheckConstraint("command ~ '^(speckit-[a-z]+|ayuda)$'", name="command"),
        CheckConstraint("char_length(arguments) <= 4000", name="arguments_len"),
        CheckConstraint("spec IS NULL OR spec ~ '^[0-9]{3}-[a-z0-9-]{1,60}$'", name="spec"),
        CheckConstraint("locale IN ('es', 'en')", name="locale"),
        CheckConstraint(_in("status", COMMAND_RUN_STATUSES), name="status"),
        CheckConstraint("resolved_from IS NULL OR " + _in("resolved_from", RESOLVE_SOURCES),
                        name="resolved_from"),
        CheckConstraint("tokens >= 0", name="tokens"),
        Index("ux_command_run_active", "session_id", unique=True,
              postgresql_where=text("status IN ('running', 'waiting')")),
        Index("ix_command_run_session", "session_id", text("started_at DESC")),
        Index("ix_command_run_project", "project_id", text("started_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant_session.id", ondelete="CASCADE"))
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("project.id", ondelete="CASCADE"))
    message_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("assistant_message.id", ondelete="SET NULL"))
    command: Mapped[str] = mapped_column(Text)
    arguments: Mapped[str] = mapped_column(Text, server_default=text("''"))
    spec: Mapped[str | None] = mapped_column(Text)
    resolved_from: Mapped[str | None] = mapped_column(Text)
    forced: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    reserved_number: Mapped[int | None] = mapped_column(SmallInteger)
    locale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    pending: Mapped[dict | None] = mapped_column(JSONB)
    resumed_from: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("assistant_command_run.id", ondelete="SET NULL"))
    files: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    result: Mapped[dict | None] = mapped_column(JSONB)
    tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))



class AssistantAutoRun(Base):
    """One autonomous run: the confirmed contract and its outcome (feature 028)."""

    __tablename__ = "assistant_auto_run"
    __table_args__ = (
        CheckConstraint(_in("status", AUTO_RUN_STATUSES), name="status"),
        CheckConstraint("stop_reason IS NULL OR char_length(stop_reason) <= 120",
                        name="stop_reason_len"),
        CheckConstraint("stage IS NULL OR " + _in("stage", AUTO_RUN_STAGES), name="stage"),
        CheckConstraint("previews >= 0", name="previews"),
        CheckConstraint("applies >= 0", name="applies"),
        CheckConstraint("tokens >= 0", name="tokens"),
        CheckConstraint(
            "watch_state IS NULL OR " + _in("watch_state", AUTO_WATCH_STATES),
            name="watch_state"),
        CheckConstraint("status <> 'applied' OR version_id IS NOT NULL",
                        name="applied_has_version"),
        Index("ux_auto_run_active", "session_id", unique=True,
              postgresql_where=text("status IN ('confirmed', 'running')")),
        Index("ix_auto_run_session", "session_id", text("started_at DESC")),
        Index("ix_auto_run_watch", "watch_state",
              postgresql_where=text("watch_state = 'pending'")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant_session.id", ondelete="CASCADE"))
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("project.id", ondelete="CASCADE"))
    contract: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default=text("'confirmed'"))
    stop_reason: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str | None] = mapped_column(Text)
    previews: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    applies: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("workspace_version.id"))
    summary: Mapped[dict | None] = mapped_column(JSONB)
    watch_integration: Mapped[str | None] = mapped_column(Text)
    watch_state: Mapped[str | None] = mapped_column(Text)
    confirmed_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    confirmed_ip: Mapped[str | None] = mapped_column(INET)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssistantRunProfile(Base):
    """A saved run contract, reused as a form prefill (feature 028, US5)."""

    __tablename__ = "assistant_run_profile"
    __table_args__ = (
        CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 60", name="name_len"),
        Index("ux_run_profile_name", "name", unique=True,
              postgresql_where=text("deleted_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    contract: Mapped[dict] = mapped_column(JSONB)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
