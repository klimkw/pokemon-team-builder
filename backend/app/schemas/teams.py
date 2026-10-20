"""Public request/response contracts; ownership is never client supplied."""
import uuid
from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

PokemonType = Literal["normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground", "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy"]


class PokemonStats(BaseModel):
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int


class PokemonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    types: list[PokemonType]
    stats: PokemonStats
    sprite_url: str | None
    synced_at: datetime


class PokemonPage(BaseModel):
    stat_maxima: dict[str, int] = Field(default_factory=dict)
    items: list[PokemonRead]
    total: int
    limit: int
    offset: int


class TeamWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    pokemon_ids: list[Annotated[int, Field(strict=True, gt=0)]] = Field(max_length=6)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class TeamMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    position: int
    pokemon: PokemonRead


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    members: list[TeamMemberRead]
    created_at: datetime
    updated_at: datetime
