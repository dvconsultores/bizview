"""Vibe-reporting assistant (feature 014): super user only."""
from datetime import datetime
from zoneinfo import ZoneInfo

from bizview_cli import layout
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import vision_enabled
from app.assistant import activity as assistant_activity
from app.assistant import attachments as _attachments
from app.assistant import preview as assistant_preview
from app.assistant import service
from app.assistant.commands import registry as commands_registry
from app.auth.deps import Auth, client_ip, recent_reauth, require_superuser
from app.config import get_settings
from app.db import DB
from app.errors import ApiError, not_found, validation
from app.i18n import M, current, t
from app.models import AppUser, AssistantAttachment, AssistantMessage, AssistantSession, Project
from app.projects import fs
from app.projects import service as projects_service
from app.reports import pdf
from app.services.audit import record as audit_record
from app.workspace import service as workspace_service

router = APIRouter(prefix="/api/assistant")


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    project: str


class SessionRename(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    current_spec: str | None = None


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = ""
    attachments: list[int] = []


class SessionSpec(BaseModel):
    """The current spec of a conversation (a normal POST, no step-up)."""
    model_config = ConfigDict(extra="forbid")
    spec: str


def require_ai_enabled() -> None:
    if not get_settings().ai_enabled:
        raise ApiError(409, "ai_not_configured", t("assistant.ai_not_configured"))


def _own_session(db: Session, session_id: int, actor: AppUser) -> AssistantSession:
    session = db.get(AssistantSession, session_id)
    if session is None or session.created_by != actor.id:
        raise not_found(t("assistant.conversation_not_found"))
    return session


def _messages(db: Session, session: AssistantSession) -> list[AssistantMessage]:
    return list(db.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.session_id == session.id)
        .order_by(AssistantMessage.id)
    ))


def _own_attachment(db: Session, attachment_id: int, actor: AppUser) -> AssistantAttachment:
    """The caller's own image, or any image when the caller is an administrator (024, §3).

    Anyone else gets a 404 and never a 403, so an id is not an oracle."""
    row = db.get(AssistantAttachment, attachment_id)
    session = db.get(AssistantSession, row.session_id) if row is not None else None
    if session is None or (session.created_by != actor.id and not actor.is_superuser):
        raise not_found(t("attachments.not_found"))
    return row


def _disposition(row: AssistantAttachment) -> str:
    """A download name that cannot break the header: the stored name is user supplied."""
    name = "".join(c for c in (row.original_name or "") if c.isalnum() or c in "._- ")
    return f'inline; filename="{name.strip()[:120]}"' if name.strip() else "inline"


def require_vision() -> None:
    """Image briefs need a model that reads images (feature 024, research R2)."""
    if not vision_enabled(get_settings()):
        raise ApiError(409, "vision_unavailable", t("attachments.vision_unavailable"))


@router.get("/sessions")
def list_sessions(project: str | None = None, actor: AppUser = Depends(require_superuser),
                  db: Session = DB):
    settings = get_settings()
    query = select(AssistantSession).where(AssistantSession.created_by == actor.id)
    if project:
        query = query.where(
            AssistantSession.project_id == projects_service.get(db, project).id)
    sessions = db.scalars(query.order_by(AssistantSession.updated_at.desc())).all()
    # First message of the conversations still named by default, in one query.
    unnamed = [s.id for s in sessions if s.title == service.DEFAULT_TITLE]
    first = dict(db.execute(
        select(AssistantMessage.session_id, AssistantMessage.content)
        .distinct(AssistantMessage.session_id)
        .where(AssistantMessage.session_id.in_(unnamed), AssistantMessage.role == "user")
        .order_by(AssistantMessage.session_id, AssistantMessage.id)).all()) if unnamed else {}
    return {
        "sessions": [
            {
                "id": s.id,
                "title": service.display_title(s, first.get(s.id)),
                "status": s.status,
                "busy": service.is_busy(s, settings),
                "updated_at": s.updated_at.isoformat(),
                "tokens_used": s.tokens_used,
                "token_budget": s.token_budget,
                "project_id": s.project_id,
                "read_only": s.read_only,
                "current_spec": s.current_spec,
            }
            for s in sessions
        ]
    }


@router.post("/sessions", dependencies=[Depends(require_ai_enabled)])
def create_session(body: SessionCreate, actor: AppUser = Depends(require_superuser),
                   db: Session = DB):
    project = projects_service.get(db, body.project)
    session = service.create_session(db, actor, body.title, project_id=project.id)
    return service.session_json(session, [])


class ProposalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000)


@router.post("/project-proposal")
def project_proposal(body: ProposalIn, actor: AppUser = Depends(require_superuser),
                     db: Session = DB):
    """Name and slug proposed for a new project from the first message (no AI call)."""
    name = service.title_from(body.text)[:80]
    return {"name": name, "slug": projects_service.suggest_slug(db, name)}


@router.get("/sessions/{session_id}")
def get_session(session_id: int, actor: AppUser = Depends(require_superuser),
                db: Session = DB):
    session = _own_session(db, session_id, actor)
    return service.session_json(session, _messages(db, session))


@router.patch("/sessions/{session_id}")
def rename_session(session_id: int, body: SessionRename,
                   actor: AppUser = Depends(require_superuser), db: Session = DB):
    session = _own_session(db, session_id, actor)
    if body.title is None and body.current_spec is None:
        raise validation({"title": "required"}, M("common.validation"))
    if body.title is not None:
        service.rename(db, session, body.title)
    if body.current_spec is not None:
        folder = body.current_spec or None
        if folder is not None:
            project = db.get(Project, session.project_id)
            if (project is None or not layout.SPEC_FOLDER_RE.match(folder)
                    or not (fs.project_root(project.slug) / "specs" / folder).is_dir()):
                raise validation({"current_spec": "unknown"},
                                 M("projects.spec_unknown", folder=folder))
        session.current_spec = folder
    return service.session_json(session, _messages(db, session))


@router.post("/sessions/{session_id}/spec")
def set_current_spec(session_id: int, body: SessionSpec,
                     actor: AppUser = Depends(require_superuser), db: Session = DB):
    """Change the conversation's current spec (the header selector)."""
    session = _own_session(db, session_id, actor)
    folder = body.spec.strip() or None
    if folder is not None:
        project = db.get(Project, session.project_id)
        if (project is None or not layout.SPEC_FOLDER_RE.match(folder)
                or not (fs.project_root(project.slug) / "specs" / folder).is_dir()):
            raise validation({"spec": "unknown"}, M("projects.spec_unknown", folder=folder))
    session.current_spec = folder
    return service.session_json(session, _messages(db, session))


@router.post("/sessions/{session_id}/messages", dependencies=[Depends(require_ai_enabled)],
             status_code=202)
def send_message(session_id: int, body: MessageCreate, request: Request,
                 actor: AppUser = Depends(require_superuser), db: Session = DB):
    session = _own_session(db, session_id, actor)
    if body.attachments:
        require_vision()
    stored = service.start(db, actor, session, body.text, get_settings(),
                           client_ip(request), body.attachments)
    db.refresh(session)
    messages = _messages(db, session)
    first = stored[0].id
    return {
        "messages": [m for m in service.messages_json(db, session.id, messages)
                     if m["id"] >= first],
        "session": service.session_json(session, messages, with_specs=False),
    }


@router.post("/sessions/{session_id}/attachments", status_code=201,
             dependencies=[Depends(require_ai_enabled)])
async def upload_attachment(session_id: int, request: Request, name: str | None = None,
                            actor: AppUser = Depends(require_superuser), db: Session = DB):
    """An image brief: the bytes are the body, the type is decided by the magic bytes (024, §1).

    There is no form parser in the product, and the declared content type is not evidence, so the
    call is a plain body POST with the optional original file name in `name`."""
    session = _own_session(db, session_id, actor)
    require_vision()
    limit = get_settings().attachments_max_mb * 1024 * 1024
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise ApiError(413, "attachment_too_large",
                           M("attachments.too_large", max=get_settings().attachments_max_mb))
        chunks.append(chunk)
    _attachments.sweep_pending(db)
    row = _attachments.store(db, session.id, b"".join(chunks), name, actor.id)
    audit_record(db, "assistant_attachment_uploaded", actor_id=actor.id, ip=client_ip(request),
                 detail={"session": session.id, "attachment": row.id,
                         "media_type": row.media_type, "byte_size": row.byte_size,
                         "sha256": row.sha256[:12]})
    db.commit()
    return service.attachment_json(row)


@router.get("/attachments/{attachment_id}")
def get_attachment(attachment_id: int, actor: AppUser = Depends(require_superuser),
                   db: Session = DB):
    row = _own_attachment(db, attachment_id, actor)
    return Response(content=_attachments.load(db, row.id), media_type=row.media_type,
                    headers={"Cache-Control": "private, max-age=3600",
                             "Content-Disposition": _disposition(row)})


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(attachment_id: int, request: Request,
                     actor: AppUser = Depends(require_superuser), db: Session = DB):
    row = _own_attachment(db, attachment_id, actor)
    audit_record(db, "assistant_attachment_deleted", actor_id=actor.id, ip=client_ip(request),
                 detail={"session": row.session_id, "attachment": row.id,
                         "media_type": row.media_type, "byte_size": row.byte_size,
                         "sha256": row.sha256[:12]})
    _attachments.remove(db, row)
    db.commit()
    return Response(status_code=204)


@router.get("/sessions/{session_id}/activity")
def get_activity(
    session_id: int,
    actor: AppUser = Depends(require_superuser),
    db: Session = DB,
):
    return assistant_activity.activity_json(db, session_id, actor.id, get_settings())


@router.post("/sessions/{session_id}/stop")
def stop_run(session_id: int, actor: AppUser = Depends(require_superuser), db: Session = DB):
    session = _own_session(db, session_id, actor)
    service.stop(db, session, get_settings())
    return service.session_json(session, _messages(db, session))


@router.get("/commands")
def list_commands(actor: AppUser = Depends(require_superuser)):
    """The `/` menu in the request language (feature 021)."""
    return {"items": commands_registry.list_commands(current())}


@router.post("/sessions/{session_id}/command/finish")
def finish_command(session_id: int, actor: AppUser = Depends(require_superuser),
                   db: Session = DB):
    session = _own_session(db, session_id, actor)
    service.finish_command(db, session)
    return service.session_json(session, _messages(db, session))


@router.post("/sessions/{session_id}/archive")
def archive_session(session_id: int, request: Request,
                    actor: AppUser = Depends(require_superuser), db: Session = DB):
    session = _own_session(db, session_id, actor)
    service.ensure_idle(db, session, get_settings())
    service.archive(db, actor, session, client_ip(request))
    return {"status": "archived"}


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, request: Request,
                   actor: AppUser = Depends(require_superuser),
                   _: Auth = Depends(recent_reauth), db: Session = DB):
    """Delete a conversation for good; its messages, runs and attachments go with it."""
    session = _own_session(db, session_id, actor)
    service.delete_session(db, actor, session, client_ip(request))
    return Response(status_code=204)


@router.post("/sessions/{session_id}/apply")
def apply_session(session_id: int, request: Request,
                  actor: AppUser = Depends(require_superuser),
                  _: Auth = Depends(recent_reauth), db: Session = DB):
    session = _own_session(db, session_id, actor)
    service.ensure_idle(db, session, get_settings())
    version, revalidated = service.apply_draft(db, actor, session, client_ip(request))
    return {"version": workspace_service.version_json(version), "revalidated": revalidated,
            "session": service.session_json(session, _messages(db, session))}


@router.post("/sessions/{session_id}/preview")
def preview_session(session_id: int, actor: AppUser = Depends(require_superuser),
                    db: Session = DB):
    session = _own_session(db, session_id, actor)
    service.ensure_idle(db, session, get_settings())
    return {"preview": assistant_preview.request_preview(db, actor, session)}


@router.get("/sessions/{session_id}/preview")
def get_preview(session_id: int, actor: AppUser = Depends(require_superuser),
                db: Session = DB):
    return {"preview": assistant_preview._view(db, _own_session(db, session_id, actor)).preview}


@router.get("/sessions/{session_id}/preview/report/{report_id}")
def get_preview_report(session_id: int, report_id: str,
                       actor: AppUser = Depends(require_superuser), db: Session = DB):
    session = _own_session(db, session_id, actor)
    return assistant_preview.report_definition(db, session, report_id)


@router.get("/sessions/{session_id}/preview/report/{report_id}/data")
def get_preview_report_data(session_id: int, report_id: str, request: Request,
                            actor: AppUser = Depends(require_superuser), db: Session = DB):
    session = _own_session(db, session_id, actor)
    settings = get_settings()
    return assistant_preview.report_data(
        db, session, report_id, request.query_params.multi_items(),
        datetime.now(ZoneInfo(settings.timezone)).date(), settings.timezone)


@router.post("/sessions/{session_id}/budget")
def extend_budget(session_id: int, request: Request,
                  actor: AppUser = Depends(require_superuser), db: Session = DB):
    session = _own_session(db, session_id, actor)
    service.ensure_idle(db, session, get_settings())
    service.extend_budget(db, actor, session, get_settings(), client_ip(request))
    return service.session_json(session, _messages(db, session))


@router.post("/sessions/{session_id}/preview/report/{report_id}/pdf")
def get_preview_report_pdf(session_id: int, report_id: str, request: Request,
                           actor: AppUser = Depends(require_superuser), db: Session = DB):
    session = _own_session(db, session_id, actor)
    settings = get_settings()
    definition = assistant_preview.report_definition(db, session, report_id)
    if not definition["pdf"]:
        raise not_found(t("report.pdf_not_allowed"))
    payload = assistant_preview.report_data(
        db, session, report_id, request.query_params.multi_items(),
        datetime.now(ZoneInfo(settings.timezone)).date(), settings.timezone)
    content = pdf.render(
        definition,
        payload,
        organization=settings.organization_name,
        product=settings.product_name,
        viewer=actor.full_name,
        preview=True,
    )
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{report_id}-vista-previa.pdf"'
        },
    )
