"""Release packaging smoke check, only inside the disposable Compose stack.

Uses real HTTP, migrations and PostgreSQL. CI does not contact the live deployment.
The HTTP transport is local; Secure cookies are explicitly replayed after checking
attributes so production cookie configuration stays enabled.
"""
import asyncio
import json
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from http.cookies import SimpleCookie

BASE = 'http://127.0.0.1:8000'
EXPECTED_DB = 'postgresql://pokemon_test:disposable_test_password@db:5432/pokemon_test'
if os.environ.get('DATABASE_URL') != EXPECTED_DB or os.environ.get('APP_ORIGIN') != BASE:
    raise RuntimeError('Smoke check requires the isolated production-test stack')


async def seed():
    from app.db.session import engine
    from app.db.models import Pokemon, utc_now
    from sqlalchemy.ext.asyncio import async_sessionmaker
    async with async_sessionmaker(engine)() as session:
        for identifier, name, kind in [(1, 'bulbasaur', 'grass'), (4, 'charmander', 'fire'), (7, 'squirtle', 'water')]:
            session.add(Pokemon(id=identifier, name=name, types=[kind],
                stats=dict(hp=45, attack=49, defense=49, special_attack=65, special_defense=65, speed=45),
                sprite_url=None, synced_at=utc_now()))
        await session.commit()
    await engine.dispose()


asyncio.run(seed())


def request(path, method='GET', payload=None, cookie=None, form=False, origin=BASE, expected=200):
    headers = {'Origin': origin}
    if cookie:
        headers['Cookie'] = cookie
    body = None
    if payload is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
        body = (urllib.parse.urlencode(payload) if form else json.dumps(payload)).encode()
    try:
        response = urllib.request.urlopen(urllib.request.Request(BASE + path, data=body, headers=headers, method=method), timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        data = response.read()
        assert response.status == expected, f'{method} {path}: expected {expected}, got {response.status}'
        content_type = response.headers.get('Content-Type', '')
        result = json.loads(data) if data and 'application/json' in content_type else data
        return result, response.headers


html, _ = request('/')
assert b'<div id="root">' in html
assets = re.findall(rb'(?:src|href)="(/assets/[^" ]+)"', html)
assert assets, 'Built frontend assets must be present'
for asset in assets:
    content, _ = request(asset.decode())
    assert content
request('/counter-method')
request('/api/health')
request('/api/not-a-route', expected=404)
request('/assets/not-a-file.js', expected=404)
request('/api/teams', expected=401)
page, _ = request('/api/pokemon')
assert page['total'] == 3
page, _ = request('/api/pokemon?q=bulbasaur')
assert [item['id'] for item in page['items']] == [1]
username = 'smoke_' + secrets.token_hex(6)
credentials = {'username': username, 'password': secrets.token_urlsafe(24)}
request('/api/auth/register', 'POST', credentials, expected=201)
_, headers = request('/api/auth/login', 'POST', credentials, form=True, expected=204)
cookies = SimpleCookie()
cookies.load(headers['Set-Cookie'])
session = cookies['pokemon_session']
assert session['secure'] and session['httponly'] and session['samesite'].lower() == 'lax'
cookie = f'{session.key}={session.value}'
request('/api/auth/me', cookie=cookie)
team, _ = request('/api/teams', 'POST', {'name': 'Release smoke', 'pokemon_ids': [1, 4]}, cookie, expected=201)
path = '/api/teams/' + team['id']
request(path, 'PUT', {'name': 'Release smoke saved', 'pokemon_ids': [4, 1]}, cookie)
saved, _ = request(path, cookie=cookie)
assert [member['pokemon']['id'] for member in saved['members']] == [4, 1]
preview, _ = request('/api/teams/counter-preview', 'POST', {'pokemon_ids': [4, 1]}, cookie)
assert preview['size'] == 2 and len(preview['matchups']) == 2
assert all(match['simulation'] for match in preview['matchups'])
teams, _ = request('/api/teams', cookie=cookie)
assert len(teams) == 1, 'Counter preview must not save a team'
request('/api/teams', 'POST', {'name': 'Blocked', 'pokemon_ids': []}, cookie, origin='https://other.example', expected=403)
request('/api/auth/logout', 'POST', cookie=cookie, expected=204)
request('/api/auth/me', cookie=cookie, expected=401)
_, headers = request('/api/auth/login', 'POST', credentials, form=True, expected=204)
cookies.load(headers['Set-Cookie'])
cookie = f'pokemon_session={cookies["pokemon_session"].value}'
request(path, cookie=cookie)
request(path, 'DELETE', cookie=cookie, expected=204)
request('/api/auth/logout', 'POST', cookie=cookie, expected=204)
print('Production image smoke passed: startup migrations, frontend assets, catalog, login, secure cookie, saved teams, counters, origin guard, logout and persistence.')
