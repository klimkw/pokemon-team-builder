"""Public, allowlisted application metadata. Never serialize settings or job payloads."""
from datetime import datetime
from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from app.api.dependencies import Database
from app.db.models import Pokemon, ScanRun, utc_now
from app.schemas.alerts import ScanStatus
from app.services.counters import MODEL_VERSION
from app.services.battle import SIMULATION_VERSION
from app.settings import CATALOG_SCAN_INTERVAL_HOURS, CHANGE_ALERT_WINDOW_DAYS
from app.version import APP_VERSION

router = APIRouter(prefix='/api/info', tags=['application'])


class AppInfo(BaseModel):
    app_version: str
    counter_model: str
    simulation_model: str
    repository_url: str
    catalog_count: int
    scan_interval_hours: int
    alert_window_days: int
    latest_live_refresh: ScanStatus | None
    last_successful_live_refresh: ScanStatus | None
    checked_at: datetime


@router.get('', response_model=AppInfo)
async def info(db: Database, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    full = select(ScanRun).where(ScanRun.summary['scope'].as_string() == 'full',
        or_(ScanRun.summary['source'].as_string().is_(None),
            ScanRun.summary['source'].as_string() == 'upstream'))
    ordered = full.order_by(ScanRun.started_at.desc(), ScanRun.id.desc())
    latest = await db.scalar(ordered.limit(1))
    succeeded = await db.scalar(ordered.where(ScanRun.status == 'succeeded', ScanRun.finished_at.is_not(None)).limit(1))
    return AppInfo(app_version=APP_VERSION, counter_model=MODEL_VERSION,
        simulation_model=SIMULATION_VERSION, repository_url='https://github.com/klimkw/pokemon-team-builder',
        catalog_count=await db.scalar(select(func.count()).select_from(Pokemon)),
        scan_interval_hours=CATALOG_SCAN_INTERVAL_HOURS, alert_window_days=CHANGE_ALERT_WINDOW_DAYS,
        latest_live_refresh=ScanStatus.model_validate(latest) if latest else None,
        last_successful_live_refresh=ScanStatus.model_validate(succeeded) if succeeded else None,
        checked_at=utc_now())
