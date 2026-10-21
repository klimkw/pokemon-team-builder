import asyncio
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import func, select
from app.db import session as db
from app.db.models import AdminJob, CatalogChange, DemoState, Pokemon, ScanRun, User
from app.api import admin
from app.jobs import worker
from app.jobs.scanner import ScanResult, scan_lock

PATCH = {'pokemon': [{'pokemon_id': 1, 'stats': {'attack': 60}}],
         'type_matchups': [{'attacking_type': 'fire', 'defending_type': 'grass', 'multiplier': 1}]}


@pytest.fixture
def administrator(signed_in, monkeypatch):
    async def grant():
        async with db.session_maker.begin() as session:
            user = await session.scalar(select(User).where(User.email == 'ash'))
            user.is_superuser = True
    asyncio.run(grant())
    monkeypatch.setattr(admin, 'ENABLE_DEMO_CONTROLS', True)
    monkeypatch.setattr(worker, 'ENABLE_DEMO_CONTROLS', True)
    return signed_in


def test_admin_requires_privilege_and_no_cache(signed_in):
    for path in ['/api/admin/jobs', f'/api/admin/jobs/{uuid.uuid4()}']:
        response = signed_in.get(path)
        assert response.status_code == 403
        assert response.headers['Cache-Control'] == 'no-store'
    assert signed_in.post('/api/admin/refresh').status_code == 403


def test_queue_is_durable_and_api_does_not_run_scan(administrator):
    response = administrator.post('/api/admin/demo/changes', json=PATCH, headers={'Origin': 'http://testserver'})
    assert response.status_code == 202
    job = response.json()
    assert job['status'] == 'queued'
    assert response.headers['Location'] == f'/api/admin/jobs/{job["id"]}'
    assert administrator.get(response.headers['Location']).json()['status'] == 'queued'
    assert len(administrator.get('/api/admin/jobs').json()) == 1
    assert administrator.get('/api/pokemon/1').json()['stats']['attack'] == 55
    assert administrator.post('/api/admin/refresh').status_code == 409


def test_demo_controls_disabled_and_validation(administrator, monkeypatch):
    monkeypatch.setattr(admin, 'ENABLE_DEMO_CONTROLS', False)
    assert administrator.post('/api/admin/demo/changes', json=PATCH).status_code == 403
    assert administrator.post('/api/admin/demo/reset').status_code == 403
    for payload in [{}, {'pokemon': [{'pokemon_id': 1, 'stats': {'attack': -1}}]},
                    {'pokemon': [{'pokemon_id': 1, 'stats': {'attack': True}}]},
                    {'pokemon': [{'pokemon_id': 1, 'types': ['fire', 'fire']}]},
                    {'type_matchups': [{'attacking_type': 'fire', 'defending_type': 'grass', 'multiplier': 4}]}]:
        assert administrator.post('/api/admin/demo/changes', json=payload).status_code == 422
    assert administrator.post('/api/admin/refresh', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert administrator.post('/api/admin/refresh', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    assert administrator.get(f'/api/admin/jobs/{uuid.uuid4()}').status_code == 404


@pytest.mark.postgres
def test_worker_apply_repeat_reset_preserves_other_data_and_history(administrator):
    team = administrator.post('/api/teams', json={'name': 'Owned', 'pokemon_ids': [1, 1]}).json()
    def submit(action, payload=None):
        response = administrator.post(f'/api/admin/{action}', json=payload)
        assert response.status_code == 202
        asyncio.run(worker.process_one(db.engine))
        return administrator.get(response.headers['Location']).json()
    first = submit('demo/changes', PATCH)
    assert first['status'] == 'succeeded' and first['result']['pokemon']['updated'] == 1
    assert first['result']['types']['updated'] == 1
    alerts = administrator.get('/api/alerts').json()
    assert alerts['total'] == 2 and all(a['is_manual_demo'] for a in alerts['items'])
    assert len(alerts['items'][0]['affected'][0]['teams'][0]['positions']) == 2
    repeat = submit('demo/changes', PATCH)
    assert repeat['result']['pokemon']['unchanged'] == 1
    assert administrator.get('/api/alerts').json()['total'] == 2
    async def other_change():
        async with db.session_maker.begin() as session:
            pokemon = await session.get(Pokemon, 1)
            pokemon.stats = {**pokemon.stats, 'speed': 80}
            session.add(CatalogChange(entity_kind='pokemon', entity_key='1', entity_name=pokemon.name,
                changes={'stats.speed': {'before': 90, 'after': 80}}))
    asyncio.run(other_change())
    reset = submit('demo/reset')
    assert reset['status'] == 'succeeded' and reset['result']['removed_history'] == 2
    pokemon = administrator.get('/api/pokemon/1').json()
    assert pokemon['stats']['attack'] == 55 and pokemon['stats']['speed'] == 80
    remaining = administrator.get('/api/alerts').json()
    assert remaining['total'] == 1 and not remaining['items'][0]['is_manual_demo']
    assert administrator.get('/api/teams').json()[0]['id'] == team['id']
    assert submit('demo/reset')['result']['removed_history'] == 0


@pytest.mark.postgres
def test_reset_refuses_newer_field_after_cumulative_changes(administrator):
    def run(action, payload=None):
        queued = administrator.post('/api/admin/' + action, json=payload)
        assert queued.status_code == 202
        asyncio.run(worker.process_one(db.engine))
        return administrator.get(queued.headers['Location']).json()
    assert run('demo/changes', PATCH)['status'] == 'succeeded'
    assert run('demo/changes', {'pokemon': [{'pokemon_id': 1, 'stats': {'attack': 70}}]})['status'] == 'succeeded'
    async def newer():
        async with db.session_maker.begin() as session:
            p = await session.get(Pokemon, 1)
            p.stats = {**p.stats, 'attack': 61}
    asyncio.run(newer())
    reset = run('demo/reset')
    assert reset['status'] == 'failed' and 'newer data' in reset['error']
    assert administrator.get('/api/pokemon/1').json()['stats']['attack'] == 61


@pytest.mark.postgres
def test_refresh_job_and_interrupted_job_recovery(administrator, monkeypatch):
    calls = []
    async def refresh(engine):
        calls.append(engine)
        return ScanResult('partial', {'pokemon': {'updated': 1, 'failed': 1}})
    monkeypatch.setattr(worker, 'run_scan', refresh)
    queued = administrator.post('/api/admin/refresh')
    asyncio.run(worker.process_one(db.engine))
    result = administrator.get(queued.headers['Location']).json()
    assert result['status'] == 'partial' and result['result']['pokemon']['failed'] == 1
    assert calls == [db.engine]
    async def recover():
        async with db.session_maker.begin() as session:
            job = await session.get(AdminJob, uuid.UUID(result['id']))
            job.status = 'running'
        await worker.recover_jobs(db.session_maker)
    asyncio.run(recover())
    assert administrator.get(queued.headers['Location']).json()['status'] == 'interrupted'


@pytest.mark.postgres
def test_demo_waits_for_existing_scan_lock(administrator):
    queued = administrator.post('/api/admin/demo/changes', json=PATCH)
    async def hold():
        async with scan_lock(db.engine):
            assert await worker.process_one(db.engine) == worker.JobOutcome.DEFERRED
    asyncio.run(hold())
    assert administrator.get(queued.headers['Location']).json()['status'] == 'queued'


@pytest.mark.postgres
def test_worker_cancellation_records_interruption(administrator, monkeypatch):
    async def cancel(engine):
        raise asyncio.CancelledError()
    monkeypatch.setattr(worker, 'run_scan', cancel)
    queued = administrator.post('/api/admin/refresh')
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(worker.process_one(db.engine))
    assert administrator.get(queued.headers['Location']).json()['status'] == 'interrupted'


@pytest.mark.postgres
def test_cumulative_demo_preserves_originals_and_timeline(administrator):
    administrator.post('/api/teams', json={'name': 'Timeline', 'pokemon_ids': [1]})
    def run(payload=None, action='demo/changes'):
        queued = administrator.post('/api/admin/' + action, json=payload)
        assert queued.status_code == 202
        asyncio.run(worker.process_one(db.engine))
        job = administrator.get(queued.headers['Location']).json()
        assert job['status'] == 'succeeded', job
        return job
    first = run(PATCH)
    second_patch = {'pokemon': [{'pokemon_id': 1, 'stats': {'attack': 70, 'speed': 77}}],
                    'type_matchups': [{'attacking_type': 'fire', 'defending_type': 'grass', 'multiplier': 0.5}]}
    second = run(second_patch)
    assert first['result']['demo_id'] == second['result']['demo_id']
    alerts = administrator.get('/api/alerts?limit=1').json()
    # Histories cover the entire window, including entries outside this page.
    histories = list(alerts['items'][0]['history'].values())
    assert any(len(entries) == 2 for entries in histories)
    run(second_patch)
    assert administrator.get('/api/alerts').json()['total'] == 4
    reset = run(action='demo/reset')
    assert reset['result']['removed_history'] == 4
    pokemon = administrator.get('/api/pokemon/1').json()
    assert pokemon['stats']['attack'] == 55 and pokemon['stats']['speed'] == 90
    assert administrator.get('/api/alerts').json()['total'] == 0
