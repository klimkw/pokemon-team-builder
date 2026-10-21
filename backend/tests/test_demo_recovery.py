import asyncio
import pytest
from app.db import session as db
from app.db.models import Pokemon, TypeChart
from app.jobs import ingest
from app.services import demo_controls

PATCH = {"pokemon": [{"pokemon_id": 1, "stats": {"attack": 60}}],
         "type_matchups": [{"attacking_type": "fire", "defending_type": "grass", "multiplier": 1}]}


@pytest.mark.parametrize('cumulative', [False, True])
@pytest.mark.parametrize('interruption', ['before_scan', 'after_types', 'after_pokemon'])
def test_demo_retry_after_interruption_preserves_originals(client, catalog, monkeypatch, cumulative, interruption):
    async def run():
        async with db.session_maker() as session:
            original_chart = (await session.get(TypeChart, 1)).damage_to
        if cumulative:
            assert (await demo_controls.apply_changes(db.session_maker, PATCH))[0] == 'succeeded'
        patch = {'pokemon': [{'pokemon_id': 1, 'stats': {'attack': 70}}],
                 'type_matchups': [{'attacking_type': 'fire', 'defending_type': 'grass', 'multiplier': 0.5}]}
        original_sync = ingest.sync_record
        async def interrupt_scan(*args, **kwargs):
            raise asyncio.CancelledError()
        async def interrupt_record(*args, **kwargs):
            if interruption == 'after_pokemon':
                await original_sync(*args, **kwargs)
            raise asyncio.CancelledError()
        with monkeypatch.context() as patcher:
            if interruption == 'before_scan':
                patcher.setattr(demo_controls, 'run_locked_scan', interrupt_scan)
            else:
                patcher.setattr(ingest, 'sync_record', interrupt_record)
            with pytest.raises(asyncio.CancelledError):
                await demo_controls.apply_changes(db.session_maker, patch)
        assert (await demo_controls.apply_changes(db.session_maker, patch))[0] == 'succeeded'
        async with db.session_maker() as session:
            assert (await session.get(Pokemon, 1)).stats['attack'] == 70
            assert (await session.get(TypeChart, 1)).damage_to['fire']['grass'] == 0.5
        assert (await demo_controls.reset_changes(db.session_maker))[0] == 'succeeded'
        async with db.session_maker() as session:
            assert (await session.get(Pokemon, 1)).stats['attack'] == 55
            assert (await session.get(TypeChart, 1)).damage_to == original_chart
    asyncio.run(run())
