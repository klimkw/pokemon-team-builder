"""Apply fixture inputs through the scanner; reset only fields owned by this scenario."""
from copy import deepcopy
import uuid
from sqlalchemy import delete, select
from app.db.models import CatalogChange, DemoState, Pokemon, ScanRun, TypeChart, utc_now
from app.jobs.scanner import run_locked_scan
from app.schemas.admin import DemoChanges
from app.services.pokeapi import CatalogRecord
from app.services.type_sync import chart_version


class ManualSource:
    """Bounded local source records in place of upstream responses, not direct edits."""
    def __init__(self, records, rows):
        self.records, self.rows = records, rows

    async def discover(self):
        return {p.id: f'https://pokeapi.co/api/v2/pokemon/{p.id}/' for p in self.records}

    async def fetch_pokemon(self, identifier, url):
        return next(p for p in self.records if p.id == identifier)

    async def get_json(self, url):
        name = url.rstrip('/').split('/')[-1]
        return {'name': name, 'damage_relations': {
            field: [{'name': target} for target, value in self.rows[name].items() if value == multiplier]
            for field, multiplier in [('no_damage_to', 0), ('half_damage_to', .5), ('double_damage_to', 2)]}}


async def apply_changes(sessions, payload):
    changes = DemoChanges.model_validate(payload)
    normalized = changes.model_dump(mode='json')
    async with sessions.begin() as session:
        state = await session.get(DemoState, 1)
        if state and state.payload != normalized:
            raise ValueError('A different demo is active. Reset it before submitting different changes.')
        rows = deepcopy((await session.get(TypeChart, 1)).damage_to)
        originals = {'pokemon': {}, 'type_matchups': []}
        records = []
        for patch in changes.pokemon:
            pokemon = await session.get(Pokemon, patch.pokemon_id)
            if pokemon is None:
                raise ValueError(f'Pokemon {patch.pokemon_id} is not in the catalog')
            values = dict(id=pokemon.id, name=pokemon.name, types=pokemon.types,
                          stats=deepcopy(pokemon.stats), sprite_url=pokemon.sprite_url)
            original = {}
            for stat, after in patch.stats.items():
                original[f'stats.{stat}'] = {'before': values['stats'][stat], 'after': after}
                values['stats'][stat] = after
            if patch.types is not None:
                original['types'] = {'before': values['types'], 'after': patch.types}
                values['types'] = patch.types
            originals['pokemon'][str(pokemon.id)] = original
            records.append(CatalogRecord(**values))
        for patch in changes.type_matchups:
            originals['type_matchups'].append({'attack': patch.attacking_type, 'defense': patch.defending_type,
                'before': rows[patch.attacking_type][patch.defending_type], 'after': patch.multiplier})
            rows[patch.attacking_type][patch.defending_type] = patch.multiplier
        if not records:
            # Discovery must contain one record; leave it unchanged for type-only scans.
            pokemon = await session.scalar(select(Pokemon).order_by(Pokemon.id).limit(1))
            if pokemon is None:
                raise ValueError('Import the catalog before applying demo changes')
            records.append(CatalogRecord(id=pokemon.id, name=pokemon.name, types=pokemon.types,
                stats=pokemon.stats, sprite_url=pokemon.sprite_url))
        if state is None:
            state = DemoState(id=1, demo_id=uuid.uuid4(), payload=normalized, originals=originals)
            session.add(state)
        demo_id = str(state.demo_id)
    result = await run_locked_scan(sessions, api=ManualSource(records, rows), limit=len(records),
        include_types=bool(changes.type_matchups), metadata={'source': 'manual_demo', 'demo_id': demo_id})
    return result.status, {'demo_id': demo_id, **result.summary}


async def reset_changes(sessions):
    async with sessions.begin() as session:
        state = await session.get(DemoState, 1)
        if state is None:
            return 'succeeded', {'message': 'No active demo', 'removed_history': 0}
        updates = []
        for identifier, fields in state.originals['pokemon'].items():
            pokemon = await session.get(Pokemon, int(identifier))
            for field, values in fields.items():
                current = pokemon.stats[field[6:]] if field.startswith('stats.') else getattr(pokemon, field)
                if current not in (values['before'], values['after']):
                    raise ValueError('A demo field was updated by another scan. Reset refused to overwrite newer data; use a full refresh.')
                updates.append((pokemon, field, values['before']))
        chart = await session.get(TypeChart, 1)
        rows = deepcopy(chart.damage_to)
        for patch in state.originals['type_matchups']:
            current = rows[patch['attack']][patch['defense']]
            if current not in (patch['before'], patch['after']):
                raise ValueError('A demo type matchup has newer data. Reset refused; use a full refresh.')
            rows[patch['attack']][patch['defense']] = patch['before']
        for pokemon, field, before in updates:
            if field.startswith('stats.'):
                pokemon.stats = {**pokemon.stats, field[6:]: before}
            else:
                setattr(pokemon, field, before)
            pokemon.synced_at = utc_now()
        chart.damage_to, chart.version, chart.synced_at = rows, chart_version(rows), utc_now()
        # Only tagged scan events are demonstration history. Live refreshes are retained.
        runs = list(await session.scalars(select(ScanRun)))
        tagged = [run.id for run in runs if run.summary.get('demo_id') == str(state.demo_id)]
        removed = await session.execute(delete(CatalogChange).where(CatalogChange.scan_run_id.in_(tagged)))
        for run in runs:
            if run.id in tagged:
                run.summary = {**run.summary, 'demo_reset': True}
        demo_id = str(state.demo_id)
        await session.delete(state)
        now = utc_now()
        session.add(ScanRun(status='succeeded', started_at=now, finished_at=now,
            summary={'source': 'demo_reset', 'demo_id': demo_id, 'removed_history': removed.rowcount}))
    return 'succeeded', {'demo_id': demo_id, 'removed_history': removed.rowcount, 'restored_fields': len(updates)}
