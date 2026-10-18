"""Per-kind field definitions of data sources (feature 004, contracts/connectors.md).

Single source of truth for validation, the profile rules (HTTP vs HTTPS), and the admin forms
(served by GET /api/sources/types). Secret fields are write-only.
"""
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.config import Settings
from app.i18n import t
from app.security import profile
from app.security.netguard import BlockedAddress, Policy, resolve_checked

TIMEOUT = {"name": "timeout_seconds", "label": "Tiempo máximo (s)", "type": "integer",
           "default": 15, "min": 1, "max": 60}


@dataclass(frozen=True)
class F:
    name: str
    label: str
    type: str                     # string | integer | enum | url | pem | headers
    required: bool = False
    secret: bool = False
    default: Any = None
    options: tuple = ()
    private_only: tuple = ()      # enum options allowed only in the private profile
    show_if: dict = field(default_factory=dict)   # {field: [values]}
    min: int | None = None
    max: int | None = None
    help: str = ""


def _t(**kw) -> F:
    return F(**kw)


PG = (
    F("host", "Servidor", "string", required=True, help="Nombre o IP del servidor PostgreSQL"),
    F("port", "Puerto", "integer", default=5432, min=1, max=65535),
    F("database", "Base de datos", "string", required=True),
    F("username", "Usuario", "string", required=True, help="Use un usuario de solo lectura"),
    F("password", "Contraseña", "string", required=True, secret=True),
    F("sslmode", "Cifrado (TLS)", "enum", default="require",
      options=("require", "verify-full", "prefer", "disable"), private_only=("prefer", "disable"),
      help="verify-full comprueba el certificado del servidor"),
    F("ca_certificate", "Certificado de la CA (PEM)", "pem", show_if={"sslmode": ["verify-full"]}),
    _t(**TIMEOUT),
)
USER_AUTH = ["basic", "wsse_username_token"]
SOAP = (
    F("wsdl_url", "Dirección del WSDL", "url", required=True),
    F("service", "Servicio (opcional)", "string"),
    F("port", "Puerto/binding (opcional)", "string"),
    F("auth", "Autenticación", "enum", default="basic",
      options=("basic", "wsse_username_token", "client_certificate", "none")),
    F("username", "Usuario", "string", required=True, show_if={"auth": USER_AUTH}),
    F("password", "Contraseña", "string", required=True, secret=True,
      show_if={"auth": USER_AUTH}),
    F("client_certificate", "Certificado de cliente (PEM)", "pem", required=True,
      show_if={"auth": ["client_certificate"]}),
    F("client_key", "Clave privada del cliente (PEM)", "pem", required=True, secret=True,
      show_if={"auth": ["client_certificate"]}),
    F("ca_certificate", "Certificado de la CA (PEM)", "pem"),
    _t(**TIMEOUT),
)
OAUTH = ["oauth2_client_credentials"]
API_KEY = ["api_key_header", "api_key_query"]
REST = (
    F("base_url", "Dirección base", "url", required=True),
    F("test_path", "Ruta de prueba", "string", default="/"),
    F("auth", "Autenticación", "enum", default="none",
      options=("none", "bearer", "basic", "api_key_header", "api_key_query",
               "oauth2_client_credentials")),
    F("token", "Token (Bearer)", "string", required=True, secret=True,
      show_if={"auth": ["bearer"]}),
    F("username", "Usuario", "string", required=True, show_if={"auth": ["basic"]}),
    F("password", "Contraseña", "string", required=True, secret=True,
      show_if={"auth": ["basic"]}),
    F("api_key_name", "Nombre de la clave", "string", show_if={"auth": API_KEY},
      help="Encabezado (p. ej. X-API-Key) o parámetro (p. ej. api_key)"),
    F("api_key", "Clave de API", "string", required=True, secret=True, show_if={"auth": API_KEY}),
    F("token_url", "Dirección del token (OAuth 2.0)", "url", required=True,
      show_if={"auth": OAUTH}),
    F("client_id", "Client ID", "string", required=True, show_if={"auth": OAUTH}),
    F("client_secret", "Client secret", "string", required=True, secret=True,
      show_if={"auth": OAUTH}),
    F("scope", "Scope", "string", show_if={"auth": OAUTH}),
    F("client_auth_method", "Envío de credenciales del cliente", "enum",
      default="client_secret_basic", options=("client_secret_basic", "client_secret_post"),
      show_if={"auth": OAUTH}),
    F("headers", "Encabezados adicionales", "headers", default=[]),
    F("ca_certificate", "Certificado de la CA (PEM)", "pem"),
    _t(**TIMEOUT),
)
# Supabase (feature 016): its REST API (PostgREST) with the project's URL and service key; the
# connector adds the `apikey` header and the Bearer token, and only ever reads (GET).
SUPABASE = (
    F("url", "URL del proyecto (SUPABASE_URL)", "url", required=True,
      help="Por ejemplo https://abcd1234.supabase.co"),
    F("service_key", "Clave de servicio (SUPABASE_SERVICE_KEY)", "string", required=True,
      secret=True, help="Se guarda cifrada y no se vuelve a mostrar. BizView solo lee."),
    _t(**TIMEOUT),
)
KINDS = {
    "postgresql": {"label": "PostgreSQL", "fields": PG},
    "soap": {"label": "SOAP (SAP y otros)", "fields": SOAP},
    "rest": {"label": "API REST", "fields": REST},
    "supabase": {"label": "Supabase", "fields": SUPABASE},
}
HOST_FIELDS = {"host"}
URL_FIELDS = {"wsdl_url", "base_url", "token_url", "url"}
FORBIDDEN_HEADERS = {"host", "content-length", "transfer-encoding", "connection", "cookie"}
HEADER_NAME = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]{1,100}$")


def header_secret_key(name: str) -> str:
    return f"header:{name.lower()}"


def types_for(settings: Settings) -> dict:
    """Field definitions for the forms; options not allowed by the profile are removed."""
    out = {}
    for kind, spec in KINDS.items():
        fields = []
        for f in spec["fields"]:
            d = asdict(f)
            if f.private_only and not settings.http_allowed:
                d["options"] = [o for o in f.options if o not in f.private_only]
            else:
                d["options"] = list(f.options)
            d.pop("private_only")
            # Labels render in the request language (feature 022); the Spanish text
            # in the definitions above is the catalogue's source and a test keeps them equal.
            d["label"] = t(f"sources.{kind}.{f.name}")
            d["help"] = t(f"sources.{kind}.{f.name}.help") if f.help else ""
            fields.append(d)
        out[kind] = {"label": t(f"sources.kind.{kind}"), "fields": fields,
                     "http_allowed": settings.http_allowed}
    return out


def _visible(f: F, values: dict) -> bool:
    return all(values.get(k) in allowed for k, allowed in f.show_if.items())


@dataclass
class Result:
    settings: dict
    secrets: dict
    errors: dict


def validate(kind: str, settings_in: dict, secrets_in: dict, existing_secrets: dict,
             app: Settings, *, check_addresses: bool = True) -> Result:
    """Normalise settings and merge secrets (omitted = keep, None = clear, value = replace)."""
    spec = KINDS.get(kind)
    if spec is None:
        return Result({}, {}, {"kind": "invalid"})
    errors: dict[str, str] = {}
    values: dict[str, Any] = {}
    secrets = dict(existing_secrets)
    for key, val in (secrets_in or {}).items():
        if val is None:
            secrets.pop(key, None)
        elif isinstance(val, str):
            secrets[key] = val
        else:
            errors[f"secrets.{key}"] = "invalid"
    secret_names = {f.name for f in spec["fields"] if f.secret}

    for f in spec["fields"]:
        if f.secret:
            continue
        raw = (settings_in or {}).get(f.name, f.default)
        if isinstance(raw, str):
            raw = raw.strip()
        if raw in ("", None):
            values[f.name] = f.default
            continue
        values[f.name] = raw
    for f in spec["fields"]:
        if not _visible(f, values):
            values.pop(f.name, None) if not f.secret else secrets.pop(f.name, None)
            continue
        if f.secret:
            if f.required and not secrets.get(f.name):
                errors[f"secrets.{f.name}"] = "required"
            continue
        val = values.get(f.name)
        key = f"settings.{f.name}"
        if f.required and val in (None, ""):
            errors[key] = "required"
            continue
        if val is None:
            continue
        if f.type == "integer":
            try:
                val = int(val)
            except (TypeError, ValueError):
                errors[key] = "invalid"
                continue
            if (f.min is not None and val < f.min) or (f.max is not None and val > f.max):
                errors[key] = "out_of_range"
            values[f.name] = val
        elif f.type == "enum":
            if val not in f.options:
                errors[key] = "invalid"
            elif val in f.private_only and not app.http_allowed:
                errors[key] = profile.NOT_ALLOWED
        elif f.type == "url":
            problem = profile.url_problem(str(val), app)
            if problem:
                errors[key] = problem
        elif f.type == "pem":
            if "-----BEGIN " not in str(val):
                errors[key] = "invalid_pem"
        elif f.type == "string" and len(str(val)) > 500:
            errors[key] = "too_long"
        elif f.type == "headers":
            values[f.name] = _headers(val, secrets, errors)
    # Headers: secret values live with the secrets; drop secrets of removed headers.
    if kind == "rest":
        keep = {header_secret_key(h["name"]) for h in values.get("headers", []) if h["secret"]}
        for k in [k for k in secrets if k.startswith("header:") and k not in keep]:
            secrets.pop(k)
        for h in values.get("headers", []):
            if h["secret"] and not secrets.get(header_secret_key(h["name"])):
                errors["settings.headers"] = "secret_value_required"
    unknown = set(secrets) - secret_names - {k for k in secrets if k.startswith("header:")}
    for k in unknown:
        errors[f"secrets.{k}"] = "unknown"
    if check_addresses and not errors:
        _check_destinations(kind, values, app, errors)
    return Result(values, secrets, errors)


def _headers(val, secrets: dict, errors: dict) -> list[dict]:
    out, seen = [], set()
    if not isinstance(val, list) or len(val) > 20:
        errors["settings.headers"] = "invalid"
        return []
    for item in val:
        if not isinstance(item, dict):
            errors["settings.headers"] = "invalid"
            continue
        name = str(item.get("name", "")).strip()
        secret = bool(item.get("secret"))
        if not HEADER_NAME.match(name) or name.lower() in FORBIDDEN_HEADERS \
                or name.lower() in seen:
            errors["settings.headers"] = "invalid_header"
            continue
        seen.add(name.lower())
        value = item.get("value")
        if secret:
            if isinstance(value, str) and value:
                secrets[header_secret_key(name)] = value
            out.append({"name": name, "secret": True})
        else:
            if not isinstance(value, str) or "\n" in value or "\r" in value:
                errors["settings.headers"] = "invalid_header"
                continue
            out.append({"name": name, "secret": False, "value": value})
    return out


def _check_destinations(kind: str, values: dict, app: Settings, errors: dict) -> None:
    from urllib.parse import urlsplit
    policy = Policy(allow_private=app.sources_allow_private_networks)
    targets = []
    if kind == "postgresql":
        targets.append(("settings.host", values.get("host"), values.get("port") or 5432))
    for name in URL_FIELDS:
        if values.get(name):
            u = urlsplit(values[name])
            targets.append((f"settings.{name}", u.hostname, u.port or 443))
    for key, host, port in targets:
        if not host:
            continue
        try:
            resolve_checked(host, int(port), policy)
        except BlockedAddress as e:
            if not e.unresolved:   # unresolvable here may resolve on the worker's net
                errors[key] = "blocked_address"


def secret_field_names(kind: str, secrets: dict) -> list[str]:
    return sorted(secrets)
