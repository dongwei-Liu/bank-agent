"""Add idempotency keys for Agent schedule and AA creation."""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("transfer_schedules") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(160), nullable=True))
        batch.create_unique_constraint(
            "uq_transfer_schedules_user_idempotency",
            ["user_id", "idempotency_key"],
        )
    with op.batch_alter_table("aa_collections") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(160), nullable=True))
        batch.add_column(sa.Column("request_hash", sa.String(64), nullable=True))
        batch.create_unique_constraint(
            "uq_aa_collections_user_idempotency",
            ["user_id", "idempotency_key"],
        )


def downgrade():
    with op.batch_alter_table("aa_collections") as batch:
        batch.drop_constraint("uq_aa_collections_user_idempotency", type_="unique")
        batch.drop_column("request_hash")
        batch.drop_column("idempotency_key")
    with op.batch_alter_table("transfer_schedules") as batch:
        batch.drop_constraint("uq_transfer_schedules_user_idempotency", type_="unique")
        batch.drop_column("idempotency_key")
