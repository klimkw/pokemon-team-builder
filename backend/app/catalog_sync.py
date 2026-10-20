"""Database synchronization, reusable by ingestion and the future change scanner."""
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from .models import CatalogChange, Pokemon, utc_now
from .pokeapi import CatalogRecord

SyncOutcome = Literal["inserted", "updated", "unchanged"]


async def sync_record(record: CatalogRecord, sessions: async_sessionmaker[AsyncSession], *, scan_run_id=None) -> SyncOutcome:
    # No network requests occur inside this short per-record transaction.
    async with sessions.begin() as session:
        existing = await session.get(Pokemon, record.id)
        values = record.model_dump(exclude={"id"})
        if existing is None:
            session.add(Pokemon(id=record.id, **values, synced_at=utc_now()))
            return "inserted"
        changes = {}
        for field, value in values.items():
            before = getattr(existing, field)
            if field == "stats":
                for stat, after in value.items():
                    if before[stat] != after:
                        changes[f"stats.{stat}"] = {"before": before[stat], "after": after}
            elif before != value:
                changes[field] = {"before": before, "after": value}
        changed = bool(changes)
        if changed:
            for field, value in values.items():
                setattr(existing, field, value)
            session.add(CatalogChange(scan_run_id=scan_run_id, entity_kind="pokemon",
                entity_key=str(record.id), entity_name=record.name, changes=changes, detected_at=utc_now()))
        existing.synced_at = utc_now()
        return "updated" if changed else "unchanged"
