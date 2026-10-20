import asyncio
import uuid
import pytest
from sqlalchemy import delete, event, func, select
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Pokemon, Team, TeamMember


def create(client, ids=None, name="Starters"):
    response = client.post("/api/teams", json={"name": name, "pokemon_ids": ids if ids is not None else [25, 1, 7]})
    assert response.status_code == 201, response.text
    assert response.headers["Location"].endswith(response.json()["id"])
    return response.json()


def lineup(team):
    return [m["pokemon"]["id"] for m in team["members"]]


def test_empty_duplicate_and_multiple_teams(signed_in):
    empty = create(signed_in, [], "  Empty team  ")
    assert empty["name"] == "Empty team"
    assert empty["members"] == []
    duplicate = create(signed_in, [25] * 6)
    assert lineup(duplicate) == [25] * 6
    assert [m["position"] for m in duplicate["members"]] == list(range(6))
    assert len(signed_in.get("/api/teams").json()) == 2
    assert duplicate["members"][0]["pokemon"]["stats"]["attack"] == 55
    assert "user_id" not in duplicate


def test_save_reorders_removes_and_persists(signed_in):
    original = create(signed_in)
    path = f"/api/teams/{original['id']}"
    response = signed_in.put(path, json={"name": "Reordered", "pokemon_ids": [7, 25]})
    assert response.status_code == 200, response.text
    updated = signed_in.get(path).json()
    assert updated["name"] == "Reordered"
    assert lineup(updated) == [7, 25]
    assert [m["position"] for m in updated["members"]] == [0, 1]
    assert updated["created_at"] == original["created_at"]
    assert updated["updated_at"] >= original["updated_at"]
    assert signed_in.put(path, json={"name": "Now empty", "pokemon_ids": []}).status_code == 200
    assert signed_in.get(path).json()["members"] == []


@pytest.mark.parametrize("payload", [
    {"name": "Team", "pokemon_ids": [25] * 7},
    {"name": "   ", "pokemon_ids": []},
    {"name": "x" * 81, "pokemon_ids": []},
    {"name": "Team", "pokemon_ids": [0]},
    {"name": "Team", "pokemon_ids": [True]},
    {"name": "Team", "pokemon_ids": [25.5]},
    {"name": "Team", "pokemon_ids": ["25"]},
    {"name": "Team", "pokemon_ids": [], "user_id": str(uuid.uuid4())},
    {"name": "Team"},
])
def test_invalid_payloads_cannot_change_team(signed_in, payload):
    original = create(signed_in)
    path = f"/api/teams/{original['id']}"
    assert signed_in.put(path, json=payload).status_code == 422
    assert signed_in.get(path).json() == original
    assert signed_in.post("/api/teams", json=payload).status_code == 422
    assert len(signed_in.get("/api/teams").json()) == 1


def test_unknown_pokemon_does_not_overwrite_team(signed_in):
    original = create(signed_in)
    path = f"/api/teams/{original['id']}"
    payload = {"name": "Invalid replacement", "pokemon_ids": [999999, 25, 999999]}
    response = signed_in.put(path, json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["pokemon_ids"] == [999999]
    assert signed_in.get(path).json() == original
    assert signed_in.post("/api/teams", json=payload).status_code == 422
    assert len(signed_in.get("/api/teams").json()) == 1


def test_ownership_on_every_operation(signed_in):
    original = create(signed_in)
    signed_in.post("/api/auth/logout")
    signed_in.post("/api/auth/register", json={"username": "misty", "password": "long-test-password"})
    signed_in.post("/api/auth/login", data={"username": "misty", "password": "long-test-password"})
    assert signed_in.get("/api/teams").json() == []
    path = f"/api/teams/{original['id']}"
    assert signed_in.get(path).status_code == 404
    assert signed_in.put(path, json={"name": "Stolen", "pokemon_ids": []}).status_code == 404
    assert signed_in.delete(path).status_code == 404
    assert signed_in.get(f"/api/teams/{uuid.uuid4()}").status_code == 404
    signed_in.post("/api/auth/logout")
    signed_in.post("/api/auth/login", data={"username": "ash", "password": "long-test-password"})
    assert signed_in.get(path).json() == original


def test_team_endpoints_require_authentication(client):
    path = f"/api/teams/{uuid.uuid4()}"
    payload = {"name": "Team", "pokemon_ids": []}
    for response in [client.get("/api/teams"), client.post("/api/teams", json=payload),
                     client.get(path), client.put(path, json=payload), client.delete(path)]:
        assert response.status_code == 401


def test_delete_cascades_members_and_preserves_catalog(signed_in):
    team = create(signed_in)
    assert signed_in.delete(f"/api/teams/{team['id']}").status_code == 204
    assert signed_in.get(f"/api/teams/{team['id']}").status_code == 404
    async def inspect():
        async with db.session_maker() as session:
            assert await session.scalar(select(func.count()).select_from(TeamMember)) == 0
            assert await session.scalar(select(func.count()).select_from(Pokemon)) == 3
    asyncio.run(inspect())


def test_failed_insert_rolls_back_name_and_member_deletion(signed_in):
    original = create(signed_in)
    def fail_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO team_members"):
            raise IntegrityError(statement, parameters, Exception("Injected write failure"))
    event.listen(db.engine.sync_engine, "before_cursor_execute", fail_insert)
    try:
        with pytest.raises(IntegrityError):
            signed_in.put(f"/api/teams/{original['id']}", json={"name": "Must roll back", "pokemon_ids": [7, 25]})
    finally:
        event.remove(db.engine.sync_engine, "before_cursor_execute", fail_insert)
    assert signed_in.get(f"/api/teams/{original['id']}").json() == original


def test_cross_origin_mutations_blocked(signed_in):
    team = create(signed_in)
    path = f"/api/teams/{team['id']}"
    headers = {"Origin": "https://other.example"}
    payload = {"name": "Other", "pokemon_ids": []}
    assert signed_in.post("/api/teams", json=payload, headers=headers).status_code == 403
    assert signed_in.put(path, json=payload, headers=headers).status_code == 403
    assert signed_in.delete(path, headers=headers).status_code == 403
    assert signed_in.get(path).headers["cache-control"] == "no-store"


def test_catalog_search_type_filter_and_pagination(client, catalog):
    page = client.get("/api/pokemon?limit=2").json()
    assert page["total"] == 3
    assert [p["id"] for p in page["items"]] == [1, 7]
    assert [p["id"] for p in client.get("/api/pokemon?offset=2").json()["items"]] == [25]
    assert client.get("/api/pokemon?q=PIKA").json()["items"][0]["id"] == 25
    assert client.get("/api/pokemon?type=poison").json()["items"][0]["id"] == 1
    assert client.get("/api/pokemon?type=grass&q=pika").json()["total"] == 0
    assert client.get("/api/pokemon?q=%25").json()["total"] == 0
    assert client.get("/api/pokemon/25").json()["types"] == ["electric"]
    assert client.get("/api/pokemon/999999").status_code == 404
    for query in ["type=invalid", "limit=101", "offset=-1"]:
        assert client.get(f"/api/pokemon?{query}").status_code == 422


def test_database_enforces_position_and_foreign_keys(signed_in):
    create(signed_in)
    async def inspect():
        async with db.session_maker() as session:
            existing = await session.scalar(select(Team))
            session.add(TeamMember(team_id=existing.id, position=6, pokemon_id=25))
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
            with pytest.raises(IntegrityError):
                await session.execute(delete(Pokemon).where(Pokemon.id == 25))
            await session.rollback()
    asyncio.run(inspect())
