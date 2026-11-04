"""AI status, connection test and the internal structure prompt (features 003, 052).

Super user only, like the rest of Administración → IA."""
from fastapi import APIRouter, Depends

from app.ai import service
from app.auth.deps import require_superuser
from app.config import get_settings
from app.models import AppUser
from app.sources import structure_ai

router = APIRouter(prefix="/api/admin/ai")


@router.get("")
def ai_status(_: AppUser = Depends(require_superuser)):
    return service.status(get_settings())


@router.post("/test")
def ai_test(_: AppUser = Depends(require_superuser)):
    return service.test_connection(get_settings())


@router.get("/prompt")
def structure_prompt(_: AppUser = Depends(require_superuser)):
    """The prompt the structure generator sends, read-only: what a run asks of the provider.

    Data, not configuration: it ships with the release, so an installation can read exactly what an
    AI pass receives and what it is asked to return (constitution VIII, feature 052).
    """
    return {"name": "source_structure", "text": structure_ai.prompt()}
