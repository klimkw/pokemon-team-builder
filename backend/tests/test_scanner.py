import asyncio
from copy import deepcopy
import uuid

import httpx
import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from app.db import session as db
from app.services.catalog_sync import sync_record
from app.services.counters import type_chart
from app.db.models import CatalogChange, Pokemon, ScanRun, TypeChart
from app.services.pokeapi import CatalogRecord
from app.jobs.scanner import LockedSessions, LostScanLock, ScanResult, run_scan, scan_lock, schedule
from app.services.type_sync import TYPES, chart_version, normalize_type, sync_chart


def record(identifier=1, **changes):
    values = dict(id=identifier, name=f"pokemon-{identifier}", types=["grass"], sprite_url=None,
                  stats=dict(hp=45, attack=49, defense=49, special_attack=65, special_defense=65, speed=45))
    values.update(changes)
    return CatalogRecord(**values)


class FakeAPI:
    def __init__(self, records=None):
        self.records = records if records is not None else [record()]
        self.rows = deepcopy(type_chart()["damage_to"])
        self.failed_ids = set()
        self.bad_type = None
        self.discovery_error = False
        self.calls = 0

    async def discover(self):
        self.calls += 1
        if self.discovery_error:
            raise ValueError("Incomplete upstream discovery")
        return {r.id: f"https://pokeapi.co/api/v2/pokemon/{r.id}/" for r in self.records}

    async def fetch_pokemon(self, identifier, url):
        if identifier in self.failed_ids:
            raise httpx.ConnectError("Upstream unavailable")
        return next(r for r in self.records if r.id == identifier)

    async def get_json(self, url):
        self.calls += 1
        name = url.rstrip("/").split("/")[-1]
        if name == self.bad_type:
            raise ValueError("Incomplete type record")
        row = self.rows[name]
        return {"name": name, "damage_relations": {
            field: [{"name": target} for target, value in row.items() if value == multiplier]
            for field, multiplier in [("no_damage_to", 0), ("half_damage_to", 0.5), ("double_damage_to", 2)]}}


async def changes():
    async with db.session_maker() as session:
        return list(await session.scalars(select(CatalogChange).order_by(CatalogChange.detected_at)))


def test_pokemon_history_tracks_used_fields_and_repeat_is_idempotent(client):
    async def run():
        initial = record()
        assert await sync_record(initial, db.session_maker) == "inserted"
        assert await changes() == []
        stats = initial.stats.model_dump()
        stats["attack"] = 52
        updated = record(name="new-name", types=["water"], sprite_url="https://example.org/1.png", stats=stats)
        assert await sync_record(updated, db.session_maker) == "updated"
        assert await sync_record(updated, db.session_maker) == "unchanged"
        history = await changes()
        assert len(history) == 1
        assert history[0].entity_key == "1"
        assert history[0].changes == {
            "name": {"before": "pokemon-1", "after": "new-name"},
            "types": {"before": ["grass"], "after": ["water"]},
            "sprite_url": {"before": None, "after": "https://example.org/1.png"},
            "stats.attack": {"before": 49, "after": 52}}
        assert history[0].detected_at is not None
    asyncio.run(run())


def test_failed_history_insert_rolls_back_pokemon_and_type_chart(client):
    async def run():
        await sync_record(record(), db.session_maker)
        def fail(connection, cursor, statement, parameters, context, executemany):
            if statement.startswith("INSERT INTO catalog_changes"):
                raise IntegrityError(statement, parameters, Exception("Injected history failure"))
        event.listen(db.engine.sync_engine, "before_cursor_execute", fail)
        try:
            with pytest.raises(IntegrityError):
                await sync_record(record(name="must-not-stick"), db.session_maker)
            rows = deepcopy(type_chart()["damage_to"])
            rows["water"]["fire"] = 1
            with pytest.raises(IntegrityError):
                await sync_chart(rows, db.session_maker)
        finally:
            event.remove(db.engine.sync_engine, "before_cursor_execute", fail)
        async with db.session_maker() as session:
            assert (await session.get(Pokemon, 1)).name == "pokemon-1"
            assert (await session.get(TypeChart, 1)).damage_to["water"]["fire"] == 2
            assert await session.scalar(select(func.count()).select_from(CatalogChange)) == 0
    asyncio.run(run())


def test_type_history_and_counter_api_use_refreshed_chart(signed_in):
    async def run():
        rows = deepcopy(type_chart()["damage_to"])
        rows["water"]["electric"] = 0
        first = await sync_chart(rows, db.session_maker)
        second = await sync_chart(rows, db.session_maker)
        assert first["updated"] == 1 and second["updated"] == 0
        history = await changes()
        assert len(history) == 1
        assert history[0].entity_kind == "type"
        assert history[0].changes == {"damage_to.electric": {"before": 1, "after": 0}}
        return chart_version(rows)
    version = asyncio.run(run())
    response = signed_in.post("/api/teams/counter-preview", json={"pokemon_ids": [25]})
    assert response.status_code == 200
    assert response.json()["chart_version"] == version


@pytest.mark.parametrize("relations", [None, {}, {"no_damage_to": [], "half_damage_to": [], "double_damage_to": [{"name": "bogus"} ]},
    {"no_damage_to": [{"name": "fire"}], "half_damage_to": [], "double_damage_to": [{"name": "fire"}]}])
def test_type_normalization_rejects_incomplete_or_conflicting_rows(relations):
    with pytest.raises(ValueError):
        normalize_type({"name": "water", "damage_relations": relations}, "water")


@pytest.mark.postgres
def test_full_scan_baseline_change_repeat_and_run_audit(client):
    async def run():
        api = FakeAPI()
        first = await run_scan(db.engine, api=api)
        assert first.status == "succeeded" and first.summary["pokemon"]["inserted"] == 1
        assert await changes() == []
        api.records = [record(name="changed")]
        api.rows["water"]["fire"] = 1
        assert (await run_scan(db.engine, api=api)).status == "succeeded"
        repeat = await run_scan(db.engine, api=api)
        assert repeat.summary["pokemon"]["unchanged"] == 1
        history = await changes()
        assert len(history) == 2 and all(change.scan_run_id for change in history)
        async with db.session_maker() as session:
            runs = list(await session.scalars(select(ScanRun)))
            assert len(runs) == 3 and all(run.status == "succeeded" and run.finished_at for run in runs)
    asyncio.run(run())


@pytest.mark.postgres
def test_partial_failures_preserve_old_records_and_whole_chart(client):
    async def run():
        api = FakeAPI([record(), record(2)])
        await run_scan(db.engine, api=api)
        api.records = [record(name="unavailable"), record(2, name="changed")]
        api.failed_ids = {1}
        api.bad_type = "fairy"  # Last type fails after earlier rows were fetched.
        api.rows["water"]["fire"] = 1
        result = await run_scan(db.engine, api=api)
        assert result.status == "partial"
        assert result.summary["pokemon"]["failed"] == 1
        async with db.session_maker() as session:
            assert (await session.get(Pokemon, 1)).name == "pokemon-1"
            assert (await session.get(Pokemon, 2)).name == "changed"
            assert (await session.get(TypeChart, 1)).damage_to == type_chart()["damage_to"]
        assert len(await changes()) == 1
    asyncio.run(run())


@pytest.mark.postgres
def test_real_advisory_lock_skips_overlap_and_releases(client):
    async def run():
        api = FakeAPI()
        async with scan_lock(db.engine) as held:
            assert held is not None
            skipped = await run_scan(db.engine, api=api)
            assert skipped.status == "skipped" and api.calls == 0
        assert (await run_scan(db.engine, api=api)).status == "succeeded"
        async with db.session_maker() as session:
            statuses = list(await session.scalars(select(ScanRun.status)))
            assert sorted(statuses) == ["skipped", "succeeded"]
    asyncio.run(run())


@pytest.mark.postgres
def test_cancellation_marks_interrupted_and_releases_lock(client):
    async def run():
        started = asyncio.Event()
        class WaitingAPI(FakeAPI):
            async def discover(self):
                started.set()
                await asyncio.Event().wait()
        active = asyncio.create_task(run_scan(db.engine, api=WaitingAPI(), include_types=False))
        await started.wait()
        active.cancel()
        with pytest.raises(asyncio.CancelledError):
            await active
        async with scan_lock(db.engine) as acquired:
            assert acquired is not None
        async with db.session_maker() as session:
            assert (await session.scalar(select(ScanRun))).status == "interrupted"
    asyncio.run(run())


@pytest.mark.postgres
def test_stale_running_scan_recovered_after_process_crash(client):
    async def run():
        stale_id = uuid.uuid4()
        async with db.session_maker.begin() as session:
            session.add(ScanRun(id=stale_id, status="running", summary={}))
        await run_scan(db.engine, api=FakeAPI())
        async with db.session_maker() as session:
            stale = await session.get(ScanRun, stale_id)
            assert stale.status == "interrupted" and stale.finished_at is not None
    asyncio.run(run())


@pytest.mark.postgres
def test_invalidated_lock_connection_cannot_silently_reconnect(client):
    async def run():
        async with scan_lock(db.engine) as sessions:
            await sessions.connection.invalidate()
            with pytest.raises(LostScanLock):
                sessions.begin()
        async with scan_lock(db.engine) as sessions:
            assert sessions is not None
    asyncio.run(run())


def test_scheduler_runs_immediately_waits_and_stops():
    async def run():
        stop = asyncio.Event()
        calls = 0
        async def scan():
            nonlocal calls
            calls += 1
            if calls == 2:
                stop.set()
            return ScanResult("succeeded", {})
        await schedule(scan, stop, interval_hours=0.000001)
        assert calls == 2
    asyncio.run(run())


def test_scheduler_shutdown_cancels_active_scan():
    async def run():
        stop, started = asyncio.Event(), asyncio.Event()
        cancelled = False
        async def scan():
            nonlocal cancelled
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled = True
        task = asyncio.create_task(schedule(scan, stop))
        await started.wait()
        stop.set()
        await task
        assert cancelled
    asyncio.run(run())


@pytest.mark.postgres
def test_failed_discovery_and_chart_leave_data_untouched_and_audit_failure(client):
    async def run():
        await sync_record(record(), db.session_maker)
        api = FakeAPI()
        api.discovery_error, api.bad_type = True, "normal"
        result = await run_scan(db.engine, api=api)
        assert result.status == "failed"
        async with db.session_maker() as session:
            assert (await session.get(Pokemon, 1)).name == "pokemon-1"
            assert (await session.get(TypeChart, 1)).version == type_chart()["version"]
            audit = await session.scalar(select(ScanRun))
            assert audit.status == "failed" and audit.finished_at
            assert set(audit.summary["errors"]) == {"types", "pokemon"}
        assert await changes() == []
    asyncio.run(run())
