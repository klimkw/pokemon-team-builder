"""Admin controls usable from same-origin Swagger docs; work runs in the scanner worker."""
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, text
from app.api.auth import fastapi_users
from app.api.dependencies import Database
from app.api.security import require_same_origin
from app.db.models import AdminJob, User
from app.schemas.admin import DemoChanges, JobRead
from app.settings import ENABLE_DEMO_CONTROLS

Admin = Annotated[User, Depends(fastapi_users.current_user(active=True, superuser=True))]
router = APIRouter(prefix='/api/admin', tags=['Admin operations'])


async def enqueue(db, user, action, payload=None):
    if action != 'refresh' and not ENABLE_DEMO_CONTROLS:
        raise HTTPException(403, 'Demo controls are disabled in this environment')
    if db.bind.dialect.name == 'postgresql':
        await db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': 0x504F4B45515545})
    if await db.scalar(select(AdminJob.id).where(AdminJob.status.in_(['queued', 'running'])).limit(1)):
        raise HTTPException(409, 'An admin job is already queued or running; check its status first')
    job = AdminJob(requested_by=user.id, action=action, payload=payload or {}, result={})
    db.add(job)
    await db.flush()
    result = JobRead.model_validate(job)
    await db.commit()
    return result


@router.post('/refresh', response_model=JobRead, status_code=202, dependencies=[Depends(require_same_origin)])
async def refresh(db: Database, user: Admin, response: Response):
    """Queue a full live refresh of all Pokemon and 18 types. Preserve teams and history."""
    job = await enqueue(db, user, 'refresh')
    response.headers['Location'] = f'/api/admin/jobs/{job.id}'
    return job


@router.post('/demo/changes', response_model=JobRead, status_code=202, dependencies=[Depends(require_same_origin)])
async def demo_changes(payload: DemoChanges, db: Database, user: Admin, response: Response):
    """Apply supplied fixture changes through the scanner. Repeat the same payload to prove idempotence.

    Use Pokemon IDs from saved teams to see alerts. Further requests accumulate changes.
    Reset restores original values across all requests. Inspect the returned job URL for completion.
    """
    job = await enqueue(db, user, 'demo_apply', payload.model_dump(mode='json'))
    response.headers['Location'] = f'/api/admin/jobs/{job.id}'
    return job


@router.post('/demo/reset', response_model=JobRead, status_code=202, dependencies=[Depends(require_same_origin)])
async def demo_reset(db: Database, user: Admin, response: Response):
    """Restore only demo fields and remove only tagged demo history; refuse to overwrite newer source values."""
    job = await enqueue(db, user, 'demo_reset')
    response.headers['Location'] = f'/api/admin/jobs/{job.id}'
    return job


@router.get('/jobs', response_model=list[JobRead])
async def jobs(db: Database, user: Admin):
    """The most recent 25 operations, including queue, scan counts and failures."""
    return list(await db.scalars(select(AdminJob).order_by(AdminJob.created_at.desc(), AdminJob.id.desc()).limit(25)))


@router.get('/jobs/{job_id}', response_model=JobRead)
async def job_status(job_id: UUID, db: Database, user: Admin):
    job = await db.get(AdminJob, job_id)
    if job is None:
        raise HTTPException(404, 'Job not found')
    return job
