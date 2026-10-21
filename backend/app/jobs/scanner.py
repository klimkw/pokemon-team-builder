"""One-shot or separately scheduled scans; no scheduler runs inside the API."""
import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
import json
import signal
import sys
import uuid

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db import session as db
from app.jobs import ingest
from app.db.models import ScanRun, utc_now
from app.services.pokeapi import PokeAPIClient
from app.services.scans import ScanStatus, ScanSummary
from app.settings import CATALOG_SCAN_INTERVAL_HOURS
from app.services.type_sync import fetch_chart, sync_chart

# One session-level lock shared by every manual/scheduled writer in this database.
SCAN_LOCK_KEY = 0x504F4B454D4F4E


@dataclass
class ScanResult:
    status: ScanStatus
    summary: ScanSummary

    @property
    def exit_code(self):
        return 0 if self.status in ("succeeded", "skipped") else 1


class LostScanLock(RuntimeError):
    pass


class LockedSessions:
    """All writes stay on the physical connection holding the advisory lock.

    After connection loss, refuse reconnection without a fresh lock acquisition.
    Network detail fetches may run concurrently, but DB writes remain sequential.
    """
    def __init__(self, connection):
        self.connection = connection
        self.factory = async_sessionmaker(connection, expire_on_commit=False)

    def check(self):
        if self.connection.closed or self.connection.invalidated:
            raise LostScanLock("Scanner lock connection was lost")

    def __call__(self):
        self.check()
        return self.factory()

    def begin(self):
        self.check()
        return self.factory.begin()


@asynccontextmanager
async def scan_lock(engine, *, key=SCAN_LOCK_KEY):
    if engine.dialect.name != "postgresql":
        raise RuntimeError("The scanner requires PostgreSQL advisory locks")
    async with engine.connect() as connection:
        acquired = False
        try:
            acquired = await connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
            await connection.commit()
            yield LockedSessions(connection) if acquired else None
        finally:
            if not acquired:
                # Acquisition may have been cancelled after the server took the lock
                # but before its result reached us. Close the physical session.
                await connection.invalidate()
            elif not connection.invalidated and not connection.closed:
                try:
                    await connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                    await connection.commit()
                except BaseException:
                    # Never return a potentially locked physical connection to its pool.
                    await connection.invalidate()
                    raise


async def finish_run(sessions, run_id, status, summary, error=None):
    async with sessions.begin() as session:
        run = await session.get(ScanRun, run_id)
        run.status, run.summary, run.error = status, summary, error
        run.finished_at = utc_now()


async def run_scan(engine, *, api=None, limit=None, include_types=True):
    async with scan_lock(engine) as sessions:
        if sessions is None:
            # Audit skipped attempts using an ordinary connection; no upstream calls.
            ordinary = async_sessionmaker(engine, expire_on_commit=False)
            async with ordinary.begin() as session:
                now = utc_now()
                session.add(ScanRun(status="skipped", started_at=now, finished_at=now, summary={"reason": "scan_already_running"}))
            return ScanResult("skipped", {"reason": "scan_already_running"})
        return await run_locked_scan(sessions, api=api, limit=limit, include_types=include_types)


async def run_locked_scan(sessions, *, api=None, limit=None, include_types=True, metadata=None):
    """Caller must hold scan_lock for the entire call, including demo state changes."""
    run_id = uuid.uuid4()
    async with sessions.begin() as session:
        # The previous process can no longer hold this lock. Its unfinished audit
        # represents an interrupted scan, including abrupt container termination.
        for previous in await session.scalars(select(ScanRun).where(ScanRun.status == "running")):
            previous.status, previous.finished_at = "interrupted", utc_now()
            previous.error = "Previous scanner stopped before recording completion"
        session.add(ScanRun(id=run_id, status="running", summary={"scope": "sample" if limit else "full", **(metadata or {})}))
    summary = {"scope": "sample" if limit else "full", **(metadata or {})}
    try:
        if api is None:
            async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=10),
                    limits=httpx.Limits(max_connections=5), follow_redirects=False,
                    headers={"User-Agent": "PokemonTeamBuilder/0.1 (catalog scanner)"}) as http:
                result = await scan_resources(PokeAPIClient(http), sessions, run_id, summary, limit, include_types)
        else:
            result = await scan_resources(api, sessions, run_id, summary, limit, include_types)
        await finish_run(sessions, run_id, result.status, result.summary)
        return result
    except asyncio.CancelledError:
        await finish_run(sessions, run_id, "interrupted", summary, "Scan cancelled during shutdown")
        raise
    except Exception as error:
        # Do not persist/log connection strings, credentials, or raw SQL errors.
        error_name = type(error).__name__
        try:
            await finish_run(sessions, run_id, "failed", summary, error_name)
        except Exception:
            # A later lock owner marks this run interrupted after connection loss.
            pass
        return ScanResult("failed", {**summary, "error": error_name})

async def scan_resources(api, sessions, run_id, summary, limit, include_types):
    errors = {}
    if include_types:
        try:
            rows = await fetch_chart(api)
            summary["types"] = await sync_chart(rows, sessions, scan_run_id=run_id)
        except (httpx.HTTPError, ValueError) as error:
            errors["types"] = type(error).__name__
    try:
        report = await ingest.ingest_catalog(api, sessions, limit=limit, scan_run_id=run_id)
        summary["pokemon"] = {**asdict(report), "failed": report.failed}
        if report.failed:
            errors["pokemon"] = f"{report.failed} records failed"
    except (httpx.HTTPError, ValueError) as error:
        errors["pokemon"] = type(error).__name__
    if errors:
        summary["errors"] = errors
        # Some resources may have committed successfully; callers must inspect counts.
        return ScanResult("partial" if "types" in summary or "pokemon" in summary else "failed", summary)
    return ScanResult("succeeded", summary)


async def schedule(scan, stop, *, interval_hours=CATALOG_SCAN_INTERVAL_HOURS):
    """Run immediately, then wait after completion; shutdown cancels active work."""
    while not stop.is_set():
        active = asyncio.create_task(scan())
        stopping = asyncio.create_task(stop.wait())
        try:
            await asyncio.wait([active, stopping], return_when=asyncio.FIRST_COMPLETED)
            if stop.is_set():
                active.cancel()
                await asyncio.gather(active, return_exceptions=True)
                return
            try:
                result = await active
                print(json.dumps({"status": result.status, **result.summary}), flush=True)
            except Exception as error:
                print(json.dumps({"status": "failed", "error": type(error).__name__}), flush=True)
        finally:
            stopping.cancel()
            if not active.done():
                active.cancel()
            await asyncio.gather(active, stopping, return_exceptions=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_hours * 3600)
        except asyncio.TimeoutError:
            pass


async def cli(scheduled):
    try:
        if scheduled:
            stop = asyncio.Event()
            loop = asyncio.get_running_loop()
            for name in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(name, stop.set)
            await schedule(lambda: run_scan(db.engine), stop)
            return 0
        result = await run_scan(db.engine)
        print(json.dumps({"status": result.status, **result.summary}, indent=2))
        return result.exit_code
    finally:
        await db.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Scan catalog and type relations, with observed-change history")
    parser.add_argument("--schedule", action="store_true", help="Run immediately and repeat after CATALOG_SCAN_INTERVAL_HOURS")
    args = parser.parse_args()
    try:
        return asyncio.run(cli(args.schedule))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
