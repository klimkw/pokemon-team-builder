"""Async Alembic runner. A supplied connection is used by schema checks in tests."""
import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from app.db.session import Base
from app.db import models  # Register every mapped table in Base.metadata.
from app.settings import DATABASE_URL

config = context.config
target_metadata = Base.metadata
url = config.attributes.get("database_url", DATABASE_URL)


def migrate(connection):
    context.configure(connection=connection, target_metadata=target_metadata,
                      compare_type=True, render_as_batch=connection.dialect.name == "sqlite")
    with context.begin_transaction():
        context.run_migrations()


async def online():
    engine = create_async_engine(url, poolclass=NullPool,
                                 connect_args=config.attributes.get("connect_args", {}))
    async with engine.connect() as connection:
        await connection.run_sync(migrate)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    migrate(config.attributes["connection"])
else:
    asyncio.run(online())
