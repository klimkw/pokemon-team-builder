"""SQLite by default; --postgres opts into isolated schemas in pokemon_test."""
import asyncio
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema
from app import db, main


def pytest_addoption(parser):
    parser.addoption("--postgres", action="store_true", help="Run against TEST_DATABASE_URL (must name pokemon_test)")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--postgres"):
        for item in items:
            if "postgres" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Requires --postgres and TEST_DATABASE_URL"))


def validated_postgres_url(value):
    if not value:
        raise pytest.UsageError("--postgres requires TEST_DATABASE_URL; DATABASE_URL is never used for test cleanup")
    url = make_url(value)
    if url.drivername != "postgresql+asyncpg" or url.database != "pokemon_test":
        raise pytest.UsageError("TEST_DATABASE_URL must use postgresql+asyncpg and database pokemon_test")
    return value


def migration_config(url, connect_args=None):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = url
    config.attributes["connect_args"] = connect_args or {}
    return config


@dataclass
class DatabaseCase:
    url: str
    connect_args: dict = field(default_factory=dict)

    def engine(self):
        # Tests use both TestClient's event loop and asyncio.run helper loops.
        # Never reuse an asyncpg pooled connection across those event loops.
        return db.make_engine(self.url, connect_args=self.connect_args, poolclass=NullPool)

    def config(self):
        return migration_config(self.url, self.connect_args)


@pytest.fixture
def database_case(tmp_path, request):
    if not request.config.getoption("--postgres"):
        yield DatabaseCase(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
        return
    url = validated_postgres_url(os.environ.get("TEST_DATABASE_URL"))
    schema = f"test_{uuid.uuid4().hex}"
    async def manage_schema(create):
        # Cleanup is limited to the exact random schema this fixture created.
        assert re.fullmatch(r"test_[0-9a-f]{32}", schema)
        engine = db.make_engine(url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                await connection.execute(CreateSchema(schema) if create else DropSchema(schema, cascade=True))
        finally:
            await engine.dispose()
    asyncio.run(manage_schema(True))
    try:
        yield DatabaseCase(url, {"server_settings": {"search_path": schema}})
    finally:
        asyncio.run(manage_schema(False))


@pytest.fixture
def client(database_case, monkeypatch):
    command.upgrade(database_case.config(), "head")
    engine = database_case.engine()
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "session_maker", async_sessionmaker(engine, expire_on_commit=False))
    with TestClient(main.app) as browser:
        yield browser


@pytest.fixture
def catalog(client):
    from app.models import Pokemon
    async def seed():
        async with db.session_maker() as session:
            for id, name, types in [(1, "bulbasaur", ["grass", "poison"]),
                                    (7, "squirtle", ["water"]), (25, "pikachu", ["electric"])]:
                session.add(Pokemon(id=id, name=name, types=types, sprite_url=None,
                    stats={"hp": 35, "attack": 55, "defense": 40, "special_attack": 50,
                           "special_defense": 50, "speed": 90}))
            await session.commit()
    asyncio.run(seed())


@pytest.fixture
def signed_in(client, catalog):
    assert client.post("/api/auth/register", json={"username": "ash", "password": "long-test-password"}).status_code == 201
    assert client.post("/api/auth/login", data={"username": "ash", "password": "long-test-password"}).status_code == 204
    return client
