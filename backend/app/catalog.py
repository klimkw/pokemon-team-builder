"""Public reads from the local catalog; population/synchronization comes next."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from .db import database
from .models import Pokemon
from .team_schemas import PokemonPage, PokemonRead, PokemonType

router = APIRouter(prefix="/api/pokemon", tags=["pokemon"])
Database = Annotated[AsyncSession, Depends(database)]


@router.get("", response_model=PokemonPage)
async def list_pokemon(db: Database, q: str = Query(default="", max_length=100),
                       type: PokemonType | None = None,
                       limit: int = Query(default=24, ge=1, le=100),
                       offset: int = Query(default=0, ge=0)):
    conditions = []
    if q.strip():
        conditions.append(Pokemon.name.contains(q.strip().lower(), autoescape=True))
    if type:
        # Pokémon have one or two types. Index lookup works with PostgreSQL JSONB
        # and the SQLite JSON fallback used in tests.
        conditions.append(or_(Pokemon.types[0].as_string() == type,
                              Pokemon.types[1].as_string() == type))
    total = await db.scalar(select(func.count()).select_from(Pokemon).where(*conditions))
    items = await db.scalars(select(Pokemon).where(*conditions).order_by(Pokemon.id)
                            .limit(limit).offset(offset))
    return PokemonPage(items=[PokemonRead.model_validate(item) for item in items],
                       total=total, limit=limit, offset=offset)


@router.get("/{pokemon_id}", response_model=PokemonRead)
async def get_pokemon(pokemon_id: int, db: Database):
    pokemon = await db.get(Pokemon, pokemon_id)
    if pokemon is None:
        raise HTTPException(404, "Pokemon not found")
    return pokemon
