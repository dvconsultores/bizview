"""SOAP origins (SAP and others) with zeep over the guarded HTTP client (feature 004).

XML safety: no DTDs, no entities, no external references, no huge trees; the transport loads
only http(s) URLs through the address guard — never local files (zeep's default loader would
open `file://` URLs and plain paths found in a WSDL).
"""
from urllib.parse import urlsplit

import httpx
import zeep
from zeep.exceptions import Error as ZeepError
from zeep.exceptions import TransportError
from zeep.wsse.username import UsernameToken

from app.config import Settings
from app.security import profile
from app.security.netguard import BlockedAddress, guarded_client, policy_from_settings
from app.sources.connectors.base import TestResult, fail, temp_pem
from app.sources.connectors.rest import MAX_BYTES, _map_http_error, _verify

MAX_OPERATIONS = 200
SAFE_XML = dict(strict=False, xml_huge_tree=False, forbid_dtd=True, forbid_entities=True,
                forbid_external=True)


class GuardedTransport(zeep.Transport):
    def __init__(self, client: httpx.Client, *, http_allowed: bool, auth=None):
        super().__init__(cache=None)
        self._client, self._http_allowed, self._auth = client, http_allowed, auth

    def _check_url(self, url: str) -> None:
        scheme = urlsplit(url).scheme.lower()
        if scheme not in ("http", "https") or (scheme == "http" and not self._http_allowed):
            raise TransportError(f"URL scheme not allowed: {scheme or 'local path'}")

    def load(self, url):
        if not url:
            raise ValueError("No url given to load")
        self._check_url(url)
        with self._client.stream("GET", url, auth=self._auth) as r:
            if r.status_code in (401, 403):
                raise TransportError("auth", status_code=r.status_code)
            if r.status_code >= 300:
                raise TransportError(f"HTTP {r.status_code}", status_code=r.status_code)
            data = b""
            for chunk in r.iter_bytes():
                data += chunk
                if len(data) > MAX_BYTES * 5:
                    raise TransportError("document too large")
            return data

    def get(self, address, params, headers):
        self._check_url(address)
        return self._client.get(address, params=params, headers=headers, auth=self._auth)

    def post(self, address, message, headers):
        self._check_url(address)
        return self._client.post(address, content=message, headers=headers, auth=self._auth)


def build_client(settings: dict, secrets: dict, app: Settings, http_client: httpx.Client):
    method = settings.get("auth") or "basic"
    http_auth = wsse = None
    if method in ("basic", "wsse_username_token"):
        http_auth = httpx.BasicAuth(settings["username"], secrets["password"])
    if method == "wsse_username_token":
        wsse = UsernameToken(settings["username"], secrets["password"])
    transport = GuardedTransport(http_client, http_allowed=app.http_allowed, auth=http_auth)
    return zeep.Client(settings["wsdl_url"], transport=transport, wsse=wsse,
                       settings=zeep.Settings(**SAFE_XML),
                       service_name=settings.get("service") or None,
                       port_name=settings.get("port") or None)


def list_operations(client: zeep.Client) -> list[dict]:
    out, count = [], 0
    for service in client.wsdl.services.values():
        ports = []
        for port in service.ports.values():
            ops = sorted(port.binding._operations.keys())[: max(0, MAX_OPERATIONS - count)]
            count += len(ops)
            ports.append({"name": port.name, "operations": ops})
        out.append({"name": service.name, "ports": ports})
    return out


def test(settings: dict, secrets: dict, app: Settings) -> TestResult:
    if profile.url_problem(settings["wsdl_url"], app):
        return TestResult(False, profile.NOT_ALLOWED)
    timeout = float(settings.get("timeout_seconds") or 15)
    try:
        with temp_pem(settings.get("client_certificate")) as cert_path, \
                temp_pem(secrets.get("client_key")) as key_path:
            cert = (cert_path, key_path) if cert_path and key_path else None
            http_client = guarded_client(policy=policy_from_settings(app), timeout=timeout,
                                         verify=_verify(settings), cert=cert)
        with http_client:
            client = build_client(settings, secrets, app, http_client)
            services = list_operations(client)
    except BlockedAddress as e:
        return fail("blocked_address", str(e.reason))
    except TransportError as e:
        code = "auth_failed" if getattr(e, "status_code", None) in (401, 403) else (
            "not_found" if getattr(e, "status_code", None) == 404 else "invalid_response")
        return fail(code, str(e), secrets)
    except httpx.HTTPError as e:
        return fail(_map_http_error(e), str(e), secrets)
    except (ZeepError, ValueError, KeyError) as e:
        # Includes DTD/entity/external-reference refusals and malformed WSDL.
        return fail("invalid_response", f"{type(e).__name__}: {e}", secrets)
    except Exception as e:  # lxml errors and other parser failures
        return fail("invalid_response", type(e).__name__, secrets)
    n_ops = sum(len(p["operations"]) for s in services for p in s["ports"])
    return TestResult(True, details={"services": services, "operations": n_ops})
