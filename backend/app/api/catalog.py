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
                       sort: Literal['index', 'hp_asc', 'hp_desc', 'attack_asc', 'attack_desc', 'defense_asc', 'defense_desc', 'special_attack_asc', 'special_attack_desc', 'special_defense_asc', 'special_defense_desc', 'speed_asc', 'speed_desc'] = 'index',
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
    bounds = {
        'hp': (hp_min, hp_max),
        'attack': (attack_min, attack_max),
        'defense': (defense_min, defense_max),
        'special_attack': (special_attack_min, special_attack_max),
        'special_defense': (special_defense_min, special_defense_max),
        'speed': (speed_min, speed_max),
    }
    for stat, (low, high) in bounds.items():
        if low is not None and high is not None and low > high:
            raise HTTPException(422, 'Minimum must not exceed maximum')
        if low is not None:
            conditions.append(Pokemon.stats[stat].as_integer() >= low)
        if high is not None:
            conditions.append(Pokemon.stats[stat].as_integer() <= high)
    total = await db.scalar(select(func.count()).select_from(Pokemon).where(*conditions))
    ordering = [Pokemon.id]
    if sort != 'index':
        stat, direction = sort.rsplit('_', 1)
        value = Pokemon.stats[stat].as_integer()
        ordering = [value.asc() if direction == 'asc' else value.desc(), Pokemon.id]
    items = await db.scalars(select(Pokemon).where(*conditions).order_by(*ordering).limit(limit).offset(offset))
    # Domains use the entire catalog, so sliders do not shrink when filters are applied.
    stats = ['hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed']
    maxima = (await db.execute(select(*(func.max(Pokemon.stats[key].as_integer()) for key in stats)))).one()
    stat_maxima = {key: max(255, value or 0) for key, value in zip(stats, maxima)}
    return PokemonPage(items=[PokemonRead.model_validate(item) for item in items], total=total, limit=limit, offset=offset, stat_maxima=stat_maxima)


@router.get('/{pokemon_id}', response_model=PokemonRead)
async def get_pokemon(pokemon_id: int, db: Database):
    pokemon = await db.get(Pokemon, pokemon_id)
    if pokemon is None:
        raise HTTPException(404, 'Pokemon not found')
    return pokemon
