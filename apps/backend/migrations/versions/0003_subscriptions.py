"""Add deterministic subscription detection and cancellation state."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "merchants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("external_key", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("adapter_type", sa.String(length=40), nullable=False),
        sa.Column("fineract_account_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_key"),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("cadence", sa.String(length=20), nullable=False),
        sa.Column("expected_amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("amount_tolerance", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("next_charge_at", sa.Date(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("rule_version", sa.String(length=30), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ignored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"]),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "merchant_id", "cadence"),
    )
    op.create_index(
        op.f("ix_subscriptions_merchant_id"),
        "subscriptions",
        ["merchant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subscriptions_user_id"),
        "subscriptions",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "subscription_occurrences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subscription_id", "account_id", "transaction_id"),
    )
    op.create_index(
        op.f("ix_subscription_occurrences_subscription_id"),
        "subscription_occurrences",
        ["subscription_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_subscription_occurrences_subscription_id"),
        table_name="subscription_occurrences",
    )
    op.drop_table("subscription_occurrences")
    op.drop_index(op.f("ix_subscriptions_user_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_merchant_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("merchants")
