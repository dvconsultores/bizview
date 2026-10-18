"""Security option (feature 004, FR-016/FR-017): `private` allows HTTP; `internet` requires HTTPS
for the product and every source connection, and two-step sign-in for administrators."""
from urllib.parse import urlsplit

from app.config import Settings

NOT_ALLOWED = "not_allowed_in_profile"
PLAIN_PG_MODES = {"disable", "prefer"}


class ProfileError(Exception):
    pass


def enforce_at_start(settings: Settings) -> None:
    if settings.profile != "internet":
        return
    if not settings.site_is_domain:
        raise ProfileError("SECURITY_PROFILE=internet requires SITE_ADDRESS to be a domain "
                           "(HTTPS with a certificate)")
    if not settings.cookie_secure:
        raise ProfileError("SECURITY_PROFILE=internet requires COOKIE_SECURE=true")
    if settings.smtp_security_effective == "none":
        raise ProfileError("SECURITY_PROFILE=internet requires SMTP_SECURITY=starttls or ssl")
    if settings.direct_reports_bi and not settings.direct_bi_role:
        raise ProfileError("SECURITY_PROFILE=internet with DIRECT_REPORTS_BI=true requires "
                           "DIRECT_BI_ROLE (a read-only database role, see docs/INSTALL.md)")


def url_problem(url: str, settings: Settings) -> str | None:
    scheme = urlsplit(url).scheme.lower()
    if scheme not in ("http", "https"):
        return "invalid_url"
    if scheme == "http" and not settings.http_allowed:
        return NOT_ALLOWED
    return None


def sslmode_problem(mode: str, settings: Settings) -> str | None:
    if mode in PLAIN_PG_MODES and not settings.http_allowed:
        return NOT_ALLOWED
    return None


def mfa_required_for(role: str, settings: Settings) -> bool:
    return settings.profile == "internet" and role == "admin"
