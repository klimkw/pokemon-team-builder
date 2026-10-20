"""Deterministic browser-test fixtures, exclusively for the disposable test DB."""
import asyncio
import os
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models import Pokemon, utc_now


async def main():
    url = make_url(os.environ["TEST_DATABASE_URL"])
    if url.drivername != "postgresql+asyncpg" or url.database != "pokemon_test":
        raise RuntimeError("Catalog fixtures require the disposable PostgreSQL pokemon_test database")
    engine = create_async_engine(url)
    names = "bulbasaur ivysaur venusaur charmander charmeleon charizard squirtle wartortle blastoise caterpie metapod butterfree weedle kakuna beedrill pidgey pidgeotto pidgeot rattata raticate spearow fearow ekans arbok pikachu".split()
    types = ["grass"] * 3 + ["fire"] * 3 + ["water"] * 3 + ["bug"] * 6 + ["flying"] * 3 + ["normal"] * 2 + ["flying"] * 2 + ["poison"] * 2 + ["electric"]
    try:
        async with async_sessionmaker(engine)() as session:
            for identifier, (name, type_name) in enumerate(zip(names, types), start=1):
                # Intentionally synthetic stats; no live upstream request is required.
                if await session.get(Pokemon, identifier) is None:
                    session.add(Pokemon(id=identifier, name=name, types=[type_name],
                        stats=dict(hp=45, attack=49, defense=49, special_attack=65, special_defense=65, speed=45),
                        sprite_url=None, synced_at=utc_now()))
            await session.commit()
    finally:
        await engine.dispose()


asyncio.run(main())
