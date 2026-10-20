"""Database synchronization, reusable by ingestion and the future change scanner."""
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from .models import Pokemon, utc_now
from .pokeapi import CatalogRecord

SyncOutcome = Literal["inserted", "updated", "unchanged"]


async def sync_record(record: CatalogRecord, sessions: async_sessionmaker[AsyncSession]) -> SyncOutcome:
    # No network requests occur inside this short per-record transaction.
    async with sessions.begin() as session:
        existing = await session.get(Pokemon, record.id)
        values = record.model_dump(exclude={"id"})
        if existing is None:
            session.add(Pokemon(id=record.id, **values, synced_at=utc_now()))
            return "inserted"
        changed = any(getattr(existing, field) != value for field, value in values.items())
        if changed:
            for field, value in values.items():
                setattr(existing, field, value)
            # The future change-log insert must be added here, within this transaction.
        existing.synced_at = utc_now()
        return "updated" if changed else "unchanged"
