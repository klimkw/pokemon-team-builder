"""PokéAPI HTTP client and pure normalization, independent of database writes."""
import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Awaitable, Callable, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field, HttpUrl
from .team_schemas import PokemonStats, PokemonType

CATALOG_URL = "https://pokeapi.co/api/v2/pokemon/?limit=200"
STAT_NAMES = {"hp", "attack", "defense", "special-attack", "special-defense", "speed"}


class NamedResource(BaseModel):
    name: str
    url: str


class CatalogPage(BaseModel):
    count: int = Field(strict=True, ge=0)
    next: str | None
    results: list[NamedResource]


class TypeName(BaseModel):
    name: PokemonType


class TypeSlot(BaseModel):
    slot: Literal[1, 2]
    type: TypeName


class StatName(BaseModel):
    name: str


class StatEntry(BaseModel):
    base_stat: int = Field(strict=True, ge=0)
    stat: StatName


class Sprites(BaseModel):
    front_default: HttpUrl | None


class PokemonPayload(BaseModel):
    id: int = Field(strict=True, gt=0)
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    types: list[TypeSlot] = Field(min_length=1, max_length=2)
    stats: list[StatEntry] = Field(min_length=6, max_length=6)
    sprites: Sprites


class CatalogRecord(BaseModel):
    id: int
    name: str
    types: list[PokemonType]
    stats: PokemonStats
    sprite_url: str | None = Field(max_length=2048)


def normalize_pokemon(payload: dict, expected_id: int) -> CatalogRecord:
    """Reject incomplete records; normalize only fields used by the application."""
    pokemon = PokemonPayload.model_validate(payload)
    if pokemon.id != expected_id:
        raise ValueError(f"Detail ID {pokemon.id} does not match requested ID {expected_id}")
    slots = sorted(pokemon.types, key=lambda item: item.slot)
    if [item.slot for item in slots] != list(range(1, len(slots) + 1)):
        raise ValueError("Type slots must be consecutive and unique")
    types = [item.type.name for item in slots]
    if len(set(types)) != len(types):
        raise ValueError("Pokemon types must be distinct")
    stats = {entry.stat.name: entry.base_stat for entry in pokemon.stats}
    if set(stats) != STAT_NAMES:
        raise ValueError("Exactly six distinct required base stats are needed")
    return CatalogRecord(id=pokemon.id, name=pokemon.name, types=types,
                         stats=PokemonStats(**{key.replace("-", "_"): value for key, value in stats.items()}),
                         sprite_url=str(pokemon.sprites.front_default) if pokemon.sprites.front_default else None)


def checked_url(url: str, *, detail: bool) -> int | None:
    """Only follow URLs inside the expected PokéAPI resource, including pagination."""
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc != "pokeapi.co" or parts.fragment):
        raise ValueError("Unexpected PokéAPI URL")
    path = parts.path.rstrip("/")
    if not detail and path == "/api/v2/pokemon":
        return None
    prefix = "/api/v2/pokemon/"
    if detail and path.startswith(prefix) and not parts.query:
        suffix = path[len(prefix):]
        if suffix.isascii() and suffix.isdigit() and int(suffix) > 0:
            return int(suffix)
    raise ValueError("Unexpected PokéAPI resource URL")


class PokeAPIClient:
    def __init__(self, http: httpx.AsyncClient, *, attempts: int = 3,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        self.http = http
        self.attempts = attempts
        self.sleep = sleep

    async def get_json(self, url: str):
        for attempt in range(self.attempts):
            try:
                response = await self.http.get(url)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as error:
                retryable = error.response.status_code == 429 or 500 <= error.response.status_code < 600
                if not retryable or attempt + 1 == self.attempts:
                    raise
                delay = self.retry_delay(error.response, attempt)
            except httpx.TransportError:
                if attempt + 1 == self.attempts:
                    raise
                delay = 2 ** attempt
            await self.sleep(delay)
        raise RuntimeError("Retry attempts exhausted")

    @staticmethod
    def retry_delay(response: httpx.Response, attempt: int) -> float:
        header = response.headers.get("Retry-After")
        if header:
            try:
                delay = float(header)
            except ValueError:
                try:
                    date = parsedate_to_datetime(header)
                    if date.tzinfo is None:
                        date = date.replace(tzinfo=timezone.utc)
                    delay = (date - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    delay = 2 ** attempt
            # Don't ignore an upstream request for a long pause or block indefinitely.
            # Fail this record so a later run can retry after the requested interval.
            if delay > 60:
                raise ValueError("PokéAPI requested Retry-After >60s; retry the import later")
            if 0 <= delay <= 60:
                return delay
        return 2 ** attempt

    async def discover(self) -> dict[int, str]:
        """Complete discovery before any writes; detect repeated pagination links."""
        url: str | None = CATALOG_URL
        seen_pages: set[str] = set()
        entries: dict[int, str] = {}
        expected_count: int | None = None
        while url is not None:
            checked_url(url, detail=False)
            if url in seen_pages:
                raise ValueError("PokéAPI pagination repeated a page")
            seen_pages.add(url)
            page = CatalogPage.model_validate(await self.get_json(url))
            if expected_count is None:
                expected_count = page.count
            if page.count != expected_count:
                raise ValueError("PokéAPI catalog changed during discovery; retry the import")
            if page.next is not None and not page.results:
                raise ValueError("Empty catalog page has a next link")
            for item in page.results:
                pokemon_id = checked_url(item.url, detail=True)
                entries[pokemon_id] = item.url
            url = page.next
        if not entries:
            raise ValueError("PokéAPI returned an empty catalog; existing data was not changed")
        if len(entries) != expected_count:
            raise ValueError("Discovered catalog size does not match the reported count")
        return entries

    async def fetch_pokemon(self, pokemon_id: int, url: str) -> CatalogRecord:
        checked_url(url, detail=True)
        return normalize_pokemon(await self.get_json(url), pokemon_id)
