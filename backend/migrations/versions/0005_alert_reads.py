"""Per-user alert acknowledgements, removed when an event or account is deleted."""
from alembic import op
import sqlalchemy as sa
from fastapi_users_db_sqlalchemy.generics import GUID

revision = '0005_alert_reads'
down_revision = '0004_admin_jobs'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('alert_reads',
        sa.Column('user_id', GUID(), sa.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('change_id', GUID(), sa.ForeignKey('catalog_changes.id', ondelete='CASCADE'), primary_key=True))


def downgrade():
    op.drop_table('alert_reads')
