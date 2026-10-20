"""Durable admin job queue and bounded reversible demo changes."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from fastapi_users_db_sqlalchemy.generics import GUID, TIMESTAMPAware

revision = '0004_admin_jobs'
down_revision = '0003_scan_history'
branch_labels = None
depends_on = None


def upgrade():
    j = sa.JSON().with_variant(JSONB(), 'postgresql')
    ts = TIMESTAMPAware(timezone=True)
    op.create_table('admin_jobs',
        sa.Column('id', GUID(), primary_key=True),
        sa.Column('requested_by', GUID(), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('payload', j, nullable=False), sa.Column('result', j, nullable=False),
        sa.Column('error', sa.String(500)), sa.Column('created_at', ts, nullable=False),
        sa.Column('started_at', ts), sa.Column('finished_at', ts),
        sa.CheckConstraint("action IN ('refresh','demo_apply','demo_reset')", name='ck_admin_job_action'),
        sa.CheckConstraint("status IN ('queued','running','succeeded','partial','failed','interrupted')", name='ck_admin_job_status'))
    op.create_index('ix_admin_jobs_status', 'admin_jobs', ['status'])
    op.create_table('demo_state', sa.Column('id', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('demo_id', GUID(), nullable=False), sa.Column('payload', j, nullable=False),
        sa.Column('originals', j, nullable=False), sa.CheckConstraint('id = 1', name='ck_demo_state_singleton'))


def downgrade():
    op.drop_table('demo_state')
    op.drop_index('ix_admin_jobs_status', table_name='admin_jobs')
    op.drop_table('admin_jobs')
