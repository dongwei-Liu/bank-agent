from typing import Literal
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BalanceResultData(BaseModel):
    """余额查询的结构化前端事件数据。"""

    currency: str = Field(min_length=3, max_length=3)
    total: str
    account_count: int = Field(ge=0)
    complete: bool


class BalanceResultEvent(BaseModel):
    """Legacy event shape, retained for existing clients; new calls use references."""

    type: Literal["BALANCE_RESULT"] = "BALANCE_RESULT"
    data: BalanceResultData


class AnalysisReadyData(BaseModel):
    analysis_id: str
    kind: Literal[
        "balance",
        "transactions",
        "statistics",
        "anomalies",
        "wealth_products",
        "wealth_recommend",
        "wealth_holdings",
    ]


class AnalysisReadyEvent(BaseModel):
    type: Literal["ANALYSIS_READY"] = "ANALYSIS_READY"
    data: AnalysisReadyData


class BillReportReadyData(BaseModel):
    report_id: str
    status: Literal["queued"]
    period: str


class BillReportReadyEvent(BaseModel):
    type: Literal["BILL_REPORT_READY"] = "BILL_REPORT_READY"
    data: BillReportReadyData


class BillReportOpenedData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str
    period: str
    status: Literal["queued", "running", "complete", "partial", "failed"]
    generated: bool


class BillReportOpenedEvent(BaseModel):
    type: Literal["BILL_REPORT_OPENED"] = "BILL_REPORT_OPENED"
    data: BillReportOpenedData


class AgentAnalysisResponse(BaseModel):
    analysis_id: str
    kind: Literal[
        "balance",
        "transactions",
        "statistics",
        "anomalies",
        "wealth_products",
        "wealth_recommend",
        "wealth_holdings",
    ]
    created_at: datetime
    expires_at: datetime
    data: dict[str, Any]


class SubscriptionScanCompletedData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    found: int = Field(ge=0)
    matched_candidates: int = Field(ge=0)
    from_date: date
    to_date: date
    scanned_at: datetime
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"


class SubscriptionScanCompletedEvent(BaseModel):
    type: Literal["SUBSCRIPTION_SCAN_COMPLETED"] = "SUBSCRIPTION_SCAN_COMPLETED"
    data: SubscriptionScanCompletedData


class SubscriptionCancelRequestedData(BaseModel):
    """聊天只保存 Action 引用，确认详情由授权接口重新读取。"""

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1)
    status: Literal[
        "WAITING_CONFIRMATION",
        "WAITING_VERIFICATION",
        "AUTHORIZED",
        "EXECUTING",
        "RECONCILING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    ]


class SubscriptionCancelRequestedEvent(BaseModel):
    type: Literal["SUBSCRIPTION_CANCEL_REQUESTED"] = (
        "SUBSCRIPTION_CANCEL_REQUESTED"
    )
    data: SubscriptionCancelRequestedData


class SubscriptionForecastReadyEvent(BaseModel):
    type: Literal["SUBSCRIPTION_FORECAST_READY"] = "SUBSCRIPTION_FORECAST_READY"
    data: dict[str, Any]


class SubscriptionReminderRuleSavedEvent(BaseModel):
    type: Literal["SUBSCRIPTION_REMINDER_RULE_SAVED"] = "SUBSCRIPTION_REMINDER_RULE_SAVED"
    data: dict[str, Any]


class SubscriptionBudgetReadyEvent(BaseModel):
    type: Literal["SUBSCRIPTION_BUDGET_READY"] = "SUBSCRIPTION_BUDGET_READY"
    data: dict[str, Any]


class SubscriptionClarificationEvent(BaseModel):
    type: Literal["SUBSCRIPTION_CLARIFICATION_REQUIRED"] = "SUBSCRIPTION_CLARIFICATION_REQUIRED"
    data: dict[str, Any]


class SubscriptionRulesReadyEvent(BaseModel):
    type: Literal["SUBSCRIPTION_RULES_READY"] = "SUBSCRIPTION_RULES_READY"
    data: dict[str, Any]


class SubscriptionQueryRequestedData(BaseModel):
    action_id: str
    query_type: Literal["FORECAST", "RULES", "LIST", "DETAIL"]
    summary: str
    conditions: list[str] = Field(default_factory=list)
    risk_level: Literal["YELLOW"] = "YELLOW"
    status: Literal[
        "WAITING_CONFIRMATION", "AUTHORIZED", "EXECUTING", "RECONCILING",
        "SUCCEEDED", "FAILED", "CANCELLED", "WAITING_VERIFICATION",
    ]
    expires_at: datetime


class SubscriptionQueryRequestedEvent(BaseModel):
    type: Literal["SUBSCRIPTION_QUERY_REQUESTED"] = "SUBSCRIPTION_QUERY_REQUESTED"
    data: SubscriptionQueryRequestedData


class TransferActionCreatedData(BaseModel):
    action_id: str
    recipient_name: str
    from_account_suffix: str = Field(pattern=r"^\d{4}$")
    amount: str
    currency: Literal["CNY"] = "CNY"
    status: Literal["WAITING_CONFIRMATION"] = "WAITING_CONFIRMATION"


class TransferActionCreatedEvent(BaseModel):
    type: Literal["TRANSFER_ACTION_CREATED"] = "TRANSFER_ACTION_CREATED"
    data: TransferActionCreatedData


class InternalTransferActionCreatedData(BaseModel):
    action_id: str
    from_account_suffix: str = Field(pattern=r"^\d{4}$")
    to_account_suffix: str = Field(pattern=r"^\d{4}$")
    amount: str
    currency: Literal["CNY"] = "CNY"
    status: Literal["WAITING_CONFIRMATION"] = "WAITING_CONFIRMATION"


class InternalTransferActionCreatedEvent(BaseModel):
    type: Literal["INTERNAL_TRANSFER_ACTION_CREATED"] = "INTERNAL_TRANSFER_ACTION_CREATED"
    data: InternalTransferActionCreatedData


class CardActionCreatedData(BaseModel):
    action_id: str
    operation: str
    card_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    status: Literal["WAITING_CONFIRMATION"] = "WAITING_CONFIRMATION"


class CardActionCreatedEvent(BaseModel):
    type: Literal["CARD_ACTION_CREATED"] = "CARD_ACTION_CREATED"
    data: CardActionCreatedData


class ScheduleAuthorizationCreatedData(BaseModel):
    action_id: str
    recipient_name: str
    from_account_suffix: str = Field(pattern=r"^\d{4}$")
    amount: str
    recurrence: Literal["once", "daily", "weekly", "monthly"]
    execute_at: str
    daily_limit: str
    valid_until: str
    status: Literal["WAITING_CONFIRMATION"] = "WAITING_CONFIRMATION"


class ScheduleAuthorizationCreatedEvent(BaseModel):
    type: Literal["SCHEDULE_AUTHORIZATION_CREATED"] = "SCHEDULE_AUTHORIZATION_CREATED"
    data: ScheduleAuthorizationCreatedData


class AAPaymentActionCreatedData(BaseModel):
    action_id: str
    title: str
    from_account_suffix: str = Field(pattern=r"^\d{4}$")
    amount: str
    status: Literal["WAITING_CONFIRMATION"] = "WAITING_CONFIRMATION"


class AAPaymentActionCreatedEvent(BaseModel):
    type: Literal["AA_PAYMENT_ACTION_CREATED"] = "AA_PAYMENT_ACTION_CREATED"
    data: AAPaymentActionCreatedData


class WealthRiskAssessmentRequiredData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal["recommendation", "subscription"]
    route: Literal["/wealth/risk-assessment"] = "/wealth/risk-assessment"


class WealthRiskAssessmentRequiredEvent(BaseModel):
    type: Literal["WEALTH_RISK_ASSESSMENT_REQUIRED"] = (
        "WEALTH_RISK_ASSESSMENT_REQUIRED"
    )
    data: WealthRiskAssessmentRequiredData


class WealthActionCreatedData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1)
    operation: Literal["subscription", "redemption"]
    status: Literal[
        "WAITING_CONFIRMATION",
        "WAITING_VERIFICATION",
        "AUTHORIZED",
        "EXECUTING",
        "RECONCILING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    ]


class WealthActionCreatedEvent(BaseModel):
    type: Literal["WEALTH_ACTION_CREATED"] = "WEALTH_ACTION_CREATED"
    data: WealthActionCreatedData


class OrchestrationTaskCreatedData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    task_status: Literal[
        "WAITING_AUTHORIZATION",
        "ACTIVE",
        "PAUSED",
        "CANCELLING",
        "WAITING_USER",
        "PARTIAL",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    ]
    authorization_status: Literal[
        "WAITING_CONFIRMATION",
        "WAITING_VERIFICATION",
        "AUTHORIZED",
        "EXECUTING",
        "RECONCILING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    ]
    route: str = Field(pattern=r"^/tasks/[^/]+$")


class OrchestrationTaskCreatedEvent(BaseModel):
    type: Literal["ORCHESTRATION_TASK_CREATED"] = "ORCHESTRATION_TASK_CREATED"
    data: OrchestrationTaskCreatedData


class OrchestrationTaskSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=120)
    event_date: date
    status: Literal[
        "WAITING_AUTHORIZATION",
        "ACTIVE",
        "PAUSED",
        "CANCELLING",
        "WAITING_USER",
        "PARTIAL",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    ]
    route: str = Field(pattern=r"^/tasks/[^/]+$")


class OrchestrationTasksReadyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrchestrationTaskSummary] = Field(max_length=20)
    has_more: bool = False


class OrchestrationTasksReadyEvent(BaseModel):
    type: Literal["ORCHESTRATION_TASKS_READY"] = "ORCHESTRATION_TASKS_READY"
    data: OrchestrationTasksReadyData


class ClarificationOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_ref: str = Field(min_length=32, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=200)


class ClarificationRequiredData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "recipient",
        "account",
        "card",
        "schedule",
        "aa",
        "product",
        "holding",
        "orchestration_account",
    ]
    question: str = Field(min_length=1, max_length=300)
    options: list[ClarificationOption] = Field(min_length=1, max_length=10)


class ClarificationRequiredEvent(BaseModel):
    type: Literal["CLARIFICATION_REQUIRED"] = "CLARIFICATION_REQUIRED"
    data: ClarificationRequiredData


AgentEvent = (
    BalanceResultEvent
    | AnalysisReadyEvent
    | BillReportReadyEvent
    | BillReportOpenedEvent
    | SubscriptionScanCompletedEvent
    | SubscriptionCancelRequestedEvent
    | SubscriptionForecastReadyEvent
    | SubscriptionReminderRuleSavedEvent
    | SubscriptionBudgetReadyEvent
    | SubscriptionClarificationEvent
    | SubscriptionRulesReadyEvent
    | SubscriptionQueryRequestedEvent
    | TransferActionCreatedEvent
    | InternalTransferActionCreatedEvent
    | CardActionCreatedEvent
    | ScheduleAuthorizationCreatedEvent
    | AAPaymentActionCreatedEvent
    | WealthRiskAssessmentRequiredEvent
    | WealthActionCreatedEvent
    | OrchestrationTaskCreatedEvent
    | OrchestrationTasksReadyEvent
    | ClarificationRequiredEvent
)


class AgentQueryContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    account_id: int | None = Field(default=None, gt=0, strict=True)
    period: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")

    @field_validator("period")
    @classmethod
    def valid_period(cls, value):
        if value is not None:
            date.fromisoformat(value + "-01")
        return value


class AgentMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    history: list[str] = Field(default_factory=list, max_length=8)
    query_context: AgentQueryContext | None = None
    continuation_ref: str | None = Field(default=None, min_length=36, max_length=36)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("消息不能为空")
        return value

    @field_validator("history")
    @classmethod
    def validate_history(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item or len(item) > 2000 for item in cleaned):
            raise ValueError("历史用户消息不能为空且每条不超过 2000 字符")
        if sum(len(item) for item in cleaned) > 6000:
            raise ValueError("历史用户消息总长度不能超过 6000 字符")
        return cleaned


class AgentMessageResponse(BaseModel):
    trace_id: str
    message: str
    events: list[AgentEvent] = Field(default_factory=list)


AgentRunStatus = Literal[
    "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"
]


class AgentConversationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="新对话", min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("会话标题不能为空")
        return value


class AgentConversationMessageRequest(BaseModel):
    """Durable conversation input; history and identity always come from the server."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    query_context: AgentQueryContext | None = None
    continuation_ref: str | None = Field(default=None, min_length=36, max_length=36)
    option_ref: str | None = Field(default=None, min_length=32, max_length=64)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("消息不能为空")
        return value


class AgentStoredMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    sequence: int
    created_at: datetime


class AgentStreamEvent(BaseModel):
    event_id: str
    conversation_id: str
    run_id: str
    trace_id: str
    type: str
    created_at: datetime
    data: dict[str, Any]


class AgentRunResponse(BaseModel):
    id: str
    conversation_id: str
    trace_id: str
    status: AgentRunStatus
    attempts: int
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    assistant_message: AgentStoredMessage | None = None


class AgentConversationSummary(BaseModel):
    id: str
    title: str
    status: Literal["ACTIVE"]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    latest_run_status: AgentRunStatus | None = None


class AgentConversationDetail(AgentConversationSummary):
    messages: list[AgentStoredMessage] = Field(default_factory=list)
    events: list[AgentStreamEvent] = Field(default_factory=list)
    current_run: AgentRunResponse | None = None
