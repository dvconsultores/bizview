"""Test fixtures. Tests run on DATABASE_URL_BI — the same database the migrations target — but
inside a temporary schema app_test_<random> that is created, migrated, and dropped by the run.
The real tables in `public` are never written (see tests/safety.py); the suite checks that
`public` is structurally unchanged afterwards."""
import os
import re
import secrets
import tempfile
from pathlib import Path

import pytest

from tests.safety import assert_test_schema

ROOT = Path(__file__).resolve().parents[2]
TEST_SCHEMA = assert_test_schema(f"app_test_{secrets.token_hex(4)}")

# The suites need the database URL, which lives in the developer's .env, but nothing else from it:
# a local AI budget or provider used to change what the tests exercised. Read the one value here
# and tell Settings to ignore the file (BIZVIEW_NO_ENV_FILE), so the rest is the test's own.
def _database_url() -> str:
    from dotenv import dotenv_values

    env_file = ROOT / ".env"
    value = os.environ.get("DATABASE_URL_BI") or (
        dotenv_values(env_file).get("DATABASE_URL_BI") if env_file.exists() else None)
    if not value:
        raise RuntimeError(
            "DATABASE_URL_BI is required to run the backend tests (define it in .env)")
    return value


DATABASE_URL_BI = _database_url()

# Settings are read at import time of the app modules. DATABASE_URL_BI comes from .env as usual.
os.environ.update({
    # Ignore the developer's .env entirely: every setting below is the test's own. Without this a
    # local .env (a larger AI budget, a real provider) changed what the suites exercised.
    "BIZVIEW_NO_ENV_FILE": "1",
    "DATABASE_URL_BI": DATABASE_URL_BI,
    "DB_SCHEMA": TEST_SCHEMA,
    # Feature 020: project folders of the run live in a throwaway directory, never in the repo
    # (tests that need their own folder override it per test).
    "PROJECTS_DIR": tempfile.mkdtemp(prefix=f"{TEST_SCHEMA}-projects-"),
    # Feature 024: image briefs are stored outside the project folders, in their own directory.
    "ATTACHMENTS_DIR": tempfile.mkdtemp(prefix=f"{TEST_SCHEMA}-attachments-"),
    "SUPER_USER_EMAIL": "root@example.com",
    "SUPER_USER_PASSWORD": "Sup3r-secret-pass",
    "COOKIE_SECURE": "false",
    "PRODUCT_NAME": "Panel de prueba",
    "ORGANIZATION_NAME": "Cliente Demo",
    "LOGO_URL": "",
    # Feature 004: fixed test key (32 zero-to-31 bytes, base64url) and the private profile.
    "BIZVIEW_SECRET_KEY": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=",
    "BIZVIEW_SECRET_KEY_PREVIOUS": "",
    "SECURITY_PROFILE": "private",
    "SITE_ADDRESS": ":80",
    "ADMIN_ALLOWED_NETWORKS": "",
    "DATABASE_URL_ORIGIN": "",
    # Tests ignore the developer's .env AI settings (AI tests use fake providers and set their
    # own values).
    "AI_PROVIDER": "none",
    "AI_API_KEY": "",
    "AI_MODEL": "",
    "AI_BASE_URL": "",
    "AI_TIMEOUT_SECONDS": "30",
    # The budget knobs too: a developer .env with a larger ceiling made the budget tests read it.
    "AI_CHAT_TOKEN_BUDGET": "400000",
    "AI_CHAT_BUDGET_STEP": "100000",
    "AI_CHAT_BUDGET_MAX": "2000000",
    # Tests change versions behind the API (TRUNCATE, SQL): no in-memory active version.
    "ACTIVE_VERSION_CACHE_SECONDS": "0",
    "DB_POOL_WARM": "0",
    # Feature 018: email and share links come from the environment; tests set them per test
    # (set_mail).
    "SMTP_HOST": "",
    "SMTP_PORT": "",
    "SMTP_SECURITY": "",
    "SMTP_USER": "",
    "SMTP_PASSWORD": "",
    "SMTP_FROM": "",
    "SMTP_FROM_NAME": "",
    "EMAIL_ALLOWED_DOMAINS": "",
    "SHARE_LINKS_ENABLED": "false",
    # Feature 019: tests ignore the developer's .env value (tests set it per test).
    "DIRECT_BI_ROLE": "",
})

from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from alembic import command
from app.assistant import service as assistant_service
from app.auth import passwords
from app.config import get_settings
from app.db import get_engine, get_sessionmaker
from app.main import app
from app.models import AppUser

PASSWORD = "Correct-horse-9"
ALEMBIC_INI = ROOT / "backend" / "alembic.ini"


def alembic_cfg() -> Config:
    return Config(str(ALEMBIC_INI))


def outside_snapshot() -> dict:
    """Structure of what the tests must not touch: schema `public` (the real product tables,
    columns, constraints, indexes, migration version) and the installed extensions."""
    raw = get_engine().execution_options(schema_translate_map=None)
    with raw.connect() as c:
        q = lambda s, **p: sorted(c.execute(text(s), p).all())
        return {
            "columns": q("SELECT table_schema, table_name, column_name, data_type "
                         "FROM information_schema.columns "
                         "WHERE table_schema = 'public'"),
            "constraints": q("SELECT n.nspname, conname, pg_get_constraintdef(x.oid) "
                             "FROM pg_constraint x JOIN pg_namespace n ON n.oid = x.connamespace "
                             "WHERE n.nspname = 'public'"),
            "indexes": q("SELECT schemaname, indexname, indexdef FROM pg_indexes "
                         "WHERE schemaname = 'public'"),
            "extensions": q("SELECT extname FROM pg_extension"),
            "version": q("SELECT version_num FROM public.alembic_version")
            if c.execute(text("SELECT to_regclass('public.alembic_version')")).scalar() else [],
        }


def drop_test_schema() -> None:
    """The test schema and the engine's dataset schemas of this run (`<test schema>__ds_*`,
    and assistant previews `<test schema>__preview_<id>__ds_*`, feature 014)."""
    with get_engine().begin() as c:
        c.execute(text(f'DROP SCHEMA IF EXISTS "{assert_test_schema(TEST_SCHEMA)}" CASCADE'))
        prefix = TEST_SCHEMA.replace("_", r"\_")
        for pattern, start in ((prefix + r"\_\_ds\_%", f"{TEST_SCHEMA}__ds_"),
                               (prefix + r"\_\_preview\_%", f"{TEST_SCHEMA}__preview_")):
            for (name,) in c.execute(
                    text("SELECT nspname FROM pg_namespace WHERE nspname LIKE :p"),
                    {"p": pattern}):
                assert name.startswith(start)
                c.execute(text(f'DROP SCHEMA "{name}" CASCADE'))


def enable_app_loggers():
    import logging

    root_manager = logging.root.manager
    for name, obj in root_manager.loggerDict.items():
        if name == "app" or name.startswith("app."):
            if isinstance(obj, logging.Logger):
                obj.disabled = False


@pytest.fixture(scope="session", autouse=True)
def database():
    before = outside_snapshot()
    drop_test_schema()
    command.upgrade(alembic_cfg(), "head")
    enable_app_loggers()
    try:
        yield before
    finally:
        drop_test_schema()
    assert outside_snapshot() == before, "tests changed schema public in the BI database"


@pytest.fixture(autouse=True)
def clean(database):
    sql("TRUNCATE audit_event, user_session, dashboard_access, recovery_code, data_source, "
        "security_state, login_throttle, integration_run_request, integration_run, "
        "report_cache, api_token, workspace_version, integration_control, share_link, "
        "email_delivery, email_send, email_subscription, app_user RESTART IDENTITY CASCADE")
    sql("DELETE FROM dashboard WHERE code <> 'ventas'")
    sql("UPDATE dashboard SET status = 'coming_soon', name = 'Ventas', icon = 'chart-line', "
        "description = 'Resumen, tendencias y productos de tus ventas.', sort_order = 10, "
        "report_id = NULL, managed_by = 'product' WHERE code = 'ventas'")
    yield


@pytest.fixture(autouse=True)
def inline_assistant_runner(monkeypatch):
    """Tests run assistant turns inline; test_assistant_autonomous uses a threaded runner."""
    monkeypatch.setattr(assistant_service, "RUNNER", assistant_service.run_turn)
    monkeypatch.setattr(assistant_service, "_SLOTS", None)


MAIL_FIELDS = ("smtp_host", "smtp_port", "smtp_security", "smtp_user", "smtp_password",
               "smtp_from", "smtp_from_name", "email_allowed_domains", "share_links_enabled")


@pytest.fixture(autouse=True)
def mail_env():
    """Email/sharing settings changed by a test (set_mail) are restored afterwards."""
    settings = get_settings()
    original = {field: getattr(settings, field) for field in MAIL_FIELDS}
    yield
    for field, value in original.items():
        setattr(settings, field, value)


def set_mail(**values) -> None:
    """Feature 018: email and share-link settings for one test (the installation environment
    in production), validated like the environment."""
    settings = get_settings()
    if "email_allowed_domains" in values and isinstance(
        values["email_allowed_domains"], (list, tuple)
    ):
        values = {**values, "email_allowed_domains": ",".join(values["email_allowed_domains"])}
    for key in values:
        if key not in MAIL_FIELDS:
            raise KeyError(key)
    checked = type(settings).model_validate({**settings.model_dump(), **values})
    for key in values:
        setattr(settings, key, getattr(checked, key))


MAIL_ENV = dict(
    smtp_host="smtp.cliente.com",
    smtp_port=587,
    smtp_security="starttls",
    smtp_user=None,
    smtp_password=None,
    smtp_from="bizview@cliente.com",
    smtp_from_name="Bizview",
    email_allowed_domains="cliente.com",
    share_links_enabled=False,
)


@pytest.fixture
def db():
    s = get_sessionmaker()()
    try:
        yield s
        s.commit()
    finally:
        s.close()


def make_user(email: str, *, role: str = "user", password: str = PASSWORD,
              is_superuser: bool = False, must_change: bool = False, active: bool = True,
              full_name: str | None = None) -> AppUser:
    with get_sessionmaker().begin() as s:
        user = AppUser(email=email, full_name=full_name or email.split("@")[0].title(),
                       role="admin" if is_superuser else role, is_superuser=is_superuser,
                       is_active=active, must_change_password=must_change, failed_attempts=0,
                       password_hash=passwords.hash_password(password))
        s.add(user)
        s.flush()
        s.expunge(user)
        return user


def client() -> TestClient:
    return TestClient(app, headers={"X-Requested-With": "fetch"})


def reauth(c: TestClient, password: str = PASSWORD) -> TestClient:
    """Step-up confirmation (feature 004) for sensitive actions."""
    r = c.post("/api/auth/reauth", json={"password": password})
    assert r.status_code == 204, r.text
    return c


def client_from(ip: str) -> TestClient:
    return TestClient(app, headers={"X-Requested-With": "fetch"}, client=(ip, 50000))


def signed_in(email: str, password: str = PASSWORD) -> TestClient:
    c = client()
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return c


def sql(query: str, **params):
    """Raw SQL for assertions; unqualified table names resolve in the test schema."""
    with get_engine().begin() as c:
        c.execute(text(f'SET LOCAL search_path TO "{TEST_SCHEMA}"'))
        result = c.execute(text(query), params)
        return result.all() if result.returns_rows else None


@pytest.fixture
def superuser():
    return make_user("root@example.com", is_superuser=True, full_name="Super Usuario")


@pytest.fixture
def admin():
    return make_user("admin@example.com", role="admin", full_name="Ana Admin")


@pytest.fixture
def user():
    return make_user("user@example.com", full_name="Ulises Usuario")


# --- Feature 020/021: conversations belong to a project ---------------------------------------

def new_chat(c: TestClient, title: str | None = None) -> int:
    """A conversation (API) on a new project of its own."""
    r = c.post("/api/projects", json={"name": f"Chat {secrets.token_hex(3)}"})
    assert r.status_code in (200, 201), r.text
    body = {"project": r.json()["slug"], **({"title": title} if title else {})}
    r = c.post("/api/assistant/sessions", json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def chat_project_id(db, user_id: int) -> int:
    """Id of a new project for conversations built directly with the ORM."""
    from app.projects import service as project_service

    project = project_service.create(db, db.get(AppUser, user_id), f"Chat {secrets.token_hex(3)}")
    db.flush()
    return project.id


@pytest.fixture
def without_command_guard(monkeypatch):
    """017/020 mechanics through plain-mode writers; the 021 guard has its own tests
    (test_assistant_commands_*)."""
    from app.assistant.tools import TOOL_SPECS

    legacy = frozenset(t["name"] for t in TOOL_SPECS
                       if t["name"] not in ("finish_command", "suggest_command"))
    monkeypatch.setattr("app.assistant.commands.guard.check_tool", lambda *a, **k: None)
    monkeypatch.setattr("app.assistant.commands.guard.allowed_tools", lambda *a, **k: legacy)
    monkeypatch.setattr("app.assistant.tools._guard_writes", lambda *a, **k: None)


def chat_response(c: TestClient, title: str | None = None):
    """POST /api/assistant/sessions on a new project; the raw response (it may be an error)."""
    r = c.post("/api/projects", json={"name": f"Chat {secrets.token_hex(3)}"})
    assert r.status_code in (200, 201), r.text
    return c.post("/api/assistant/sessions",
                  json={"project": r.json()["slug"], **({"title": title} if title else {})})


_LEGACY_SPEC = re.compile(r"^specs/(integrations|reports)/(\d{3}-[a-z0-9-]+)/")
_KIND_LINE = {"integrations": "integracion", "reports": "reporte"}


def v2_files(files: dict[str, str], first: int = 1) -> dict[str, str]:
    """A legacy draft (`specs/reports/NNN-x/…`) as v2 project files: specs renumbered from
    `first` in their old order, `spec:` fields rewritten and a `**Tipo**:` line added."""
    folders: dict[str, tuple[str, str]] = {}
    for path in sorted(files):
        m = _LEGACY_SPEC.match(path)
        if m and m.group(0) not in folders:
            folders[m.group(0)] = (m.group(1), m.group(2))
    renamed = {}
    for index, (old, (group, name)) in enumerate(
            sorted(folders.items(), key=lambda item: item[1][1])):
        renamed[old.rstrip("/")] = (f"specs/{first + index:03d}-{name[4:]}", group)
    out: dict[str, str] = {}
    for path, content in files.items():
        for old, (new, group) in renamed.items():
            content = content.replace(old, new)
            if path.startswith(old + "/"):
                path = new + path[len(old):]
                if path.endswith("/spec.md") and "**Tipo**:" not in content:
                    first_line, _, rest = content.partition("\n")
                    content = f"{first_line}\n\n**Tipo**: {_KIND_LINE[group]}\n{rest}"
        out[path] = content
    return out


def write_project(project_id: int, files: dict[str, str], user_id: int) -> None:
    """Write (or overwrite) project files as the user, through the 020 write path."""
    from app.projects import fs

    fs.apply_ops(project_id, [{"op": "write", "path": path, "content": content,
                               "base_sha256": None, "force": True}
                              for path, content in files.items()],
                 {"kind": "user", "user_id": user_id, "session_id": None, "command": "edit"})


def project_view(db, user_id: int, files: dict[str, str] | None = None):
    """The WorkView of a conversation on a new project holding `files`."""
    from app.assistant import service as chat
    from app.projects.workview import for_session

    project_id = chat_project_id(db, user_id)
    db.commit()
    if files:
        write_project(project_id, files, user_id)
    session = chat.create_session(db, db.get(AppUser, user_id), project_id=project_id)
    db.commit()
    return for_session(db, session)
