"""Run explicitly: python -m app.ingest [--limit N]. Never clears the catalog."""
import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from . import db
from .catalog_sync import sync_record
from .models import Pokemon
from .pokeapi import PokeAPIClient


@dataclass
class ImportReport:
    discovered: int
    selected: int
    scope: str
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    failures: dict[int, str] = field(default_factory=dict)
    absent_ids: list[int] = field(default_factory=list)

    @property
    def failed(self):
        return len(self.failures)

    @property
    def exit_code(self):
        return 1 if self.failures else 0


async def ingest_catalog(api: PokeAPIClient, sessions, *, concurrency: int = 5,
                         limit: int | None = None, progress=None) -> ImportReport:
    if concurrency < 1 or (limit is not None and limit < 1):
        raise ValueError("Concurrency and limit must be positive")
    discovered = await api.discover()
    selected = sorted(discovered.items())
    if limit is not None:
        selected = selected[:limit]
    report = ImportReport(discovered=len(discovered), selected=len(selected),
                          scope="full" if limit is None else "sample")
    # Report removals only after complete discovery and only for a full import.
    if limit is None:
        async with sessions() as session:
            stored = set(await session.scalars(select(Pokemon.id)))
        report.absent_ids = sorted(stored - discovered.keys())
    if progress:
        progress(f"Discovered {report.discovered}; importing {report.selected} ({report.scope}).")
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch(pokemon_id, url):
        async with semaphore:
            try:
                return pokemon_id, await api.fetch_pokemon(pokemon_id, url), None
            except (httpx.HTTPError, ValueError) as error:
                return pokemon_id, None, f"{type(error).__name__}: {error}"

    tasks = [asyncio.create_task(fetch(pokemon_id, url)) for pokemon_id, url in selected]
    try:
        for completed, task in enumerate(asyncio.as_completed(tasks), start=1):
            pokemon_id, record, error = await task
            if error is None:
                try:
                    outcome = await sync_record(record, sessions)
                    setattr(report, outcome, getattr(report, outcome) + 1)
                except SQLAlchemyError as failure:
                    error = f"{type(failure).__name__}: database write failed"
            if error is not None:
                report.failures[pokemon_id] = error
            if progress and (completed % 50 == 0 or completed == len(selected)):
                progress(f"Processed {completed}/{len(selected)}; failed {report.failed}.")
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return report


async def run_cli(limit: int | None) -> int:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=10),
                                     limits=httpx.Limits(max_connections=5),
                                     headers={"User-Agent": "PokemonTeamBuilder/0.1 (catalog sync)"},
                                     follow_redirects=False) as http:
            report = await ingest_catalog(PokeAPIClient(http), db.session_maker, limit=limit,
                                           progress=lambda text: print(text, file=sys.stderr))
        print(json.dumps({**asdict(report), "failed": report.failed}, indent=2))
        return report.exit_code
    except (httpx.HTTPError, ValueError, SQLAlchemyError) as error:
        print(f"Import aborted: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    finally:
        await db.engine.dispose()


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Must be a positive integer")
    return number


def main():
    parser = argparse.ArgumentParser(description="Refresh the local Pokemon catalog from PokeAPI; never delete records.")
    parser.add_argument("--limit", type=positive_int, help="Import only the first N discovered IDs for a smoke test (partial catalog).")
    args = parser.parse_args()
    try:
        return asyncio.run(run_cli(args.limit))
    except KeyboardInterrupt:
        print("Import interrupted; committed records are preserved. Rerun to continue.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
