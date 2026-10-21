"""Explicitly provision the public take-home demo account; never runs at API startup."""
import asyncio
import uuid
from fastapi_users.password import PasswordHelper
from sqlalchemy import select
from app.db import session as db
from app.db.models import User
from app.settings import ENABLE_DEMO_CONTROLS, DEMO_EXECUTION_MODE

REVIEWER_ACCOUNT_ID = uuid.UUID('00000000-0000-4000-8000-000000000003')


async def provision(sessions):
    if not ENABLE_DEMO_CONTROLS or DEMO_EXECUTION_MODE != 'request':
        raise ValueError('Public demo provisioning requires enabled request-mode demo controls')
    async with sessions.begin() as session:
        existing = await session.scalar(select(User).where(User.email == 'admin'))
        if existing is not None and existing.id != REVIEWER_ACCOUNT_ID:
            raise ValueError('Username admin already belongs to another account; refusing to overwrite it')
        user = await session.get(User, REVIEWER_ACCOUNT_ID)
        if user is None:
            session.add(User(id=REVIEWER_ACCOUNT_ID, email='admin',
                hashed_password=PasswordHelper().hash('admin'), is_active=True,
                is_superuser=True, is_verified=False))
        elif user.email != 'admin' or not user.is_superuser or not user.is_active:
            raise ValueError('Managed reviewer account was modified; inspect it before provisioning')
    print('Public demo account ready: admin / admin')


async def main():
    try:
        await provision(db.session_maker)
    finally:
        await db.engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
