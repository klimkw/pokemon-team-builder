"""Bounded manual changes; accepted only by explicitly enabled admin controls."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.teams import PokemonType

Stat = Literal['hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed']


class PokemonPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pokemon_id: int = Field(strict=True, gt=0)
    stats: dict[Stat, Annotated[int, Field(strict=True, ge=0, le=999)]] = Field(default_factory=dict)
    types: list[PokemonType] | None = Field(default=None, min_length=1, max_length=2)

    @model_validator(mode='after')
    def valid_patch(self):
        if not self.stats and self.types is None:
            raise ValueError('Provide stats or types')
        if self.types and len(set(self.types)) != len(self.types):
            raise ValueError('Types must be distinct')
        return self


class TypePatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    attacking_type: PokemonType
    defending_type: PokemonType
    multiplier: Literal[0, 0.5, 1, 2]


class DemoChanges(BaseModel):
    model_config = ConfigDict(extra='forbid', json_schema_extra={'example': {
        'pokemon': [{'pokemon_id': 1, 'stats': {'attack': 60}}],
        'type_matchups': [{'attacking_type': 'fire', 'defending_type': 'grass', 'multiplier': 1}]}})
    pokemon: list[PokemonPatch] = Field(default_factory=list, max_length=6)
    type_matchups: list[TypePatch] = Field(default_factory=list, max_length=12)

    @model_validator(mode='after')
    def bounded_unique_changes(self):
        if not self.pokemon and not self.type_matchups:
            raise ValueError('Provide at least one change')
        ids = [p.pokemon_id for p in self.pokemon]
        pairs = [(p.attacking_type, p.defending_type) for p in self.type_matchups]
        if len(set(ids)) != len(ids) or len(set(pairs)) != len(pairs):
            raise ValueError('Duplicate Pokemon or type matchup patches')
        return self


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    action: str
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    result: dict
    error: str | None
