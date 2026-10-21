import asyncio
from datetime import datetime, timedelta, timezone
import uuid

from app.db import session as db
from app.db.models import CatalogChange, ScanRun
from app.services.alerts import get_alerts

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def event(key="1", *, kind="pokemon", at=None, changes=None):
    return CatalogChange(entity_kind=kind, entity_key=key, entity_name="bulbasaur" if kind == "pokemon" else key,
        detected_at=at or datetime.now(timezone.utc),
        changes=changes or {"stats.attack": {"before": 49, "after": 60}})


def store(*rows):
    async def run():
        async with db.session_maker.begin() as session:
            session.add_all(rows)
    asyncio.run(run())


def save(client, ids, name="My team"):
    response = client.post("/api/teams", json={"name": name, "pokemon_ids": ids})
    assert response.status_code == 201
    return response.json()


def test_alerts_require_auth_and_are_never_cached(client):
    response = client.get("/api/alerts")
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"


def test_alerts_group_duplicate_slots_and_multiple_owned_teams(signed_in):
    first = save(signed_in, [1, 1])
    second = save(signed_in, [1], "Another")
    store(event(), event("7"))
    response = signed_in.get("/api/alerts")
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    page = response.json()
    assert page["total"] == 1 and page["window_days"] == 7
    alert = page["items"][0]
    assert alert["changes"]["stats.attack"] == {"before": 49, "after": 60}
    assert len(alert["affected"]) == 1
    assert alert["affected"][0]["types"] == ["grass", "poison"]
    teams = {team["id"]: team for team in alert["affected"][0]["teams"]}
    assert teams[first["id"]]["positions"] == [0, 1]
    assert teams[second["id"]]["positions"] == [0]
    assert signed_in.post("/api/auth/logout").status_code == 204
    assert signed_in.post("/api/auth/register", json={"username": "misty", "password": "long-test-password"}).status_code == 201
    assert signed_in.post("/api/auth/login", data={"username": "misty", "password": "long-test-password"}).status_code == 204
    assert signed_in.get("/api/alerts").json()["items"] == []


def test_alert_window_includes_cutoff_excludes_old_and_future_and_is_configurable(signed_in):
    save(signed_in, [1])
    store(event(at=NOW - timedelta(days=7)), event(at=NOW - timedelta(days=7, microseconds=1)),
          event(at=NOW + timedelta(microseconds=1)))
    user_id = uuid.UUID(signed_in.get("/api/auth/me").json()["id"])
    async def run():
        async with db.session_maker() as session:
            week = await get_alerts(session, user_id, now=NOW)
            fortnight = await get_alerts(session, user_id, now=NOW, window_days=14)
            assert week.total == 1 and fortnight.total == 2
            assert week.since == NOW - timedelta(days=7)
    asyncio.run(run())


def test_type_alerts_match_both_attack_and_defense_and_hide_unrelated_fields(signed_in):
    save(signed_in, [1, 25])
    store(event("fire", kind="type", changes={"damage_to.grass": {"before": 2, "after": 1},
          "damage_to.rock": {"before": 0.5, "after": 1}}),
          event("electric", kind="type", changes={"damage_to.water": {"before": 2, "after": 1}}),
          event("ice", kind="type", changes={"damage_to.rock": {"before": 1, "after": 2}}))
    page = signed_in.get("/api/alerts").json()
    assert page["total"] == 2
    by_name = {item["entity_name"]: item for item in page["items"]}
    fire = by_name["fire"]
    assert list(fire["changes"]) == ["damage_to.grass"]
    assert fire["affected"][0]["reasons"] == ["defending_type"]
    assert by_name["electric"]["affected"][0]["id"] == 25
    assert by_name["electric"]["affected"][0]["reasons"] == ["attacking_type"]


def test_current_saved_membership_controls_alerts_not_team_creation_time(signed_in):
    store(event())
    assert signed_in.get("/api/alerts").json()["total"] == 0
    team = save(signed_in, [1])
    assert signed_in.get("/api/alerts").json()["total"] == 1
    assert signed_in.put(f'/api/teams/{team["id"]}', json={"name": "Renamed", "pokemon_ids": [7]}).status_code == 200
    assert signed_in.get("/api/alerts").json()["total"] == 0
    assert signed_in.put(f'/api/teams/{team["id"]}', json={"name": "Renamed", "pokemon_ids": [1]}).status_code == 200
    assert signed_in.get("/api/alerts").json()["items"][0]["affected"][0]["teams"][0]["name"] == "Renamed"
    assert signed_in.delete(f'/api/teams/{team["id"]}').status_code == 204
    assert signed_in.get("/api/alerts").json()["total"] == 0


def test_alert_pagination_sorts_before_slicing_and_validates_bounds(signed_in):
    save(signed_in, [1])
    now = datetime.now(timezone.utc)
    store(*(event(at=now - timedelta(minutes=i)) for i in range(4)), event("7", at=now))
    first = signed_in.get("/api/alerts?limit=2").json()
    second = signed_in.get("/api/alerts?limit=2&offset=2").json()
    assert first["total"] == second["total"] == 4
    assert len({a["id"] for a in first["items"] + second["items"]}) == 4
    assert first["items"][0]["detected_at"] > second["items"][0]["detected_at"]
    assert signed_in.get("/api/alerts?offset=20").json()["items"] == []
    for query in ["limit=0", "limit=101", "offset=-1"]:
        assert signed_in.get(f"/api/alerts?{query}").status_code == 422


def test_latest_scan_reports_partial_status_without_exposing_errors(signed_in):
    assert signed_in.get("/api/alerts").json()["latest_scan"] is None
    store(ScanRun(status="partial", started_at=datetime.now(timezone.utc),
                  summary={"private": "do not expose"}, error="private diagnostic"))
    latest = signed_in.get("/api/alerts").json()["latest_scan"]
    assert latest["status"] == "partial"
    assert set(latest) == {"status", "started_at", "finished_at"}


def test_field_history_spans_pages_but_respects_window_and_entity(signed_in):
    save(signed_in, [1, 7])
    store(event(at=NOW - timedelta(days=1), changes={'stats.attack': {'before': 49, 'after': 60}}),
          event(at=NOW, changes={'stats.attack': {'before': 60, 'after': 70}}),
          event(at=NOW - timedelta(days=8)), event('7', at=NOW - timedelta(hours=1)))
    user_id = uuid.UUID(signed_in.get('/api/auth/me').json()['id'])
    async def run():
        async with db.session_maker() as session:
            page = await get_alerts(session, user_id, now=NOW, limit=1)
            assert page.total == 3 and len(page.items) == 1
            history = page.items[0].history['stats.attack']
            assert [(entry.before, entry.after) for entry in history] == [(60, 70), (49, 60)]
            assert history[0].detected_at > history[1].detected_at
    asyncio.run(run())
