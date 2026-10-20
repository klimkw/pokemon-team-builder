"""Application assembly; run Alembic before starting the API."""
from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import Depends, FastAPI, Request
from app.db import session as db
from app.api.auth import UserCreate, UserRead, current_user, fastapi_users, auth_backend
from app.api.catalog import router as catalog_router
from app.api.counters import router as counter_router
from app.db.models import User
from app.api.security import require_same_origin
from app.api.teams import router as teams_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        await db.engine.dispose()


app = FastAPI(title="Pokemon Team Builder", lifespan=lifespan)


@app.middleware("http")
async def prevent_private_caching(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/api/auth/", "/api/teams")):
        response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(fastapi_users.get_register_router(UserRead, UserCreate),
                   prefix="/api/auth", tags=["auth"],
                   dependencies=[Depends(require_same_origin)])
app.include_router(fastapi_users.get_auth_router(auth_backend),
                   prefix="/api/auth", tags=["auth"],
                   dependencies=[Depends(require_same_origin)])
app.include_router(catalog_router)
app.include_router(teams_router)
app.include_router(counter_router)


@app.get("/api/auth/me", response_model=UserRead, tags=["auth"])
async def me(user: Annotated[User, Depends(current_user)]):
    return user


@app.get("/api/health")
async def health():
    return {"status": "ok"}
