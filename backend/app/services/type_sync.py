"""Validate a complete upstream chart before replacing the active database snapshot."""
import hashlib
import json
from typing import get_args
from app.db.models import CatalogChange, TypeChart, utc_now
from app.schemas.teams import PokemonType

TYPES = tuple(get_args(PokemonType))


def chart_version(rows):
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def normalize_type(payload, expected_name):
    if payload.get("name") != expected_name:
        raise ValueError("Upstream type name does not match requested type")
    relations = payload.get("damage_relations")
    if not isinstance(relations, dict):
        raise ValueError("Missing type damage relations")
    row = dict.fromkeys(TYPES, 1)
    seen = set()
    for field, multiplier in [("no_damage_to", 0), ("half_damage_to", 0.5), ("double_damage_to", 2)]:
        values = relations.get(field)
        if not isinstance(values, list):
            raise ValueError("Incomplete type damage relations")
        for item in values:
            name = item.get("name") if isinstance(item, dict) else None
            if name in ("stellar", "unknown", "shadow"):
                continue  # The application's documented model uses 18 standard types.
            if name not in row or name in seen:
                raise ValueError("Invalid or conflicting type damage relation")
            seen.add(name)
            row[name] = multiplier
    return row


async def fetch_chart(api):
    # Fetching all 18 first prevents a partial chart from becoming active.
    return {name: normalize_type(await api.get_json(f"https://pokeapi.co/api/v2/type/{name}/"), name)
            for name in TYPES}


async def sync_chart(rows, sessions, *, scan_run_id=None):
    if set(rows) != set(TYPES) or any(set(row) != set(TYPES) or any(value not in (0, 0.5, 1, 2) for value in row.values()) for row in rows.values()):
        raise ValueError("A complete valid 18-type chart is required")
    version = chart_version(rows)
    async with sessions.begin() as session:
        chart = await session.get(TypeChart, 1)
        if chart is None:
            session.add(TypeChart(id=1, damage_to=rows, version=version, synced_at=utc_now()))
            return {"inserted": 1, "updated": 0, "unchanged": 0}
        changed_rows = 0
        for attack in TYPES:
            changes = {f"damage_to.{defense}": {"before": chart.damage_to[attack][defense], "after": rows[attack][defense]}
                       for defense in TYPES if chart.damage_to[attack][defense] != rows[attack][defense]}
            if changes:
                changed_rows += 1
                session.add(CatalogChange(scan_run_id=scan_run_id, entity_kind="type",
                    entity_key=attack, entity_name=attack, changes=changes, detected_at=utc_now()))
        chart.damage_to = rows
        chart.version = version
        chart.synced_at = utc_now()
        return {"inserted": 0, "updated": changed_rows, "unchanged": len(TYPES) - changed_rows}
