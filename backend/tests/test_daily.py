import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from app.jobs import daily
from app.jobs.scanner import ScanResult


@pytest.mark.parametrize('locked,delay,status,expected', [
    (False, 0, 'succeeded', 60),
    (True, 123, 'succeeded', 123),
    (True, 0, 'succeeded', daily.CATALOG_SCAN_INTERVAL_HOURS * 3600),
    (True, 0, 'failed', 60),
])
def test_daily_checks_persisted_due_time_under_lock(monkeypatch, locked, delay, status, expected):
    active = False
    @asynccontextmanager
    async def lock(engine):
        nonlocal active
        active = locked
        yield object() if locked else None
        active = False
    async def due(sessions):
        assert active
        return delay
    async def scan(sessions):
        assert active
        return ScanResult(status, {'scope': 'full', 'types': {}})
    scan_mock = AsyncMock(side_effect=scan)
    monkeypatch.setattr(daily, 'scan_lock', lock)
    monkeypatch.setattr(daily, 'scan_delay', due)
    monkeypatch.setattr(daily, 'run_locked_scan', scan_mock)
    assert asyncio.run(daily.tick(object())) == expected
    assert scan_mock.await_count == int(locked and delay == 0)
