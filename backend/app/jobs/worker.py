"""Separate scanner process: durable admin queue plus optional periodic full refresh."""
import argparse
import asyncio
import signal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db import session as db
from app.db.models import AdminJob, utc_now
from app.jobs.scanner import run_scan, scan_lock
from app.services.demo_controls import apply_changes, reset_changes
from app.settings import CATALOG_SCAN_INTERVAL_HOURS, ENABLE_DEMO_CONTROLS

WORKER_LOCK_KEY = 0x504F4B45574F52


async def recover_jobs(sessions):
    async with sessions.begin() as session:
        for job in await session.scalars(select(AdminJob).where(AdminJob.status == 'running')):
            job.status, job.finished_at = 'interrupted', utc_now()
            job.error = 'Worker stopped before completion; inspect alerts and submit again if needed'


async def process_one(engine):
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions.begin() as session:
        job = await session.scalar(select(AdminJob).where(AdminJob.status == 'queued')
            .order_by(AdminJob.created_at, AdminJob.id).with_for_update(skip_locked=True).limit(1))
        if job is None:
            return False
        job.status, job.started_at = 'running', utc_now()
        job_id, action, payload = job.id, job.action, job.payload
    try:
        if action == 'refresh':
            result = await run_scan(engine)
            status, output = result.status, result.summary
            if status == 'skipped':
                # Keep durable requests queued when a CLI/scheduled scan holds the lock.
                async with sessions.begin() as session:
                    job = await session.get(AdminJob, job_id)
                    job.status, job.started_at = 'queued', None
                return False
        else:
            if not ENABLE_DEMO_CONTROLS:
                raise ValueError('Demo controls are disabled in this worker environment')
            async with scan_lock(engine) as locked:
                if locked is None:
                    async with sessions.begin() as session:
                        job = await session.get(AdminJob, job_id)
                        job.status, job.started_at = 'queued', None
                    return False
                status, output = await (apply_changes(locked, payload) if action == 'demo_apply' else reset_changes(locked))
        async with sessions.begin() as session:
            job = await session.get(AdminJob, job_id)
            job.status, job.result, job.finished_at = status, output, utc_now()
            if status == 'failed':
                job.error = 'Scan failed; inspect counts and retry'
    except asyncio.CancelledError:
        async with sessions.begin() as session:
            job = await session.get(AdminJob, job_id)
            job.status, job.finished_at, job.error = 'interrupted', utc_now(), 'Worker shut down during operation'
        raise
    except Exception as error:
        async with sessions.begin() as session:
            job = await session.get(AdminJob, job_id)
            job.status, job.finished_at = 'failed', utc_now()
            # SQL/network exceptions can contain credentials; expose only their class.
            job.error = str(error)[:500] if isinstance(error, ValueError) else type(error).__name__
    return True


async def work(engine, stop, *, scheduled=False, poll_seconds=2):
    async with scan_lock(engine, key=WORKER_LOCK_KEY) as ownership:
        if ownership is None:
            raise RuntimeError('Another scanner worker already owns this database queue')
        await recover_jobs(ownership)
        next_scan = 0
        while not stop.is_set():
            ownership.check()
            # Prove the worker still owns its original physical advisory-lock session.
            async with ownership() as session:
                from sqlalchemy import text
                await session.execute(text('SELECT 1'))
                await session.commit()
            if await process_one(engine):
                continue
            now = asyncio.get_running_loop().time()
            if scheduled and now >= next_scan:
                await run_scan(engine)
                next_scan = asyncio.get_running_loop().time() + CATALOG_SCAN_INTERVAL_HOURS * 3600
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
            except asyncio.TimeoutError:
                pass


async def cli(scheduled):
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    task = asyncio.create_task(work(db.engine, stop, scheduled=scheduled))
    def shutdown():
        stop.set()
        task.cancel()
    for name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(name, shutdown)
    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        await db.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schedule', action='store_true', help='Also run periodic live catalog scans')
    asyncio.run(cli(parser.parse_args().schedule))


if __name__ == '__main__':
    main()
