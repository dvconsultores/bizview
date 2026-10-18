from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.db import DB
from app.models import AppUser
from app.services import dashboards

router = APIRouter(prefix="/api/dashboards")


@router.get("")
def list_dashboards(user: AppUser = Depends(current_user), db: Session = DB):
    definitions = dashboards.report_definitions(db)
    return {"items": [dashboards.to_json(d, definitions)
                      for d in dashboards.visible_for(db, user)]}


@router.get("/{code}")
def open_dashboard(code: str, user: AppUser = Depends(current_user),
                   db: Session = DB):
    return dashboards.to_json(dashboards.get_for_open(db, user, code),
                              dashboards.report_definitions(db))
