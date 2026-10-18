"""REST origins over the guarded HTTP client (feature 004)."""
import ssl
from urllib.parse import urljoin, urlsplit

import httpx

from app.config import Settings
from app.i18n import t
from app.security import profile
from app.security.netguard import BlockedAddress, guarded_client, policy_from_settings
from app.sources.connectors.base import TestResult, fail
from app.sources.schemas import header_secret_key

MAX_BYTES = 1_000_000


def _verify(settings: dict) -> ssl.SSLContext | bool:
    ca = settings.get("ca_certificate")
    return ssl.create_default_context(cadata=ca) if ca else True


def _map_http_error(e: httpx.HTTPError) -> str:
    if isinstance(e, httpx.TimeoutException):
        return "timeout"
    text = str(e).lower()
    if "ssl" in text or "certificate" in text:
        return "tls_error"
    return "unreachable"


def _read_limited(response: httpx.Response) -> bytes:
    data = b""
    for chunk in response.iter_bytes():
        data += chunk
        if len(data) > MAX_BYTES:
            break
    return data[:MAX_BYTES]


def build_request(settings: dict, secrets: dict, client: httpx.Client) -> tuple[dict, dict, object]:
    """Headers, query params, and httpx auth for the configured authentication."""
    headers: dict[str, str] = {"User-Agent": "Bizview", "Accept": "application/json, */*"}
    params: dict[str, str] = {}
    auth = None
    for h in settings.get("headers") or []:
        value = secrets.get(header_secret_key(h["name"])) if h["secret"] else h.get("value")
        if value is not None:
            headers[h["name"]] = value
    method = settings.get("auth") or "none"
    if method == "bearer":
        headers["Authorization"] = f"Bearer {secrets['token']}"
    elif method == "basic":
        auth = httpx.BasicAuth(settings["username"], secrets["password"])
    elif method == "api_key_header":
        headers[settings.get("api_key_name") or "X-API-Key"] = secrets["api_key"]
    elif method == "api_key_query":
        params[settings.get("api_key_name") or "api_key"] = secrets["api_key"]
    elif method == "oauth2_client_credentials":
        headers["Authorization"] = f"Bearer {oauth_token(settings, secrets, client)}"
    return headers, params, auth


class OAuthError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code


def oauth_token(settings: dict, secrets: dict, client: httpx.Client) -> str:
    data = {"grant_type": "client_credentials"}
    if settings.get("scope"):
        data["scope"] = settings["scope"]
    auth = None
    if (settings.get("client_auth_method") or "client_secret_basic") == "client_secret_basic":
        auth = httpx.BasicAuth(settings["client_id"], secrets["client_secret"])
    else:
        data |= {"client_id": settings["client_id"], "client_secret": secrets["client_secret"]}
    r = client.post(settings["token_url"], data=data, auth=auth,
                    headers={"Accept": "application/json"})
    if r.status_code in (400, 401, 403):
        raise OAuthError("auth_failed", f"token HTTP {r.status_code}")
    if r.status_code >= 300:
        raise OAuthError("invalid_response", f"token HTTP {r.status_code}")
    try:
        token = r.json()["access_token"]
    except (ValueError, KeyError, TypeError):
        raise OAuthError("invalid_response", "token response without access_token") from None
    return str(token)


def test(settings: dict, secrets: dict, app: Settings) -> TestResult:
    for key in ("base_url", "token_url"):
        if settings.get(key) and profile.url_problem(settings[key], app):
            return TestResult(False, profile.NOT_ALLOWED)
    url = urljoin(settings["base_url"].rstrip("/") + "/", (settings.get("test_path") or "/")
                  .lstrip("/"))
    timeout = float(settings.get("timeout_seconds") or 15)
    try:
        with guarded_client(policy=policy_from_settings(app), timeout=timeout,
                            verify=_verify(settings)) as client:
            headers, params, auth = build_request(settings, secrets, client)
            with client.stream("GET", url, headers=headers, params=params, auth=auth) as r:
                body = _read_limited(r)
                status, ctype = r.status_code, r.headers.get("content-type", "")
                location = r.headers.get("location")
    except BlockedAddress as e:
        return fail("blocked_address", str(e.reason))
    except OAuthError as e:
        return fail(e.code, str(e), secrets)
    except httpx.HTTPError as e:
        return fail(_map_http_error(e), str(e), secrets)
    details = {"status": status, "content_type": ctype.split(";")[0], "bytes": len(body)}
    if 300 <= status < 400:
        host = urlsplit(location or "").hostname or "?"
        return fail("invalid_response", t("sources.redirect_not_followed", host=host))
    if status in (401, 403):
        return TestResult(False, "auth_failed", details=details)
    if status == 404:
        return TestResult(False, "not_found", details=details)
    if status >= 400:
        return TestResult(False, "invalid_response", details=details)
    return TestResult(True, details=details)
