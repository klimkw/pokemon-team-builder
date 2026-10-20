import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.db import session as db
from app.db.models import User, AccessToken
from app.settings import COOKIE_NAME


def register(client, username="Ash", password="long-test-password"):
    return client.post("/api/auth/register", json={"username": username, "password": password})


def login(client, username="ASH", password="long-test-password"):
    return client.post("/api/auth/login", data={"username": username, "password": password})


def test_register_login_logout_revokes_token(client):
    assert client.get("/api/auth/me").status_code == 401
    result = register(client)
    assert result.status_code == 201, result.text
    assert set(result.json()) == {"id", "username"}
    assert result.json()["username"] == "ash"
    assert client.get("/api/auth/me").status_code == 401
    result = login(client)
    assert result.status_code == 204, result.text
    assert "HttpOnly" in result.headers["set-cookie"]
    assert "SameSite=lax" in result.headers["set-cookie"]
    token = client.cookies.get(COOKIE_NAME)
    assert client.get("/api/auth/me").json()["username"] == "ash"
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set(COOKIE_NAME, token)
    assert client.get("/api/auth/me").status_code == 401


def test_duplicates_validation_and_bad_password(client):
    assert register(client).status_code == 201
    assert register(client, "aSH").status_code == 400
    assert register(client, "x").status_code == 422
    assert register(client, "Misty", "short").status_code == 422
    assert login(client, password="incorrect-password").status_code == 400
    assert login(client, username="unknown").status_code == 400
    assert client.get("/api/auth/me").status_code == 401


def test_registration_cannot_escalate_privileges(client):
    result = client.post("/api/auth/register", json={
        "username": "ash", "password": "long-test-password",
        "is_superuser": True, "is_verified": True,
    })
    assert result.status_code == 201
    async def inspect_user():
        async with db.session_maker() as session:
            user = await session.scalar(select(User))
            assert user.is_superuser is False
            assert user.is_verified is False
            assert user.hashed_password != "long-test-password"
            assert user.hashed_password.startswith("$argon2")
    asyncio.run(inspect_user())


def test_expired_session_rejected(client):
    register(client)
    login(client)
    async def expire():
        async with db.session_maker() as session:
            await session.execute(update(AccessToken).values(
                created_at=datetime.now(timezone.utc) - timedelta(days=8)))
            await session.commit()
    asyncio.run(expire())
    assert client.get("/api/auth/me").status_code == 401


def test_cross_origin_mutations_rejected(client):
    for path in ["register", "login", "logout"]:
        assert client.post(f"/api/auth/{path}", headers={"Origin": "https://other.example"}).status_code == 403
        assert client.post(f"/api/auth/{path}", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
