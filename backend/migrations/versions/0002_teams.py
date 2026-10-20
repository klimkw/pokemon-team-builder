"""Current Pokemon catalog and ordered teams; historical logs are a later revision."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from fastapi_users_db_sqlalchemy.generics import GUID, TIMESTAMPAware

revision = "0002_teams"
down_revision = "0001_accounts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("pokemon",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("types", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("stats", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("sprite_url", sa.String(2048), nullable=True),
        sa.Column("synced_at", TIMESTAMPAware(timezone=True), nullable=False),
        sa.CheckConstraint("id > 0", name="ck_pokemon_positive_id"))
    op.create_table("teams",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("created_at", TIMESTAMPAware(timezone=True), nullable=False),
        sa.Column("updated_at", TIMESTAMPAware(timezone=True), nullable=False),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 80", name="ck_team_name_length"))
    op.create_index("ix_teams_user_id", "teams", ["user_id"])
    op.create_table("team_members",
        sa.Column("team_id", GUID(), sa.ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("position", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("pokemon_id", sa.Integer(), sa.ForeignKey("pokemon.id", ondelete="RESTRICT"), nullable=False),
        sa.CheckConstraint("position BETWEEN 0 AND 5", name="ck_team_member_position"))
    op.create_index("ix_team_members_pokemon_id", "team_members", ["pokemon_id"])


def downgrade():
    op.drop_table("team_members")
    op.drop_table("teams")
    op.drop_table("pokemon")
