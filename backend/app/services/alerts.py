"""Compute relevance at read time; no per-user alert copies or history pruning."""
from datetime import timedelta
from sqlalchemy import and_, or_, select
from app.db.models import AlertRead, CatalogChange, Pokemon, ScanRun, Team, TeamMember, utc_now
from app.schemas.alerts import AlertPage, ChangeAlert, ScanStatus
from app.settings import CHANGE_ALERT_WINDOW_DAYS, DEMO_MODE


async def get_alerts(session, user_id, *, limit=20, offset=0, now=None,
                     window_days=CHANGE_ALERT_WINDOW_DAYS):
    now = now or utc_now()
    since = now - timedelta(days=window_days)
    rows = (await session.execute(select(Team, TeamMember, Pokemon)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .join(Pokemon, Pokemon.id == TeamMember.pokemon_id)
        .where(Team.user_id == user_id).order_by(Team.id, TeamMember.position))).all()
    members = {}
    for team, member, pokemon in rows:
        entry = members.setdefault(pokemon.id, {"pokemon": pokemon, "teams": {}})
        reference = entry["teams"].setdefault(team.id, {"id": team.id, "name": team.name, "positions": []})
        reference["positions"].append(member.position)
    latest = await session.scalar(select(ScanRun).order_by(ScanRun.started_at.desc(), ScanRun.id.desc()).limit(1))
    read_ids = set(await session.scalars(select(AlertRead.change_id).where(AlertRead.user_id == user_id)))
    alerts = []
    if members:
        candidates = await session.execute(select(CatalogChange, ScanRun.summary).outerjoin(ScanRun, ScanRun.id == CatalogChange.scan_run_id).where(
            CatalogChange.detected_at >= since, CatalogChange.detected_at <= now,
            or_(CatalogChange.entity_kind == "type", and_(CatalogChange.entity_kind == "pokemon",
                CatalogChange.entity_key.in_([str(key) for key in members]))))
            .order_by(CatalogChange.detected_at.desc(), CatalogChange.id.desc()))
        for change, scan_summary in candidates:
            affected, relevant_fields = [], set()
            for pokemon_id, member in members.items():
                pokemon = member["pokemon"]
                reasons = []
                if change.entity_kind == "pokemon" and change.entity_key == str(pokemon_id):
                    reasons.append("catalog")
                    relevant_fields.update(change.changes)
                elif change.entity_kind == "type":
                    if change.entity_key in pokemon.types:
                        reasons.append("attacking_type")
                        relevant_fields.update(change.changes)
                    defenses = {field for field in change.changes
                                if field.removeprefix("damage_to.") in pokemon.types}
                    if defenses:
                        reasons.append("defending_type")
                        relevant_fields.update(defenses)
                if reasons:
                    affected.append({"id": pokemon_id, "name": pokemon.name, "types": pokemon.types, "reasons": reasons,
                                     "teams": list(member["teams"].values())})
            if affected:
                alerts.append(ChangeAlert(is_read=change.id in read_ids, is_manual_demo=(scan_summary or {}).get("source") == "manual_demo", id=change.id, entity_kind=change.entity_kind,
                    entity_name=change.entity_name, detected_at=change.detected_at,
                    changes={key: value for key, value in change.changes.items() if key in relevant_fields},
                    affected=affected))
    return AlertPage(unread_total=sum(not alert.is_read for alert in alerts), is_demo=DEMO_MODE, items=alerts[offset:offset + limit], total=len(alerts), limit=limit, offset=offset,
                     window_days=window_days, since=since, as_of=now,
                     latest_scan=ScanStatus.model_validate(latest) if latest else None)
