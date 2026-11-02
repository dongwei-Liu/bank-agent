"""Repair bill-report job tables when an old stamped database skipped 0007.

Revision ID: 0012
Revises: 0011

The migration is intentionally idempotent. Healthy databases already contain
both tables and are left unchanged. Its downgrade is a no-op because the
objects belong to revision 0007; downgrading this repair marker must never drop
tables that a healthy 0007 installation still owns.
"""

from alembic import op
import sqlalchemy as sa


revision = "0012"
down_revision = "0011"
branch_labels = depends_on = None


def _table_names():
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade():
    tables = _table_names()
    if "bill_report_jobs" not in tables:
        op.create_table(
            "bill_report_jobs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("report_id", sa.String(36), sa.ForeignKey("bill_reports.id"), nullable=False, unique=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("idempotency_key", sa.String(160), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("account_ids", sa.JSON(), nullable=False),
            sa.Column("dependency_account_ids", sa.JSON(), nullable=False),
            sa.Column("period", sa.String(7), nullable=False),
            sa.Column("cutoff_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("lease_until", sa.DateTime(timezone=True)),
            sa.Column("error_code", sa.String(80)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "idempotency_key"),
        )
        op.create_index("ix_bill_report_jobs_user_id", "bill_report_jobs", ["user_id"])
        op.create_index("ix_bill_report_jobs_status", "bill_report_jobs", ["status"])

    if "bill_report_transactions" not in tables:
        op.create_table(
            "bill_report_transactions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("report_id", sa.String(36), sa.ForeignKey("bill_reports.id"), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("transaction_id", sa.Integer(), nullable=False),
            sa.Column("occurred_on", sa.Date(), nullable=False),
            sa.Column("direction", sa.String(20), nullable=False),
            sa.Column("category", sa.String(120), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.UniqueConstraint("report_id", "account_id", "transaction_id"),
        )
        op.create_index("ix_bill_report_transactions_report_id", "bill_report_transactions", ["report_id"])
        op.create_index("ix_bill_report_transactions_occurred_on", "bill_report_transactions", ["occurred_on"])


def downgrade():
    pass
