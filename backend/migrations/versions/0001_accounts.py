"""Baseline matching the FastAPI Users account scaffold."""
from alembic import op
import sqlalchemy as sa
from fastapi_users_db_sqlalchemy.generics import GUID, TIMESTAMPAware

revision = "0001_accounts"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("user",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False))
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_table("accesstoken",
        sa.Column("user_id", GUID(), sa.ForeignKey("user.id", ondelete="cascade"), nullable=False),
        sa.Column("token", sa.String(43), primary_key=True),
        sa.Column("created_at", TIMESTAMPAware(timezone=True), nullable=False))
    op.create_index("ix_accesstoken_created_at", "accesstoken", ["created_at"])


def downgrade():
    op.drop_table("accesstoken")
    op.drop_table("user")
