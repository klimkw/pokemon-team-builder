"""Retire the reserved public reviewer identity without cascading away saved data.

Downgrading never restores public credentials, privileges or revoked sessions.
"""
import uuid
from alembic import op
import sqlalchemy as sa
from fastapi_users_db_sqlalchemy.generics import GUID

revision = '0006_retire_reviewer'
down_revision = '0005_alert_reads'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    # Historical identity, not a username match: personal admin accounts are untouched.
    account_id = uuid.UUID('00000000-0000-4000-8000-000000000003')
    users = sa.table('user', sa.column('id', GUID()),
                     sa.column('is_active', sa.Boolean()), sa.column('is_superuser', sa.Boolean()))
    tokens = sa.table('accesstoken', sa.column('user_id', GUID()))
    teams = sa.table('teams', sa.column('user_id', GUID()))
    reads = sa.table('alert_reads', sa.column('user_id', GUID()))
    jobs = sa.table('admin_jobs', sa.column('requested_by', GUID()), sa.column('status', sa.String()),
                    sa.column('finished_at', sa.DateTime(timezone=True)), sa.column('error', sa.String()))
    if connection.scalar(sa.select(users.c.id).where(users.c.id == account_id)) is None:
        return
    connection.execute(users.update().where(users.c.id == account_id).values(is_active=False, is_superuser=False))
    connection.execute(tokens.delete().where(tokens.c.user_id == account_id))
    connection.execute(jobs.update().where(jobs.c.requested_by == account_id, jobs.c.status == 'queued')
        .values(status='interrupted', finished_at=sa.func.now(), error='Requester retired before execution'))
    for table, owner in ((teams, teams.c.user_id), (reads, reads.c.user_id), (jobs, jobs.c.requested_by)):
        if connection.scalar(sa.select(sa.func.count()).select_from(table).where(owner == account_id)):
            return  # Preserve the inactive owner and every dependent saved record.
    connection.execute(users.delete().where(users.c.id == account_id))


def downgrade():
    # Intentional one-way security cleanup; schema is unchanged.
    pass
