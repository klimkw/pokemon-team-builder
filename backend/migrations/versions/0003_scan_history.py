"""Scan audit, append-only observed changes, and refreshable type chart baseline."""
import json
from pathlib import Path
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from fastapi_users_db_sqlalchemy.generics import GUID, TIMESTAMPAware

revision = "0003_scan_history"
down_revision = "0002_teams"
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    timestamp = TIMESTAMPAware(timezone=True)
    op.create_table("scan_runs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("started_at", timestamp, nullable=False),
        sa.Column("finished_at", timestamp, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("summary", json_type, nullable=False),
        sa.Column("error", sa.String(500), nullable=True),
        sa.CheckConstraint("status IN ('running','succeeded','partial','failed','interrupted','skipped')", name="ck_scan_run_status"))
    op.create_index("ix_scan_runs_started_at", "scan_runs", ["started_at"])
    op.create_table("catalog_changes",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("scan_run_id", GUID(), sa.ForeignKey("scan_runs.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("entity_kind", sa.String(20), nullable=False),
        sa.Column("entity_key", sa.String(100), nullable=False),
        sa.Column("entity_name", sa.String(100), nullable=False),
        sa.Column("detected_at", timestamp, nullable=False),
        sa.Column("changes", json_type, nullable=False),
        sa.CheckConstraint("entity_kind IN ('pokemon','type')", name="ck_catalog_change_kind"))
    op.create_index("ix_catalog_changes_scan_run_id", "catalog_changes", ["scan_run_id"])
    op.create_index("ix_catalog_changes_detected_at", "catalog_changes", ["detected_at"])
    op.create_table("type_chart",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("damage_to", json_type, nullable=False),
        sa.Column("version", sa.String(71), nullable=False),
        sa.Column("synced_at", timestamp, nullable=False),
        sa.CheckConstraint("id = 1", name="ck_type_chart_singleton"))
    # Frozen migration fixture; future snapshot edits must not rewrite this baseline.
    baseline = json.loads((Path(__file__).parents[1] / "data" / "type_chart_v1.json").read_text())
    table = sa.table("type_chart", sa.column("id", sa.Integer()), sa.column("damage_to", json_type),
                     sa.column("version", sa.String(71)), sa.column("synced_at", timestamp))
    op.bulk_insert(table, [{"id": 1, "damage_to": baseline["damage_to"], "version": baseline["version"],
                            "synced_at": datetime.fromisoformat(baseline["retrieved_at"])}])


def downgrade():
    op.drop_table("type_chart")
    op.drop_table("catalog_changes")
    op.drop_table("scan_runs")
