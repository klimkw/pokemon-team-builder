from tests.test_alerts import event, store


def test_catalog_multitype_any_all_and_stat_ranges(client, catalog):
    any_page = client.get('/api/pokemon?types=grass&types=water&type_match=any').json()
    assert [p['id'] for p in any_page['items']] == [1, 7]
    assert [p['id'] for p in client.get('/api/pokemon?types=grass&types=poison&type_match=all').json()['items']] == [1]
    assert client.get('/api/pokemon?types=grass&types=water&type_match=all').json()['total'] == 0
    assert client.get('/api/pokemon?attack_min=55&attack_max=55&speed_min=90').json()['total'] == 3
    assert client.get('/api/pokemon?attack_min=56').json()['total'] == 0
    assert client.get('/api/pokemon?limit=12&offset=2').json()['limit'] == 12
    for query in ['attack_min=80&attack_max=20', 'hp_min=-1', 'speed_max=1000', 'types=nonsense', 'type_match=bad']:
        assert client.get('/api/pokemon?' + query).status_code == 422


def test_profile_requires_password_preserves_teams_and_normalizes_username(signed_in):
    team = signed_in.post('/api/teams', json={'name': 'Keep me', 'pokemon_ids': [1]}).json()
    bad = signed_in.patch('/api/profile', json={'current_password': 'wrong', 'username': 'new_ash'})
    assert bad.status_code == 400
    assert signed_in.get('/api/auth/me').json()['username'] == 'ash'
    updated = signed_in.patch('/api/profile', json={'current_password': 'long-test-password', 'username': 'New_Ash'})
    assert updated.status_code == 200 and updated.json()['user']['username'] == 'new_ash'
    assert not updated.json()['session_revoked']
    assert updated.headers['Cache-Control'] == 'no-store'
    assert signed_in.get('/api/teams').json()[0]['id'] == team['id']
    assert signed_in.patch('/api/profile', json={'current_password': 'long-test-password', 'username': 'invalid name'}).status_code == 422
    assert signed_in.patch('/api/profile', json={'current_password': 'long-test-password', 'username': 'newer'}, headers={'Origin': 'https://evil.example'}).status_code == 403


def test_password_change_revokes_sessions_and_rejects_old_password(signed_in):
    cookie = signed_in.cookies.get('pokemon_session')
    response = signed_in.patch('/api/profile', json={'current_password': 'long-test-password', 'new_password': 'another-long-password'})
    assert response.status_code == 200 and response.json()['session_revoked']
    assert signed_in.get('/api/auth/me').status_code == 401
    signed_in.cookies.set('pokemon_session', cookie)
    assert signed_in.get('/api/auth/me').status_code == 401
    assert signed_in.post('/api/auth/login', data={'username': 'ash', 'password': 'long-test-password'}).status_code == 400
    assert signed_in.post('/api/auth/login', data={'username': 'ash', 'password': 'another-long-password'}).status_code == 204


def test_profile_username_conflict_and_no_privilege_changes(signed_in):
    assert signed_in.post('/api/auth/register', json={'username': 'misty', 'password': 'long-test-password'}).status_code == 201
    assert signed_in.patch('/api/profile', json={'current_password': 'long-test-password', 'username': 'MISTY'}).status_code == 409
    assert signed_in.patch('/api/profile', json={'current_password': 'long-test-password', 'username': 'new_ash', 'is_superuser': True}).status_code == 422
    assert signed_in.get('/api/auth/me').json()['username'] == 'ash'


def test_unread_alerts_persist_per_user_and_acknowledgements_are_idempotent(signed_in):
    signed_in.post('/api/teams', json={'name': 'My team', 'pokemon_ids': [1]})
    store(event(), event('7'))
    first = signed_in.get('/api/alerts').json()
    assert first['unread_total'] == 1 and not first['items'][0]['is_read']
    payload = {'change_ids': [first['items'][0]['id']]}
    assert signed_in.post('/api/alerts/read', json=payload).status_code == 204
    assert signed_in.post('/api/alerts/read', json=payload).status_code == 204
    after = signed_in.get('/api/alerts').json()
    assert after['total'] == 1 and after['unread_total'] == 0 and after['items'][0]['is_read']
    signed_in.post('/api/auth/logout')
    signed_in.post('/api/auth/login', data={'username': 'ash', 'password': 'long-test-password'})
    assert signed_in.get('/api/alerts').json()['unread_total'] == 0
    store(event())
    assert signed_in.get('/api/alerts').json()['unread_total'] == 1
    signed_in.post('/api/auth/logout')
    signed_in.post('/api/auth/register', json={'username': 'misty', 'password': 'long-test-password'})
    signed_in.post('/api/auth/login', data={'username': 'misty', 'password': 'long-test-password'})
    assert signed_in.post('/api/alerts/read', json=payload).status_code == 204
    signed_in.post('/api/teams', json={'name': 'Other team', 'pokemon_ids': [1]})
    assert signed_in.get('/api/alerts').json()['unread_total'] == 2


def test_worker_restart_respects_last_full_scan_interval(client):
    import asyncio
    from datetime import datetime, timedelta, timezone
    from app.db import session as db
    from app.db.models import ScanRun
    from app.jobs.worker import scan_delay
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    async def run():
        assert await scan_delay(db.session_maker, now=now) == 0
        async with db.session_maker.begin() as session:
            session.add(ScanRun(status='succeeded', started_at=now - timedelta(hours=1),
                finished_at=now - timedelta(hours=1), summary={'scope': 'full', 'types': {'unchanged': 18}}))
            session.add(ScanRun(status='succeeded', started_at=now, finished_at=now,
                summary={'source': 'manual_demo', 'scope': 'sample'}))
        assert await scan_delay(db.session_maker, now=now) == 23 * 3600
        assert await scan_delay(db.session_maker, now=now + timedelta(days=2)) == 0
    asyncio.run(run())
