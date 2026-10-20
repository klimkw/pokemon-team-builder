"""Preview contracts: generation does not create or modify a saved team."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.teams import PokemonRead, PokemonType


class CounterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pokemon_ids: list[Annotated[int, Field(strict=True, gt=0)]] = Field(min_length=1, max_length=6)


class CounterMatchup(BaseModel):
    opponent_position: int
    opponent: PokemonRead
    counter: PokemonRead
    attacking_type: PokemonType
    incoming_type: PokemonType
    outgoing_multiplier: float
    incoming_multiplier: float
    safe: bool
    type_strength: float
    attack_potential: int
    durability: int
    speed: int
    stats_score: int


class CounterPreview(BaseModel):
    model_version: str
    chart_version: str
    safe_count: int
    size: int
    type_strength: float
    stats_score: int
    matchups: list[CounterMatchup]
