"""Owner-only credential changes with current-password verification."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi_users.password import PasswordHelper
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from app.schemas.credentials import Username, Password, PASSWORD_MAX_LENGTH
from app.api.auth import UserRead
from app.api.dependencies import Database, Owner
from app.api.security import require_same_origin
from app.db.models import AccessToken, User

router = APIRouter(prefix='/api/profile', tags=['profile'])


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    username: Username | None = None
    new_password: Password | None = None

    @model_validator(mode='after')
    def validate_fields(self):
        if self.username is None and self.new_password is None:
            raise ValueError('Provide a username or new password')
        return self


class ProfileResult(BaseModel):
    user: UserRead
    session_revoked: bool


@router.patch('', response_model=ProfileResult, dependencies=[Depends(require_same_origin)])
async def update_profile(payload: ProfileUpdate, db: Database, owner: Owner):
    user = await db.scalar(select(User).where(User.id == owner.id).with_for_update().execution_options(populate_existing=True))
    helper = PasswordHelper()
    valid, upgraded = await run_in_threadpool(helper.verify_and_update, payload.current_password, user.hashed_password)
    if not valid:
        raise HTTPException(400, {'code': 'CURRENT_PASSWORD_INVALID'})
    if payload.username is not None:
        existing = await db.scalar(select(User.id).where(User.email == payload.username, User.id != user.id))
        if existing is not None:
            raise HTTPException(409, {'code': 'USERNAME_TAKEN'})
        user.email = payload.username
    if payload.new_password is not None:
        user.hashed_password = await run_in_threadpool(helper.hash, payload.new_password)
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
