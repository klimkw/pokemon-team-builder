import asyncio
import pytest
from app.db import session as db
from app.db.models import Pokemon

STATS = ['hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed']


@pytest.mark.parametrize('stat', STATS)
def test_stat_sort_precedes_pagination_and_breaks_ties_by_index(client, catalog, stat):
    async def values():
        async with db.session_maker.begin() as session:
            for identifier, value in [(1, 60), (7, 100), (25, 60)]:
                pokemon = await session.get(Pokemon, identifier)
                pokemon.stats = {**pokemon.stats, stat: value}
    asyncio.run(values())
    ascending = client.get(f'/api/pokemon?sort={stat}_asc&limit=2').json()
    assert [item['id'] for item in ascending['items']] == [1, 25]
    descending = client.get(f'/api/pokemon?sort={stat}_desc&limit=2').json()
    assert [item['id'] for item in descending['items']] == [7, 1]
    assert [item['id'] for item in client.get(f'/api/pokemon?sort={stat}_desc&limit=2&offset=2').json()['items']] == [25]
    assert [item['id'] for item in client.get('/api/pokemon').json()['items']] == [1, 7, 25]
    assert client.get(f'/api/pokemon?sort={stat}_desc&types=grass').json()['items'][0]['id'] == 1


def test_sort_validation_and_slider_domain_are_global(client, catalog):
    async def values():
        async with db.session_maker.begin() as session:
            pokemon = await session.get(Pokemon, 25)
            pokemon.stats = {**pokemon.stats, 'attack': 500}
    asyncio.run(values())
    assert client.get('/api/pokemon?sort=invalid').status_code == 422
    empty = client.get('/api/pokemon?q=nonexistent').json()
    assert empty['total'] == 0 and empty['stat_maxima']['attack'] == 500
    assert empty['stat_maxima']['hp'] == 255
