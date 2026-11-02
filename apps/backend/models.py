"""Bank Agent-owned data only. No mappings to Fineract tables."""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from core.security import now


def uid():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    client_id: Mapped[int] = mapped_column(Integer, unique=True)
    tenant: Mapped[str] = mapped_column(String(80))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    otp_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    login_failures: Mapped[int] = mapped_column(Integer, default=0)
    login_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginSession(Base):
    __tablename__ = "login_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    access_hash: Mapped[str] = mapped_column(String(64), unique=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    access_expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    refresh_expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class AgentConversation(Base):
    """User-owned durable Agent conversation; never stores credentials or OTPs."""

    __tablename__ = "agent_conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="新对话")
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    trusted_refs: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}


class AgentMessage(Base):
    __tablename__ = "agent_messages"
    __table_args__ = (UniqueConstraint("conversation_id", "sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    sequence: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    user_message_id: Mapped[str] = mapped_column(ForeignKey("agent_messages.id"))
    assistant_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_messages.id")
    )
    trace_id: Mapped[str] = mapped_column(String(64), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}


class AgentEvent(Base):
    __tablename__ = "agent_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(80), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="SET NULL"), index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True
    )
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="INFO")
    outcome: Mapped[str] = mapped_column(String(30))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )


class SecurityLock(Base):
    __tablename__ = "security_locks"
    __table_args__ = (UniqueConstraint("user_id", "scope"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    scope: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(100))
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}


class Recipient(Base):
    __tablename__ = "recipients"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(30), default="")
    alias: Mapped[str] = mapped_column(String(100), default="")
    account_id: Mapped[int] = mapped_column(Integer)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Action(Base):
    __tablename__ = "actions"
    __table_args__ = (UniqueConstraint("user_id", "kind", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(40), default="WAITING_CONFIRMATION", index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0)
    risk_level: Mapped[str] = mapped_column(
        String(10), default="UNKNOWN", index=True
    )
    source: Mapped[str] = mapped_column(String(30), default="API", index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    steps: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(100))
    quota_date: Mapped[datetime | None] = mapped_column(Date)
    reserved: Mapped[bool] = mapped_column(Boolean, default=False)
    otp_hash: Mapped[str | None] = mapped_column(String(64))
    otp_nonce: Mapped[str | None] = mapped_column(String(100))
    otp_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    otp_attempts: Mapped[int] = mapped_column(Integer, default=0)
    dev_otp: Mapped[str | None] = mapped_column(String(6))

    __mapper_args__ = {"version_id_col": version}


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (UniqueConstraint("user_id", "day"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    day: Mapped[datetime] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0)


class Schedule(Base):
    __tablename__ = "transfer_schedules"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(40), default="DRAFT")
    next_run: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    authorization_action_id: Mapped[str | None] = mapped_column(
        ForeignKey("actions.id")
    )
    authorization_hash: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(160))


class ScheduleRun(Base):
    __tablename__ = "schedule_runs"
    __table_args__ = (UniqueConstraint("schedule_id", "scheduled_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    schedule_id: Mapped[str] = mapped_column(
        ForeignKey("transfer_schedules.id"), index=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40))
    action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"))


class AACollection(Base):
    __tablename__ = "aa_collections"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    status: Mapped[str] = mapped_column(String(40), default="OPEN")
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    request_hash: Mapped[str | None] = mapped_column(String(64))


class AAShare(Base):
    __tablename__ = "aa_shares"
    __table_args__ = (UniqueConstraint("collection_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    collection_id: Mapped[str] = mapped_column(
        ForeignKey("aa_collections.id"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    status: Mapped[str] = mapped_column(String(40), default="UNPAID")
    action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"))


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100))


class ClassificationRule(Base):
    __tablename__ = "classification_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"))
    field: Mapped[str] = mapped_column(String(30))
    contains: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=0)


class Annotation(Base):
    __tablename__ = "transaction_annotations"
    __table_args__ = (UniqueConstraint("user_id", "account_id", "transaction_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    account_id: Mapped[int] = mapped_column(Integer)
    transaction_id: Mapped[int] = mapped_column(Integer)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"))
    merchant: Mapped[str | None] = mapped_column(String(100))
    note: Mapped[str] = mapped_column(String(500), default="")


class BillReport(Base):
    __tablename__ = "bill_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BillReportJob(Base):
    __tablename__ = "bill_report_jobs"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    report_id: Mapped[str] = mapped_column(ForeignKey("bill_reports.id"), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[str] = mapped_column(String(64))
    account_ids: Mapped[list] = mapped_column(JSON)
    dependency_account_ids: Mapped[list] = mapped_column(JSON)
    period: Mapped[str] = mapped_column(String(7))
    cutoff_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class BillReportTransaction(Base):
    __tablename__ = "bill_report_transactions"
    __table_args__ = (UniqueConstraint("report_id", "account_id", "transaction_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    report_id: Mapped[str] = mapped_column(ForeignKey("bill_reports.id"), index=True)
    account_id: Mapped[int] = mapped_column(Integer)
    transaction_id: Mapped[int] = mapped_column(Integer)
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    direction: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSON)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    scope_hash: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    summary: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AnomalyModel(Base):
    __tablename__ = "anomaly_models"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    as_of: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(40))
    metadata_: Mapped[dict] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AnomalyReview(Base):
    __tablename__ = "anomaly_reviews"
    __table_args__ = (UniqueConstraint("user_id", "anomaly_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    anomaly_key: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    answers: Mapped[list] = mapped_column(JSON)
    score: Mapped[int] = mapped_column(Integer)
    level: Mapped[int] = mapped_column(Integer)
    version: Mapped[str] = mapped_column(String(20), default="demo-v1")
    purpose: Mapped[str] = mapped_column(String(30), default="subscription")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    action_id: Mapped[str | None] = mapped_column(
        ForeignKey("actions.id"), unique=True
    )


class ProductMetadata(Base):
    __tablename__ = "product_metadata"
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant: Mapped[str] = mapped_column(String(80))
    risk_level: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    allows_premature: Mapped[bool] = mapped_column(Boolean, default=False)


class Merchant(Base):
    __tablename__ = "merchants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    external_key: Mapped[str] = mapped_column(String(160), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(100), default="未分类")
    adapter_type: Mapped[str] = mapped_column(String(40), default="demo_subscription")
    fineract_account_id: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "merchant_id", "cadence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="CANDIDATE")
    cadence: Mapped[str] = mapped_column(String(20))
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    amount_tolerance: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0.1000")
    )
    next_charge_at: Mapped[date | None] = mapped_column(Date)
    evidence: Mapped[dict] = mapped_column(JSON)
    rule_version: Mapped[str] = mapped_column(String(30), default="subscription-v1")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ignored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class SubscriptionOccurrence(Base):
    __tablename__ = "subscription_occurrences"
    __table_args__ = (
        UniqueConstraint("subscription_id", "account_id", "transaction_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    subscription_id: Mapped[str] = mapped_column(
        ForeignKey("subscriptions.id"), index=True
    )
    account_id: Mapped[int] = mapped_column(Integer)
    transaction_id: Mapped[int] = mapped_column(Integer)
    occurred_on: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))


class SubscriptionReminderRule(Base):
    """Persistent, user-owned in-app renewal reminder rule."""
    __tablename__ = "subscription_reminder_rules"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    scope: Mapped[str] = mapped_column(String(24))
    subscription_id: Mapped[str | None] = mapped_column(
        ForeignKey("subscriptions.id"), index=True
    )
    amount_gt: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    month: Mapped[str | None] = mapped_column(String(7), index=True)
    lead_days: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class SubscriptionBudgetRule(Base):
    __tablename__ = "subscription_budget_rules"
    __table_args__ = (
        UniqueConstraint("user_id", "month"),
        UniqueConstraint("user_id", "idempotency_key"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    last_evaluated_on: Mapped[date | None] = mapped_column(Date)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class SubscriptionNotification(Base):
    __tablename__ = "subscription_notifications"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("subscription_reminder_rules.id"), index=True
    )
    subscription_id: Mapped[str | None] = mapped_column(
        ForeignKey("subscriptions.id"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(160))
    occurrence_date: Mapped[date | None] = mapped_column(Date, index=True)
    lead_days: Mapped[int | None] = mapped_column(Integer)
    planned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SubscriptionClarification(Base):
    __tablename__ = "subscription_clarifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SubscriptionAgentResult(Base):
    __tablename__ = "subscription_agent_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SubscriptionMutationKey(Base):
    __tablename__ = "subscription_mutation_keys"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(24))
    resource_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BankCard(Base):
    __tablename__ = "bank_cards"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    fineract_account_id: Mapped[int] = mapped_column(Integer, index=True)
    product_name: Mapped[str] = mapped_column(String(100))
    alias: Mapped[str] = mapped_column(String(100), default="")
    pan_ciphertext: Mapped[str] = mapped_column(Text)
    last4: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(30), default="PENDING_ACTIVATION")
    single_limit: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("5000.00")
    )
    daily_limit: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("20000.00")
    )
    online_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    pos_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    atm_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    international_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    replaces_card_id: Mapped[str | None] = mapped_column(ForeignKey("bank_cards.id"))
    application_action_id: Mapped[str] = mapped_column(
        ForeignKey("actions.id"), unique=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class CardAuthorization(Base):
    __tablename__ = "card_authorizations"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("bank_cards.id"), index=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    channel: Mapped[str] = mapped_column(String(20))
    country_code: Mapped[str] = mapped_column(String(2), default="CN")
    status: Mapped[str] = mapped_column(String(30))
    decline_code: Mapped[str | None] = mapped_column(String(100))
    action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"))
    fineract_transfer_id: Mapped[int | None] = mapped_column(Integer)
    from_transaction_id: Mapped[int | None] = mapped_column(Integer)
    to_transaction_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class PersonalEvent(Base):
    __tablename__ = "personal_events"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="BIRTHDAY")
    label: Mapped[str] = mapped_column(String(120))
    event_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class OrchestrationTask(Base):
    __tablename__ = "orchestration_tasks"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key"),
        UniqueConstraint("authorization_action_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("personal_events.id"), index=True)
    template: Mapped[str] = mapped_column(String(40), default="BIRTHDAY_GIFTS_V1")
    status: Mapped[str] = mapped_column(
        String(30), default="WAITING_AUTHORIZATION", index=True
    )
    from_account_id: Mapped[int] = mapped_column(Integer)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    authorization_action_id: Mapped[str | None] = mapped_column(
        ForeignKey("actions.id")
    )
    plan_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[str] = mapped_column(String(64))
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )

    __mapper_args__ = {"version_id_col": version}


class TaskNode(Base):
    __tablename__ = "task_nodes"
    __table_args__ = (UniqueConstraint("task_id", "node_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("orchestration_tasks.id", ondelete="CASCADE"), index=True
    )
    node_key: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    risk_level: Mapped[str] = mapped_column(String(10), default="GREEN")
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0)
    merchant_id: Mapped[str | None] = mapped_column(ForeignKey("merchants.id"))
    fingerprint: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class TaskEdge(Base):
    __tablename__ = "task_edges"
    __table_args__ = (UniqueConstraint("task_id", "from_node_id", "to_node_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("orchestration_tasks.id", ondelete="CASCADE"), index=True
    )
    from_node_id: Mapped[str] = mapped_column(
        ForeignKey("task_nodes.id", ondelete="CASCADE")
    )
    to_node_id: Mapped[str] = mapped_column(
        ForeignKey("task_nodes.id", ondelete="CASCADE")
    )


class TaskEvent(Base):
    __tablename__ = "task_events"
    __table_args__ = (UniqueConstraint("task_id", "idempotency_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("orchestration_tasks.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[str | None] = mapped_column(
        ForeignKey("task_nodes.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[str] = mapped_column(String(80), index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )


class FundReservation(Base):
    __tablename__ = "fund_reservations"
    __table_args__ = (
        UniqueConstraint("task_id", "purpose"),
        UniqueConstraint("node_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("orchestration_tasks.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[str] = mapped_column(
        ForeignKey("task_nodes.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(30))
    account_id: Mapped[int] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    hold_transaction_id: Mapped[int | None] = mapped_column(Integer)
    release_transaction_id: Mapped[int | None] = mapped_column(Integer)
    hold_key: Mapped[str] = mapped_column(String(160))
    release_key: Mapped[str] = mapped_column(String(160))
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class DemoOrder(Base):
    __tablename__ = "demo_orders"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key"),
        UniqueConstraint("node_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("orchestration_tasks.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[str] = mapped_column(
        ForeignKey("task_nodes.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    reservation_id: Mapped[str] = mapped_column(ForeignKey("fund_reservations.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[str] = mapped_column(String(64))
    fineract_transfer_id: Mapped[int | None] = mapped_column(Integer)
    from_transaction_id: Mapped[int | None] = mapped_column(Integer)
    to_transaction_id: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class Audit(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action_id: Mapped[str | None] = mapped_column(String(36))
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(80), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(80), index=True)
    event: Mapped[str] = mapped_column(String(80))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
