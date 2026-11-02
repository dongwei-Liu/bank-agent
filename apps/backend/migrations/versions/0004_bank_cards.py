"""Add ordinary debit cards and durable card authorization records."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bank_cards",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("fineract_account_id", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=100), nullable=False),
        sa.Column("alias", sa.String(length=100), nullable=False),
        sa.Column("pan_ciphertext", sa.Text(), nullable=False),
        sa.Column("last4", sa.String(length=4), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("single_limit", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("daily_limit", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("online_enabled", sa.Boolean(), nullable=False),
        sa.Column("pos_enabled", sa.Boolean(), nullable=False),
        sa.Column("atm_enabled", sa.Boolean(), nullable=False),
        sa.Column("international_enabled", sa.Boolean(), nullable=False),
        sa.Column("replaces_card_id", sa.String(length=36), nullable=True),
        sa.Column("application_action_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_action_id"], ["actions.id"]),
        sa.ForeignKeyConstraint(["replaces_card_id"], ["bank_cards.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_action_id"),
    )
    op.create_index(op.f("ix_bank_cards_user_id"), "bank_cards", ["user_id"])
    op.create_index(
        op.f("ix_bank_cards_fineract_account_id"),
        "bank_cards",
        ["fineract_account_id"],
    )
    op.create_table(
        "card_authorizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("card_id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("decline_code", sa.String(length=100), nullable=True),
        sa.Column("action_id", sa.String(length=36), nullable=True),
        sa.Column("fineract_transfer_id", sa.Integer(), nullable=True),
        sa.Column("from_transaction_id", sa.Integer(), nullable=True),
        sa.Column("to_transaction_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"]),
        sa.ForeignKeyConstraint(["card_id"], ["bank_cards.id"]),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key"),
    )
    op.create_index(
        op.f("ix_card_authorizations_card_id"),
        "card_authorizations",
        ["card_id"],
    )
    op.create_index(
        op.f("ix_card_authorizations_user_id"),
        "card_authorizations",
        ["user_id"],
    )


def downgrade():
    op.drop_index(
        op.f("ix_card_authorizations_user_id"), table_name="card_authorizations"
    )
    op.drop_index(
        op.f("ix_card_authorizations_card_id"), table_name="card_authorizations"
    )
    op.drop_table("card_authorizations")
    op.drop_index(
        op.f("ix_bank_cards_fineract_account_id"), table_name="bank_cards"
    )
    op.drop_index(op.f("ix_bank_cards_user_id"), table_name="bank_cards")
    op.drop_table("bank_cards")
