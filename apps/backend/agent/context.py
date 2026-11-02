import calendar
import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import uuid4

from core.errors import require
from core.security import SHANGHAI, now
from models import User
from schemas.agent import AgentQueryContext, SubscriptionScanCompletedEvent, SubscriptionCancelRequestedEvent
from services.subscription_service import SubscriptionService
from services.subscription_planning_service import SubscriptionPlanningService
from services.account_service import AccountService
from services.analysis_result_service import AnalysisResultService
from services.billing_service import BillingService
from services.transaction_service import TransactionService
from services.recipient_service import RecipientService
from services.transfer_service import TransferService
from services.action_service import ActionService
from services.card_service import CardService
from services.schedule_service import ScheduleService
from services.aa_service import AAService
from services.investment_service import InvestmentService
from schemas.agent import AgentEvent

# A four-digit year after the ordinary word "账户" is natural date language,
# not an account identifier. Keep longer numeric IDs and explicit account_id labels.
ACCOUNT_PATTERN = r"(?:账户\s*(?:id|ID|编号)?|account(?:_id)?)\s*[:：=]?\s*(\d+)(?!\d)(?!\s*年)"
_INSIGHT_QUERY_TERMS = (
    "消费分类", "消费统计", "消费情况", "消费分析", "月度账单", "年度账单",
    "账单统计", "异常消费", "异常交易", "异常候选",
)
_EXPLICIT_PERIOD = re.compile(
    r"(?:20\d{2}\s*年\s*\d{1,2}\s*月|20\d{2}-\d{2}"
    r"|\d{1,2}\s*月份?|本月|这个月|当月|上个月|上月|下个月|下月"
    r"|今年|本年|去年|上一年|最近\s*\d+\s*天)"
)
_ALL_ACCOUNTS = re.compile(r"(?:所有|全部|各个|每个)\s*账户")
_REPORT_VIEW_VERB = re.compile(r"(?:查看|查阅|查询|查一下|打开|我要看|我想看|帮我(?:查看|看)|看(?:看|一下|下)?)")
_REPORT_CREATE_VERB = re.compile(
    r"(?:重新生成|重生成|再生成|(?:生成|保存|创建)(?!的|过|了).{0,8}(?:账单报告|月报|年报|报告))"
)
_BIRTHDAY_AMOUNT = r"(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,2})?"


def routing_message(message):
    """Shortcuts may embed a bank-sourced ID; the router only needs intent."""
    return re.sub(ACCOUNT_PATTERN, "所选账户", message, flags=re.IGNORECASE)


def parse_birthday_orchestration_intent(message: str):
    """Parse only a complete fixed birthday plan; incomplete plans stay model-assisted."""

    compact = re.sub(r"\s+", "", message)
    if "生日" not in compact or "鲜花" not in compact or "蛋糕" not in compact:
        return None

    label_match = re.search(r"为(.{1,40}?生日)(?:创建|制定|安排)(?:计划|任务)", compact)
    date_match = re.search(
        r"(20\d{2})年(0?[1-9]|1[0-2])月(3[01]|[12]\d|0?[1-9])(?:日|号)",
        compact,
    ) or re.search(
        r"(20\d{2})-(0?[1-9]|1[0-2])-(3[01]|[12]\d|0?[1-9])(?!\d)",
        compact,
    )
    account_match = re.search(
        r"(?:尾号|末四位)[<＜]?(\d{4})[>＞]?账户", compact
    )
    flower_matches = [
        *re.findall(rf"[¥￥]?({_BIRTHDAY_AMOUNT})(?:元|块)(?:的)?鲜花", compact),
        *re.findall(rf"鲜花(?:预算|金额|花费)?(?:为|是|：|:)?[¥￥]?({_BIRTHDAY_AMOUNT})(?:元|块)", compact),
    ]
    cake_matches = [
        *re.findall(rf"[¥￥]?({_BIRTHDAY_AMOUNT})(?:元|块)(?:的)?蛋糕", compact),
        *re.findall(rf"蛋糕(?:预算|金额|花费)?(?:为|是|：|:)?[¥￥]?({_BIRTHDAY_AMOUNT})(?:元|块)", compact),
    ]
    if not (
        label_match
        and date_match
        and account_match
        and len(set(flower_matches)) == 1
        and len(set(cake_matches)) == 1
    ):
        return None
    try:
        event_date = date(*(int(value) for value in date_match.groups()))
    except ValueError:
        return None
    return {
        "label": label_match.group(1),
        "event_date": event_date.isoformat(),
        "flower_amount": flower_matches[0],
        "cake_amount": cake_matches[0],
        "from_account_suffix": account_match.group(1),
    }


def explicit_cancel_merchant(message, service, user):
    """Resolve only a complete, unambiguous single-merchant cancellation sentence."""
    text = " ".join(message.casefold().split())
    prefix = r"(?:请帮我|麻烦帮我|帮我|麻烦|请)?\s*(?:取消|退订)\s*"
    if not re.match(r"^" + prefix, text):
        return None
    matches = []
    for row in service.list(user):
        merchant = " ".join(row["merchant"].casefold().split())
        if merchant and re.fullmatch(prefix + re.escape(merchant) + r"\s*(?:订阅|自动续费)?\s*[。！!？?]?", text):
            matches.append(row)
    if len(matches) != 1 or not matches[0].get("demo_adapter"):
        return None
    return matches[0]["merchant"]


def _month_from_message(message, today):
    match = re.search(r"(20\d{2})\s*年\s*(0?[1-9]|1[0-2])\s*月", message)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}"
    match = re.search(r"(20\d{2})-(0[1-9]|1[0-2])", message)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    if "下个月" in message or "下月" in message:
        first = today.replace(day=1)
        next_month = first + timedelta(days=32)
        return f"{next_month.year:04d}-{next_month.month:02d}"
    if "本月" in message or "这个月" in message or "当月" in message:
        return f"{today.year:04d}-{today.month:02d}"
    return None


def is_bill_report_view_request(message):
    """Identify explicit report-opening language, separate from report creation."""
    text = " ".join(message.split())
    has_report = (
        "报告" in text and any(term in text for term in ("账单", "月度", "年度", "月报", "年报"))
    ) or "全年账单" in text
    return bool(has_report and _REPORT_VIEW_VERB.search(text) and not _REPORT_CREATE_VERB.search(text))


def is_bill_report_generate_request(message):
    """Identify an explicit request to create/save a monthly or annual report."""
    text = " ".join(message.split())
    has_report = any(
        term in text for term in ("账单报告", "月度报告", "年度报告", "月报", "年报")
    )
    return bool(
        has_report
        and any(term in text for term in ("生成", "保存", "创建", "重生成", "重新生成"))
    )


def _parse_bill_report_intent(message, today, query_context, account_refs):
    text = " ".join(message.split())

    relative_year = today.year - 1 if any(term in text for term in ("去年", "上一年")) else today.year
    month_match = re.search(r"(20\d{2})\s*年\s*(0?[1-9]|1[0-2])\s*月", text)
    if month_match:
        period = f"{int(month_match.group(1)):04d}-{int(month_match.group(2)):02d}"
    else:
        iso_month = re.search(r"(20\d{2})-(0[1-9]|1[0-2])", text)
        if iso_month:
            period = f"{iso_month.group(1)}-{iso_month.group(2)}"
        elif any(term in text for term in ("上个月", "上月")):
            previous = today.replace(day=1) - timedelta(days=1)
            period = f"{previous.year:04d}-{previous.month:02d}"
        elif re.search(r"(?<!\d)(0?[1-9]|1[0-2])\s*月", text):
            numeric_month = re.search(r"(?<!\d)(0?[1-9]|1[0-2])\s*月", text)
            year = relative_year
            if query_context and query_context.period and not any(term in text for term in ("去年", "上一年")):
                year = int(query_context.period[:4])
            period = f"{year:04d}-{int(numeric_month.group(1)):02d}"
        elif any(term in text for term in ("去年", "上一年")):
            if any(term in text for term in ("月度", "月报")):
                return None
            period = f"{today.year - 1:04d}"
        elif any(term in text for term in ("今年", "本年")):
            if any(term in text for term in ("月度", "月报")):
                return None
            period = f"{today.year:04d}"
        elif any(term in text for term in ("年度", "年报")):
            year_match = re.search(r"(19\d{2}|20\d{2})\s*年?", text)
            period = year_match.group(1) if year_match else f"{today.year:04d}"
        elif (year_match := re.search(r"(?<!\d)(19\d{2}|20\d{2})\s*年(?!\s*\d{1,2}\s*月)", text)):
            period = year_match.group(1)
        else:
            period = _month_from_message(text, today) or f"{today.year:04d}-{today.month:02d}"

    if _ALL_ACCOUNTS.search(text):
        account_ref = None
    else:
        explicit_account = re.search(ACCOUNT_PATTERN, text, flags=re.IGNORECASE)
        if explicit_account:
            account_id = int(explicit_account.group(1))
            account_ref = next(
                (reference for reference, value in account_refs.items() if value == account_id),
                None,
            )
        else:
            account_ref = None
            if query_context and query_context.account_id is not None:
                account_ref = next(
                    (reference for reference, value in account_refs.items() if value == query_context.account_id),
                    None,
                )
    return {"account_ref": account_ref, "period": period}


def parse_bill_report_view_intent(message, today, query_context, account_refs):
    """Resolve an explicit report view to a trusted scope and Shanghai period."""
    if not is_bill_report_view_request(message):
        return None
    return _parse_bill_report_intent(message, today, query_context, account_refs)


def parse_bill_report_generate_intent(message, today, query_context, account_refs):
    """Resolve an explicit report generation request without model guesswork."""
    if not is_bill_report_generate_request(message):
        return None
    return _parse_bill_report_intent(message, today, query_context, account_refs)


def _insight_date_range(message, today):
    text = " ".join(message.split())
    month = re.search(r"(20\d{2})\s*年\s*(0?[1-9]|1[0-2])\s*月", text)
    if month:
        year, number = int(month.group(1)), int(month.group(2))
        return date(year, number, 1), date(year, number, calendar.monthrange(year, number)[1])
    if any(term in text for term in ("上个月", "上月")):
        day = today.replace(day=1) - timedelta(days=1)
        return day.replace(day=1), day
    recent = re.search(r"最近\s*(\d{1,3})\s*天", text)
    if recent:
        days = min(int(recent.group(1)), 366)
        return today - timedelta(days=days - 1), today
    if any(term in text for term in ("今年", "本年")):
        return date(today.year, 1, 1), date(today.year, 12, 31)
    return today.replace(day=1), today.replace(
        day=calendar.monthrange(today.year, today.month)[1]
    )


def parse_insight_query_intent(message, today, query_context, account_refs):
    """Resolve supported read-only statistics/anomaly prompts deterministically."""
    if is_bill_report_view_request(message) or is_bill_report_generate_request(message):
        return None
    text = " ".join(message.split())
    anomaly = any(term in text for term in ("异常候选", "异常交易", "异常消费", "重复扣款"))
    statistics = any(term in text for term in (
        "消费分类", "收入和支出", "收支", "消费趋势", "净现金流", "消费统计", "消费分析",
    ))
    if not anomaly and not statistics:
        return None
    account_ref = None
    if not _ALL_ACCOUNTS.search(text) and query_context and query_context.account_id is not None:
        account_ref = next(
            (reference for reference, value in account_refs.items() if value == query_context.account_id),
            None,
        )
    start, end = _insight_date_range(text, today)
    return {
        "tool": "get_spending_anomalies" if anomaly else "get_spending_statistics",
        "args": {
            "account_ref": account_ref,
            "from_date": start.isoformat(),
            "to_date": end.isoformat(),
        },
    }


_CN_DIGITS = {"一": 1, "三": 3, "七": 7, "1": 1, "3": 3, "7": 7}


def parse_lead_days(message):
    match = re.search(r"提前\s*([0-9一三七](?:\s*[、,，和及/]\s*[0-9一三七])*)\s*天", message)
    if not match:
        return None
    digits = re.findall(r"[0-9一三七]", match.group(1))
    if any(item not in _CN_DIGITS for item in digits):
        return None
    return sorted({_CN_DIGITS[item] for item in digits})


def is_lead_only_reply(message):
    return bool(re.fullmatch(
        r"\s*提前\s*[0-9一二三四五六七八九十、,，和及/\s]+\s*天\s*(?:提醒我|告诉我|通知我)?\s*[。！!？?]?\s*",
        message,
    ))


def parse_subscription_intent(message, today):
    text = " ".join(message.split())
    month = _month_from_message(text, today)
    if any(term in text for term in ("暂停", "恢复", "编辑", "删除", "停用")) and any(
        term in text for term in ("提醒", "预算")
    ):
        return {"kind": "UNSUPPORTED_MANAGEMENT"}
    if (any(term in text for term in ("不要提醒", "不提醒", "不需要提醒", "无需提醒", "取消提醒", "不通知", "别提醒"))
            or re.search(r"(?:不要|不需要|无需|不用|别).{0,24}(?:提醒|通知|告诉我)", text)):
        return None
    if any(term in text for term in ("预算", "不要超过", "不超过")) and any(
        term in text for term in ("订阅", "续费", "自动扣费", "自动续费")
    ):
        amount_match = re.search(r"(?:预算|不要超过|不超过)\s*[¥￥]?\s*(\d+(?:\.\d{1,2})?)", text)
        if amount_match:
            return {"kind": "BUDGET", "month": month, "amount": amount_match.group(1)}
        return {"kind": "INVALID_BUDGET", "month": month}
    if any(term in text for term in (
        "提醒规则", "预算规则", "订阅规则", "提醒设置", "我设置的提醒",
        "我有哪些提醒", "已保存的提醒", "当前预算规则",
    )):
        return {"kind": "RULES"}
    comparator = r"(?:(?<!不)(?<!没)超过|大于|高于|多于)"
    amount_match = re.search(comparator + r"\s*[¥￥]?\s*(\d+(?:\.\d{1,2})?)(?![\d.])", text)
    amount_gt = amount_match.group(1) if amount_match else None
    leads = parse_lead_days(text)
    has_subscription = any(term in text for term in ("订阅", "续费", "扣费", "会员"))
    if has_subscription and re.search(comparator, text) and not amount_match:
        return {"kind": "INVALID_AMOUNT_FILTER"}
    wants_reminder = "提醒" in text or "通知" in text or (
        "提前" in text and "告诉我" in text
    )
    if wants_reminder and has_subscription:
        if "提前" in text and leads is None:
            return {"kind": "INVALID_CONTINUATION"}
        # A merchant is chosen only when its complete normalized name occurs.
        # The API supplies the actual owned-subscription match after authentication.
        merchant_match = re.search(r"(?:提醒|通知)\s*(?:我)?\s*(.+?)\s*(?:订阅)?\s*(?:续费|扣费|时)?\s*提前", text)
        return {"kind": "REMINDER", "month": month, "amount_gt": amount_gt,
                "lead_days": leads, "merchant_phrase": merchant_match.group(1).strip() if merchant_match else None}
    if any(term in text for term in (
        "哪些自动扣费", "自动续费", "订阅续费", "续费安排", "订阅费用", "什么时候扣费",
        "哪些订阅要续费", "哪些订阅会续费", "哪些订阅快续费", "订阅要续费", "订阅会续费",
        "预计订阅总额", "订阅总额",
    )):
        return {"kind": "FORECAST", "month": month, "amount_gt": amount_gt}
    detail = re.search(
        r"(?:查看|查询|查一下|看看|了解)(?:一下)?(?:我)?(?:的)?\s*"
        r"(.+?)(?:的)?(?:订阅|会员)(?:详情|信息)?[。！!？?]*$",
        text,
    )
    if detail:
        merchant = detail.group(1).strip()
        if merchant and merchant not in {"所有", "全部", "哪些", "有哪些", "订阅"}:
            return {"kind": "DETAIL", "merchant": merchant}
    if any(term in text for term in (
        "订阅列表", "订阅有哪些", "有哪些订阅", "我的订阅", "所有订阅", "全部订阅", "查看订阅",
        "查询订阅", "列出订阅", "订阅清单", "已保存订阅",
    )):
        return {"kind": "LIST"}
    return None


_CARD_APPLICATION = re.compile(
    r"(?:申请|办理|办)(?:一张|张|个)?[^。！？!?]{0,24}(?:借记卡|新卡)"
)
_CARD_OPERATION_TERMS = (
    "单笔限额", "日累计限额", "线上交易", "线上支付", "POS", "pos", "ATM", "atm",
    "境外交易", "激活", "锁定", "解锁", "挂失", "补卡", "补办", "完整卡号", "查看卡号", "卡号",
)


def parse_card_request_intent(
    message: str,
    *,
    known_aliases: tuple[str, ...] = (),
    has_trusted_target: bool = False,
):
    """Force only unambiguous card application or safe list-before-select flows."""
    text = " ".join(message.split())
    if _CARD_APPLICATION.search(text):
        # “日常消费用” describes purpose, not necessarily a user-chosen alias.
        # Keep the optional alias empty unless the UI later collects one explicitly.
        return {"tool": "request_card", "args": {"alias": ""}}
    if not any(term in text for term in _CARD_OPERATION_TERMS):
        return None
    if has_trusted_target or re.search(r"(?:尾号|末四位)\s*\d{4}(?!\d)", text):
        return None
    aliases = tuple(alias.strip() for alias in known_aliases if alias and alias.strip())
    if any(alias in text for alias in aliases):
        return None
    return {"tool": "list_my_cards", "args": {}}


@dataclass(frozen=True)
class AgentContext:
    user: User
    account_service: AccountService
    billing_service: BillingService | None = None
    bill_reports: object | None = None
    report_events: list = field(default_factory=list)
    report_view_intent: dict | None = None
    report_generate_intent: dict | None = None
    insight_query_intent: dict | None = None
    transaction_service: TransactionService | None = None
    recipient_service: RecipientService | None = None
    transfer_service: TransferService | None = None
    action_service: ActionService | None = None
    card_service: CardService | None = None
    schedule_service: ScheduleService | None = None
    aa_service: AAService | None = None
    investment_service: InvestmentService | None = None
    orchestration_service: object | None = None
    orchestration_intent: dict | None = None
    security_service: object | None = None
    events: list[AgentEvent] = field(default_factory=list)
    query_context: AgentQueryContext | None = None
    current_date: date = field(default_factory=lambda: now().astimezone(SHANGHAI).date())
    private_results: AnalysisResultService | None = None
    account_refs: dict[str, int] = field(default_factory=dict)
    selected_ref: str | None = None
    subscription_service: SubscriptionService | None = None
    subscription_planning_service: SubscriptionPlanningService | None = None
    subscription_intent: dict | None = None
    card_request_intent: dict | None = None
    continuation_ref: str | None = None
    subscription_workflow_events: list = field(default_factory=list)
    subscription_query_events: list = field(default_factory=list)
    subscription_events: list[SubscriptionScanCompletedEvent] = field(default_factory=list)
    trace_id: str | None = None
    agent_run_id: str | None = None

    # 原始消息来自已认证 HTTP 请求，不来自模型生成的工具参数。
    user_message: str = ""
    user_history: tuple[str, ...] = ()
    explicit_cancel_merchant: str | None = None
    conversation_id: str | None = None
    reference_service: object | None = None
    selected_option_ref: str | None = None
    trusted_option: dict | None = None

    # 每次请求都有自己的事件列表。
    subscription_cancel_events: list[
        SubscriptionCancelRequestedEvent
    ] = field(default_factory=list)

    def resolve_account(self, reference):
        if reference is None:
            return None
        require(reference in self.account_refs, "INVALID_ACCOUNT_REFERENCE", "请选择本人账户后重新查询", 422)
        account_id = self.account_refs[reference]
        self.account_service.get_account(self.user, account_id)
        return account_id

    def issue_option(self, kind: str, resource_id: str, label: str):
        if self.reference_service is None or self.conversation_id is None:
            return None
        return self.reference_service.issue_reference(
            self.user, self.conversation_id, kind, str(resource_id), label
        )

    def selected_resource(self, kind: str, supplied: str | None = None):
        item = self.trusted_option
        if item and item.get("kind") == kind:
            if supplied is not None and supplied.strip().casefold() not in {
                str(self.selected_option_ref or "").casefold(),
                str(item.get("label") or "").casefold(),
            }:
                return None
            return str(item["resource_id"])
        if (
            supplied
            and re.fullmatch(r"[0-9a-f]{32}", supplied, re.IGNORECASE)
            and self.reference_service is not None
            and self.conversation_id is not None
        ):
            resolved = self.reference_service.resolve_reference(
                self.user,
                self.conversation_id,
                supplied,
                kind=kind,
            )
            return str(resolved["resource_id"])
        return None


def prepare_account_refs(user, accounts, query_context, message, reference_factory=None):
    refs = {}
    def reference(account_id):
        account = accounts.get_account(user, account_id)
        for key, value in refs.items():
            if value == account_id:
                return key
        key = (
            reference_factory("account", str(account_id), f"账户尾号 {account.account_no[-4:]}")
            if reference_factory
            else uuid4().hex
        )
        refs[key] = account_id
        return key
    selected = reference(query_context.account_id) if query_context and query_context.account_id else None
    text = re.sub(ACCOUNT_PATTERN, lambda m: "账户引用 " + reference(int(m.group(1))), message, flags=re.IGNORECASE)
    return refs, selected, text


def effective_query_context(query_context, message):
    """Do not let a stale UI month silently scope an undated insight query."""
    if query_context is None or not any(term in message for term in _INSIGHT_QUERY_TERMS):
        return query_context
    all_accounts = _ALL_ACCOUNTS.search(message) is not None
    explicit_period = _EXPLICIT_PERIOD.search(message) is not None
    if not all_accounts and explicit_period:
        return query_context
    return AgentQueryContext(
        account_id=None if all_accounts else query_context.account_id,
        period=query_context.period if explicit_period else None,
    )


def query_context_prompt(context: AgentContext) -> str:
    def month_range(day):
        return {"from_date": day.replace(day=1).isoformat(),
                "to_date": day.replace(day=calendar.monthrange(day.year, day.month)[1]).isoformat()}
    today = context.current_date
    previous_month = today.replace(day=1) - timedelta(days=1)
    data = {"timezone": "Asia/Shanghai", "current_date": today.isoformat(),
            "this_month": month_range(today), "last_month": month_range(previous_month),
            "last_30_days": {
                "from_date": (today - timedelta(days=29)).isoformat(),
                "to_date": today.isoformat(),
            },
            "this_year": {"from_date": f"{today.year}-01-01", "to_date": f"{today.year}-12-31"},
            "last_year": {"from_date": f"{today.year - 1}-01-01", "to_date": f"{today.year - 1}-12-31"},
            "bill_report_periods": {"this_month": f"{today.year:04d}-{today.month:02d}",
                "last_month": f"{previous_month.year:04d}-{previous_month.month:02d}",
                "this_year": f"{today.year:04d}", "last_year": f"{today.year - 1:04d}"},
            "available_account_refs": list(context.account_refs)}
    if context.trusted_option and context.selected_option_ref:
        data["selected_option"] = {
            "kind": context.trusted_option.get("kind"),
            "option_ref": context.selected_option_ref,
            "label": context.trusted_option.get("label"),
        }
    if context.query_context is not None:
        data["selection"] = {"account_ref": context.selected_ref, "period": context.query_context.period}
        if context.query_context.period:
            data["selected_month"] = month_range(date.fromisoformat(context.query_context.period + "-01"))
    return "本次请求的日期参照与不透明账户选择（选择不是授权）：\n" + json.dumps(data, ensure_ascii=False)
