import asyncio
import uuid
from alembic import command
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db import session as db
from app.db.models import User


def test_migrations_match_models_and_support_round_trip(database_case):
    config = database_case.config()
    command.upgrade(config, "head")
    command.check(config)  # No model/schema drift after applying migrations.
    command.downgrade(config, "0001_accounts")

    async def inspect_baseline():
        engine = database_case.engine()
        async with engine.connect() as connection:
            tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
            assert {"user", "accesstoken", "alembic_version"} == set(tables)
        await engine.dispose()
    asyncio.run(inspect_baseline())
    command.upgrade(config, "head")
    command.check(config)


def test_adopting_existing_account_schema_preserves_accounts(database_case):
    account_id = uuid.uuid4()

    async def create_old_schema():
        engine = database_case.engine()
        async with engine.begin() as connection:
            # Match the previous create_all account-only schema.
            await connection.run_sync(lambda sync: db.Base.metadata.create_all(
                sync, tables=[db.Base.metadata.tables["user"], db.Base.metadata.tables["accesstoken"]]))
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add(User(id=account_id, email="existing_user", hashed_password="existing-hash"))
            await session.commit()
        await engine.dispose()
    asyncio.run(create_old_schema())

    config = database_case.config()
    command.stamp(config, "0001_accounts")
    command.upgrade(config, "head")

    async def check_account():
        engine = database_case.engine()
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            user = await session.scalar(select(User).where(User.id == account_id))
            assert user.email == "existing_user"
            assert user.hashed_password == "existing-hash"
        await engine.dispose()
    asyncio.run(check_account())
    command.check(config)
