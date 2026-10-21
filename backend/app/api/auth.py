"""FastAPI Users configuration and username-only account schemas."""
import uuid
from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, schemas
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.exceptions import InvalidPasswordException
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from pydantic import BaseModel, Field
from app.schemas.credentials import Username, Password, PASSWORD_MIN_LENGTH, PASSWORD_MAX_LENGTH
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import database
from app.db.models import User, AccessToken
from app.settings import COOKIE_NAME, COOKIE_SECURE, SESSION_SECONDS

async def get_user_db(session: AsyncSession = Depends(database)):
    yield SQLAlchemyUserDatabase(session, User)

async def get_token_db(session: AsyncSession = Depends(database)):
    yield SQLAlchemyAccessTokenDatabase(session, AccessToken)

class UserCreate(schemas.BaseUserCreate):
    # Alias preserves the username API while using the library's create flow.
    email: Username = Field(alias="username")
    password: Password


class UserRead(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    username: str


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    async def validate_password(self, password: str, user) -> None:
        if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
            raise InvalidPasswordException(reason="Password must contain 8-128 characters")


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


cookie_transport = CookieTransport(cookie_name=COOKIE_NAME,
    cookie_max_age=SESSION_SECONDS, cookie_secure=COOKIE_SECURE,
    cookie_httponly=True, cookie_samesite="lax")


def get_strategy(token_db=Depends(get_token_db)):
    return DatabaseStrategy(token_db, lifetime_seconds=SESSION_SECONDS)


auth_backend = AuthenticationBackend(name="cookie", transport=cookie_transport,
                                     get_strategy=get_strategy)
fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])
current_user = fastapi_users.current_user(active=True)


