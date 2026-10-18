"""Admin network allow-list (feature 004, FR-022, research R9)."""
import ipaddress
import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import error_body
from app.i18n import M

log = logging.getLogger("app.security")

PROTECTED_PREFIXES = ("/api/admin", "/api/sources", "/api/security", "/api/workspace",
                      "/api/integrations", "/api/tokens")
# Super-user only areas (reads included): projects and the AI assistant. Ordinary users never
# reach them, so covering the whole prefix does not break their reads.
ADMIN_ONLY_PREFIXES = ("/api/projects", "/api/assistant")
# Admin-only share controls under /api/dashboards: minting a public link, sending by e-mail and
# scheduled subscriptions. Their GET reads stay available; only the state-changing methods are
# covered below.
DASHBOARD_ADMIN_SEGMENTS = frozenset({"links", "email", "subscriptions"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_last_audit: dict[str, float] = {}


def _client(request: Request):
    host = request.client.host if request.client else None
    try:
        return ipaddress.ip_address(host) if host else None
    except ValueError:
        return None


def is_protected(path: str, method: str = "GET") -> bool:
    """Paths an administrator may only reach from allowed networks (FR-022).

    Besides the original admin prefixes, this covers the super-user areas and the dashboard
    share controls that turn a stolen session into a public data URL or an outbound e-mail."""
    if any(path == p or path.startswith(p + "/") for p in PROTECTED_PREFIXES):
        return True
    if any(path == p or path.startswith(p + "/") for p in ADMIN_ONLY_PREFIXES):
        return True
    if method.upper() not in SAFE_METHODS:
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 4 and parts[0] == "api" and parts[1] == "dashboards" \
                and parts[3] in DASHBOARD_ADMIN_SEGMENTS:
            return True
    return False


async def admin_networks(request: Request, call_next):
    networks = get_settings().admin_networks
    if networks and is_protected(request.url.path, request.method):
        ip = _client(request)
        if ip is None or not any(ip in net for net in networks if net.version == ip.version):
            _audit_once(str(ip), request.url.path)
            return JSONResponse(error_body("address_not_allowed",
                                           M("security.admin_network_blocked")),
                                status_code=403)
    return await call_next(request)


def _audit_once(ip: str, path: str) -> None:
    now = time.monotonic()
    if now - _last_audit.get(ip, -3600) < 3600:
        return
    _last_audit[ip] = now
    from app.db import get_sessionmaker
    from app.services import audit
    try:
        with get_sessionmaker().begin() as db:
            audit.record(db, "admin_address_refused", ip=ip if ip != "None" else None,
                         detail={"path": path[:200]})
    except Exception:  # auditing must never turn a refusal into a 500
        log.exception("could not audit refused admin address")
