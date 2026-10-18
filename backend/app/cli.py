"""Operator commands (research R4).

    python -m app.cli bootstrap                  # run by the container before serving
    python -m app.cli reset-superuser-password   # recovery: apply SUPER_USER_PASSWORD again
    python -m app.cli mail-test <address>        # send a test email with the SMTP_* settings
"""
import argparse
import logging
import os
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import passwords, sessions
from app.config import get_settings
from app.db import get_sessionmaker
from app.models import AppUser
from app.security import crypto, profile, throttle
from app.services import audit, users

log = logging.getLogger("app.cli")


class ConfigError(Exception):
    pass


def _configured() -> tuple[str, str]:
    s = get_settings()
    email = passwords.normalise_email(s.super_user_email or "")
    pw = s.super_user_password or ""
    if not email or not users.EMAIL_RE.match(email):
        raise ConfigError("SUPER_USER_EMAIL is missing or not a valid email")
    if not pw:
        raise ConfigError("SUPER_USER_PASSWORD is missing")
    problem = passwords.password_problem(pw, email)
    if problem:
        raise ConfigError(f"SUPER_USER_PASSWORD breaks the password rules ({problem})")
    return email, pw


def bootstrap(db: Session) -> str:
    """Check security settings and the secret key, ensure exactly one super user exists."""
    try:
        profile.enforce_at_start(get_settings())
        crypto.verify_key_at_start(db, crypto.get_keyring())
    except (profile.ProfileError, crypto.CryptoError) as exc:
        raise ConfigError(str(exc)) from None
    sessions.purge_expired(db)
    audit.purge_older_than(db)
    throttle.purge(db)
    from app.projects import fs as project_fs
    if not project_fs.check_dir():       # 020 plan: say it at start, not on the first create
        log.warning("PROJECTS_DIR %s is missing or not writable by uid %s (the container runs as "
                    "the 'app' user): BI projects cannot be created. On the host: "
                    "sudo mkdir -p projects attachments && sudo chown -R 10001:10001 projects "
                    "attachments", get_settings().projects_dir, os.getuid())
    from app.projects.service import purge_trash
    purge_trash(db)
    from app.sources.service import import_legacy_origin
    import_legacy_origin(db, get_settings())
    result = _superuser_step(db)
    from app.projects.importer import upgrade
    upgrade(db)   # feature 020: `principal` and open drafts become projects (idempotent)
    return result


def _superuser_step(db: Session) -> str:
    existing = db.scalar(select(AppUser).where(AppUser.is_superuser.is_(True)))
    if existing is not None:
        configured = passwords.normalise_email(get_settings().super_user_email or "")
        if configured and configured != existing.email:
            log.warning("SUPER_USER_EMAIL differs from the existing super user; ignored")
        return "exists"
    email, pw = _configured()
    user = users.by_email(db, email)
    if user is None:
        user = AppUser(email=email, full_name="Superusuario", role="admin", is_superuser=True,
                       is_active=True, must_change_password=False, failed_attempts=0,
                       password_hash=passwords.hash_password(pw))
        db.add(user)
        db.flush()
        audit.record(db, "superuser_created", target_id=user.id)
        return "created"
    user.role, user.is_superuser, user.is_active = "admin", True, True
    users.set_password(user, pw, temporary=False)
    user.failed_attempts, user.locked_until = 0, None
    sessions.delete_all(db, user.id)
    db.flush()
    audit.record(db, "superuser_promoted", target_id=user.id)
    return "promoted"


def reset_superuser_password(db: Session) -> str:
    email, pw = _configured()
    user = db.scalar(select(AppUser).where(AppUser.is_superuser.is_(True)))
    if user is None:
        raise ConfigError("no super user exists yet; run bootstrap")
    if user.email != email:
        raise ConfigError(f"SUPER_USER_EMAIL does not match the super user ({user.email})")
    users.set_password(user, pw, temporary=False)
    user.failed_attempts, user.locked_until = 0, None
    sessions.delete_all(db, user.id)
    audit.record(db, "superuser_recovered", target_id=user.id)
    return "recovered"


def reset_superuser_mfa(db: Session) -> str:
    """Server-side recovery when the super user lost the authenticator and recovery codes."""
    from app.security import mfa
    user = db.scalar(select(AppUser).where(AppUser.is_superuser.is_(True)))
    if user is None:
        raise ConfigError("no super user exists yet; run bootstrap")
    mfa.disable(db, user)
    sessions.delete_all(db, user.id)
    audit.record(db, "mfa_reset", target_id=user.id, detail={"via": "cli"})
    return "two-step sign-in reset; enroll again after signing in"


def rotate_secret_key(db: Session) -> str:
    counts = crypto.rotate(db, crypto.get_keyring())
    audit.record(db, "secret_key_rotated", detail=counts)
    return (
        f"re-encrypted {counts['data_source']} sources, {counts['app_user']} two-step "
        f"secrets, {counts['telegram_settings']} Telegram tokens and "
        f"{counts['email_send']} email links; now remove BIZVIEW_SECRET_KEY_PREVIOUS"
    )


def mail_test(db: Session, address: str) -> tuple[bool, str]:
    from app.mail import send as mail_send
    from app.mail import sends
    from app.mail import settings as mail_settings
    from app.mail.addresses import normalize_email

    addr = normalize_email(address)
    if addr is None:
        raise ConfigError("mail-test needs one valid email address")
    settings = get_settings()
    if not settings.email_enabled:
        missing = settings.email_missing or ["SMTP_HOST", "SMTP_FROM"]
        raise ConfigError(
            f"email is not configured: set {', '.join(missing)} in the installation .env"
        )
    code = mail_settings.deliver_test(addr, base_url=sends.site_base())
    ok = code is None
    detail = {"ok": ok, "via": "cli"}
    if not ok:
        detail["reason"] = code
    audit.record(db, "email_test_sent", actor_id=None, detail=detail)
    if ok:
        return True, f"test email sent to {addr}"
    return False, f"test email failed ({code}): {mail_send.reason(code)}"


COMMANDS = {"bootstrap": bootstrap, "reset-superuser-password": reset_superuser_password,
            "reset-superuser-mfa": reset_superuser_mfa, "rotate-secret-key": rotate_secret_key,
            "mail-test": mail_test}


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="app.cli")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("address", nargs="?")
    args = parser.parse_args(argv)
    if args.command != "mail-test" and args.address is not None:
        parser.error(f"{args.command} takes no arguments")
    if args.command == "mail-test" and args.address is None:
        log.error("mail-test needs one email address: python -m app.cli mail-test <address>")
        return 1
    try:
        with get_sessionmaker().begin() as db:
            if args.command == "mail-test":
                ok, result = COMMANDS[args.command](db, args.address)
            else:
                result = COMMANDS[args.command](db)
    except (ConfigError, crypto.CryptoError) as exc:
        log.error("%s", exc)
        return 1
    if args.command == "mail-test":
        if ok:
            log.info("mail-test: %s", result)
            return 0
        log.error("mail-test: %s", result)
        return 1
    log.info("%s: %s", args.command, result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
