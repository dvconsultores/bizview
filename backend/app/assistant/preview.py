"""Assistant draft preview (feature 014): run draft integrations into temporary schemas and render
draft reports for the super user only. Never touches published ds_* schemas or integration_run."""
import copy
import logging
import re
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from psycopg import sql
from sqlalchemy import select

from app.assistant import readiness
from app.config import get_settings
from app.db import get_engine, get_sessionmaker, lock_key
from app.engine import datasets, direct, render_errors, runner
from app.engine import report as engine
from app.engine.render_errors import RenderError
from app.errors import ApiError
from app.i18n import M, t, use_locale
from app.models import (
    AppUser,
    AssistantMessage,
    AssistantPreviewRequest,
    AssistantSession,
    Project,
)
from app.workspace import service as workspace_service

log = logging.getLogger(__name__)

_INTEGRATION_FILE = re.compile(r"^integrations/([^/]+)/(.+)$")
_REPORT_FILE = re.compile(r"^reports/([^/]+)/report\.yaml$")
STALE_AFTER = timedelta(hours=24)
CONNECT_TEXT = "No se pudo conectar con la fuente."


def preview_lock_key(session_id: int) -> str:
    """Advisory-lock key of a session's draft preview (scoped to this schema)."""
    return lock_key("assistant-preview", session_id)


class PreviewBusy(Exception):
    """Raised when the per-session preview lock is already held."""


def draft_items(files: dict[str, str], base: dict | None = None) -> tuple[dict, dict]:
    """Parses draft files. `base` is the active version's integration artifacts; anything taken
    from it is deep-copied and never shared."""
    integrations: dict[str, dict] = {}
    reports: dict[str, dict] = {}
    for path, text in files.items():
        m = _INTEGRATION_FILE.match(path)
        if m:
            iid, rel = m.groups()
            item = integrations.setdefault(iid, {"definition": None, "files": {}})
            if rel == "integration.yaml":
                item["definition"] = yaml.safe_load(text) or {}
            else:
                item["files"][rel] = text
            continue
        m = _REPORT_FILE.match(path)
        if m:
            reports[m.group(1)] = {"definition": yaml.safe_load(text) or {}}

    base = base or {}
    for iid, item in integrations.items():
        active = base.get(iid)
        if active:
            if item["definition"] is None:
                item["definition"] = copy.deepcopy(active.get("definition") or {})
            merged_files = copy.deepcopy(active.get("files") or {})
            merged_files.update(item["files"])
            item["files"] = merged_files
        else:
            if item["definition"] is None:
                item["definition"] = {}
    return integrations, reports


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def active_integrations(db) -> dict:
    active = workspace_service.active(db)
    if not active:
        return {}
    return (active.artifacts or {}).get("integrations") or {}


def redact_values(text: str, limit: int = 300) -> str:
    """Database error texts can quote row values: strip quoted literals and key groups."""
    text = re.sub(r"'[^']*'", "«…»", text)
    text = re.sub(r'"[^"]*"', "«…»", text)
    text = re.sub(r"=\([^)]*\)", "=(…)", text)
    text = re.sub(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://\S+", "«…»", text)
    for key in ("host", "hostaddr", "port", "user", "dbname", "database", "password", "sslmode"):
        text = re.sub(rf"\b{key}=[^\s,]+", f"{key}=«…»", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "«…»", text)
    ipv6 = (r"(?<![\w:.])"
            r"\[?"
            r"(?=[A-Fa-f0-9:]*:[A-Fa-f0-9:]*:)"
            r"[A-Fa-f0-9:]+"
            r"\]?"
            r"(?::\d{2,5})?"
            r"(?![\w:])")
    text = re.sub(ipv6, "«…»", text)
    text = re.sub(r"\b[^\s@]+@[^\s]+\b", "«…»", text)
    for word in ("hostname", "host name", "host", "server at", "servidor en", "address",
                 "port", "puerto", "user", "usuario", "role", "database", "base de datos"):
        text = re.sub(rf"\b({word})\b(?:\s+to\s+|\s+)([^\s,]+)",
                      r"\1 «…»", text, flags=re.IGNORECASE)
    text = re.sub(r"\b([^\s:]+):\d{2,5}(?=[\s,;)\]]|$)", "«…»", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit] + "…"


_CONNECTION_PATTERNS = (
    r"operationalerror",
    r"connectiontimeout",
    r"connecterror",
    r"connecttimeout",
    r"netguarderror",
    r"connectionrefusederror",
    r"(?:socket\.)?gaierror",
    r"connection to server",
    r"connection failed",
    r"could not connect",
    r"could not translate host",
    r"connection refused",
    r"timeout expired",
    r"no pg_hba\.conf",
    r"password authentication failed",
    r"authentication failed",
    r"server closed the connection",
    r"name or service not known",
    r"network is unreachable",
    r"no route to host",
    r"getaddrinfo",
    r"\bssl\b",
    r"error de red",
)
_CONNECTION_RE = re.compile("|".join(_CONNECTION_PATTERNS), re.IGNORECASE)


_TIMESTAMP_RANGE_RE = re.compile(
    r"date/time field value out of range|timestamp out of range|"
    r"out of range for type timestamp|datetime field overflow", re.IGNORECASE)


def ai_error_text(message: str) -> str:
    """Returns the safe connection error text for network failures, otherwise redacts values."""
    if _CONNECTION_RE.search(message):
        return CONNECT_TEXT
    if _TIMESTAMP_RANGE_RE.search(message):
        # 040 (E): the Postgres cast of a mapped epoch in the wrong unit. Named, with the content
        # fix (`timestamp_units`) instead of a raw driver sentence.
        return t("preview.timestamp_unit_mismatch")
    return redact_values(message)


def outcome_lines(preview: dict | None) -> list[str]:
    """Preview outcome for the AI: status, row counts, redacted errors; never check details."""
    if not preview or preview.get("status") == "pending":
        return []
    lines = [f"Vista previa: {preview.get('status')}"]
    integrations = preview.get("integrations") or {}
    for iid in sorted(integrations):
        item = integrations[iid]
        line = f"- {iid}: {item.get('status')}"
        rows = ", ".join(f"{name}={data.get('rows')}"
                         for name, data in sorted((item.get("datasets") or {}).items()))
        if rows:
            line += f"; filas: {rows}"
        if item.get("message"):
            line += f"; error: {ai_error_text(item['message'])}"
        lines.append(line)
        for check in item.get("checks") or []:
            if not check.get("ok", True):
                lines.append(f"- comprobación {check.get('type')} no superada en "
                             f"{check.get('dataset')}")
    reports = preview.get("reports") or {}
    for rid in sorted(reports):
        item = reports[rid]
        line = f"- reporte directo {rid}: {item.get('status')}"
        if isinstance(item.get("duration_ms"), int):
            line += f"; {item['duration_ms']} ms"
        if item.get("message"):
            line += f"; error: {ai_error_text(item['message'])}"
        lines.append(line)
    if preview.get("message"):
        lines.append(f"- error: {ai_error_text(preview['message'])}")
    return lines


def summary_text(preview: dict) -> str:
    """One line for the conversation (FR-007)."""
    integrations = (preview.get("integrations") or {}).values()
    reports = (preview.get("reports") or {}).values()
    if preview.get("status") == "succeeded":
        parts = [t("preview.summary_dataset_rows", name=name, rows=data.get('rows'))
                 for item in integrations
                 for name, data in (item.get("datasets") or {}).items()]
        parts.extend(t("preview.summary_metric_item", path=rid)
                     for rid in sorted(preview.get("reports") or {}))
        if parts:
            return t("preview.ready", items=', '.join(parts))
        return t("preview.ready_empty")
    messages = [item["message"] for item in integrations if item.get("message")]
    messages.extend(item["message"] for item in reports if item.get("message"))
    if preview.get("message"):
        messages.append(preview["message"])
    reason = ai_error_text(messages[0]) if messages else t("preview.checks_not_passed")
    return t("preview.failed_reason", reason=reason)


def _view(db, session):
    """The conversation seen at project level (feature 020, research R4)."""
    from app.projects.workview import WorkView, for_session

    if isinstance(session, WorkView) or not getattr(session, "project_id", None):
        return session
    view = for_session(db, session)
    if view.project is None:
        # Feature 037: a conversation whose project row is gone has no folder to read; saying so is
        # better than previewing "nothing" (that is what «no ve ningún archivo» looked like).
        raise ApiError(404, "not_found", M("preview.project_gone", slug=str(session.project_id)))
    return view


def project_scope(session) -> tuple[str | None, Path | None]:
    """Slug and folder of the project a preview runs for (feature 037, logged on every run)."""
    from app.projects import fs

    slug = getattr(getattr(session, "project", None), "slug", None)
    if not slug:
        return None, None
    try:
        return slug, fs.project_root(slug)
    except fs.ProjectPathError:
        return slug, None


def _schemas_of(session) -> int:
    """Conversation whose preview schemas hold the project's current preview."""
    return (session.preview or {}).get("session_id") or session.id


def record_outcome(db, session) -> None:
    """Shows the finished preview in the conversation; the AI reads it via outcome_lines."""
    db.add(AssistantMessage(session_id=session.id, role="tool", tool_name="preview",
                            content=summary_text(session.preview),
                            tool_payload={"result": {"lines": outcome_lines(session.preview)}}))
    db.flush()


@contextmanager
def session_lock(session_id: int):
    """Takes the per-session advisory lock or raises PreviewBusy; unlocks on the same
    connection in finally."""
    with get_engine().connect() as conn:
        driver = conn.connection.driver_connection
        got = driver.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
            (preview_lock_key(session_id),),
        ).fetchone()[0]
        driver.commit()
        if not got:
            raise PreviewBusy()
        try:
            yield
        finally:
            driver.execute(
                "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                (preview_lock_key(session_id),),
            )
            driver.commit()


def preview_running(session_id: int) -> bool:
    """True when the per-session preview advisory lock cannot be acquired immediately."""
    with get_engine().connect() as conn:
        driver = conn.connection.driver_connection
        got = driver.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
            (preview_lock_key(session_id),),
        ).fetchone()[0]
        driver.commit()
        if got:
            driver.execute(
                "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                (preview_lock_key(session_id),),
            )
            driver.commit()
        return not got


def _direct_version() -> engine.PreviewVersion:
    return engine.PreviewVersion(
        id=None,
        artifacts={"workspace": {}, "integrations": {}, "reports": {}},
    )


def _render_direct(session, rid: str, definition: dict) -> dict:
    start = time.monotonic()
    try:
        tz = get_settings().timezone
        ctx = engine.preview_context(
            _direct_version(), rid, definition, {}, set(), session.id
        )
        sel, filters = engine.selection(
            ctx, {}, datetime.now(ZoneInfo(tz)).date()
        )
        views = engine.run_views(ctx, sel, filters, tz)
        # A view that cannot render is a failed preview check (038): the card names the piece.
        broken = next((v["error"] for v in views if v.get("error")), None)
        if broken:
            return {
                "status": "failed",
                "message": broken["message"],
                "duration_ms": int((time.monotonic() - start) * 1000),
            }
        return {
            "status": "succeeded",
            "message": None,
            "duration_ms": int((time.monotonic() - start) * 1000),
        }
    except direct.DirectError as e:
        return {
            "status": "failed",
            "message": e.message,
            "duration_ms": int((time.monotonic() - start) * 1000),
        }
    except ApiError as e:
        return {
            "status": "failed",
            "message": e.message,
            "duration_ms": int((time.monotonic() - start) * 1000),
        }
    except Exception as e:
        log.warning("direct preview failed (%s)", type(e).__name__)
        return {
            "status": "failed",
            "message": "No se pudo mostrar el reporte directo.",
            "duration_ms": int((time.monotonic() - start) * 1000),
        }


def run_draft_preview(db, session, *, time_limit_s: int = 300,
                      files: dict[str, str] | None = None) -> dict:
    """Runs every draft integration into the session's preview schemas (worker and agent tool
    share it), stores session.preview with the draft fingerprint and posts the outcome notice.
    The preview lives on the project: one from another conversation drops that one's schemas.

    `files` is the draft to run. The worker passes the copy stored with the request, so a preview
    never depends on it seeing the projects folder (reported 2026-10-22: it did not).
    """
    session = _view(db, session)
    previous = (session.preview or {}).get("session_id")
    if previous and previous != session.id:
        drop_for_session(previous)
    if files is None:
        files = (session.draft or {}).get("files", {})
    slug, root = project_scope(session)
    empty_message = t("preview.empty_draft", slug=slug or "?", root=root or "?")
    # Feature 037: the resolved folder is logged at the start, so a wrong scope and a missing
    # volume are told apart from the log without guessing (reported 2026-10-26).
    log.info("preview: session %s, project %s, root %s, files %s", session.id, slug, root,
             len(files))
    if slug and (root is None or not root.is_dir()):
        log.warning("preview: project folder %s of %s is missing", root, slug)
    integrations, draft_reports = draft_items(files, active_integrations(db))
    fp = readiness.fingerprint(files)
    if integrations:
        with session_lock(session.id):
            drop_for_session(session.id)
            results = {}
            for iid, item in sorted(integrations.items()):
                definition = item["definition"]
                if not (isinstance(definition.get("id"), str)
                        and isinstance(definition.get("source"), str)
                        and isinstance(definition.get("datasets"), dict)):
                    results[iid] = {"status": "failed", "message":
                                    t("preview.invalid_integration_yaml"),
                                    "datasets": {}, "checks": []}
                    continue
                results[iid] = runner.run_preview(definition, item["files"],
                                                  session_id=session.id,
                                                  time_limit_s=time_limit_s)
    else:
        results = {}
    direct_results = {
        rid: _render_direct(session, rid, item["definition"])
        for rid, item in sorted(draft_reports.items())
        if isinstance(item.get("definition"), dict)
        and isinstance(item["definition"].get("direct"), dict)
    }
    outcomes = [*results.values(), *direct_results.values()]
    failed_for_no_files = not files
    if failed_for_no_files:
        # An empty draft is not a successful preview: recording one here (the worker without the
        # projects volume saw no files) left the project saying "el borrador cambió desde la última
        # vista previa" forever, with Apply disabled and no explanation.
        status = "failed"
        outcomes = []
    else:
        status = ("succeeded" if all(r["status"] == "succeeded" for r in outcomes)
                  else "failed")
    now = datetime.now(UTC)
    session.preview = {"status": status, "finished_at": _iso(now),
                       "integrations": results, "preview_integrations": sorted(results),
                       "reports": direct_results, "fingerprint": fp,
                       "session_id": session.id}
    if failed_for_no_files:
        session.preview["message"] = empty_message
    record_outcome(db, session)
    return session.preview


def request_preview(db, actor, session) -> dict:
    session = _view(db, session)
    if session.status != "open":
        raise ApiError(409, "conflict", M("assistant.not_open"))
    if not session.draft or not (session.validation or {}).get("valid"):
        raise ApiError(409, "invalid_draft", M("preview.validate_draft_before_preview"))
    if preview_running(session.id):
        raise ApiError(409, "preview_running", M("preview.busy"))
    integrations, _ = draft_items(session.draft["files"], active_integrations(db))
    if not integrations:  # reports only: they read published datasets, nothing to run
        try:
            return run_draft_preview(db, session)
        except PreviewBusy:
            raise ApiError(409, "preview_running", M("preview.busy")) from None
    # The draft travels with the request: the worker may not share this process's projects folder.
    db.add(AssistantPreviewRequest(session_id=session.id, project_id=session.project.id,
                                   requested_by=actor.id,
                                   files=dict(session.draft["files"])))
    preview = {"status": "pending", "requested_at": _iso(datetime.now(UTC)),
               "session_id": session.id}
    session.preview = preview
    db.flush()
    return preview


def _fail_request(db, request_id: int, message: str) -> None:
    req = db.get(AssistantPreviewRequest, request_id)
    if req is None:
        return
    now = datetime.now(UTC)
    req.finished_at = now
    session = db.get(AssistantSession, req.session_id)
    if session is None:
        db.commit()
        return
    try:
        session = _view(db, session)
    except ApiError:
        # The project is gone: nowhere to publish the outcome, but the work order is finished.
        db.commit()
        return
    session.preview = {"status": "failed", "finished_at": _iso(now), "message": message,
                       "session_id": session.id}
    record_outcome(db, session)
    db.commit()


def _owner_locale(db, request_id: int) -> str:
    """Language of the conversation owner for worker texts (feature 022)."""
    try:
        req = db.get(AssistantPreviewRequest, request_id)
        if req is None:
            return get_settings().default_locale
        session = db.get(AssistantSession, req.session_id)
        if session is None:
            return get_settings().default_locale
        user = db.get(AppUser, session.created_by)
        if user is None or user.locale not in {"es", "en"}:
            return get_settings().default_locale
        return user.locale
    except Exception:
        return get_settings().default_locale


def process_request(request_id: int) -> None:
    """Worker thread: run every draft integration into the session's preview schemas.

    Feature 037: the request names its project; the worker checks it against the conversation and
    resolves the folder from it, logging the root it is about to read.
    """
    with get_sessionmaker()() as db:
        with use_locale(_owner_locale(db, request_id)):
            try:
                req = db.get(AssistantPreviewRequest, request_id)
                if req is None or req.finished_at is not None:
                    return
                session = db.get(AssistantSession, req.session_id)
                if session is None:
                    _fail_request(db, request_id, t("preview.run_failed"))
                    return
                project = db.get(Project, req.project_id)
                expected = db.get(Project, session.project_id) if session.project_id else None
                if project is None or project.deleted_at is not None:
                    _fail_request(db, request_id,
                                  t("preview.project_gone", slug=str(req.project_id)))
                    return
                if expected is None or expected.id != project.id:
                    log.warning("preview %s: request project %s, conversation project %s",
                                request_id, project.slug,
                                expected.slug if expected is not None else None)
                    _fail_request(db, request_id,
                                  t("preview.project_mismatch", sent=project.slug,
                                    expected=expected.slug if expected is not None else "?"))
                    return
                from app.projects import fs

                root = fs.project_root(project.slug)
                log.info("preview %s: project %s (id %s), root %s, carried %s files",
                         request_id, project.slug, project.id, root,
                         len(req.files or {}))
                carried = req.files if isinstance(req.files, dict) and req.files else None
                run_draft_preview(db, session, files=carried)
                req.finished_at = datetime.now(UTC)
                db.commit()
            except PreviewBusy:
                db.rollback()
                _fail_request(db, request_id, t("preview.busy_retry"))
            except Exception:
                db.rollback()
                _fail_request(db, request_id, t("preview.run_failed"))


def schema_prefix_pattern(session_id: int) -> str:
    with datasets.preview_schemas(datasets.preview_prefix(session_id)):
        sample = datasets.schema_name("x")
    prefix = sample[: -len("ds_x")]
    escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped + "ds\\_%"


def drop_schemas(pg, session_id: int) -> list[str]:
    rows = pg.execute(
        "SELECT nspname FROM pg_namespace WHERE nspname LIKE %s ESCAPE '\\'",
        (schema_prefix_pattern(session_id),),
    ).fetchall()
    names = [row[0] for row in rows]
    for name in names:
        pg.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(name)))
    return names


def drop_for_session(session_id: int) -> None:
    with get_engine().begin() as conn:
        drop_schemas(conn.connection.driver_connection, session_id)


def cleanup_stale(db) -> int:
    """Expire previews older than STALE_AFTER: per project (feature 020) and legacy per
    conversation; drops the preview schemas of the conversation that ran them."""
    now = datetime.now(UTC)
    count = 0
    for project in db.scalars(select(Project).where(Project.preview.is_not(None))):
        preview = project.preview or {}
        finished = preview.get("finished_at")
        stale = project.deleted_at is not None or (
            finished and datetime.fromisoformat(finished) < now - STALE_AFTER
        )
        if not stale or preview.get("status") == "expired":
            continue
        if preview.get("status") in ("succeeded", "failed") and preview.get("session_id"):
            drop_for_session(preview["session_id"])
        project.preview = {"status": "expired"}
        count += 1
    sessions = list(db.scalars(
        select(AssistantSession).where(AssistantSession.preview.is_not(None))))
    for session in sessions:
        preview = session.preview or {}
        finished = preview.get("finished_at")
        stale = session.status != "open" or (
            finished and datetime.fromisoformat(finished) < now - STALE_AFTER
        )
        if not stale:
            continue
        if preview.get("status") in ("succeeded", "failed"):
            drop_for_session(session.id)
        if session.status == "open":
            session.preview = {"status": "expired"}
        count += 1
    db.flush()
    return count


def _is_preview_schema(name: str) -> bool:
    """`preview_7__ds_x` (and the test schema in front of it) is a preview schema (feature 014)."""
    return any(part.startswith("preview_") for part in name.split("__"))


def _missing_preview_schemas(ctx: engine.Context) -> list[str]:
    """Schemas the report needs that are gone: an applied/expired preview dropped them (038)."""
    expected = {schema for schema, _ in ctx.tables.values() if _is_preview_schema(schema)}
    if not expected:
        return []
    from sqlalchemy import text

    with get_engine().connect() as conn:
        found = {row[0] for row in conn.execute(
            text("SELECT nspname FROM pg_namespace WHERE nspname = ANY(:names)"),
            {"names": sorted(expected)})}
    return sorted(expected - found)


def _context(db, session, report_id):
    session = _view(db, session)
    preview = session.preview or {}
    status = preview.get("status")
    if status == "replaced":
        version = preview.get("version")
        raise RenderError(
            render_errors.PREVIEW_EXPIRED,
            str(M("render.preview_replaced", version=version or "?")), status=409,
            report_id=report_id, version=version,
        )
    if status != "succeeded":
        raise ApiError(409, "preview_not_ready", M("preview.run_preview_first"))
    active = workspace_service.active(db)
    active_artifacts = (active.artifacts if active
                        else {"workspace": {}, "integrations": {}, "reports": {}})
    d_integ, d_rep = draft_items((session.draft or {}).get("files", {}),
                                 active_artifacts.get("integrations", {}))
    integrations = {
        **active_artifacts.get("integrations", {}),
        **{k: {"definition": v["definition"], "files": v["files"]} for k, v in d_integ.items()},
    }
    reports = {**active_artifacts.get("reports", {}), **d_rep}
    rep = reports.get(report_id)
    if rep is None:
        raise ApiError(404, "not_found", M("preview.metric_not_found"))
    is_direct = isinstance(rep.get("definition"), dict) and isinstance(
        rep["definition"].get("direct"), dict
    )
    version_like = engine.PreviewVersion(
        id=None if is_direct else 0,
        artifacts={"workspace": active_artifacts.get("workspace") or {},
                   "integrations": integrations, "reports": reports},
    )
    ctx = engine.preview_context(version_like, report_id, rep["definition"], integrations,
                                 set(preview.get("preview_integrations") or []),
                                 _schemas_of(session))
    missing = _missing_preview_schemas(ctx)
    if missing:
        # The preview ran, but its schemas went away (an apply, or the stale cleanup). Saying so
        # also retires the links: the page stops offering a preview that cannot be read (038).
        session.preview = {**preview, "status": "expired", "expired_reason": "schemas_dropped"}
        log.error("preview %s of report %s lost its schemas: %s", _schemas_of(session),
                  report_id, ", ".join(missing))
        raise RenderError(
            render_errors.PREVIEW_EXPIRED, str(M("render.preview_expired")), status=409,
            report_id=report_id, datasets=", ".join(missing),
        )
    return ctx


def report_definition(db, session, report_id) -> dict:
    return engine.definition_json(_context(db, session, report_id))


def report_data(db, session, report_id, params, today, tz) -> dict:
    session = _view(db, session)
    ctx = _context(db, session, report_id)
    sel, filters = engine.selection(ctx, params, today)
    reference = engine.render_reference()
    if ctx.direct is not None:
        queried_at = datetime.now(UTC).isoformat()
        try:
            views = engine.run_views(ctx, sel, filters, tz, reference=reference)
        except direct.DirectError as e:
            raise direct.api_error(e) from None
        return {
            "selection": sel.to_json(),
            "filters": filters,
            "render_reference": reference,
            "freshness": {
                "updated_at": queried_at,
                "data_version": "preview",
                "mode": "direct",
                "source": engine.direct_source_label(ctx.direct.label),
                "queried_at": queried_at,
                "stale": False,
                "preview": True,
            },
            "views": views,
        }
    return {
        "selection": sel.to_json(),
        "filters": filters,
        "render_reference": reference,
        "freshness": {"updated_at": (session.preview or {}).get("finished_at"),
                      "data_version": "preview"},
        "views": engine.run_views(ctx, sel, filters, tz, reference=reference),
    }
