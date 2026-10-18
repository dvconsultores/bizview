"""AI status and connection test — super user only (contracts/api.md, feature 003)."""
from fastapi import APIRouter, Depends

from app.ai import service
from app.auth.deps import require_superuser
from app.config import get_settings
from app.models import AppUser

router = APIRouter(prefix="/api/admin/ai")


@router.get("")
def ai_status(_: AppUser = Depends(require_superuser)):
    return service.status(get_settings())


@router.post("/test")
def ai_test(_: AppUser = Depends(require_superuser)):
    return service.test_connection(get_settings())
