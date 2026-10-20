"""Local catalog search with portable JSON filters and bounded pagination."""
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import database
from app.db.models import Pokemon
from app.schemas.teams import PokemonPage, PokemonRead, PokemonType

router = APIRouter(prefix='/api/pokemon', tags=['pokemon'])
Database = Annotated[AsyncSession, Depends(database)]
@router.get('', response_model=PokemonPage)
async def list_pokemon(db: Database, q: str = Query(default='', max_length=100),
                       type: PokemonType | None = None,
                       types: Annotated[list[PokemonType] | None, Query()] = None,
                       type_match: Literal['any', 'all'] = 'any',
                       limit: int = Query(default=24, ge=1, le=100),
                       offset: int = Query(default=0, ge=0),
                       hp_min: int | None = Query(None, ge=0, le=999),
                       hp_max: int | None = Query(None, ge=0, le=999),
                       attack_min: int | None = Query(None, ge=0, le=999),
                       attack_max: int | None = Query(None, ge=0, le=999),
                       defense_min: int | None = Query(None, ge=0, le=999),
                       defense_max: int | None = Query(None, ge=0, le=999),
                       special_attack_min: int | None = Query(None, ge=0, le=999),
                       special_attack_max: int | None = Query(None, ge=0, le=999),
                       special_defense_min: int | None = Query(None, ge=0, le=999),
                       special_defense_max: int | None = Query(None, ge=0, le=999),
                       speed_min: int | None = Query(None, ge=0, le=999),
                       speed_max: int | None = Query(None, ge=0, le=999)):
    conditions = []
    if q.strip():
        conditions.append(Pokemon.name.contains(q.strip().lower(), autoescape=True))
    selected = set(types or []) | ({type} if type else set())
    if selected:
        checks = [or_(Pokemon.types[0].as_string() == t, Pokemon.types[1].as_string() == t) for t in sorted(selected)]
        conditions.append((and_ if type_match == 'all' else or_)(*checks))
    bounds = locals()
    for stat in ['hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed']:
        low, high = bounds[stat + '_min'], bounds[stat + '_max']
        if low is not None and high is not None and low > high:
            raise HTTPException(422, 'Minimum must not exceed maximum')
        if low is not None:
            conditions.append(Pokemon.stats[stat].as_integer() >= low)
        if high is not None:
            conditions.append(Pokemon.stats[stat].as_integer() <= high)
    total = await db.scalar(select(func.count()).select_from(Pokemon).where(*conditions))
    items = await db.scalars(select(Pokemon).where(*conditions).order_by(Pokemon.id).limit(limit).offset(offset))
    return PokemonPage(items=[PokemonRead.model_validate(item) for item in items], total=total, limit=limit, offset=offset)


@router.get('/{pokemon_id}', response_model=PokemonRead)
async def get_pokemon(pokemon_id: int, db: Database):
    pokemon = await db.get(Pokemon, pokemon_id)
    if pokemon is None:
        raise HTTPException(404, 'Pokemon not found')
    return pokemon
