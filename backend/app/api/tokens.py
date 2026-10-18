"""Personal access tokens (feature 005, research R8): super user only, scope `describe`, shown
once, stored as SHA-256, revocable, 90 days by default. They grant nothing else."""
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import (
    Auth,
    auth_allow_temporary,
    client_ip,
    current_auth,
    recent_reauth,
    require_superuser,
)
from app.db import DB
from app.errors import not_found, unauthenticated
from app.i18n import t
from app.models import ApiToken, AppUser
from app.services import audit

router = APIRouter(prefix="/api/tokens")
PREFIX = "bzv_"


def token_hash(raw: str) -> bytes:
    return hashlib.sha256(raw.encode()).digest()


def to_json(t: ApiToken) -> dict:
    return {"id": t.id, "name": t.name, "scopes": t.scopes, "created_at": t.created_at,
            "expires_at": t.expires_at, "last_used_at": t.last_used_at,
            "revoked_at": t.revoked_at,
            "active": t.revoked_at is None and t.expires_at > datetime.now(UTC)}


class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    scopes: list[Literal["describe"]] = Field(default_factory=lambda: ["describe"], min_length=1)
    expires_days: int = Field(default=90, ge=1, le=365)


@router.get("")
def list_tokens(user: AppUser = Depends(require_superuser), db: Session = DB):
    rows = db.scalars(select(ApiToken).where(ApiToken.user_id == user.id)
                      .order_by(ApiToken.id.desc()))
    return {"items": [to_json(t) for t in rows]}


@router.post("", status_code=201)
def create_token(body: TokenIn, request: Request, user: AppUser = Depends(require_superuser),
                 _: Auth = Depends(recent_reauth), db: Session = DB):
    raw = PREFIX + secrets.token_urlsafe(32)
    token = ApiToken(user_id=user.id, name=body.name.strip(), token_hash=token_hash(raw),
                     scopes=sorted(set(body.scopes)),
                     expires_at=datetime.now(UTC) + timedelta(days=body.expires_days))
    db.add(token)
    db.flush()
    audit.record(db, "token_created", actor_id=user.id, ip=client_ip(request),
                 detail={"key_id": token.id, "name": token.name, "scopes": token.scopes})
    db.refresh(token)
    return {**to_json(token), "token": raw}


@router.delete("/{token_id}", status_code=204)
def revoke_token(token_id: int, request: Request, user: AppUser = Depends(require_superuser),
                 db: Session = DB):
    token = db.get(ApiToken, token_id)
    if token is None or token.user_id != user.id:
        raise not_found(t("tokens.not_found"))
    if token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        audit.record(db, "token_revoked", actor_id=user.id, ip=client_ip(request),
                     detail={"key_id": token.id, "name": token.name})
    return Response(status_code=204)


def token_or_session(scope: str):
    """`Authorization: Bearer <token>` with `scope`, or a super-user session."""
    def _dep(request: Request, db: Session = DB) -> tuple[AppUser, ApiToken | None]:
        header = request.headers.get("authorization") or ""
        if header[:7].lower() == "bearer ":
            raw = header[7:].strip()
            token = db.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash(raw)))
            now = datetime.now(UTC)
            if (token is None or token.revoked_at is not None or token.expires_at <= now
                    or scope not in token.scopes):
                raise unauthenticated()
            user = db.get(AppUser, token.user_id)
            if user is None or not user.is_active or not user.is_superuser:
                raise unauthenticated()
            token.last_used_at = now
            return user, token
        auth = current_auth(auth_allow_temporary(request, db))
        return require_superuser(auth.user), None
    return _dep
