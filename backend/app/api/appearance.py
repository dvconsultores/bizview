"""Installation appearance (feature 030): the palette preset, chosen by the super user.

Singleton row (`appearance_settings`), the `telegram_settings` precedent: a super-user `GET`/`PUT`
pair and an audit event. The value is also exposed by `GET /api/config`, because the shared view is
unauthenticated and must render with the installation's preset.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth.deps import client_ip, require_superuser
from app.db import DB
from app.errors import validation
from app.i18n import current
from app.models import PALETTE_PRESET_IDS, AppearanceSettings, AppUser
from app.services import audit

router = APIRouter()

UNKNOWN_PRESET = {
    "es": "Esa paleta no existe. Elige una de las disponibles.",
    "en": "That palette does not exist. Choose one of the available ones.",
}


class AppearanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    palette_preset: str = Field(max_length=32)


def preset_ids() -> tuple[str, ...]:
    """The preset ids, from the product data (`app/reports/palette.py`) both renderers read."""
    try:
        from app.reports.palette import PRESET_IDS
    except ImportError:   # the model keeps the mirror for exactly this fallback
        return PALETTE_PRESET_IDS
    return tuple(PRESET_IDS)


def preset_of(db: Session) -> str:
    """The installation's preset; a missing row behaves as the default (`impacto`)."""
    row = db.get(AppearanceSettings, 1)
    return row.palette_preset if row is not None else PALETTE_PRESET_IDS[0]


@router.get("/api/admin/appearance")
def get_appearance(_actor: AppUser = Depends(require_superuser), db: Session = DB):
    return {"palette_preset": preset_of(db), "presets": list(preset_ids())}


@router.put("/api/admin/appearance")
def put_appearance(
    body: AppearanceIn,
    request: Request,
    actor: AppUser = Depends(require_superuser),
    db: Session = DB,
):
    if body.palette_preset not in preset_ids():
        raise validation({"palette_preset": "invalid"}, UNKNOWN_PRESET[current()])

    row = db.get(AppearanceSettings, 1, with_for_update=True)
    previous = row.palette_preset if row is not None else PALETTE_PRESET_IDS[0]
    if row is None:
        row = AppearanceSettings(id=1, palette_preset=body.palette_preset)
        db.add(row)
    else:
        row.palette_preset = body.palette_preset
    row.updated_by = actor.id
    audit.record(db, "appearance_updated", actor_id=actor.id, ip=client_ip(request),
                 detail={"palette_preset": {"from": previous, "to": body.palette_preset}})
    return {"palette_preset": row.palette_preset}
