from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

Amount = Annotated[
    Decimal,
    Field(gt=0, max_digits=18, decimal_places=2),
    AfterValidator(lambda value: value.quantize(Decimal(".01"))),
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginRequest(Contract):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(Contract):
    refresh_token: str = Field(min_length=20, max_length=200)


class RecipientRequest(Contract):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(default="", max_length=30)
    alias: str = Field(default="", max_length=100)
    account_id: int = Field(gt=0)


class TransferRequest(Contract):
    from_account_id: int = Field(gt=0)
    recipient_id: str
    amount: Amount
    currency: Literal["CNY"] = "CNY"
    remark: str = Field(default="", max_length=500)


class InternalTransferRequest(Contract):
    from_account_id: int = Field(gt=0)
    to_account_id: int = Field(gt=0)
    amount: Amount
    currency: Literal["CNY"] = "CNY"
    remark: str = Field(default="", max_length=500)


class ConfirmRequest(Contract):
    request_hash: str = Field(min_length=64, max_length=64)


class VerifyRequest(Contract):
    code: str = Field(pattern=r"^\d{6}$")


class CardApplicationRequest(Contract):
    product_name: str = Field(default="智汇借记卡", min_length=1, max_length=100)
    alias: str = Field(default="", max_length=100)


class CardAliasRequest(Contract):
    alias: str = Field(default="", max_length=100)


class CardControlsRequest(Contract):
    single_limit: Decimal | None = Field(
        default=None, gt=0, le=Decimal("50000"), decimal_places=2
    )
    daily_limit: Decimal | None = Field(
        default=None, gt=0, le=Decimal("100000"), decimal_places=2
    )
    online_enabled: bool | None = None
    pos_enabled: bool | None = None
    atm_enabled: bool | None = None
    international_enabled: bool | None = None

    @model_validator(mode="after")
    def at_least_one_change(self):
        if all(value is None for value in self.model_dump().values()):
            raise ValueError("至少提交一项限额或渠道设置")
        return self


class CardTransactionRequest(Contract):
    card_id: str = Field(min_length=36, max_length=36)
    merchant_id: str = Field(min_length=36, max_length=36)
    amount: Amount
    channel: Literal["ONLINE", "POS", "ATM"] = "ONLINE"
    country_code: str = Field(default="CN", pattern=r"^[A-Z]{2}$")


class PersonalEventRequest(Contract):
    label: str = Field(min_length=1, max_length=120)
    event_date: date


class BirthdayTaskRequest(PersonalEventRequest):
    from_account_id: int = Field(gt=0)
    flower_amount: Amount
    cake_amount: Amount
    currency: Literal["CNY"] = "CNY"


class ScheduleRequest(TransferRequest):
    execute_at: datetime
    recurrence: Literal["once", "daily", "weekly", "monthly"] = "once"
    daily_limit: Amount
    valid_until: datetime

    @model_validator(mode="after")
    def dates(self):
        if self.execute_at.tzinfo is None or self.valid_until.tzinfo is None:
            raise ValueError("时间必须包含时区")
        if self.execute_at.second or self.execute_at.microsecond:
            raise ValueError("执行时间精确到分钟")
        if self.valid_until < self.execute_at or self.daily_limit < self.amount:
            raise ValueError("授权截止时间或每日上限无效")
        return self


class AAParticipant(Contract):
    user_id: str
    amount: Amount | None = None


class AARequest(Contract):
    account_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=100)
    amount: Amount
    mode: Literal["equal", "custom"] = "equal"
    participants: list[AAParticipant] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def participants_valid(self):
        ids = [p.user_id for p in self.participants]
        if len(set(ids)) != len(ids):
            raise ValueError("参与人不得重复")
        if self.mode == "custom" and (
            any(p.amount is None for p in self.participants)
            or sum(p.amount for p in self.participants) != self.amount
        ):
            raise ValueError("指定份额之和必须等于总额")
        return self


class AAPayRequest(Contract):
    from_account_id: int = Field(gt=0)


class CategoryRequest(Contract):
    name: str = Field(min_length=1, max_length=100)


class RuleRequest(Contract):
    category_id: str
    field: Literal["merchant", "note", "type"]
    contains: str = Field(min_length=1, max_length=100)
    priority: int = Field(default=0, ge=0, le=1000)


class AnnotationRequest(Contract):
    account_id: int = Field(gt=0)
    transaction_id: int = Field(gt=0)
    category_id: str | None = None
    merchant: str | None = Field(default=None, max_length=100)
    note: str = Field(default="", max_length=500)


class ReportRequest(Contract):
    account_id: int = Field(gt=0)
    period: str = Field(pattern=r"^\d{4}(-(?:0[1-9]|1[0-2]))?$")


class BillReportGenerationRequest(Contract):
    account_id: int | None = Field(..., gt=0)
    period: str = Field(pattern=r"^\d{4}(-(?:0[1-9]|1[0-2]))?$")


class BillReportStatusResponse(BaseModel):
    report_id: str
    status: Literal["queued", "running", "complete", "partial", "failed"]
    period: str
    cutoff_date: date
    created_at: datetime


class ReviewRequest(Contract):
    anomaly_key: str = Field(min_length=1, max_length=100)
    status: Literal["verified", "ignored"]


class RiskRequest(Contract):
    answers: list[int] = Field(min_length=5, max_length=5)

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, answers):
        if any(a < 1 or a > 5 for a in answers):
            raise ValueError("每题为 1–5 分")
        return answers


class MetadataRequest(Contract):
    risk_level: int = Field(ge=1, le=5)
    enabled: bool = False
    allows_premature: bool = False


class SubscriptionRequest(Contract):
    product_id: int = Field(gt=0)
    from_account_id: int = Field(gt=0)
    amount: Amount
    term_months: int = Field(ge=1, le=120)
    assessment_id: str | None = Field(default=None, min_length=36, max_length=36)


class SubscriptionResponse(BaseModel):
    id: str
    user_id: str
    merchant_id: str
    status: Literal["CANDIDATE", "VERIFIED", "IGNORED", "CANCELLED"]
    cadence: Literal["MONTHLY", "YEARLY"]
    expected_amount: Decimal
    amount_tolerance: Decimal
    next_charge_at: date | None
    evidence: dict[str, Any]
    rule_version: str
    verified_at: datetime | None
    ignored_at: datetime | None
    cancelled_at: datetime | None
    action_id: str | None
    created_at: datetime
    updated_at: datetime
    merchant: str
    merchant_category: str
    demo_adapter: bool
    occurrence_count: int


class SubscriptionScanResponse(BaseModel):
    created: int
    updated: int
    found: int
    matched_candidates: int
    from_date: date
    to_date: date
    scanned_at: datetime
    items: list[SubscriptionResponse]


class SubscriptionRenewalsResponse(BaseModel):
    as_of: date
    timezone: Literal["Asia/Shanghai"]
    days: int = Field(ge=1, le=90)
    from_date: date
    to_date: date
    last_scan_at: datetime | None
    upcoming: list[SubscriptionResponse]
    needs_review: list[SubscriptionResponse]


class SubscriptionReminderRuleRequest(Contract):
    scope: Literal["ALL_VERIFIED", "SUBSCRIPTION", "AMOUNT_GT"]
    subscription_id: str | None = Field(default=None, min_length=36, max_length=36)
    amount_gt: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    month: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    lead_days: list[StrictInt] = Field(min_length=1, max_length=3)

    @field_validator("lead_days")
    @classmethod
    def valid_lead_days(cls, value):
        if len(value) != len(set(value)) or not set(value).issubset({1, 3, 7}):
            raise ValueError("提前天数只支持1、3、7天及其组合")
        return sorted(value)


class SubscriptionBudgetRuleRequest(Contract):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class RedemptionRequest(Contract):
    holding_id: int = Field(gt=0)
    to_account_id: int = Field(gt=0)
    quote_hash: str = Field(min_length=64, max_length=64)
