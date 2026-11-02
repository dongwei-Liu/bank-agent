"""Bind one short-lived risk assessment to one fixed-deposit purchase."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("risk_assessments") as batch:
        batch.add_column(
            sa.Column(
                "purpose",
                sa.String(length=30),
                nullable=False,
                server_default="legacy",
            )
        )
        batch.add_column(sa.Column("used_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("action_id", sa.String(length=36)))
        batch.create_foreign_key(
            "fk_risk_assessments_action_id_actions",
            "actions",
            ["action_id"],
            ["id"],
        )
        batch.create_unique_constraint(
            "uq_risk_assessments_action_id", ["action_id"]
        )
    with op.batch_alter_table("risk_assessments") as batch:
        batch.alter_column("purpose", server_default=None)


def downgrade():
    with op.batch_alter_table("risk_assessments") as batch:
        batch.drop_constraint("uq_risk_assessments_action_id", type_="unique")
        batch.drop_constraint(
            "fk_risk_assessments_action_id_actions", type_="foreignkey"
        )
        batch.drop_column("action_id")
        batch.drop_column("used_at")
        batch.drop_column("purpose")
