"""Shared API dependencies; services and jobs do not depend on HTTP routes."""
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.auth import current_user
from app.db.models import User
from app.db.session import database

Database = Annotated[AsyncSession, Depends(database)]
Owner = Annotated[User, Depends(current_user)]
