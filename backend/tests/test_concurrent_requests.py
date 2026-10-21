"""Overlapping HTTP mutations exercise application transactions on real PostgreSQL."""
import asyncio
import uuid

import httpx
import pytest
from sqlalchemy import select, text
from app.main import app
from app.db import session as db
from app.db.models import Team, User

pytestmark = pytest.mark.postgres


async def wait_for_blocked_requests(lock_pid, count):
    """Observe actual database lock waits, rather than guessing with a sleep."""
    async with asyncio.timeout(10):
        while True:
            async with db.session_maker() as observer:
                waiting = await observer.scalar(text(
                    '''WITH RECURSIVE blocked(pid) AS (
                        SELECT CAST(:lock_pid AS integer)
                        UNION
                        SELECT activity.pid FROM pg_stat_activity AS activity
                        JOIN blocked ON blocked.pid = ANY(pg_blocking_pids(activity.pid))
                    ) SELECT count(*) - 1 FROM blocked'''), {'lock_pid': lock_pid})
            if waiting >= count:
                return
            await asyncio.sleep(0.01)


async def overlap_requests(browser, model, identifier, requests):
    tasks = []
    try:
        async with db.session_maker() as blocker:
            await blocker.scalar(select(model).where(model.id == identifier).with_for_update())
            lock_pid = await blocker.scalar(text('SELECT pg_backend_pid()'))
            for method, path, payload in requests:
                tasks.append(asyncio.create_task(browser.request(method, path, json=payload)))
                await wait_for_blocked_requests(lock_pid, len(tasks))
            await blocker.commit()
        return await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def test_overlapping_team_saves_never_mix_name_and_lineup(signed_in):
    team = signed_in.post('/api/teams', json={'name': 'Initial', 'pokemon_ids': []}).json()
    first = {'name': 'First', 'pokemon_ids': [1, 7]}
    second = {'name': 'Second', 'pokemon_ids': [25, 25, 1]}
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver',
                                     cookies=dict(signed_in.cookies)) as browser:
            responses = await overlap_requests(browser, Team, uuid.UUID(team['id']), [
                ('PUT', f"/api/teams/{team['id']}", first),
                ('PUT', f"/api/teams/{team['id']}", second),
            ])
            for response, expected in zip(responses, [first, second]):
                assert response.status_code == 200
                assert response.json()['name'] == expected['name']
                assert [m['pokemon']['id'] for m in response.json()['members']] == expected['pokemon_ids']
            saved = (await browser.get(f"/api/teams/{team['id']}")).json()
            assert saved['name'] == second['name']
            assert [m['pokemon']['id'] for m in saved['members']] == second['pokemon_ids']
    asyncio.run(run())


def test_delete_waits_for_inflight_save_without_resurrecting_team(signed_in):
    team = signed_in.post('/api/teams', json={'name': 'Initial', 'pokemon_ids': [1]}).json()
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver',
                                     cookies=dict(signed_in.cookies)) as browser:
            responses = await overlap_requests(browser, Team, uuid.UUID(team['id']), [
                ('PUT', f"/api/teams/{team['id']}", {'name': 'Edited', 'pokemon_ids': [7, 25]}),
                ('DELETE', f"/api/teams/{team['id']}", None),
            ])
            assert [r.status_code for r in responses] == [200, 204]
            assert (await browser.get(f"/api/teams/{team['id']}")).status_code == 404
            assert (await browser.get('/api/teams')).json() == []
    asyncio.run(run())


def test_overlapping_password_changes_revalidate_current_password(signed_in):
    owner = signed_in.get('/api/auth/me').json()
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver',
                                     cookies=dict(signed_in.cookies)) as browser:
            responses = await overlap_requests(browser, User, uuid.UUID(owner['id']), [
                ('PATCH', '/api/profile', {'current_password': 'long-test-password', 'new_password': 'first-new-password'}),
                ('PATCH', '/api/profile', {'current_password': 'long-test-password', 'new_password': 'second-new-password'}),
            ])
            assert [r.status_code for r in responses] == [200, 400]
            assert responses[1].json()['detail']['code'] == 'CURRENT_PASSWORD_INVALID'
            assert (await browser.get('/api/auth/me')).status_code == 401
            assert (await browser.post('/api/auth/login', data={'username': 'ash', 'password': 'second-new-password'})).status_code == 400
            assert (await browser.post('/api/auth/login', data={'username': 'ash', 'password': 'first-new-password'})).status_code == 204
    asyncio.run(run())
