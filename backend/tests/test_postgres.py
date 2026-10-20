"""Checks SQLite cannot substitute for: JSONB storage and PostgreSQL row locks."""
import asyncio
import uuid
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from app.db import session as db
from app.db.models import Team

pytestmark = pytest.mark.postgres


def test_catalog_uses_real_jsonb(client, catalog):
    async def inspect():
        async with db.session_maker() as session:
            types = (await session.execute(text(
                "SELECT pg_typeof(types)::text, pg_typeof(stats)::text FROM pokemon LIMIT 1"))).one()
            assert tuple(types) == ("jsonb", "jsonb")
    asyncio.run(inspect())
    page = client.get("/api/pokemon?type=poison").json()
    assert [pokemon["id"] for pokemon in page["items"]] == [1]


def test_team_row_lock_blocks_another_writer_until_commit(signed_in):
    created = signed_in.post("/api/teams", json={"name": "Locked team", "pokemon_ids": [25]}).json()
    team_id = uuid.UUID(created["id"])
    async def check_lock():
        async with db.session_maker() as first, db.session_maker() as second:
            query = select(Team).where(Team.id == team_id)
            assert await first.scalar(query.with_for_update()) is not None
            with pytest.raises(DBAPIError) as failure:
                await second.scalar(query.with_for_update(nowait=True))
            assert failure.value.orig.sqlstate == "55P03"  # lock_not_available
            await second.rollback()
            await first.commit()
            assert await second.scalar(query.with_for_update(nowait=True)) is not None
    asyncio.run(check_lock())
