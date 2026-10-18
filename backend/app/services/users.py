"""User administration rules (research R6) — the single source of who may do what to whom."""
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import passwords, sessions
from app.errors import ApiError, forbidden, validation
from app.i18n import M
from app.models import AppUser
from app.services import audit

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_FAILED = 5
LOCK_FOR = timedelta(minutes=15)

# Actions an administrator can take on another user from the administration area.
MANAGE_ACTIONS = ("edit", "activate", "reset_password", "grant", "role")


def now() -> datetime:
    return datetime.now(UTC)


def can_manage(actor: AppUser, target: AppUser, action: str) -> bool:
    assert action in MANAGE_ACTIONS, action
    if actor.role != "admin" or target.is_superuser or target.id == actor.id:
        return False
    if action == "role" or target.role == "admin":
        return actor.is_superuser
    return True


def ensure_can_manage(actor: AppUser, target: AppUser, action: str) -> None:
    if not can_manage(actor, target, action):
        raise forbidden(M("users.action_forbidden"))


def is_locked(user: AppUser) -> bool:
    return user.locked_until is not None and user.locked_until > now()


def locked_error(user: AppUser) -> ApiError:
    seconds = max(1, int((user.locked_until - now()).total_seconds()))
    minutes = -(-seconds // 60)
    return ApiError(423, "locked",
                    M("auth.locked", minutes=minutes),
                    extra={"retry_after_seconds": seconds})


def register_failure(db: Session, user: AppUser, ip: str | None) -> ApiError | None:
    """Count a wrong password; lock the account on the 5th. Returns the lock error if locked."""
    user.failed_attempts += 1
    if user.failed_attempts >= MAX_FAILED:
        user.failed_attempts = 0
        user.locked_until = now() + LOCK_FOR
        audit.record(db, "login_locked", actor_id=user.id, target_id=user.id, ip=ip)
        return locked_error(user)
    audit.record(db, "login_failed", target_id=user.id, ip=ip,
                 detail={"attempt": user.failed_attempts})
    return None


def check_new_password(password: str, email: str, current: str | None = None) -> None:
    problem = passwords.password_problem(password, email, current)
    if problem:
        field = "new_password" if current is not None else "temporary_password"
        raise validation({field: problem}, _password_message(problem))


def _password_message(problem: str) -> M:
    return {
        "too_short": M("password.too_short", n=passwords.MIN_LEN),
        "too_long": M("password.too_long", n=passwords.MAX_LEN),
        "contains_email": M("password.contains_email"),
        "same_as_current": M("password.same_as_current"),
    }[problem]


def by_email(db: Session, email: str) -> AppUser | None:
    return db.scalar(select(AppUser).where(AppUser.email == passwords.normalise_email(email)))


def get(db: Session, user_id: int) -> AppUser | None:
    return db.get(AppUser, user_id)


def list_users(db: Session, q: str | None, role: str | None, status: str | None,
               limit: int, offset: int) -> tuple[list[AppUser], int]:
    stmt = select(AppUser)
    if q:
        like = "%" + q.strip().replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
        stmt = stmt.where(or_(AppUser.full_name.ilike(like), AppUser.email.ilike(like)))
    if role:
        stmt = stmt.where(AppUser.role == role)
    if status == "active":
        stmt = stmt.where(AppUser.is_active.is_(True))
    elif status == "inactive":
        stmt = stmt.where(AppUser.is_active.is_(False))
    elif status == "locked":
        stmt = stmt.where(AppUser.locked_until > func.now())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(func.lower(AppUser.full_name), AppUser.id)
                      .limit(limit).offset(offset)).all()
    return list(rows), total


def create(db: Session, actor: AppUser, *, email: str, full_name: str, role: str,
           temporary_password: str, ip: str | None) -> AppUser:
    email = passwords.normalise_email(email)
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise validation({"email": "invalid"}, M("users.invalid_email"))
    full_name = full_name.strip()
    if not 1 <= len(full_name) <= 120:
        raise validation({"full_name": "invalid"}, M("users.invalid_full_name"))
    if role == "admin" and not actor.is_superuser:
        raise forbidden(M("users.only_superuser_creates_admins"))
    check_new_password(temporary_password, email)
    if by_email(db, email):
        raise ApiError(409, "conflict", M("users.email_exists"))
    user = AppUser(email=email, full_name=full_name, role=role, created_by=actor.id,
                   password_hash=passwords.hash_password(temporary_password),
                   must_change_password=True, is_superuser=False, is_active=True,
                   failed_attempts=0)
    db.add(user)
    db.flush()
    audit.record(db, "user_created", actor_id=actor.id, target_id=user.id, ip=ip,
                 detail={"email": email, "role": role})
    return user


def update(db: Session, actor: AppUser, target: AppUser, *, full_name: str | None,
           role: str | None, is_active: bool | None, ip: str | None) -> AppUser:
    if full_name is not None and full_name.strip() != target.full_name:
        ensure_can_manage(actor, target, "edit")
        name = full_name.strip()
        if not 1 <= len(name) <= 120:
            raise validation({"full_name": "invalid"}, M("users.invalid_full_name"))
        audit.record(db, "user_updated", actor_id=actor.id, target_id=target.id, ip=ip,
                     detail={"full_name": {"from": target.full_name, "to": name}})
        target.full_name = name
    if role is not None and role != target.role:
        ensure_can_manage(actor, target, "role")
        audit.record(db, "role_changed", actor_id=actor.id, target_id=target.id, ip=ip,
                     detail={"from": target.role, "to": role})
        target.role = role
    if is_active is not None and is_active != target.is_active:
        ensure_can_manage(actor, target, "activate")
        target.is_active = is_active
        if not is_active:
            sessions.delete_all(db, target.id)
        audit.record(db, "user_reactivated" if is_active else "user_deactivated",
                     actor_id=actor.id, target_id=target.id, ip=ip)
    db.flush()
    return target


def reset_password(db: Session, actor: AppUser, target: AppUser, temporary_password: str,
                   ip: str | None) -> None:
    ensure_can_manage(actor, target, "reset_password")
    check_new_password(temporary_password, target.email)
    set_password(target, temporary_password, temporary=True)
    target.failed_attempts = 0
    target.locked_until = None
    sessions.delete_all(db, target.id)
    audit.record(db, "password_reset", actor_id=actor.id, target_id=target.id, ip=ip)


def set_password(user: AppUser, password: str, *, temporary: bool) -> None:
    user.password_hash = passwords.hash_password(password)
    user.must_change_password = temporary
    user.password_changed_at = now()
