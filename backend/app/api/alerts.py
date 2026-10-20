"""Owner-scoped recent changes; reading does not acknowledge or modify history."""
from fastapi import APIRouter, Query
from app.api.dependencies import Database, Owner
from app.schemas.alerts import AlertPage
from app.services.alerts import get_alerts

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=AlertPage)
async def alerts(db: Database, user: Owner, limit: int = Query(20, ge=1, le=100),
                 offset: int = Query(0, ge=0)):
    return await get_alerts(db, user.id, limit=limit, offset=offset)
