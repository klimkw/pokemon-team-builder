"""Migration coverage for retiring a public login without losing saved data."""
import asyncio
import uuid
import pytest
from alembic import command
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.models import AccessToken, AdminJob, AlertRead, CatalogChange, Team, User

RETIRED_ID = uuid.UUID('00000000-0000-4000-8000-000000000003')


@pytest.mark.parametrize('saved_record', ['absent', 'empty', 'team', 'job', 'read'])
def test_retirement_preserves_personal_accounts_and_saved_records(database_case, saved_record):
    config = database_case.config()
    command.upgrade(config, '0005_alert_reads')
    personal_id, record_id = uuid.uuid4(), uuid.uuid4()

    async def seed():
        engine = database_case.engine()
        try:
            async with async_sessionmaker(engine).begin() as session:
                session.add(User(id=personal_id, email='admin', hashed_password='personal-hash',
                                 is_active=True, is_superuser=True))
                if saved_record != 'absent':
                    session.add(User(id=RETIRED_ID, email='legacy_reviewer', hashed_password='legacy-hash',
                                     is_active=True, is_superuser=True))
                await session.flush()
                session.add(AccessToken(token='personal-session', user_id=personal_id))
                if saved_record != 'absent':
                    session.add(AccessToken(token='legacy-session', user_id=RETIRED_ID))
                if saved_record == 'team':
                    session.add(Team(id=record_id, user_id=RETIRED_ID, name='Preserve this lineup'))
                elif saved_record == 'job':
                    session.add(AdminJob(id=record_id, requested_by=RETIRED_ID, action='demo_reset', status='queued'))
                elif saved_record == 'read':
                    session.add(CatalogChange(id=record_id, entity_kind='pokemon', entity_key='1',
                                              entity_name='bulbasaur', changes={}))
                    await session.flush()
                    session.add(AlertRead(user_id=RETIRED_ID, change_id=record_id))
        finally:
            await engine.dispose()

    async def verify():
        engine = database_case.engine()
        try:
            async with async_sessionmaker(engine)() as session:
                personal = await session.get(User, personal_id)
                assert personal.email == 'admin' and personal.is_active and personal.is_superuser
                assert personal.hashed_password == 'personal-hash'
                assert await session.get(AccessToken, 'personal-session') is not None
                assert await session.get(AccessToken, 'legacy-session') is None
                retired = await session.get(User, RETIRED_ID)
                if saved_record in ('absent', 'empty'):
                    assert retired is None
                else:
                    assert retired is not None and not retired.is_active and not retired.is_superuser
                if saved_record == 'team':
                    assert (await session.get(Team, record_id)).name == 'Preserve this lineup'
                elif saved_record == 'job':
                    job = await session.get(AdminJob, record_id)
                    assert job.status == 'interrupted' and job.finished_at is not None
                elif saved_record == 'read':
                    assert await session.get(AlertRead, (RETIRED_ID, record_id)) is not None
                    assert await session.get(CatalogChange, record_id) is not None
        finally:
            await engine.dispose()

    asyncio.run(seed())
    command.upgrade(config, 'head')
    asyncio.run(verify())
    command.downgrade(config, '0005_alert_reads')
    asyncio.run(verify())  # Rollback must not restore public access.
    command.upgrade(config, 'head')
    asyncio.run(verify())
