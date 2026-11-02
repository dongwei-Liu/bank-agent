"""Add queryable Action policy metadata and audit resource linkage."""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "actions", sa.Column("risk_level", sa.String(length=10), nullable=True)
    )
    op.add_column("actions", sa.Column("source", sa.String(length=30), nullable=True))
    op.add_column(
        "actions", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "actions", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("actions", sa.Column("version", sa.Integer(), nullable=True))
    expires = (
        "datetime(created_at, '+1 day')"
        if op.get_bind().dialect.name == "sqlite"
        else "created_at + INTERVAL '1 day'"
    )
    op.execute(
        "UPDATE actions SET risk_level = 'UNKNOWN', source = 'LEGACY', "
        f"expires_at = {expires}, updated_at = created_at, version = 1"
    )
    with op.batch_alter_table("actions") as batch:
        batch.alter_column("risk_level", nullable=False)
        batch.alter_column("source", nullable=False)
        batch.alter_column("updated_at", nullable=False)
        batch.alter_column("version", nullable=False)
    op.create_index(op.f("ix_actions_risk_level"), "actions", ["risk_level"])
    op.create_index(op.f("ix_actions_source"), "actions", ["source"])

    op.add_column(
        "audit_events", sa.Column("trace_id", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "audit_events", sa.Column("resource_type", sa.String(length=80), nullable=True)
    )
    op.add_column(
        "audit_events", sa.Column("resource_id", sa.String(length=80), nullable=True)
    )
    op.execute(
        "UPDATE audit_events AS audit SET trace_id = audit.action_id, "
        "resource_type = actions.kind, resource_id = audit.action_id "
        "FROM actions WHERE audit.action_id = actions.id"
    )
    op.create_index(op.f("ix_audit_events_trace_id"), "audit_events", ["trace_id"])
    op.create_index(
        op.f("ix_audit_events_resource_type"), "audit_events", ["resource_type"]
    )
    op.create_index(
        op.f("ix_audit_events_resource_id"), "audit_events", ["resource_id"]
    )


def downgrade():
    op.drop_index(op.f("ix_audit_events_resource_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_resource_type"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_trace_id"), table_name="audit_events")
    op.drop_column("audit_events", "resource_id")
    op.drop_column("audit_events", "resource_type")
    op.drop_column("audit_events", "trace_id")

    op.drop_index(op.f("ix_actions_source"), table_name="actions")
    op.drop_index(op.f("ix_actions_risk_level"), table_name="actions")
    op.drop_column("actions", "version")
    op.drop_column("actions", "updated_at")
    op.drop_column("actions", "expires_at")
    op.drop_column("actions", "source")
    op.drop_column("actions", "risk_level")
