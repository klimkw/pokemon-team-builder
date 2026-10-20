"""Authenticated, side-effect-free previews from the editor's current ordered IDs."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from .counter_schemas import CounterPreview, CounterRequest
from .counters import generate_counter
from .models import Pokemon
from .security import require_same_origin
from .team_schemas import PokemonRead
from .teams import Database, Owner

router = APIRouter(prefix="/api/teams", tags=["counter teams"])


@router.post("/counter-preview", response_model=CounterPreview, dependencies=[Depends(require_same_origin)])
async def counter_preview(payload: CounterRequest, db: Database, user: Owner):
    # One query provides both the opponents and candidates from the same catalog read.
    catalog = [PokemonRead.model_validate(pokemon) for pokemon in await db.scalars(select(Pokemon).order_by(Pokemon.id))]
    by_id = {pokemon.id: pokemon for pokemon in catalog}
    missing = sorted(set(payload.pokemon_ids) - by_id.keys())
    if missing:
        raise HTTPException(422, {"code": "UNKNOWN_POKEMON", "pokemon_ids": missing})
    if len(catalog) < len(payload.pokemon_ids):
        raise HTTPException(409, {"code": "INSUFFICIENT_CATALOG"})
    opponents = [by_id[identifier] for identifier in payload.pokemon_ids]
    return await run_in_threadpool(generate_counter, opponents, catalog)
