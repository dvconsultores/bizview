"""Runtime settings, read from the environment (or the repository's .env for local runs)."""
import ipaddress
import os
import re
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.mail.addresses import HOST, normalize_domains, normalize_email

ROOT = Path(__file__).resolve().parents[2]
ROOT_ENV = ROOT / ".env"
VERSION_FILE = ROOT / "VERSION"

AIProvider = Literal["none", "anthropic", "openai_compatible", "fake"]  # fake: test hooks only
SecurityProfile = Literal["private", "internet"]
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"


def _file_version() -> str:
    try:
        return VERSION_FILE.read_text().strip() or "dev"
    except OSError:
        return "dev"


# The vendor's own installations (the demo and any *.getbizview.com deployment) show the vendor's
# legal pages without extra configuration. A customer's domain gets nothing until it sets its own
# URLs, so the product never presents Global DV as the controller of their data.
OFFICIAL_LEGAL_DOMAIN = "getbizview.com"
OFFICIAL_PRIVACY_URL = "https://www.getbizview.com/privacidad/"
OFFICIAL_TERMS_URL = "https://www.getbizview.com/terminos/"


def _official_legal_host(host: str) -> bool:
    return host == OFFICIAL_LEGAL_DOMAIN or host.endswith("." + OFFICIAL_LEGAL_DOMAIN)


class Settings(BaseSettings):
    # Tests set BIZVIEW_NO_ENV_FILE so a developer's .env (a larger budget, a real provider) cannot
    # leak into them; deployments never set it.
    model_config = SettingsConfigDict(
        env_file=(ROOT_ENV
                  if ROOT_ENV.exists() and not os.environ.get("BIZVIEW_NO_ENV_FILE") else None),
        extra="ignore",
        hide_input_in_errors=True,
    )

    database_url_bi: str
    # Schema for the product's tables. Always the standard "public" in real deployments; the
    # test suites set a temporary "app_test_*" schema so they never touch real data.
    db_schema: str = "public"
    super_user_email: str | None = None
    super_user_password: str | None = None

    # Baked into the backend image (BIZVIEW_VERSION); the VERSION file in development.
    bizview_version: str = Field(default_factory=_file_version)
    # Commit the image was built from (BIZVIEW_COMMIT, a build arg deploy.sh passes): /api/health
    # then answers which code a running installation actually has, instead of leaving it to guess.
    bizview_commit: str | None = None
    # Source code offered to every user (AGPL-3.0 §13). Release images bake in the repository
    # address (build arg BIZVIEW_SOURCE_URL → SOURCE_URL); an installation may override it.
    source_url: str | None = None

    # Optional AI provider (constitution VIII): off unless configured. Since 045 the callers are the
    # read-only help agent (033) and the structure generator (052); authoring lives outside BizView.
    ai_provider: AIProvider = "none"
    ai_api_key: SecretStr | None = None
    ai_model: str | None = Field(default=None, max_length=100)
    ai_base_url: str | None = None
    ai_timeout_seconds: float = Field(default=30, ge=1, le=300)
    # Feature 052: one structure generation is a super user's deliberate action, so the ceiling is
    # per run (not per day): past it the run stops chunking and says what it did not examine.
    ai_structure_tokens: int = Field(default=150_000, ge=0)
    # Origin checks run inside this window (SQL/HTTP), on the explicit validate action only.
    origin_check_timeout_seconds: float = Field(default=20, ge=1, le=120)

    # Email and share links (feature 018, amendment 2026-10-07): installation environment only,
    # like the AI settings; nothing about the SMTP server is stored in the database.
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    # None: ssl on 465, else starttls
    smtp_security: Literal["starttls", "ssl", "none"] | None = None
    smtp_user: str | None = Field(default=None, max_length=254)
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None
    smtp_from_name: str | None = Field(default=None, max_length=120)
    # 058: an optional restriction. Empty (the default) accepts any domain; a list limits the free
    # addresses and the members of a mailing list, never the installation's own users.
    email_allowed_domains: str = ""
    # 058: delivery throughput, the only guard the product keeps. A big list is one job delivered in
    # messages of EMAIL_BATCH_SIZE recipients (BCC) at EMAIL_SEND_RATE messages per second (0 = no
    # pause); EMAIL_INDIVIDUAL_MESSAGES sends one message per address instead (SES bounce handling).
    email_batch_size: int = Field(default=50, ge=1, le=500)
    email_send_rate: int = Field(default=10, ge=0, le=100)
    email_individual_messages: bool = False
    email_sending_paused: bool = False
    # 058: who the mail says it comes from — the installation's address with the sender as Reply-To,
    # or the sender's own address through the same relay (a corporate send-as account).
    email_from_mode: Literal["installation", "user"] = "installation"
    # 058: `admin` restricts free addresses to administrators; list members are unaffected.
    email_free_addresses_role: Literal["user", "admin"] = "user"
    share_links_enabled: bool = False

    # Google sign-in (feature 027): an additional identity for accounts that already exist, off
    # unless the installation configures its own OAuth client. The secret is read only here.
    google_auth_enabled: bool = False
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_allowed_domains: str | None = None   # comma- or space-separated email domains
    google_redirect_uri: str | None = None      # default: derived from SITE_ADDRESS

    # ---- Direct reports (feature 019) ------------------------------------------------
    # reports may read tables of the BI database directly
    direct_reports_bi: bool = True
    # at most this many direct queries at once per source
    direct_report_concurrency: int = Field(default=2, ge=1, le=20)
    # above this estimated row count a direct table needs an index on its date column;
    # the agent warns
    direct_report_warn_rows: int = Field(default=5_000_000, ge=1)
    # defence in depth: read-only database role applied to built-in bi sessions
    # (required on the internet profile; see docs/INSTALL.md)
    direct_bi_role: str | None = None
    # Integration transforms (feature 005 amendment 2026-10-08): safety stop on whole-mode
    # input rows, and the folder where whole-mode windows are spilled to Arrow files.
    transform_max_rows: int = Field(default=50_000_000, ge=1)
    transform_spill_dir: str = Field(
        default_factory=lambda: os.path.join(tempfile.gettempdir(), "bizview-transform"))
    # daily rollups (feature 005 amendment): time limit of a build outside a run (worker job)
    rollup_timeout_seconds: int = Field(default=1800, ge=1)
    # Feature 060: an origin that refuses the connection because it has no free slots is waited
    # out inside the run — attempts counted in total (1 = never retry) and the base of the
    # exponential backoff (15 s → 15 s, 45 s, 2 min, 5 min for four attempts).
    source_connect_retries: int = Field(default=4, ge=1, le=10)
    source_connect_backoff_s: int = Field(default=15, ge=1, le=600)

    # Reports read the active workspace version from memory for this long (one round trip less
    # per request on a remote database); applies and rollbacks in this process clear it at once.
    active_version_cache_seconds: float = Field(default=5.0, ge=0, le=60)
    # Connections to the BI database. A new one costs ~1.4 s against a remote server (TCP + TLS +
    # auth), so enough of them stay open for a page's parallel requests, and a few are opened
    # when the app starts.
    db_pool_size: int = Field(default=12, ge=1, le=50)
    db_pool_overflow: int = Field(default=8, ge=0, le=50)
    db_pool_warm: int = Field(default=8, ge=0, le=50)

    # Encryption of credentials at rest (feature 004): base64url of 32 bytes. Never in the DB.
    bizview_secret_key: SecretStr | None = None
    bizview_secret_key_previous: SecretStr | None = None  # only while rotating

    # Security option (feature 004, FR-016/017): private allows HTTP; internet requires HTTPS.
    security_profile: Literal["auto", "private", "internet"] = "auto"
    site_address: str = ":80"
    admin_allowed_networks: str = ""        # comma-separated CIDRs; empty = no restriction
    sources_allow_private_networks: bool = True
    # Feature 061: the only folder a SQLite source may read from. Unset means the SQLite kind is
    # not offered at all (the operator has mounted no export folder).
    sources_files_dir: str | None = None
    login_rate_limit: int = Field(default=20, ge=1, le=10_000)
    login_rate_window_minutes: int = Field(default=15, ge=1, le=1440)

    # Legacy (feature 004, research R10): imported once as a data source, otherwise unused.
    database_url_origin: str | None = None

    # Vibe reporting (feature 005): the customer's workspace checkout (mounted read-only), the
    # installation time zone (integration schedules and report periods), and the worker.
    # Feature 020: reports and integrations normally come from BI projects below, so the shipped
    # compose mounts no checkout; this default is an internal, always-present folder and only an
    # operator who wants a Git checkout sets WORKSPACE_PATH and adds the volume.
    workspace_path: str = "/app/data/workspace"
    timezone: str = "UTC"
    worker_poll_seconds: int = Field(default=10, ge=1, le=3600)
    # BI projects (feature 020): one writable folder per project (backend only).
    # Feature 049: two allowances, counted separately — the project's own files and its images.
    # These are the deployment defaults; a super user may override any of them in the app, and a
    # stored override wins over these.
    projects_dir: str = Field(default_factory=lambda: str(ROOT / "projects"))
    project_max_files: int = Field(default=400, ge=1, le=100_000)
    project_max_kb: int = Field(default=2048, ge=1, le=1_048_576)
    project_max_mb: int = Field(default=20, ge=1, le=500)
    project_asset_max_files: int = Field(default=2000, ge=1, le=100_000)
    project_asset_max_kb: int = Field(default=300, ge=1, le=1_048_576)
    project_asset_max_mb: int = Field(default=25, ge=1, le=2000)
    # Feature 055: how many revisions of a project are kept. A project is re-imported on every
    # correction, so the list grows by design; the applied and previous ones are never pruned.
    project_revisions_keep: int = Field(default=20, ge=1, le=200)
    # Images fetched once from an `image_url` column of a report (feature 044): content-addressed
    # files outside PROJECTS_DIR, shared by every project that asks for the same URL.
    image_cache_dir: str = Field(default_factory=lambda: str(ROOT / "image-cache"))
    image_cache_days: int = Field(default=90, ge=1, le=3650)
    # Interface language when neither the account nor the browser decides (feature 022)
    default_locale: Literal["es", "en"] = "es"

    product_name: str = "Bizview"
    organization_name: str = ""
    logo_url: str | None = None
    # Who publishes the installation, shown after the license in the footer (feature 024 polish).
    footer_credit: str = "GlobalDV"
    # Public legal pages of whoever operates this installation. Google's OAuth consent screen asks
    # for them, and the footer shows them when set; empty keeps them out of a self-hosted install.
    legal_privacy_url: str | None = Field(default=None, max_length=500)
    legal_terms_url: str | None = Field(default=None, max_length=500)

    cookie_secure: bool = True
    docs_enabled: bool = False
    log_level: str = "INFO"

    @field_validator("database_url_bi")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, v: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"TIMEZONE: unknown time zone {v!r}") from None
        return v

    @field_validator("db_schema")
    @classmethod
    def _schema_name(cls, v: str) -> str:
        if v != "public" and not re.fullmatch(r"app_test_[a-z0-9_]{1,40}", v):
            raise ValueError("DB_SCHEMA must be 'public' (or 'app_test_*' for tests)")
        return v

    @field_validator("logo_url", "source_url", "ai_api_key", "ai_model", "ai_base_url",
                     "bizview_secret_key", "bizview_secret_key_previous", "database_url_origin",
                     "direct_bi_role", "google_client_id", "google_client_secret",
                     "google_allowed_domains", "google_redirect_uri", "legal_privacy_url",
                     "legal_terms_url", mode="before")
    @classmethod
    def _empty_is_none(cls, v):
        return v or None

    @field_validator("legal_privacy_url", "legal_terms_url")
    @classmethod
    def _public_http_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        from urllib.parse import urlsplit

        parts = urlsplit(v)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("LEGAL_*_URL must be an absolute http(s) URL")
        return v

    @field_validator("direct_bi_role")
    @classmethod
    def _valid_role_name(cls, v):
        if v is None:
            return v
        if len(v) > 63 or "\x00" in v:
            raise ValueError("DIRECT_BI_ROLE: invalid role name")
        return v

    @field_validator("ai_provider", mode="before")
    @classmethod
    def _provider_default(cls, v):
        return v or "none"

    @field_validator("ai_provider")
    @classmethod
    def _fake_only_with_test_hooks(cls, v):
        if v == "fake" and os.environ.get("BIZVIEW_TEST_HOOKS") != "1":
            raise ValueError("AI_PROVIDER=fake is only available with BIZVIEW_TEST_HOOKS=1")
        return v

    @field_validator("security_profile", mode="before")
    @classmethod
    def _profile_default(cls, v):
        return (v or "auto").strip().lower()

    @field_validator("admin_allowed_networks")
    @classmethod
    def _networks(cls, v: str) -> str:
        for part in filter(None, (p.strip() for p in v.split(","))):
            try:
                ipaddress.ip_network(part, strict=False)
            except ValueError as e:
                raise ValueError(f"ADMIN_ALLOWED_NETWORKS: invalid network {part!r}") from e
        return v

    @field_validator("ai_base_url")
    @classmethod
    def _http_url(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"https?://[^\s/]+", v):
            raise ValueError("AI_BASE_URL must start with http:// or https://")
        return v.rstrip("/") if v else v

    @field_validator("smtp_host", "smtp_user", "smtp_from", "smtp_from_name",
                     mode="before")
    @classmethod
    def _strip_or_none(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
        return v

    @field_validator("email_from_mode", "email_free_addresses_role", mode="before")
    @classmethod
    def _lower_or_default(cls, v, info):
        if isinstance(v, str):
            v = v.strip().lower()
            if v == "":
                return "installation" if info.field_name == "email_from_mode" else "user"
        return v

    @field_validator("email_batch_size", "email_send_rate", mode="before")
    @classmethod
    def _empty_int_to_default(cls, v, info):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return 50 if info.field_name == "email_batch_size" else 10
        return v

    @field_validator("smtp_security", mode="before")
    @classmethod
    def _smtp_security_lower(cls, v):
        if isinstance(v, str):
            v = v.strip().lower()
            if v == "":
                return None
        return v

    @field_validator("smtp_password", mode="before")
    @classmethod
    def _empty_password_to_none(cls, v):
        if v == "":
            return None
        return v

    @field_validator("smtp_port", mode="before")
    @classmethod
    def _empty_port_to_default(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return 587
        return v

    @field_validator("email_individual_messages", "email_sending_paused",
                     "share_links_enabled", "google_auth_enabled", mode="before")
    @classmethod
    def _empty_bool_to_false(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return False
        return v

    @field_validator("smtp_host")
    @classmethod
    def _smtp_host_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not HOST.match(v):
            try:
                ipaddress.ip_address(v)
            except ValueError:
                raise ValueError("SMTP_HOST must be a host name or IP address") from None
        return v

    @field_validator("smtp_user")
    @classmethod
    def _smtp_user_ascii(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if "\r" in v or "\n" in v or not v.isascii():
            raise ValueError("SMTP_USER must be ASCII text without line breaks")
        return v

    @field_validator("smtp_password")
    @classmethod
    def _smtp_password_policy(cls, v: SecretStr | None) -> SecretStr | None:
        if v is None:
            return v
        value = v.get_secret_value()
        if len(value) > 256 or "\r" in value or "\n" in value or not value.isascii():
            raise ValueError(
                "SMTP_PASSWORD must be ASCII text without line breaks, at most 256 characters"
            )
        return v

    @field_validator("smtp_from")
    @classmethod
    def _smtp_from_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        normalized = normalize_email(v)
        if normalized is None:
            raise ValueError("SMTP_FROM must be one email address (name@domain)")
        return normalized

    @field_validator("smtp_from_name")
    @classmethod
    def _smtp_from_name_no_linebreaks(cls, v: str | None) -> str | None:
        if v is not None and ("\r" in v or "\n" in v):
            raise ValueError("SMTP_FROM_NAME must not contain line breaks")
        return v

    @field_validator("email_allowed_domains")
    @classmethod
    def _email_allowed_domains_canonical(cls, v: str) -> str:
        try:
            domains = normalize_domains(v)
        except ValueError as e:
            raise ValueError(f"EMAIL_ALLOWED_DOMAINS: {e}") from e
        return ",".join(domains)

    @property
    def version(self) -> str:
        return self.bizview_version

    @property
    def site_is_domain(self) -> bool:
        return not self.site_address.strip().startswith(":")

    @property
    def profile(self) -> SecurityProfile:
        """Resolved security profile: `auto` → internet for a domain, private otherwise."""
        if self.security_profile == "auto":
            return "internet" if self.site_is_domain else "private"
        return self.security_profile

    @property
    def http_allowed(self) -> bool:
        return self.profile == "private"

    @property
    def admin_networks(self) -> list[IPNetwork]:
        return [ipaddress.ip_network(p.strip(), strict=False)
                for p in self.admin_allowed_networks.split(",") if p.strip()]

    @property
    def ai_model_effective(self) -> str | None:
        if self.ai_model:
            return self.ai_model
        if self.ai_provider == "anthropic":
            return DEFAULT_ANTHROPIC_MODEL
        return "fake" if self.ai_provider == "fake" else None

    @property
    def ai_missing(self) -> list[str]:
        missing: list[str] = []
        if self.ai_provider == "anthropic" and self.ai_api_key is None:
            missing.append("AI_API_KEY")
        if self.ai_provider == "openai_compatible":
            if not self.ai_model:
                missing.append("AI_MODEL")
            if not self.ai_base_url:
                missing.append("AI_BASE_URL")
        return missing

    @property
    def ai_enabled(self) -> bool:
        return self.ai_provider != "none" and not self.ai_missing

    @property
    def smtp_security_effective(self) -> str:
        return self.smtp_security or ("ssl" if self.smtp_port == 465 else "starttls")

    @property
    def email_domains(self) -> list[str]:
        return [d for d in self.email_allowed_domains.split(",") if d]

    @property
    def email_missing(self) -> list[str]:
        if not any((self.smtp_host, self.smtp_from, self.smtp_user, self.smtp_password)):
            return []
        missing: list[str] = []
        if self.smtp_host is None:
            missing.append("SMTP_HOST")
        if self.smtp_from is None:
            missing.append("SMTP_FROM")
        return missing

    @property
    def email_enabled(self) -> bool:
        return self.smtp_host is not None and self.smtp_from is not None

    @property
    def google_enabled_effective(self) -> bool:
        """Google sign-in acts only with a complete OAuth client (feature 027)."""
        return bool(self.google_auth_enabled and self.google_client_id
                    and self.google_client_secret)

    @property
    def google_redirect_uri_effective(self) -> str:
        """Fixed from SITE_ADDRESS, never the request Host: a forged header cannot move the code.

        A plain `:port` address is a local installation without TLS, where Google only accepts a
        loopback redirect.
        """
        if self.google_redirect_uri:
            return self.google_redirect_uri
        host = self.site_address.strip()
        if self.site_is_domain:
            return f"https://{host}/api/auth/google/callback"
        return f"http://localhost{host}/api/auth/google/callback"

    @property
    def legal_privacy_url_effective(self) -> str | None:
        if self.legal_privacy_url:
            return self.legal_privacy_url
        host = self.site_address.strip().lower()
        if _official_legal_host(host):
            return OFFICIAL_PRIVACY_URL
        return None

    @property
    def legal_terms_url_effective(self) -> str | None:
        if self.legal_terms_url:
            return self.legal_terms_url
        host = self.site_address.strip().lower()
        if _official_legal_host(host):
            return OFFICIAL_TERMS_URL
        return None

    @property
    def google_domains(self) -> list[str]:
        if not self.google_allowed_domains:
            return []
        return [d.lower().lstrip("@") for d in re.split(r"[,\s]+", self.google_allowed_domains)
                if d.lstrip("@")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
