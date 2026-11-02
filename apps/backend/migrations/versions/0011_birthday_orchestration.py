"""Fixed birthday orchestration tasks and Fineract-backed reservations."""

from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "personal_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "idempotency_key"),
    )
    for column in ("user_id", "event_date", "status"):
        op.create_index(f"ix_personal_events_{column}", "personal_events", [column])

    op.create_table(
        "orchestration_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("personal_events.id"), nullable=False),
        sa.Column("template", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("from_account_id", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("authorization_action_id", sa.String(36), sa.ForeignKey("actions.id")),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "idempotency_key"),
        sa.UniqueConstraint("authorization_action_id"),
    )
    for column in ("user_id", "event_id", "status", "next_run_at", "lease_until"):
        op.create_index(
            f"ix_orchestration_tasks_{column}", "orchestration_tasks", [column]
        )

    op.create_table(
        "task_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("orchestration_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_key", sa.String(60), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("risk_level", sa.String(10), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("merchant_id", sa.String(36), sa.ForeignKey("merchants.id")),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "node_key"),
    )
    for column in ("task_id", "status", "scheduled_at", "lease_until"):
        op.create_index(f"ix_task_nodes_{column}", "task_nodes", [column])

    op.create_table(
        "task_edges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("orchestration_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_node_id", sa.String(36), sa.ForeignKey("task_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_node_id", sa.String(36), sa.ForeignKey("task_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("task_id", "from_node_id", "to_node_id"),
    )
    op.create_index("ix_task_edges_task_id", "task_edges", ["task_id"])

    op.create_table(
        "task_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("orchestration_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("task_nodes.id", ondelete="SET NULL")),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(160)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "idempotency_key"),
    )
    for column in ("task_id", "node_id", "type", "created_at"):
        op.create_index(f"ix_task_events_{column}", "task_events", [column])

    op.create_table(
        "fund_reservations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("orchestration_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("task_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("hold_transaction_id", sa.Integer()),
        sa.Column("release_transaction_id", sa.Integer()),
        sa.Column("hold_key", sa.String(160), nullable=False),
        sa.Column("release_key", sa.String(160), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "purpose"),
        sa.UniqueConstraint("node_id"),
    )
    for column in ("task_id", "user_id", "status"):
        op.create_index(f"ix_fund_reservations_{column}", "fund_reservations", [column])

    op.create_table(
        "demo_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("orchestration_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("task_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("merchant_id", sa.String(36), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("reservation_id", sa.String(36), sa.ForeignKey("fund_reservations.id"), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("fineract_transfer_id", sa.Integer()),
        sa.Column("from_transaction_id", sa.Integer()),
        sa.Column("to_transaction_id", sa.Integer()),
        sa.Column("error_code", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "idempotency_key"),
        sa.UniqueConstraint("node_id"),
    )
    for column in ("task_id", "user_id", "status", "merchant_id"):
        op.create_index(f"ix_demo_orders_{column}", "demo_orders", [column])


def downgrade():
    op.drop_table("demo_orders")
    op.drop_table("fund_reservations")
    op.drop_table("task_events")
    op.drop_table("task_edges")
    op.drop_table("task_nodes")
    op.drop_table("orchestration_tasks")
    op.drop_table("personal_events")
