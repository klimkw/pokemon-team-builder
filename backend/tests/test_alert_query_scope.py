"""History volume must not make one page hydrate every event or read marker."""
import asyncio
from datetime import timedelta
from uuid import UUID

from sqlalchemy import event as sqlalchemy_event
from app.db import session as db
from app.db.models import AlertRead, CatalogChange, Pokemon, Team, TeamMember, utc_now
from app.services.alerts import get_alerts


def test_alert_page_loads_only_its_entities_history(signed_in):
    owner_id = UUID(signed_in.get('/api/auth/me').json()['id'])
    async def run():
        now = utc_now()
        async with db.session_maker.begin() as session:
            template = await session.get(Pokemon, 1)
            team = Team(user_id=owner_id, name='History scope')
            session.add(team)
            await session.flush()
            for index in range(6):
                identifier = 100 + index
                session.add(Pokemon(id=identifier, name=f'fixture-{identifier}', types=['normal'],
                                    stats=dict(template.stats), sprite_url=None))
                await session.flush()
                session.add(TeamMember(team_id=team.id, position=index, pokemon_id=identifier))
                for change in range(10):
                    session.add(CatalogChange(entity_kind='pokemon', entity_key=str(identifier),
                        entity_name=f'fixture-{identifier}', detected_at=now - timedelta(minutes=index * 10 + change),
                        changes={'stats.attack': {'before': change, 'after': change + 1}}))
            # Retained acknowledgements and unrelated history must not be loaded into the feed.
            old = [CatalogChange(entity_kind='pokemon', entity_key='7', entity_name='squirtle',
                detected_at=now - timedelta(days=30), changes={'stats.attack': {'before': 1, 'after': 2}})
                for _ in range(1000)]
            session.add_all(old)
            await session.flush()
            session.add_all([AlertRead(user_id=owner_id, change_id=row.id) for row in old])
        loaded = []
        def record_load(instance, context):
            loaded.append(type(instance))
        for model in (CatalogChange, AlertRead):
            sqlalchemy_event.listen(model, 'load', record_load)
        try:
            async with db.session_maker() as session:
                page = await get_alerts(session, owner_id, limit=2, now=now)
                assert page.total == page.unread_total == 60
                assert len(page.items) == 2
                assert all(len(alert.history['stats.attack']) == 10 for alert in page.items)
                assert AlertRead not in loaded
                assert loaded.count(CatalogChange) == 10
        finally:
            for model in (CatalogChange, AlertRead):
                sqlalchemy_event.remove(model, 'load', record_load)
    asyncio.run(run())
