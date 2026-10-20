"""One SQLAlchemy session per request; callers commit successful writes explicitly."""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from .settings import DATABASE_URL


class Base(DeclarativeBase):
    pass


def make_engine(url: str, **options):
    engine = create_async_engine(url, pool_pre_ping=True, **options)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine.sync_engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine


engine = make_engine(DATABASE_URL)
session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def database():
    async with session_maker() as session:
        yield session
