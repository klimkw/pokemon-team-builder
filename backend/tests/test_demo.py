import asyncio
import pytest
from app.db import session as db
from app.db.models import Pokemon
from app.jobs.demo import DEMO_PASSWORD, demo_step, validate_demo_target


@pytest.mark.parametrize("url,enabled", [
    ("postgresql+asyncpg://user:pass@db/pokemon", "true"),
    ("postgresql+asyncpg://user:pass@db/pokemon_test", "true"),
    ("postgresql+asyncpg://user:pass@db/pokemon_demo", None),
    ("sqlite+aiosqlite:///pokemon_demo", "true"),
])
def test_demo_cli_refuses_non_demo_targets(url, enabled):
    with pytest.raises(ValueError, match="Demo requires"):
        validate_demo_target(url, enabled)


def test_demo_cli_accepts_explicit_isolated_database():
    validate_demo_target("postgresql+asyncpg://user:pass@db/pokemon_demo", "true")


@pytest.mark.postgres
def test_deterministic_demo_runs_real_scanner_alerts_and_repeat(client):
    async def run():
        with pytest.raises(ValueError, match="baseline"):
            await demo_step(db.engine, "change")
        baseline = await demo_step(db.engine, "baseline")
        assert baseline["history_after"] == baseline["alert_count"] == 0
        with pytest.raises(ValueError, match="change step"):
            await demo_step(db.engine, "repeat")
        changed = await demo_step(db.engine, "change")
        assert changed["history_before"] == 0 and changed["history_after"] == 2
        assert changed["pokemon"]["updated"] == 1 and changed["types"]["updated"] == 1
        repeated = await demo_step(db.engine, "repeat")
        assert repeated["history_before"] == repeated["history_after"] == 2
        assert repeated["pokemon"]["updated"] == repeated["types"]["updated"] == 0
        with pytest.raises(ValueError, match="fresh demo"):
            await demo_step(db.engine, "baseline")
        async with db.session_maker() as session:
            assert (await session.get(Pokemon, 1)).stats["attack"] == 60
    asyncio.run(run())
    assert client.post("/api/auth/login", data={"username": "demo_trainer", "password": DEMO_PASSWORD}).status_code == 204
    page = client.get("/api/alerts").json()
    assert page["total"] == 2
    assert any(team["positions"] == [0, 1] for alert in page["items"] for pokemon in alert["affected"] for team in pokemon["teams"])
