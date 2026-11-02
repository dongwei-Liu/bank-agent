"""Durable subscription forecasts, reminder rules and notifications."""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "subscription_reminder_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scope", sa.String(24), nullable=False),
        sa.Column("subscription_id", sa.String(36), sa.ForeignKey("subscriptions.id")),
        sa.Column("amount_gt", sa.Numeric(20, 2)),
        sa.Column("month", sa.String(7)),
        sa.Column("lead_days", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "idempotency_key"),
    )
    op.create_index("ix_subscription_reminder_rules_user_id", "subscription_reminder_rules", ["user_id"])
    op.create_index("ix_subscription_reminder_rules_subscription_id", "subscription_reminder_rules", ["subscription_id"])
    op.create_index("ix_subscription_reminder_rules_month", "subscription_reminder_rules", ["month"])
    op.create_index("ix_subscription_reminder_rules_status", "subscription_reminder_rules", ["status"])

    op.create_table(
        "subscription_budget_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("last_evaluated_on", sa.Date()),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "month"),
        sa.UniqueConstraint("user_id", "idempotency_key"),
    )
    op.create_index("ix_subscription_budget_rules_user_id", "subscription_budget_rules", ["user_id"])
    op.create_index("ix_subscription_budget_rules_month", "subscription_budget_rules", ["month"])
    op.create_index("ix_subscription_budget_rules_status", "subscription_budget_rules", ["status"])

    op.create_table(
        "subscription_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("subscription_reminder_rules.id")),
        sa.Column("subscription_id", sa.String(36), sa.ForeignKey("subscriptions.id")),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("dedupe_key", sa.String(160), nullable=False),
        sa.Column("occurrence_date", sa.Date()),
        sa.Column("lead_days", sa.Integer()),
        sa.Column("planned_at", sa.DateTime(timezone=True)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "dedupe_key"),
    )
    for name, col in (("user_id", "user_id"), ("rule_id", "rule_id"),
                      ("subscription_id", "subscription_id"), ("kind", "kind"),
                      ("occurrence_date", "occurrence_date"), ("status", "status")):
        op.create_index(f"ix_subscription_notifications_{name}", "subscription_notifications", [col])

    op.create_table(
        "subscription_clarifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_subscription_clarifications_user_id", "subscription_clarifications", ["user_id"])
    op.create_index("ix_subscription_clarifications_status", "subscription_clarifications", ["status"])
    op.create_index("ix_subscription_clarifications_expires_at", "subscription_clarifications", ["expires_at"])

    op.create_table(
        "subscription_agent_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_subscription_agent_results_user_id", "subscription_agent_results", ["user_id"])
    op.create_index("ix_subscription_agent_results_expires_at", "subscription_agent_results", ["expires_at"])

    op.create_table(
        "subscription_mutation_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(24), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "idempotency_key"),
    )
    op.create_index("ix_subscription_mutation_keys_user_id", "subscription_mutation_keys", ["user_id"])


def downgrade():
    op.drop_table("subscription_mutation_keys")
    op.drop_table("subscription_agent_results")
    op.drop_table("subscription_clarifications")
    op.drop_table("subscription_notifications")
    op.drop_table("subscription_budget_rules")
    op.drop_table("subscription_reminder_rules")
