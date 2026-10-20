"""Owner-only credential changes with current-password verification."""
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi_users.password import PasswordHelper
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from app.api.auth import UserRead
from app.api.dependencies import Database, Owner
from app.api.security import require_same_origin
from app.db.models import AccessToken, User

router = APIRouter(prefix='/api/profile', tags=['profile'])


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: str = Field(min_length=1, max_length=128)
    username: str | None = Field(default=None, min_length=3, max_length=32)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode='after')
    def validate_fields(self):
        if self.username is None and self.new_password is None:
            raise ValueError('Provide a username or new password')
        if self.username is not None:
            if not re.fullmatch(r'[a-zA-Z0-9_]{3,32}', self.username):
                raise ValueError('Invalid username')
            self.username = self.username.lower()
        return self


class ProfileResult(BaseModel):
    user: UserRead
    session_revoked: bool


@router.patch('', response_model=ProfileResult, dependencies=[Depends(require_same_origin)])
async def update_profile(payload: ProfileUpdate, db: Database, owner: Owner):
    user = await db.scalar(select(User).where(User.id == owner.id).with_for_update().execution_options(populate_existing=True))
    helper = PasswordHelper()
    valid, upgraded = helper.verify_and_update(payload.current_password, user.hashed_password)
    if not valid:
        raise HTTPException(400, {'code': 'CURRENT_PASSWORD_INVALID'})
    if payload.username is not None:
        existing = await db.scalar(select(User.id).where(User.email == payload.username, User.id != user.id))
        if existing is not None:
            raise HTTPException(409, {'code': 'USERNAME_TAKEN'})
        user.email = payload.username
    if payload.new_password is not None:
        user.hashed_password = helper.hash(payload.new_password)
        await db.execute(delete(AccessToken).where(AccessToken.user_id == user.id))
    elif upgraded:
        user.hashed_password = upgraded
    result = ProfileResult(user=UserRead.model_validate(user), session_revoked=payload.new_password is not None)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, {'code': 'USERNAME_TAKEN'})
    return result
