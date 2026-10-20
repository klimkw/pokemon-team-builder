"""Atomic whole-team saves, always scoped to the authenticated owner."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.dependencies import Database, Owner
from app.db.models import Pokemon, Team, TeamMember, utc_now
from app.api.security import require_same_origin
from app.schemas.teams import TeamRead, TeamWrite

router = APIRouter(prefix="/api/teams", tags=["teams"])
member_details = selectinload(Team.members).selectinload(TeamMember.pokemon)
mutations = [Depends(require_same_origin)]


async def owned_team(db: AsyncSession, team_id: uuid.UUID, user_id: uuid.UUID, *, lock=False):
    query = select(Team).where(Team.id == team_id, Team.user_id == user_id)
    if lock:
        query = query.with_for_update()
    team = await db.scalar(query)
    if team is None:
        raise HTTPException(404, "Team not found")
    return team


async def validate_pokemon(db: AsyncSession, pokemon_ids: list[int]):
    requested = set(pokemon_ids)
    if not requested:
        return
    found = set(await db.scalars(select(Pokemon.id).where(Pokemon.id.in_(requested))))
    missing = sorted(requested - found)
    if missing:
        raise HTTPException(422, {"code": "UNKNOWN_POKEMON", "pokemon_ids": missing})


async def team_response(db: AsyncSession, team_id: uuid.UUID, user_id: uuid.UUID):
    team = await db.scalar(select(Team).where(Team.id == team_id, Team.user_id == user_id)
                           .options(member_details).execution_options(populate_existing=True))
    return TeamRead.model_validate(team)


@router.get("", response_model=list[TeamRead])
async def list_teams(db: Database, user: Owner):
    teams = await db.scalars(select(Team).where(Team.user_id == user.id)
                            .options(member_details).order_by(Team.updated_at.desc(), Team.id))
    return [TeamRead.model_validate(team) for team in teams]


@router.post("", response_model=TeamRead, status_code=201, dependencies=mutations)
async def create_team(payload: TeamWrite, db: Database, user: Owner, response: Response):
    await validate_pokemon(db, payload.pokemon_ids)
    team = Team(user_id=user.id, name=payload.name)
    db.add(team)
    await db.flush()  # Obtain the team's generated ID within this transaction.
    db.add_all([TeamMember(team_id=team.id, position=position, pokemon_id=pokemon_id)
                for position, pokemon_id in enumerate(payload.pokemon_ids)])
    await db.flush()
    result = await team_response(db, team.id, user.id)
    await db.commit()
    response.headers["Location"] = f"/api/teams/{team.id}"
    return result


@router.get("/{team_id}", response_model=TeamRead)
async def get_team(team_id: uuid.UUID, db: Database, user: Owner):
    await owned_team(db, team_id, user.id)
    return await team_response(db, team_id, user.id)


@router.put("/{team_id}", response_model=TeamRead, dependencies=mutations)
async def save_team(team_id: uuid.UUID, payload: TeamWrite, db: Database, user: Owner):
    team = await owned_team(db, team_id, user.id, lock=True)
    await validate_pokemon(db, payload.pokemon_ids)
    team.name = payload.name
    team.updated_at = utc_now()
    # Delete then insert avoids position-key conflicts during swaps/reordering.
    await db.execute(delete(TeamMember).where(TeamMember.team_id == team_id))
    db.add_all([TeamMember(team_id=team_id, position=position, pokemon_id=pokemon_id)
                for position, pokemon_id in enumerate(payload.pokemon_ids)])
    await db.flush()
    result = await team_response(db, team_id, user.id)
    await db.commit()
    return result


@router.delete("/{team_id}", status_code=204, dependencies=mutations)
async def delete_team(team_id: uuid.UUID, db: Database, user: Owner):
    team = await owned_team(db, team_id, user.id, lock=True)
    await db.delete(team)
    await db.commit()
