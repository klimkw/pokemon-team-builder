"""Select relevant events in SQL; render only the requested page and its histories."""
from datetime import timedelta
from uuid import UUID
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AlertRead, CatalogChange, Pokemon, ScanRun, Team, TeamMember, utc_now
from app.schemas.alerts import AlertPage, ChangeAlert, FieldHistory, ScanStatus
from app.settings import CHANGE_ALERT_WINDOW_DAYS, DEMO_MODE


def relevant_changes(pokemon_ids: set[int], types: set[str], since, now):
    """The same relevance predicate serves pages, counts, and acknowledgements."""
    defenses = [CatalogChange.changes[f'damage_to.{kind}']['before'].as_float().is_not(None)
                for kind in sorted(types)]
    return and_(
        CatalogChange.detected_at.between(since, now),
        or_(
            and_(CatalogChange.entity_kind == 'pokemon',
                 CatalogChange.entity_key.in_([str(key) for key in pokemon_ids])),
            and_(CatalogChange.entity_kind == 'type',
                 or_(CatalogChange.entity_key.in_(types), *defenses)),
        ),
    )


async def relevant_change_ids(session: AsyncSession, user_id: UUID, change_ids: list[UUID]) -> list[UUID]:
    if not change_ids:
        return []
    rows = (await session.execute(select(Pokemon.id, Pokemon.types)
        .join(TeamMember, TeamMember.pokemon_id == Pokemon.id)
        .join(Team, Team.id == TeamMember.team_id).where(Team.user_id == user_id))).all()
    ids = {identifier for identifier, _ in rows}
    types = {kind for _, kinds in rows for kind in kinds}
    now = utc_now()
    return list(await session.scalars(select(CatalogChange.id).where(
        CatalogChange.id.in_(set(change_ids)),
        relevant_changes(ids, types, now - timedelta(days=CHANGE_ALERT_WINDOW_DAYS), now))))


def affected_members(change: CatalogChange, members: dict) -> tuple[list[dict], set[str]]:
    affected, fields = [], set()
    for pokemon_id, member in members.items():
        pokemon = member['pokemon']
        reasons = []
        if change.entity_kind == 'pokemon' and change.entity_key == str(pokemon_id):
            reasons.append('catalog')
            fields.update(change.changes)
        elif change.entity_kind == 'type':
            if change.entity_key in pokemon.types:
                reasons.append('attacking_type')
                fields.update(change.changes)
            defenses = {field for field in change.changes
                        if field.removeprefix('damage_to.') in pokemon.types}
            if defenses:
                reasons.append('defending_type')
                fields.update(defenses)
        if reasons:
            affected.append({'id': pokemon_id, 'name': pokemon.name, 'types': pokemon.types,
                             'reasons': reasons, 'teams': list(member['teams'].values())})
    return affected, fields


async def get_alerts(session: AsyncSession, user_id: UUID, *, limit=20, offset=0, now=None,
                     window_days=CHANGE_ALERT_WINDOW_DAYS) -> AlertPage:
    now = now or utc_now()
    since = now - timedelta(days=window_days)
    rows = (await session.execute(select(Team, TeamMember, Pokemon)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .join(Pokemon, Pokemon.id == TeamMember.pokemon_id)
        .where(Team.user_id == user_id).order_by(Team.id, TeamMember.position))).all()
    members = {}
    for team, member, pokemon in rows:
        entry = members.setdefault(pokemon.id, {'pokemon': pokemon, 'teams': {}})
        reference = entry['teams'].setdefault(team.id, {'id': team.id, 'name': team.name, 'positions': []})
        reference['positions'].append(member.position)
    types = {kind for member in members.values() for kind in member['pokemon'].types}
    relevant = relevant_changes(set(members), types, since, now)
    is_read = select(AlertRead.change_id).where(
        AlertRead.user_id == user_id, AlertRead.change_id == CatalogChange.id).exists()
    total = await session.scalar(select(func.count()).select_from(CatalogChange).where(relevant))
    unread_total = await session.scalar(select(func.count()).select_from(CatalogChange).where(relevant, ~is_read))
    ordering = (CatalogChange.detected_at.desc(), CatalogChange.id.desc())
    page = await session.execute(select(CatalogChange, ScanRun.summary, is_read)
        .outerjoin(ScanRun, ScanRun.id == CatalogChange.scan_run_id).where(relevant)
        .order_by(*ordering).limit(limit).offset(offset))
    alerts = []
    history_fields = {}
    for change, scan_summary, read in page:
        affected, fields = affected_members(change, members)
        identity = (change.entity_kind, change.entity_key)
        history_fields.setdefault(identity, set()).update(fields)
        alerts.append((identity, ChangeAlert(
            is_read=read, is_manual_demo=(scan_summary or {}).get('source') == 'manual_demo',
            id=change.id, entity_kind=change.entity_kind, entity_name=change.entity_name,
            detected_at=change.detected_at, changes={key: change.changes[key] for key in fields},
            affected=affected)))
    histories = {}
    if history_fields:
        # Full-window histories remain available, but only for entities on this page.
        identities = [and_(CatalogChange.entity_kind == kind, CatalogChange.entity_key == key)
                      for kind, key in history_fields]
        changes = await session.scalars(select(CatalogChange).where(relevant, or_(*identities)).order_by(*ordering))
        for change in changes:
            identity = (change.entity_kind, change.entity_key)
            for field in history_fields[identity] & change.changes.keys():
                histories.setdefault((*identity, field), []).append(FieldHistory(
                    id=change.id, detected_at=change.detected_at, **change.changes[field]))
    for identity, alert in alerts:
        alert.history = {field: histories[(*identity, field)] for field in alert.changes}
    latest = await session.scalar(select(ScanRun).order_by(ScanRun.started_at.desc(), ScanRun.id.desc()).limit(1))
    return AlertPage(unread_total=unread_total, is_demo=DEMO_MODE, items=[alert for _, alert in alerts],
                     total=total, limit=limit, offset=offset, window_days=window_days, since=since,
                     as_of=now, latest_scan=ScanStatus.model_validate(latest) if latest else None)
