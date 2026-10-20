"""Explicit local CLI for granting/revoking admin access; never enabled by registration."""
import argparse
import asyncio
from sqlalchemy import select
from app.db import session as db
from app.db.models import User


async def set_admin(username, enabled):
    try:
        async with db.session_maker.begin() as session:
            user = await session.scalar(select(User).where(User.email == username.lower()))
            if user is None:
                raise ValueError('Account not found; register through the app first')
            user.is_superuser = enabled
        print('Admin access updated.')
    finally:
        await db.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['grant', 'revoke'])
    parser.add_argument('username')
    args = parser.parse_args()
    asyncio.run(set_admin(args.username, args.action == 'grant'))


if __name__ == '__main__':
    main()
