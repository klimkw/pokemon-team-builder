"""Read-only alerts derived from history and current saved-team membership."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel
from app.schemas.teams import PokemonType


class FieldChange(BaseModel):
    before: Any
    after: Any


class AffectedTeam(BaseModel):
    id: UUID
    name: str
    positions: list[int]


class AffectedPokemon(BaseModel):
    types: list[PokemonType]
    id: int
    name: str
    reasons: list[Literal["catalog", "attacking_type", "defending_type"]]
    teams: list[AffectedTeam]


class ChangeAlert(BaseModel):
    is_read: bool = False
    is_manual_demo: bool = False
    id: UUID
    entity_kind: Literal["pokemon", "type"]
    entity_name: str
    detected_at: datetime
    changes: dict[str, FieldChange]
    affected: list[AffectedPokemon]


class ScanStatus(BaseModel):
    model_config = {"from_attributes": True}
    status: str
    started_at: datetime
    finished_at: datetime | None


class AlertPage(BaseModel):
    unread_total: int = 0
    is_demo: bool = False
    items: list[ChangeAlert]
    total: int
    limit: int
    offset: int
    window_days: int
    since: datetime
    as_of: datetime
    latest_scan: ScanStatus | None
