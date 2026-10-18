"""Test-only hooks (features 007, 014, 017, 018, 019). Mounted only when BIZVIEW_TEST_HOOKS=1
(set by the e2e backend script); never in images. No network: a local transport records what
the bot would send."""

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import DB, get_sessionmaker
from app.mail import send as mail_send
from app.mail import sends as mail_sends
from app.mail import settings as mail_settings
from app.mail import subscriptions as mail_subscriptions
from app.models import (
    EmailDelivery,
    EmailSend,
    EmailSubscription,
    TelegramLink,
    TelegramRequest,
)
from app.telegram import handler, service
from app.telegram.client import BotClient

router = APIRouter()

SENT: list[dict] = []


def _transport() -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/sendMessage"):
            SENT.append(json.loads(request.content))
            return httpx.Response(200, json={"ok": True, "result": {"message_id": len(SENT)}})
        if path.endswith("/editMessageText") or path.endswith("/answerCallbackQuery"):
            return httpx.Response(200, json={"ok": True, "result": True})
        return httpx.Response(200, json={"ok": True, "result": {}})

    return httpx.MockTransport(handle)


@router.post("/api/test/telegram/update")
def telegram_update(body: dict, db: Session = DB):
    row = service.settings_row(db)
    bot = BotClient(service.token_of(row) or "0:test", transport=_transport())
    try:
        handler.handle_update(db, bot, body)
    finally:
        bot.close()
    return {"ok": True}


@router.get("/api/test/telegram/sent")
def telegram_sent():
    return SENT[-10:]


@router.post("/api/test/telegram/check-ok")
def telegram_check_ok(db: Session = DB):
    row = service.settings_row(db, lock=True)
    row.last_check_ok = True
    row.last_check = {"bot_name": "Prueba"}
    # No worker polls during e2e: report Telegram as reachable for the whole run.
    row.last_poll_ok_at = service.now() + timedelta(days=1)
    return {"ok": True}


@router.post("/api/test/telegram/reset")
def telegram_reset(db: Session = DB):
    db.execute(delete(TelegramLink))
    db.execute(delete(TelegramRequest))
    row = service.settings_row(db, lock=True)
    row.enabled = False
    row.bot_username = None
    row.token_ct = None
    row.token_key_id = None
    row.last_check_ok = None
    row.last_check = None
    row.last_poll_ok_at = None
    SENT.clear()
    return {"ok": True}


# Feature 014: the e2e suite scripts the fake AI provider and turns it off again afterwards.
@router.post("/api/test/assistant/script")
def assistant_script(body: dict):
    from app.ai import ChatReply, ChatUsage, ToolCall, fake
    from app.config import get_settings

    get_settings().ai_provider = "fake"
    fake.SHARED.reset()
    fake.SHARED.queue(*(
        ChatReply(
            text=step["text"],
            tool_calls=tuple(ToolCall(id=c["id"], name=c["name"], args=c["args"],
                                      args_error=c.get("args_error"))
                             for c in step.get("tool_calls", [])),
            usage=ChatUsage(),
            model="fake",
            reasoning=step.get("reasoning"),
        )
        for step in body["steps"]
    ))
    return {"ok": True}


@router.post("/api/test/assistant/reset")
def assistant_reset(db: Session = DB):
    from app.ai import fake
    from app.config import get_settings
    from app.models import AppUser, AssistantAttachment, AssistantSession

    get_settings().ai_provider = "none"
    fake.SHARED.reset()
    db.execute(delete(AssistantSession))
    # Feature 024: the image notice is per account and the attachments live outside the database,
    # so a reset has to clear both for the suite to start from the same state every time.
    db.execute(delete(AssistantAttachment))
    db.execute(update(AppUser).values(attachments_notice_at=None))
    shutil.rmtree(get_settings().attachments_dir, ignore_errors=True)
    return {"ok": True}


# Feature 017: the agent e2e starts from an empty installation and checks what the worker builds.
_STASHED: dict[int, str] = {}


@router.post("/api/test/workspace/stash")
def workspace_stash(db: Session = DB):
    """Archiva todas las versiones activas/previas y oculta los dashboards de workspace."""
    from app.models import Dashboard, WorkspaceVersion
    from app.workspace import service as workspace

    versions = db.scalars(
        select(WorkspaceVersion).where(WorkspaceVersion.state.in_(("active", "previous")))
    ).all()
    for version in versions:
        if version.id not in _STASHED:
            _STASHED[version.id] = version.state
        version.state = "archived"
    db.flush()
    db.execute(
        update(Dashboard).where(Dashboard.report_id.is_not(None)).values(status="hidden")
    )
    db.flush()
    workspace.forget_active_version()
    return {"ok": True, "stashed": sorted(_STASHED)}


@router.post("/api/test/workspace/restore")
def workspace_restore(db: Session = DB):
    """Restaura las versiones archivadas por stash y vuelve a sincronizar los dashboards."""
    from app.models import WorkspaceVersion
    from app.workspace import service as workspace

    if not _STASHED:
        return {"ok": True, "restored": []}

    versions = db.scalars(
        select(WorkspaceVersion).where(WorkspaceVersion.state.in_(("active", "previous")))
    ).all()
    for version in versions:
        if version.id not in _STASHED:
            version.state = "archived"
    db.flush()
    restored = []
    for version_id, state in _STASHED.items():
        version = db.get(WorkspaceVersion, version_id)
        if version is not None:
            version.state = state
            restored.append(version_id)
    db.flush()
    _STASHED.clear()
    workspace.forget_active_version()
    active = workspace.active(db)
    if active is not None:
        workspace.sync_dashboards(db, active)
    return {"ok": True, "restored": restored}


@router.post("/api/test/workspace/run")
def workspace_run(body: dict, db: Session = DB):
    """Ejecuta una integración de la versión activa y reporta esquema y calendarios."""
    from app import worker
    from app.db import get_engine
    from app.engine import datasets, runner
    from app.models import IntegrationControl
    from app.workspace import service as workspace

    version = workspace.active(db)
    if version is None:
        raise HTTPException(404, "No hay una versión activa.")
    iid = body.get("integration")
    if not isinstance(iid, str) or not iid:
        raise HTTPException(400, "Indica la integración.")
    if iid not in version.artifacts.get("integrations", {}):
        raise HTTPException(404, f"La integración «{iid}» no está en la versión activa.")

    item = version.artifacts["integrations"][iid]
    run = runner.run_integration(
        item["definition"], item["files"], version_id=version.id, kind="full"
    )

    schema = datasets.schema_name(iid)
    tables: dict[str, list[str]] = {}
    primary_keys: dict[str, list[str]] = {}
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT c.table_name, c.column_name
                FROM information_schema.columns c
                JOIN information_schema.tables t
                  ON t.table_schema = c.table_schema
                 AND t.table_name = c.table_name
                WHERE c.table_schema = :schema
                  AND t.table_type = 'BASE TABLE'
                ORDER BY c.table_name, c.ordinal_position
                """
            ),
            {"schema": schema},
        )
        for table_name, column_name in rows:
            tables.setdefault(table_name, []).append(column_name)

        rows = conn.execute(
            text(
                """
                SELECT tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.table_schema = :schema
                  AND tc.constraint_type = 'PRIMARY KEY'
                ORDER BY tc.table_name, kcu.ordinal_position
                """
            ),
            {"schema": schema},
        )
        for table_name, column_name in rows:
            primary_keys.setdefault(table_name, []).append(column_name)

    controls = {c.integration_id: c for c in db.scalars(select(IntegrationControl))}
    schedules = [
        [sid, kind, cron]
        for sid, kind, cron in worker.schedules(version, controls)
        if sid == iid
    ]
    return {
        "ok": run.status == "succeeded",
        "status": run.status,
        "message": run.message,
        "schema": schema,
        "tables": tables,
        "primary_keys": primary_keys,
        "schedules": schedules,
    }


# Feature 018: mail goes to an in-memory recorder; the e2e reads it and runs the queue.
MAIL: list[dict] = []


def _record_mail(cfg, msg) -> None:
    text_body = msg.get_body(preferencelist=("plain",)).get_content()
    link_match = re.search(r"https?://\S+/s/[A-Za-z0-9_-]+", text_body)
    attachments = []
    for part in msg.iter_attachments():
        payload = part.get_payload(decode=True) or b""
        attachments.append(
            {
                "filename": part.get_filename(),
                "content_type": part.get_content_type(),
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    MAIL.append(
        {
            "to": msg["To"],
            "from": msg["From"],
            "subject": msg["Subject"],
            "text": text_body,
            "attachments": attachments,
            "link": link_match.group(0) if link_match else None,
        }
    )


mail_send.transport = _record_mail


@router.get("/api/test/mail")
def test_mail_get():
    return MAIL[-20:]


@router.post("/api/test/mail/process")
def test_mail_process():
    return {"handled": mail_sends.process_due()}


@router.post("/api/test/mail/tick")
def test_mail_tick(body: dict):
    at = body.get("at")
    if at:
        dt = datetime.fromisoformat(at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
    else:
        dt = None
    with get_sessionmaker().begin() as db:
        created = mail_subscriptions.tick(db, dt)
    handled = mail_sends.process_due(now=dt)
    return {"created": created, "handled": handled}


SETTINGS_OVERRIDABLE = (
    "smtp_host",
    "smtp_port",
    "smtp_security",
    "smtp_user",
    "smtp_password",
    "smtp_from",
    "smtp_from_name",
    "email_allowed_domains",
    "share_links_enabled",
)
_ORIGINAL: dict[str, object] = {}


def _override(values: dict) -> dict:
    for key in values:
        if key not in SETTINGS_OVERRIDABLE:
            raise HTTPException(400, f"No se puede cambiar {key}.")
    if "email_allowed_domains" in values and isinstance(values["email_allowed_domains"], list):
        values = {**values, "email_allowed_domains": ",".join(values["email_allowed_domains"])}

    settings = get_settings()
    try:
        checked = type(settings).model_validate({**settings.model_dump(), **values})
    except ValidationError:
        raise HTTPException(422, "Valor inválido.") from None

    for key in values:
        _ORIGINAL.setdefault(key, getattr(settings, key))
        setattr(settings, key, getattr(checked, key))
    return mail_settings.status()


def _restore() -> None:
    settings = get_settings()
    for key, value in _ORIGINAL.items():
        setattr(settings, key, value)
    _ORIGINAL.clear()


@router.post("/api/test/settings")
def test_settings_override(body: dict):
    return {"ok": True, "status": _override(body)}


@router.post("/api/test/settings/reset")
def test_settings_reset():
    _restore()
    return {"ok": True, "status": mail_settings.status()}


@router.post("/api/test/mail/reset")
def test_mail_reset(db: Session = DB):
    MAIL.clear()
    db.execute(delete(EmailDelivery))
    db.execute(delete(EmailSend))
    db.execute(delete(EmailSubscription))
    _restore()
    return {"ok": True}


@router.post("/api/test/mail/configure")
def test_mail_configure(body: dict):
    _override({
        "smtp_host": "smtp.prueba.local",
        "smtp_port": 2525,
        "smtp_security": "none",
        "smtp_user": None,
        "smtp_password": None,
        "smtp_from": "bizview@prueba.local",
        "smtp_from_name": "Bizview",
        "email_allowed_domains": body.get("allowed_domains", ["cliente.com"]),
        "share_links_enabled": bool(body.get("sharing", True)),
    })
    return {"ok": True}


_DIRECT_STATE: dict = {}


@router.post("/api/test/direct/seed")
def test_direct_seed():
    import shutil
    import tempfile
    from datetime import datetime
    from pathlib import Path
    from zoneinfo import ZoneInfo

    from bizview_cli import authoring
    from bizview_cli import validate as wsv

    from app.db import get_engine
    from app.engine import direct

    settings = get_settings()
    if not settings.db_schema.startswith("app_test_"):
        raise HTTPException(status_code=409, detail="Solo disponible en esquemas app_test_*")
    phys = direct.physical_schema("public")
    if phys != f"{settings.db_schema}__public":
        raise HTTPException(status_code=409, detail="No apunta al esquema físico esperado")
    today = datetime.now(ZoneInfo(settings.timezone)).date()

    rows = [
        (today, "Centro", "Alimento premium", 120.50, 3),
        (today, "Este", "Vacuna triple", 80.00, 2),
        (today, "Centro", "Vacuna triple", 40.00, 1),
    ]
    with get_engine().begin() as c:
        c.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{phys}"'))
        c.execute(text(f'DROP TABLE IF EXISTS "{phys}".bi_ventas'))
        c.execute(text(f'CREATE TABLE "{phys}".bi_ventas (fecha date, sucursal text, '
                       "producto text, monto numeric, unidades integer)"))
        c.execute(
            text(f'INSERT INTO "{phys}".bi_ventas (fecha, sucursal, producto, monto, unidades) '
                 "VALUES (:f, :s, :p, :m, :u)"),
            [{"f": d, "s": s, "p": p, "m": m, "u": u} for d, s, p, m, u in rows],
        )

    tmp_root = Path(tempfile.mkdtemp(prefix="bizview-direct-e2e-"))
    folder = tmp_root / "workspace"
    folder.mkdir()

    def copy(node, target: Path) -> None:    # the whole v2 workspace (bizview.yaml, projects/)
        for child in node.iterdir():
            if child.name == "__pycache__":
                continue
            if child.is_dir():
                (target / child.name).mkdir()
                copy(child, target / child.name)
            else:
                (target / child.name).write_text(child.read_text(encoding="utf-8"),
                                                 encoding="utf-8")

    copy(authoring.golden_root("golden-direct"), folder)

    result = wsv.validate(folder)
    if not result.ok:
        issues = "\n".join(str(i) for i in result.issues)
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Workspace inválido:\n{issues}")
    wsv.write_lock(folder, result.lock)

    _DIRECT_STATE.setdefault("original_workspace", settings.workspace_path)
    _DIRECT_STATE.setdefault("tmp_roots", []).append(tmp_root)
    settings.workspace_path = str(folder)
    direct.clear_cache()

    return {
        "ok": True,
        "schema": phys,
        "table": f"{phys}.bi_ventas",
        "workspace": str(folder),
        "today": today.isoformat(),
        "total": 240.5,
    }


@router.post("/api/test/direct/reset")
def test_direct_reset():
    import shutil

    from app.db import get_engine
    from app.engine import direct

    settings = get_settings()
    if not settings.db_schema.startswith("app_test_"):
        raise HTTPException(status_code=409, detail="Solo disponible en esquemas app_test_*")
    phys = direct.physical_schema("public")
    if phys != f"{settings.db_schema}__public":
        raise HTTPException(status_code=409, detail="No apunta al esquema físico esperado")

    original = _DIRECT_STATE.pop("original_workspace", None)
    if original is not None:
        settings.workspace_path = original
    for root in _DIRECT_STATE.pop("tmp_roots", []):
        shutil.rmtree(root, ignore_errors=True)

    with get_engine().begin() as c:
        c.execute(text(f'DROP TABLE IF EXISTS "{phys}".bi_ventas'))
    direct.clear_cache()
    return {"ok": True}


# Feature 020 T079 (SC-002): what is really on disk for a project, to compare with the explorer.
@router.get("/api/test/projects/{slug}/disk")
def project_disk(slug: str):
    from app.projects import fs

    root = fs.project_root(slug)
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*")
                   if p.is_file() and not p.relative_to(root).as_posix().startswith(fs.TRASH))
    return {"files": files}
