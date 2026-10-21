"""Independent daily catalog job using persisted scan history and the shared lock."""
import asyncio
import json
import signal

from app.db import session as db
from app.jobs.scanner import run_locked_scan, scan_lock
from app.jobs.worker import scan_delay
from app.services.scans import is_live_refresh
from app.settings import CATALOG_SCAN_INTERVAL_HOURS


async def tick(engine):
    # Check the due time under the writer lock so concurrent schedulers cannot
    # both decide to scan. Manual refreshes also advance the persisted due time.
    async with scan_lock(engine) as sessions:
        if sessions is None:
            return 60
        delay = await scan_delay(sessions)
        if delay > 0:
            return delay
        result = await run_locked_scan(sessions)
        print(json.dumps({"status": result.status, **result.summary}), flush=True)
        if result.status in ("succeeded", "partial") and is_live_refresh(result.summary):
            return CATALOG_SCAN_INTERVAL_HOURS * 3600
        return 60


async def run(engine):
    while True:
        try:
            delay = await tick(engine)
        except Exception as error:
            # Never log raw database errors or credentials.
            print(json.dumps({"status": "failed", "error": type(error).__name__}), flush=True)
            delay = 60
        await asyncio.sleep(delay)


async def cli():
    task = asyncio.create_task(run(db.engine))
    loop = asyncio.get_running_loop()
    for name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(name, task.cancel)
    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        await db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(cli())
