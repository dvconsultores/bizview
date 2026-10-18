"""Email status and test email helpers (feature 018). The SMTP server and the share-link
switch come from the installation environment (SMTP_*, EMAIL_ALLOWED_DOMAINS,
SHARE_LINKS_ENABLED); nothing is stored in the database. `status()` is used by the test
hooks and `deliver_test()` by the CLI mail-test command."""
from app.config import Settings, get_settings
from app.i18n import t
from app.mail import send as mail_send
from app.mail.addresses import email_domain, normalize_email  # noqa: F401  (re-exported)


def available() -> bool:
    return get_settings().email_enabled


def sharing_enabled() -> bool:
    return get_settings().share_links_enabled


def allowed_domains() -> list[str]:
    return get_settings().email_domains


def smtp_config() -> mail_send.SmtpConfig:
    return mail_send.config_from(get_settings())


def status(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    security = settings.smtp_security_effective
    return {
        "enabled": settings.email_enabled,
        "configured": settings.email_enabled,
        "missing": settings.email_missing,
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "security": security,
        "security_allowed": not (security == "none" and settings.profile == "internet"),
        "username": settings.smtp_user,
        "password_configured": settings.smtp_password is not None,
        "sender_name": settings.smtp_from_name,
        "sender_address": settings.smtp_from,
        "allowed_domains": settings.email_domains,
        "sharing_enabled": settings.share_links_enabled,
        "profile": settings.profile,
    }


def deliver_test(to: str, *, base_url: str | None = None) -> str | None:
    """Send the test email to `to`; None on success, else the sanitized MailError code."""
    settings = get_settings()
    if not settings.email_enabled:
        return "not_configured"
    cfg = smtp_config()
    msg = mail_send.build_message(
        cfg=cfg,
        to=to,
        subject=t("mail.test_subject"),
        organization=settings.organization_name,
        product=settings.product_name,
        dashboard_name=t("mail.test_subject"),
        period_label=None,
        note=t("mail.test_note"),
        link_url=None,
        link_expires=None,
        attachment=None,
        logo_url=mail_send.logo_src(settings.logo_url, base_url),
    )
    try:
        mail_send.deliver(cfg, msg)
    except mail_send.MailError as e:
        return e.code
    return None
