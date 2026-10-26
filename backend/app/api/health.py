import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.ai import state, vision_enabled
from app.api.appearance import preset_ids
from app.config import get_settings
from app.db import get_engine, get_read_sessionmaker
from app.models import PALETTE_PRESET_IDS, AppearanceSettings, TelegramSettings
from app.telegram import service as telegram

LICENSE = "AGPL-3.0-or-later"

router = APIRouter()
log = logging.getLogger("app")


@router.get("/api/health")
def health():
    try:
        with get_engine().connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "unavailable", **_build(), "ai": ai_block()},
                            status_code=503)
    return {"status": "ok", **_build(), "ai": ai_block()}


def ai_block() -> dict:
    """Whether the AI is configured and how its last call went — never the key, never the text.

    Feature 035: «is the AI working?» must be answerable from outside, and a reader must not have to
    find the backend container to know. `last_error_detail` stays on the Administración page only.
    """
    s = get_settings()
    status = state.read()
    return {"configured": bool(s.ai_enabled), "provider": s.ai_provider,
            "model": s.ai_model_effective,
            "last_ok_at": status["last_ok_at"],
            "last_error_code": status["last_error_code"],
            "last_error_at": status["last_error_at"]}


def _build() -> dict:
    """What this process is: the release version and, in a release image, its commit.

    Release images carry the commit they were built from (`deploy.sh` → build arg →
    `BIZVIEW_COMMIT`), so `curl /api/health` answers whether a fix is actually deployed instead of
    looking for line numbers in a traceback. A development checkout leaves it out.
    """
    s = get_settings()
    return {"version": s.version, **({"commit": s.bizview_commit} if s.bizview_commit else {})}


@router.get("/api/config")
def public_config():
    s = get_settings()
    return {"product_name": s.product_name, "organization_name": s.organization_name,
            "logo_url": s.logo_url, "version": s.version, "source_url": s.source_url,
            "license": LICENSE, "ai_enabled": s.ai_enabled, "default_locale": s.default_locale,
            "footer_credit": s.footer_credit,
            "vision_enabled": vision_enabled(s),
            "attachments_max_mb": s.attachments_max_mb,
            "attachments_max_per_message": s.attachments_max_per_message,
            "google_auth": s.google_enabled_effective,
            **_telegram_config(),
            **_palette_config()}


def _telegram_config() -> dict:
    """Telegram sign-in availability (feature 007); off whenever it cannot be read."""
    try:
        with get_read_sessionmaker()() as db:   # one round trip, no BEGIN/ROLLBACK
            row = db.get(TelegramSettings, 1)
            if telegram.is_available(row):
                return {"telegram_sign_in": True, "telegram_bot": row.bot_username}
    except Exception:
        log.warning("telegram availability could not be read")
    return {"telegram_sign_in": False, "telegram_bot": None}


def _palette_config() -> dict:
    """Installation palette (feature 030); the default preset whenever the row cannot be read."""
    preset = PALETTE_PRESET_IDS[0]
    try:
        with get_read_sessionmaker()() as db:   # one round trip, no BEGIN/ROLLBACK
            row = db.get(AppearanceSettings, 1)
            if row is not None:
                preset = row.palette_preset
    except Exception:
        log.warning("palette preset could not be read")
    return {"palette_preset": preset, "palette_presets": list(preset_ids())}
