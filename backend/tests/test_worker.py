import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
import pytest
from app.db import session as db
from app.jobs import worker
from app.jobs.scanner import ScanResult


def setup_worker(monkeypatch):
    class Ownership:
        def check(self): pass
        def __call__(self): return db.session_maker()
        def begin(self): return db.session_maker.begin()

    @asynccontextmanager
    async def lock(*args, **kwargs):
        yield Ownership()

    monkeypatch.setattr(worker, 'scan_lock', lock)
    monkeypatch.setattr(worker, 'recover_jobs', AsyncMock())
    monkeypatch.setattr(worker, 'scan_delay', AsyncMock(return_value=0))



def test_queued_refresh_postpones_due_schedule(client, monkeypatch):
    setup_worker(monkeypatch)
    async def run():
        stop = asyncio.Event()
        outcomes = iter([worker.JobOutcome.REFRESHED, worker.JobOutcome.IDLE])
        async def process(engine):
            outcome = next(outcomes)
            if outcome == worker.JobOutcome.IDLE:
                stop.set()
            return outcome
        scan = AsyncMock()
        monkeypatch.setattr(worker, 'process_one', process)
        monkeypatch.setattr(worker, 'run_scan', scan)
        await worker.work(db.engine, stop, scheduled=True, poll_seconds=0)
        scan.assert_not_awaited()
    asyncio.run(run())



def test_skipped_scheduled_scan_retries_without_waiting_full_interval(client, monkeypatch):
    setup_worker(monkeypatch)
    async def run():
        stop = asyncio.Event()
        calls = []
        async def scan(engine):
            calls.append(engine)
            if len(calls) == 1:
                return ScanResult('skipped', {'reason': 'scan_already_running'})
            stop.set()
            return ScanResult('succeeded', {'scope': 'full', 'types': {}})
        monkeypatch.setattr(worker, 'process_one', AsyncMock(return_value=worker.JobOutcome.IDLE))
        monkeypatch.setattr(worker, 'run_scan', scan)
        await asyncio.wait_for(worker.work(db.engine, stop, scheduled=True, poll_seconds=0), timeout=2)
        assert len(calls) == 2
    asyncio.run(run())



@pytest.mark.parametrize('status,summary,expected', [
    ('succeeded', {'scope': 'full', 'types': {}}, worker.JobOutcome.REFRESHED),
    ('partial', {'scope': 'full', 'types': {}}, worker.JobOutcome.REFRESHED),
    ('failed', {'scope': 'full'}, worker.JobOutcome.COMPLETED),
    ('skipped', {'reason': 'scan_already_running'}, worker.JobOutcome.DEFERRED),
])
def test_refresh_job_reports_scheduling_outcome(signed_in, monkeypatch, status, summary, expected):
    from uuid import UUID
    from app.db.models import AdminJob
    owner_id = UUID(signed_in.get('/api/auth/me').json()['id'])
    monkeypatch.setattr(worker, 'run_scan', AsyncMock(return_value=ScanResult(status, summary)))
    async def run():
        async with db.session_maker.begin() as session:
            job = AdminJob(requested_by=owner_id, action='refresh', status='queued')
            session.add(job)
        assert await worker.process_one(db.engine) == expected
        async with db.session_maker() as session:
            stored = await session.get(AdminJob, job.id)
            assert stored.status == ('queued' if status == 'skipped' else status)
    asyncio.run(run())
