"""Deterministic, offline scanner demonstration. CLI accepts only pokemon_demo."""
import argparse
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import uuid

import httpx
from fastapi_users.password import PasswordHelper
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db import session as db
from app.db.models import CatalogChange, Team, TeamMember, User
from app.jobs.scanner import run_scan
from app.services.alerts import get_alerts
from app.services.counters import type_chart
from app.services.pokeapi import PokeAPIClient

DEMO_USER = uuid.UUID("00000000-0000-4000-8000-000000000001")
DEMO_TEAM = uuid.UUID("00000000-0000-4000-8000-000000000002")
DEMO_PASSWORD = "Demo-only-password-2026"


def validate_demo_target(url, enabled):
    parsed = make_url(url)
    if enabled != "true" or parsed.drivername != "postgresql+asyncpg" or parsed.database != "pokemon_demo":
        raise ValueError("Demo requires DEMO_MODE=true and a postgresql+asyncpg database named pokemon_demo")


def fixture_transport(changed):
    records = json.loads((Path(__file__).parents[1] / "data" / "demo_pokemon.json").read_text())
    rows = deepcopy(type_chart()["damage_to"])
    if changed:
        records[0]["stats"][1]["base_stat"] = 60
        rows["fire"]["grass"] = 1

    def respond(request):
        path = request.url.path.rstrip("/")
        if path == "/api/v2/pokemon":
            payload = {"count": len(records), "next": None, "results": [
                {"name": record["name"], "url": f'https://pokeapi.co/api/v2/pokemon/{record["id"]}/'}
                for record in records]}
        elif path.startswith("/api/v2/pokemon/"):
            payload = next((record for record in records if str(record["id"]) == path.split("/")[-1]), None)
        elif path.startswith("/api/v2/type/") and path.split("/")[-1] in rows:
            name = path.split("/")[-1]
            payload = {"name": name, "damage_relations": {
                field: [{"name": target} for target, value in rows[name].items() if value == multiplier]
                for field, multiplier in [("no_damage_to", 0), ("half_damage_to", 0.5), ("double_damage_to", 2)]}}
        else:
            payload = None
        if request.url.host != "pokeapi.co" or payload is None:
            raise ValueError("Demo requested a resource outside its local fixtures")
        return httpx.Response(200, json=payload)
    return httpx.MockTransport(respond)


async def history_count(sessions):
    async with sessions() as session:
        return await session.scalar(select(func.count()).select_from(CatalogChange))


async def demo_step(engine, step):
    """Shared scenario; tests supply their isolated PostgreSQL schema engine."""
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    before = await history_count(sessions)
    async with sessions() as session:
        seeded = await session.get(Team, DEMO_TEAM) is not None
    if step == "baseline" and before:
        raise ValueError("Baseline requires a fresh demo database. Stop the demo stack and start it again.")
    if step != "baseline" and not seeded:
        raise ValueError("Run the baseline step before applying or repeating changes")
    if step == "repeat" and before != 2:
        raise ValueError("Run the change step before the repeat step")
    async with httpx.AsyncClient(transport=fixture_transport(step != "baseline")) as http:
        result = await run_scan(engine, api=PokeAPIClient(http))
    if result.status != "succeeded":
        raise RuntimeError(f"Demo scanner did not succeed: {result.status}")
    if step == "baseline":
        async with sessions.begin() as session:
            if await session.get(User, DEMO_USER) is None:
                session.add(User(id=DEMO_USER, email="demo_trainer", hashed_password=PasswordHelper().hash(DEMO_PASSWORD),
                                 is_active=True, is_superuser=False, is_verified=False))
                await session.flush()
            if await session.get(Team, DEMO_TEAM) is None:
                session.add(Team(id=DEMO_TEAM, user_id=DEMO_USER, name="Demo lineup"))
                await session.flush()
                session.add_all([TeamMember(team_id=DEMO_TEAM, position=position, pokemon_id=identifier)
                                 for position, identifier in enumerate([1, 1, 4])])
    after = await history_count(sessions)
    async with sessions() as session:
        alerts = await get_alerts(session, DEMO_USER)
    expected = 0 if step == "baseline" else 2
    if after != expected or alerts.total != expected or (step == "repeat" and before != after):
        raise RuntimeError("Demo history/alert assertions failed")
    return {"step": step, "scan_status": result.status, "history_before": before,
            "history_after": after, "alert_count": alerts.total,
            "pokemon": result.summary["pokemon"], "types": result.summary["types"]}


async def run(step):
    try:
        for stage in (["baseline", "change", "repeat"] if step == "all" else [step]):
            print(json.dumps(await demo_step(db.engine, stage)), flush=True)
    finally:
        await db.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=["baseline", "change", "repeat", "all"], nargs="?", default="all")
    args = parser.parse_args()
    try:
        validate_demo_target(os.environ.get("DATABASE_URL", ""), os.environ.get("DEMO_MODE"))
        asyncio.run(run(args.step))
    except (ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
