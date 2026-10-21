"""Signed-in, explicitly enabled demo operations: durable local queue or bounded hosted requests."""
import asyncio
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, text
from app.api.auth import fastapi_users
from app.api.dependencies import Database, Owner
from app.api.security import require_same_origin
from app.db.models import AdminJob, User, utc_now
from app.db import session as database_session
from app.jobs.scanner import scan_lock
from app.services.demo_controls import apply_changes, reset_changes
from app.schemas.admin import DemoChanges, JobRead
from app.settings import ENABLE_DEMO_CONTROLS, DEMO_EXECUTION_MODE

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


async def run_demo(db, user, action, payload=None):
    if not ENABLE_DEMO_CONTROLS:
        raise HTTPException(403, 'Demo controls are disabled in this environment')
    if DEMO_EXECUTION_MODE == 'worker':
        return await enqueue(db, user, action, payload)
    # Release the authentication query's connection before taking the scan lock.
    user_id = user.id
    await db.rollback()
    async with scan_lock(database_session.engine) as sessions:
        if sessions is None:
            raise HTTPException(409, 'A catalog scan or demo is running; retry after it finishes')
        async with sessions.begin() as session:
            # A previous web process may have stopped mid-request. Pending demo
            # markers preserve recovery semantics; expose its interrupted audit.
            for old in await session.scalars(select(AdminJob).where(AdminJob.status == 'running',
                    AdminJob.action.in_(['demo_apply', 'demo_reset']))):
                old.status, old.finished_at = 'interrupted', utc_now()
                old.error = 'Demo request stopped; inspect the catalog and retry or reset'
            job = AdminJob(requested_by=user_id, action=action, payload=payload or {},
                result={}, status='running', started_at=utc_now())
            session.add(job)
            await session.flush()
            job_id = job.id
        try:
            async with asyncio.timeout(10):
                status, result = await (apply_changes(sessions, payload) if action == 'demo_apply'
                                        else reset_changes(sessions))
            error = None
        except asyncio.CancelledError:
            async with sessions.begin() as session:
                job = await session.get(AdminJob, job_id)
                job.status, job.finished_at = 'interrupted', utc_now()
                job.error = 'Demo request cancelled; inspect the catalog and retry or reset'
            raise
        except Exception as exc:
            status, result = 'failed', {}
            error = str(exc)[:500] if isinstance(exc, ValueError) else type(exc).__name__
        async with sessions.begin() as session:
            job = await session.get(AdminJob, job_id)
            job.status, job.result, job.error, job.finished_at = status, result, error, utc_now()
            await session.flush()
            return JobRead.model_validate(job)


@router.post('/refresh', response_model=JobRead, status_code=202, dependencies=[Depends(require_same_origin)])
async def refresh(db: Database, user: Admin, response: Response):
    """Queue a full live refresh of all Pokemon and 18 types. Preserve teams and history."""
    if DEMO_EXECUTION_MODE == 'request':
        raise HTTPException(409, 'Run Demo catalog scan in GitHub Actions for a live refresh')
    job = await enqueue(db, user, 'refresh')
    response.headers['Location'] = f'/api/admin/jobs/{job.id}'
    return job


@router.post('/demo/changes', response_model=JobRead, status_code=202, dependencies=[Depends(require_same_origin)])
async def demo_changes(payload: DemoChanges, db: Database, user: Owner, response: Response):
    """Apply supplied fixture changes through the scanner. Repeat the same payload to prove idempotence.

    Use Pokemon IDs from saved teams to see alerts. Further requests accumulate changes.
    Reset restores original values across all requests. These changes affect every user.
    Hosted request mode returns the completed audit (200); worker mode queues it (202).
    """
    job = await run_demo(db, user, 'demo_apply', payload.model_dump(mode='json'))
    response.headers['Location'] = f'/api/admin/jobs/{job.id}'
    if DEMO_EXECUTION_MODE == 'request':
        response.status_code = 200
    return job


@router.post('/demo/reset', response_model=JobRead, status_code=202, dependencies=[Depends(require_same_origin)])
async def demo_reset(db: Database, user: Owner, response: Response):
    """Restore only demo fields and remove only tagged demo history; refuse to overwrite newer source values."""
    job = await run_demo(db, user, 'demo_reset')
    response.headers['Location'] = f'/api/admin/jobs/{job.id}'
    if DEMO_EXECUTION_MODE == 'request':
        response.status_code = 200
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
