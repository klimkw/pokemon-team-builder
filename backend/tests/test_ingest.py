import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select, update
from app import db
from app.catalog_sync import sync_record
from app.ingest import ingest_catalog
from app.models import Pokemon
from app.pokeapi import CATALOG_URL, PokeAPIClient, normalize_pokemon

NAMES = {1: "bulbasaur", 7: "squirtle", 25: "pikachu"}


def detail(pokemon_id=25):
    return {
        "id": pokemon_id, "name": NAMES.get(pokemon_id, f"pokemon-{pokemon_id}"),
        "types": [{"slot": 1, "type": {"name": "electric"}}],
        "stats": [{"base_stat": value, "stat": {"name": name}}
                  for name, value in [("hp", 35), ("attack", 55), ("defense", 40),
                                      ("special-attack", 50), ("special-defense", 50), ("speed", 90)]],
        "sprites": {"front_default": None},
        "unused_upstream_field": "ignored",
    }


def page(ids, next=None, count=None):
    return {"count": len(ids) if count is None else count, "next": next,
            "results": [{"name": NAMES.get(id, f"pokemon-{id}"),
                         "url": f"https://pokeapi.co/api/v2/pokemon/{id}/"} for id in ids]}


def test_normalization_orders_types_and_maps_stats():
    payload = detail(1)
    payload["types"] = [{"slot": 2, "type": {"name": "poison"}},
                        {"slot": 1, "type": {"name": "grass"}}]
    record = normalize_pokemon(payload, 1)
    assert record.types == ["grass", "poison"]
    assert record.stats.special_attack == 50
    assert record.sprite_url is None
    payload["sprites"]["front_default"] = "https://example.org/1.png"
    assert normalize_pokemon(payload, 1).sprite_url == "https://example.org/1.png"


@pytest.mark.parametrize("change", ["missing_stat", "duplicate_stat", "negative_stat", "invalid_type",
                                   "duplicate_slot", "missing_slot", "wrong_id", "bad_sprite"])
def test_malformed_records_rejected(change):
    payload = detail()
    if change == "missing_stat": payload["stats"].pop()
    if change == "duplicate_stat": payload["stats"][-1] = payload["stats"][0]
    if change == "negative_stat": payload["stats"][0]["base_stat"] = -1
    if change == "invalid_type": payload["types"][0]["type"]["name"] = "unknown"
    if change == "duplicate_slot": payload["types"].append(deepcopy(payload["types"][0]))
    if change == "missing_slot": payload["types"][0]["slot"] = 2
    if change == "wrong_id": payload["id"] = 7
    if change == "bad_sprite": payload["sprites"]["front_default"] = "javascript:alert(1)"
    with pytest.raises(ValueError): normalize_pokemon(payload, 25)


def test_pagination_import_and_repeat_are_idempotent(client):
    next_url = "https://pokeapi.co/api/v2/pokemon/?offset=2&limit=2"
    calls = []
    def handle(request):
        calls.append(str(request.url))
        if request.url.path.rstrip("/") == "/api/v2/pokemon":
            return httpx.Response(200, json=page([25], count=3) if request.url.params.get("offset")
                                  else page([1, 7], next=next_url, count=3))
        return httpx.Response(200, json=detail(int(request.url.path.strip("/").split("/")[-1])))
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            api = PokeAPIClient(http)
            first = await ingest_catalog(api, db.session_maker)
            assert first.inserted == 3 and first.exit_code == 0
            async with db.session_maker() as session:
                await session.execute(update(Pokemon).values(synced_at=datetime.now(timezone.utc)-timedelta(days=1)))
                await session.commit()
            second = await ingest_catalog(api, db.session_maker)
            assert second.unchanged == 3 and second.inserted == second.updated == 0
            async with db.session_maker() as session:
                records = list(await session.scalars(select(Pokemon)))
                assert len(records) == 3
                assert all(p.synced_at > datetime.now(timezone.utc)-timedelta(minutes=1) for p in records)
    asyncio.run(run())
    assert calls.count(next_url) == 2
    assert client.get("/api/pokemon").json()["total"] == 3


def test_changed_catalog_updates_in_place_without_altering_team(signed_in):
    team = signed_in.post("/api/teams", json={"name": "Partners", "pokemon_ids": [25, 25]}).json()
    async def run():
        payload = detail()
        payload["name"] = "pikachu-renamed"
        payload["stats"][1]["base_stat"] = 60
        assert await sync_record(normalize_pokemon(payload, 25), db.session_maker) == "updated"
    asyncio.run(run())
    result = signed_in.get(f"/api/teams/{team['id']}").json()
    assert [m["position"] for m in result["members"]] == [0, 1]
    assert all(m["pokemon"]["id"] == 25 for m in result["members"])
    assert result["members"][0]["pokemon"]["name"] == "pikachu-renamed"
    assert result["members"][0]["pokemon"]["stats"]["attack"] == 60


def test_partial_failures_preserve_successes_and_existing_records(client):
    attempts = []
    def handle(request):
        attempts.append(request.url.path)
        if request.url.path.rstrip("/") == "/api/v2/pokemon":
            return httpx.Response(200, json=page([1, 7, 25]))
        id = int(request.url.path.strip("/").split("/")[-1])
        if id == 7: return httpx.Response(404)
        payload = detail(id)
        if id == 25: payload["stats"].pop()
        return httpx.Response(200, json=payload)
    async def run():
        await sync_record(normalize_pokemon(detail(25), 25), db.session_maker)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            report = await ingest_catalog(PokeAPIClient(http), db.session_maker)
        assert report.inserted == 1 and report.failed == 2 and report.exit_code == 1
        assert set(report.failures) == {7, 25}
        async with db.session_maker() as session:
            assert set(await session.scalars(select(Pokemon.id))) == {1, 25}
    asyncio.run(run())
    assert attempts.count("/api/v2/pokemon/7/") == 1


def test_transient_errors_retry_and_respect_retry_after():
    delays = []
    count = 0
    async def sleep(delay): delays.append(delay)
    def handle(request):
        nonlocal count
        count += 1
        if count == 1: raise httpx.ConnectError("temporary", request=request)
        if count == 2: return httpx.Response(429, headers={"Retry-After": "3"})
        return httpx.Response(200, json=detail())
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            record = await PokeAPIClient(http, sleep=sleep).fetch_pokemon(25, "https://pokeapi.co/api/v2/pokemon/25/")
            assert record.id == 25
    asyncio.run(run())
    assert delays == [1, 3] and count == 3


def test_retries_exhaust_and_long_retry_after_does_not_wait():
    async def run():
        delays = []
        async def sleep(delay): delays.append(delay)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503))) as http:
            with pytest.raises(httpx.HTTPStatusError):
                await PokeAPIClient(http, sleep=sleep).get_json(CATALOG_URL)
        assert delays == [1, 2]
        response = httpx.Response(429, headers={"Retry-After": "120"})
        with pytest.raises(ValueError): PokeAPIClient.retry_delay(response, 0)
    asyncio.run(run())


@pytest.mark.parametrize("bad_next", [CATALOG_URL, "https://other.example/api/v2/pokemon/", "https://pokeapi.co/api/v2/ability/"])
def test_bad_discovery_aborts_before_writing(client, bad_next):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=page([25], next=bad_next)))) as http:
            with pytest.raises(ValueError): await ingest_catalog(PokeAPIClient(http), db.session_maker)
        async with db.session_maker() as session:
            assert list(await session.scalars(select(Pokemon.id))) == []
    asyncio.run(run())


def test_missing_ids_are_reported_but_not_deleted_and_sample_is_explicit(client):
    async def run():
        await sync_record(normalize_pokemon(detail(25), 25), db.session_maker)
        def handle(request):
            if request.url.path.rstrip("/") == "/api/v2/pokemon":
                return httpx.Response(200, json=page([1, 7]))
            return httpx.Response(200, json=detail(int(request.url.path.strip("/").split("/")[-1])))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            full = await ingest_catalog(PokeAPIClient(http), db.session_maker)
            assert full.absent_ids == [25]
            sample = await ingest_catalog(PokeAPIClient(http), db.session_maker, limit=1)
            assert sample.scope == "sample" and sample.selected == 1 and sample.discovered == 2
            assert sample.absent_ids == []
        async with db.session_maker() as session:
            assert await session.get(Pokemon, 25) is not None
    asyncio.run(run())


def test_detail_concurrency_is_bounded(client):
    active = maximum = 0
    async def handle(request):
        nonlocal active, maximum
        if request.url.path.rstrip("/") == "/api/v2/pokemon":
            return httpx.Response(200, json=page(list(range(1, 11))))
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.005)
        active -= 1
        return httpx.Response(200, json=detail(int(request.url.path.strip("/").split("/")[-1])))
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            report = await ingest_catalog(PokeAPIClient(http), db.session_maker, concurrency=3)
            assert report.inserted == 10 and report.failed == 0
    asyncio.run(run())
    assert maximum == 3


def test_database_failure_is_isolated_to_one_record(client):
    async def run():
        # A source name collision violates the unique-name constraint. The failed
        # transaction must roll back without preventing another record's save.
        await sync_record(normalize_pokemon(detail(25), 25), db.session_maker)
        def handle(request):
            if request.url.path.rstrip("/") == "/api/v2/pokemon":
                return httpx.Response(200, json=page([1, 7]))
            id = int(request.url.path.strip("/").split("/")[-1])
            payload = detail(id)
            if id == 1: payload["name"] = "pikachu"
            return httpx.Response(200, json=payload)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            report = await ingest_catalog(PokeAPIClient(http), db.session_maker)
        assert report.failed == 1 and 1 in report.failures
        assert report.inserted == 1 and report.exit_code == 1
        async with db.session_maker() as session:
            assert set(await session.scalars(select(Pokemon.id))) == {7, 25}
    asyncio.run(run())


def test_incomplete_catalog_count_aborts_without_writes(client):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=page([25], count=2)))) as http:
            with pytest.raises(ValueError, match="reported count"):
                await ingest_catalog(PokeAPIClient(http), db.session_maker)
        async with db.session_maker() as session:
            assert list(await session.scalars(select(Pokemon.id))) == []
    asyncio.run(run())


def test_cli_propagates_partial_failure_exit_code(client, monkeypatch, capsys):
    from app import ingest
    from app import scanner
    async def partial(*args, **kwargs):
        return scanner.ScanResult("partial", {"pokemon": {"failed": 1}})
    monkeypatch.setattr(scanner, "run_scan", partial)
    assert asyncio.run(ingest.run_cli(None)) == 1
    import json
    assert json.loads(capsys.readouterr().out)["failed"] == 1
