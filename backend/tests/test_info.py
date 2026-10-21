import asyncio
from datetime import datetime, timedelta, timezone
from app.db import session as db
from app.db.models import ScanRun
from app.version import APP_VERSION


def test_public_info_is_allowlisted_and_uncached(client, catalog):
    response = client.get('/api/info')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    result = response.json()
    assert set(result) == {'app_version', 'repository_url',
        'catalog_source_url', 'catalog_count', 'scan_interval_hours', 'alert_window_days',
        'last_successful_live_refresh', 'checked_at'}
    assert result['app_version'] == APP_VERSION
    assert result['catalog_count'] == 3
    assert result['catalog_source_url'] == 'https://pokeapi.co/api/v2/pokemon/?limit=200'
    assert 'latest_live_refresh' not in result
    assert result['repository_url'] == 'https://github.com/klimkw/pokemon-team-builder'
    assert client.get('/openapi.json').json()['info']['version'] == APP_VERSION


def test_refresh_metadata_excludes_demo_sample_and_private_details(client):
    now = datetime.now(timezone.utc)
    async def store():
        async with db.session_maker.begin() as session:
            for days, status, summary in [
                (4, 'succeeded', {'scope': 'full', 'types': {}}),
                (3, 'partial', {'scope': 'full', 'source': 'upstream'}),
                (2, 'failed', {'scope': 'full'}),
                (1, 'succeeded', {'scope': 'full', 'source': 'manual_demo'}),
                (0, 'succeeded', {'scope': 'sample'}),
            ]:
                session.add(ScanRun(started_at=now - timedelta(days=days), finished_at=now - timedelta(days=days),
                    status=status, summary={**summary, 'private_payload': 'DO_NOT_EXPOSE'}, error='DO_NOT_EXPOSE'))
    asyncio.run(store())
    response = client.get('/api/info')
    result = response.json()
    assert result['last_successful_live_refresh']['started_at'].startswith((now - timedelta(days=4)).date().isoformat())
    assert 'DO_NOT_EXPOSE' not in response.text
    assert set(result['last_successful_live_refresh']) == {'status', 'started_at', 'finished_at'}


def test_full_pokemon_only_import_does_not_replace_refresh_metadata(client):
    from app.db.models import ScanRun
    from app.jobs.worker import scan_delay
    now = datetime.now(timezone.utc)
    async def seed():
        async with db.session_maker.begin() as session:
            session.add_all([
                ScanRun(status='succeeded', started_at=now - timedelta(hours=1),
                        finished_at=now - timedelta(hours=1), summary={'scope': 'full', 'types': {}}),
                ScanRun(status='succeeded', started_at=now, finished_at=now,
                        summary={'scope': 'full', 'pokemon': {'unchanged': 3}}),
            ])
        assert await scan_delay(db.session_maker, now=now) == 23 * 3600
    asyncio.run(seed())
    info = client.get('/api/info').json()
    assert datetime.fromisoformat(info['last_successful_live_refresh']['finished_at']) == now - timedelta(hours=1)
