"""Preview contracts: generation does not create or modify a saved team."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.teams import PokemonRead, PokemonType


class CounterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pokemon_ids: list[Annotated[int, Field(strict=True, gt=0)]] = Field(min_length=1, max_length=6)


class Strike(BaseModel):
    category: Literal['physical', 'special']
    attack_type: PokemonType
    attack: int
    defense: int
    effectiveness: float
    damage: int


class DuelTurn(BaseModel):
    turn: int
    counter_hp: int
    opponent_hp: int
    counter_damage: int
    opponent_damage: int


class Duel(BaseModel):
    model_version: str
    result: Literal['counter', 'opponent', 'draw', 'stalemate']
    order: Literal['counter', 'opponent', 'simultaneous']
    counter_hp: int
    opponent_hp: int
    outgoing: Strike
    incoming: Strike
    turns: list[DuelTurn]


class CounterMatchup(BaseModel):
    simulation: Duel | None = None
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
