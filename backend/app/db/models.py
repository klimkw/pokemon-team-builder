"""Current account, catalog, and ordered team state. Historical records are separate."""
import uuid
from datetime import datetime, timezone
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTableUUID
from fastapi_users_db_sqlalchemy.generics import GUID, TIMESTAMPAware
from sqlalchemy import JSON, CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(SQLAlchemyBaseUserTableUUID, Base):
    @property
    def username(self) -> str:
        # The library's internal email column stores our normalized username.
        return self.email


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, Base):
    pass


class Pokemon(Base):
    __tablename__ = "pokemon"
    __table_args__ = (CheckConstraint("id > 0", name="ck_pokemon_positive_id"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    types: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    stats: Mapped[dict[str, int]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    sprite_url: Mapped[str | None] = mapped_column(String(2048))
    synced_at: Mapped[datetime] = mapped_column(TIMESTAMPAware(timezone=True), default=utc_now)


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (CheckConstraint("length(trim(name)) BETWEEN 1 AND 80", name="ck_team_name_length"),)
    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPAware(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPAware(timezone=True), default=utc_now)
    members: Mapped[list["TeamMember"]] = relationship(
        order_by="TeamMember.position", lazy="raise", cascade="all, delete-orphan", passive_deletes=True,
    )


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (CheckConstraint("position BETWEEN 0 AND 5", name="ck_team_member_position"),)
    # A Pokémon may appear more than once, but each position is unique in its team.
    team_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    pokemon_id: Mapped[int] = mapped_column(ForeignKey("pokemon.id", ondelete="RESTRICT"), index=True)
    pokemon: Mapped[Pokemon] = relationship(lazy="raise")


class ScanRun(Base):
    __tablename__ = "scan_runs"
    __table_args__ = (CheckConstraint("status IN ('running','succeeded','partial','failed','interrupted','skipped')", name="ck_scan_run_status"),)
    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMPAware(timezone=True), default=utc_now, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMPAware(timezone=True))
    status: Mapped[str] = mapped_column(String(20))
    summary: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), default=dict)
    error: Mapped[str | None] = mapped_column(String(500))


class CatalogChange(Base):
    __tablename__ = "catalog_changes"
    __table_args__ = (
        CheckConstraint("entity_kind IN ('pokemon','type')", name="ck_catalog_change_kind"),
    )
    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    scan_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("scan_runs.id", ondelete="RESTRICT"), index=True)
    entity_kind: Mapped[str] = mapped_column(String(20))
    entity_key: Mapped[str] = mapped_column(String(100))
    entity_name: Mapped[str] = mapped_column(String(100))
    detected_at: Mapped[datetime] = mapped_column(TIMESTAMPAware(timezone=True), default=utc_now, index=True)
    changes: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))


class TypeChart(Base):
    __tablename__ = "type_chart"
    __table_args__ = (CheckConstraint("id = 1", name="ck_type_chart_singleton"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    damage_to: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    version: Mapped[str] = mapped_column(String(71))
    synced_at: Mapped[datetime] = mapped_column(TIMESTAMPAware(timezone=True), default=utc_now)
