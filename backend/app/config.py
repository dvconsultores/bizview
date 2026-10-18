"""Runtime settings, read from the environment (or the repository's .env for local runs)."""
import ipaddress
import os
import re
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_ENV if ROOT_ENV.exists() else None,
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
    # Source code offered to every user (AGPL-3.0 §13). Release images bake in the repository
    # address (build arg BIZVIEW_SOURCE_URL → SOURCE_URL); an installation may override it.
    source_url: str | None = None

    # Optional AI provider (constitution VIII): off unless configured.
    ai_provider: AIProvider = "none"
    ai_api_key: SecretStr | None = None
    ai_model: str | None = Field(default=None, max_length=100)
    ai_base_url: str | None = None
    ai_timeout_seconds: float = Field(default=30, ge=1, le=300)
    # Per-request timeout of assistant chat() calls (a round writing a full draft is slow).
    ai_chat_timeout_seconds: float = Field(default=180, ge=10, le=600)
    ai_chat_token_budget: int = Field(default=400_000, ge=10_000, le=5_000_000)
    # Cached prompt tokens cost a fraction of normal tokens (DeepSeek ~10%).
    ai_chat_cached_token_weight: float = Field(default=0.1, ge=0, le=1)
    # Longest answer per round: a full draft (specs, YAML, SQL) needs several thousand tokens.
    ai_chat_max_tokens: int = Field(default=16_000, ge=1_024, le=64_000)
    # Tool rounds per autonomous run before the assistant posts a progress message.
    ai_chat_max_rounds: int = Field(default=60, ge=1, le=200)
    # The budget extends itself by the step during a run up to the max (only the max stops a run).
    ai_chat_budget_step: int = Field(default=100_000, ge=10_000, le=5_000_000)
    ai_chat_budget_max: int = Field(default=2_000_000, ge=10_000, le=5_000_000)
    # Assistant runs working at the same time in this process; more get 409 assistant_capacity.
    ai_agent_max_concurrent: int = Field(default=4, ge=1, le=32)
    # Agent previews per conversation (kept small so preview generation stays cheap).
    ai_chat_max_previews: int = Field(default=5, ge=1, le=20)
    # Seconds after which a stale assistant busy claim is considered abandoned, counted
    # from the last saved round. The loop heartbeats before its single timeout retry and
    # the SDK does not retry chat calls, so the longest stretch between heartbeats is one
    # chat call plus tool time; the validator keeps a 2x margin.
    ai_chat_busy_stale_seconds: int = Field(default=900, ge=60, le=7200)
    # Origin tool timeout: SQL/HTTP tools run inside this window.
    ai_tool_timeout_seconds: float = Field(default=20, ge=1, le=120)
    # Discovery tool calls per run before the assistant must propose a draft.
    ai_agent_discovery_limit: int = Field(default=15, ge=3, le=100)

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
    email_allowed_domains: str = ""   # comma-separated external recipient domains
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
    login_rate_limit: int = Field(default=20, ge=1, le=10_000)
    login_rate_window_minutes: int = Field(default=15, ge=1, le=1440)

    # Legacy (feature 004, research R10): imported once as a data source, otherwise unused.
    database_url_origin: str | None = None

    # Vibe reporting (feature 005): the customer's workspace checkout (mounted read-only), the
    # installation time zone (integration schedules and report periods), and the worker.
    workspace_path: str = "/workspace"
    timezone: str = "UTC"
    worker_poll_seconds: int = Field(default=10, ge=1, le=3600)
    # BI projects (feature 020): one writable folder per project (backend only), size cap in MB.
    projects_dir: str = Field(default_factory=lambda: str(ROOT / "projects"))
    project_max_mb: int = Field(default=20, ge=1, le=500)
    # Image briefs in the chat (feature 024): files live outside PROJECTS_DIR, with limits.
    attachments_dir: str = Field(default_factory=lambda: str(ROOT / "attachments"))
    attachments_max_per_message: int = Field(default=4, ge=1, le=10)
    attachments_max_mb: int = Field(default=5, ge=1, le=20)
    # auto: on for the Anthropic-style provider, off for an OpenAI-compatible endpoint (the
    # product cannot know its catalogue); true/false overrides both (feature 024, research R2).
    ai_vision: Literal["auto", "true", "false"] = "auto"
    # Interface language when neither the account nor the browser decides (feature 022)
    default_locale: Literal["es", "en"] = "es"

    product_name: str = "Bizview AI Powered"
    organization_name: str = ""
    logo_url: str | None = None
    # Who publishes the installation, shown after the license in the footer (feature 024 polish).
    footer_credit: str = "GlobalDV"

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
                     "google_allowed_domains", "google_redirect_uri", mode="before")
    @classmethod
    def _empty_is_none(cls, v):
        return v or None

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

    @field_validator("share_links_enabled", "google_auth_enabled", mode="before")
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

    @model_validator(mode="after")
    def _busy_stale_covers_round(self) -> "Settings":
        worst_case = 2 * self.ai_chat_timeout_seconds + self.ai_tool_timeout_seconds
        if self.ai_chat_busy_stale_seconds <= worst_case:
            raise ValueError(
                "AI_CHAT_BUSY_STALE_SECONDS must exceed 2 x "
                "AI_CHAT_TIMEOUT_SECONDS + AI_TOOL_TIMEOUT_SECONDS"
            )
        return self

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
    def google_domains(self) -> list[str]:
        if not self.google_allowed_domains:
            return []
        return [d.lower().lstrip("@") for d in re.split(r"[,\s]+", self.google_allowed_domains)
                if d.lstrip("@")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
