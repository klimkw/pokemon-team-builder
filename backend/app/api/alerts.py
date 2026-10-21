"""Owner-scoped recent changes; reading does not acknowledge or modify history."""
from fastapi import APIRouter, Query, Depends
from uuid import UUID
from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.api.security import require_same_origin
from app.db.models import AlertRead
from app.api.dependencies import Database, Owner
from app.schemas.alerts import AlertPage
from app.services.alerts import get_alerts, relevant_change_ids

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=AlertPage)
async def alerts(db: Database, user: Owner, limit: int = Query(20, ge=1, le=100),
                 offset: int = Query(0, ge=0)):
    return await get_alerts(db, user.id, limit=limit, offset=offset)


class ReadAlerts(BaseModel):
    change_ids: list[UUID] = Field(max_length=100)


@router.post('/read', status_code=204, dependencies=[Depends(require_same_origin)])
async def mark_read(payload: ReadAlerts, db: Database, user: Owner):
    # Only currently relevant events can be acknowledged, never another owner's feed.
    allowed = await relevant_change_ids(db, user.id, payload.change_ids)
    rows = [{'user_id': user.id, 'change_id': key} for key in allowed]
    if rows:
        insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
        await db.execute(insert(AlertRead).values(rows).on_conflict_do_nothing())
        await db.commit()
