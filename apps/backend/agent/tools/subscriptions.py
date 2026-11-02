from typing import Annotated, Any
import re
from uuid import uuid4
from decimal import Decimal
from datetime import date, timedelta
import calendar

from langchain_core.tools import InjectedToolArg, tool
from langgraph.prebuilt import ToolRuntime
from pydantic import BaseModel, ConfigDict, Field

from agent.context import AgentContext
from agent.state import AgentState
from core.errors import DomainError, require
from schemas.agent import (
    SubscriptionCancelRequestedData,
    SubscriptionCancelRequestedEvent,
    SubscriptionScanCompletedData,
    SubscriptionScanCompletedEvent,
    SubscriptionForecastReadyEvent,
    SubscriptionReminderRuleSavedEvent,
    SubscriptionBudgetReadyEvent,
    SubscriptionClarificationEvent,
    SubscriptionRulesReadyEvent,
    SubscriptionQueryRequestedData,
    SubscriptionQueryRequestedEvent,
)


class ScanSubscriptionsInput(BaseModel):
    """模型可见的业务参数为空。"""

    model_config = ConfigDict(extra="forbid")


class _ScanSubscriptionsToolInput(ScanSubscriptionsInput):
    runtime: Annotated[Any, InjectedToolArg]


class RequestSubscriptionCancelInput(BaseModel):
    """模型只能提供商户名称，不能指定订阅、用户或 Action。"""

    model_config = ConfigDict(extra="forbid")

    merchant: str = Field(
        min_length=1,
        max_length=160,
        description="用户明确提到的订阅商户名称",
    )


class _RequestSubscriptionCancelToolInput(RequestSubscriptionCancelInput):
    runtime: Annotated[Any, InjectedToolArg]


def _normalize_merchant(merchant: str) -> str:
    """忽略商户名称的大小写和多余空白。"""
    return " ".join(str(merchant or "").casefold().split())


@tool(args_schema=_ScanSubscriptionsToolInput)
def scan_subscriptions(runtime: ToolRuntime[AgentContext, AgentState]) -> dict:
    """按用户要求识别本人全部合格账户中的周期订阅扣费。

    固定读取最近 800 天流水，使用已有月付/年付确定性规则。
    会保存订阅候选及扫描审计；不是只读查询。
    不接受用户身份、账户、日期或识别阈值参数。
    不核实、忽略或取消订阅，也不移动资金。
    """
    context = runtime.context
    require(context.subscription_service is not None,
            "AGENT_CONTEXT_MISSING", "订阅服务未配置", 500)
    require(not context.subscription_events,
            "AGENT_SCAN_ALREADY_COMPLETED", "本次请求已经完成订阅识别", 409)
    result = context.subscription_service.scan(context.user, trace_id=context.trace_id)
    context.subscription_events.append(SubscriptionScanCompletedEvent(
        data=SubscriptionScanCompletedData(**{
            key: result[key] for key in (
                "created", "updated", "found", "matched_candidates",
                "from_date", "to_date", "scanned_at",
            )
        }),
    ))
    # 私有证据及摘要不进入 ToolMessage；成功后图直接结束。
    return {"status": "completed"}


@tool(args_schema=_RequestSubscriptionCancelToolInput)
def request_subscription_cancel(
    merchant: str,
    runtime: ToolRuntime[AgentContext, AgentState],
) -> dict:
    """为用户明确指定的本人 Demo 订阅创建或复用取消 Action。

    仅接受商户名称，并要求它在本人 Demo 订阅中唯一匹配。
    本工具不会执行取消；用户必须前往 Action 页面核对详情并确认。
    """
    context = runtime.context
    require(
        context.subscription_service is not None,
        "AGENT_CONTEXT_MISSING",
        "订阅服务未配置",
        500,
    )
    require(
        not context.subscription_cancel_events,
        "AGENT_CANCEL_ALREADY_REQUESTED",
        "本次请求已经提交订阅取消请求",
        409,
    )

    normalized = _normalize_merchant(merchant)
    require(
        bool(normalized),
        "SUBSCRIPTION_MERCHANT_REQUIRED",
        "请提供要取消的商户名称",
        422,
    )
    require(
        normalized in _normalize_merchant(context.user_message),
        "SUBSCRIPTION_MERCHANT_NOT_IN_MESSAGE",
        "请在消息中明确写出要取消的商户名称",
        422,
    )
    require(
        not re.search(r"(?:不要|不想|不能|不必|别|暂不|暂时不|不用|无需|不需要|先不|勿).{0,20}(?:取消|退订)", context.user_message),
        "SUBSCRIPTION_CANCEL_INTENT_UNCLEAR",
        "请明确确认是否要发起取消请求",
        422,
    )
    matches = [
        item
        for item in context.subscription_service.list(context.user)
        if _normalize_merchant(item.get("merchant", "")) == normalized
    ]
    require(
        matches,
        "SUBSCRIPTION_NOT_FOUND",
        "未找到名称匹配的本人订阅，请核对商户名称",
        404,
    )
    require(
        len(matches) == 1,
        "SUBSCRIPTION_MERCHANT_AMBIGUOUS",
        "该商户匹配到多项本人订阅，请先在订阅管理页核对",
        409,
    )
    require(matches[0].get("demo_adapter") is True, "DEMO_MERCHANT_REQUIRED",
            "当前仅支持取消 Demo 商户订阅", 409)

    action = context.subscription_service.request_cancel(
        context.user,
        matches[0]["id"],
        uuid4().hex,
    )
    context.subscription_cancel_events.append(
        SubscriptionCancelRequestedEvent(
            data=SubscriptionCancelRequestedData(
                action_id=action["id"],
                status=action["status"],
            )
        )
    )
    # Action 引用只通过结构化事件交给前端，不进入模型可见的 ToolMessage。
    return {"status": "request_ready"}


class ManageSubscriptionInput(BaseModel):
    """The trusted request parser supplies the only accepted workflow intent."""
    model_config = ConfigDict(extra="forbid")


class _ManageSubscriptionToolInput(ManageSubscriptionInput):
    runtime: Annotated[Any, InjectedToolArg]


def _forecast_event(context, planning, *, month=None, amount_gt=None):
    result = planning.forecast(context.user, month=month)
    if amount_gt is not None:
        threshold = Decimal(str(amount_gt))
        result["items"] = [item for item in result["items"]
                           if Decimal(str(item["amount"])) > threshold]
        result["projected_total"] = str(sum(
            (Decimal(item["amount"]) for item in result["items"]), Decimal("0.00")
        ))
    result["filters"] = {"amount_gt": str(amount_gt) if amount_gt is not None else None}
    result_id = planning.create_result(context.user, "forecast", result)
    context.subscription_workflow_events.append(SubscriptionForecastReadyEvent(data={
        "result_id": result_id, "from_date": result["from_date"],
        "to_date": result["to_date"], "complete": result["complete"],
        "item_count": len(result["items"]),
    }))


@tool(args_schema=_ManageSubscriptionToolInput)
def manage_subscription_request(runtime: ToolRuntime[AgentContext, AgentState]) -> dict:
    """Query verified-subscription forecasts, create reminder rules, or monitor a monthly budget.

    Request scope and dates come from the authenticated message parser. Precise
    account and amount evidence is stored behind a user-owned result reference.
    This tool never scans transactions to create subscriptions and never cancels.
    """
    context = runtime.context
    planning = context.subscription_planning_service
    intent = context.subscription_intent
    require(planning is not None and intent is not None,
            "AGENT_CONTEXT_MISSING", "订阅管理服务未配置", 500)
    events = context.subscription_workflow_events
    require(
        not events and not context.subscription_query_events,
        "SUBSCRIPTION_REQUEST_ALREADY_HANDLED",
        "本次订阅请求已处理",
        409,
    )
    kind = intent["kind"]

    if kind in {"FORECAST", "RULES", "LIST", "DETAIL"}:
        require(context.action_service is not None,
                "AGENT_CONTEXT_MISSING", "订阅查询授权服务未配置", 500)
        request = {"query_kind": kind}
        if kind == "FORECAST":
            as_of = context.current_date
            month = intent.get("month")
            if month:
                year, number = (int(part) for part in month.split("-", 1))
                start = date(year, number, 1)
                end = date(year, number, calendar.monthrange(year, number)[1])
            else:
                start = as_of
                end = as_of + timedelta(days=3)
            request.update({
                "as_of": as_of.isoformat(),
                "from_date": start.isoformat(),
                "to_date": end.isoformat(),
                "amount_gt": intent.get("amount_gt"),
            })
        elif kind == "DETAIL":
            request["merchant"] = intent["merchant"]

        labels = {
            "FORECAST": "续费预测",
            "RULES": "提醒与预算规则",
            "LIST": "本人订阅列表",
            "DETAIL": f"{intent.get('merchant', '')}订阅详情",
        }
        conditions = []
        if kind == "FORECAST":
            conditions.append(f"期间：{request['from_date']} 至 {request['to_date']}（上海时间）")
            if request["amount_gt"] is not None:
                conditions.append(f"金额严格大于 {request['amount_gt']} 元")
        elif kind == "DETAIL":
            conditions.append(f"商户：{intent['merchant']}（精确匹配）")
        payload = {
            **request,
            "conversation_id": context.conversation_id,
            "run_id": context.agent_run_id,
            "trace_id": context.trace_id,
            "summary": labels[kind],
            "conditions": conditions,
        }
        action = context.action_service.create(
            context.user,
            "subscription_query",
            payload,
            f"agent-subscription-query:{context.agent_run_id or context.trace_id}",
            source="AGENT",
            expires_in=timedelta(minutes=30),
        )
        context.subscription_query_events.append(SubscriptionQueryRequestedEvent(
            data=SubscriptionQueryRequestedData(
                action_id=action.id,
                query_type=kind,
                summary=labels[kind],
                conditions=conditions,
                risk_level="YELLOW",
                status=action.status,
                expires_at=action.expires_at,
            )
        ))
        return {"status": action.status}

    if kind == "UNSUPPORTED_MANAGEMENT":
        raise DomainError(
            "SUBSCRIPTION_RULE_PAGE_REQUIRED",
            "暂停、恢复、编辑和删除提醒规则，请在订阅管理页操作。",
            422,
        )

    if kind == "INVALID_CONTINUATION":
        raise DomainError("INVALID_REMINDER_LEAD_DAYS", "提前天数只支持1天、3天、7天及其组合", 422)

    if kind == "INVALID_AMOUNT_FILTER":
        raise DomainError("INVALID_AMOUNT_FILTER", "请用数字明确金额门槛，最多保留两位小数。", 422)

    if kind == "FORECAST":
        _forecast_event(context, planning, month=intent.get("month"), amount_gt=intent.get("amount_gt"))
        return {"status": "queried"}

    if kind == "RULES":
        result_id = planning.create_result(context.user, "rules", {
            "reminder_rules": planning.list_reminder_rules(context.user),
            "budget_rules": planning.list_budget_rules(context.user),
        })
        events.append(SubscriptionRulesReadyEvent(data={"result_id": result_id}))
        return {"status": "queried"}

    if kind in {"BUDGET", "INVALID_BUDGET"}:
        require(kind == "BUDGET", "SUBSCRIPTION_BUDGET_AMOUNT_REQUIRED",
                "请说明订阅预算金额，例如“下个月订阅费用不超过200元”", 422)
        month = intent.get("month") or f"{context.current_date.year:04d}-{context.current_date.month:02d}"
        rule, reused, evaluation = planning.upsert_budget_rule(
            context.user, month=month, amount=intent["amount"], key=uuid4().hex
        )
        result_id = planning.create_result(context.user, "budget", evaluation)
        events.append(SubscriptionBudgetReadyEvent(data={
            "rule_id": rule.id, "month": rule.month, "amount": str(rule.amount),
            "result_id": result_id, "reused": reused,
            "over_budget": evaluation["over_budget"],
            "complete": evaluation["complete"],
        }))
        return {"status": "budget_saved"}

    if kind == "REMINDER":
        amount_gt = intent.get("amount_gt")
        verified = [row for row in context.subscription_service.list(context.user)
                    if row["status"] == "VERIFIED"]
        mention = " ".join(context.user_message.casefold().split())
        merchant_matches = [row for row in verified
            if " ".join(row["merchant"].casefold().split()) in mention]
        require(len(merchant_matches) <= 1,
                "SUBSCRIPTION_MERCHANT_AMBIGUOUS",
                "消息中出现多个订阅商户，请先指定一个项目或移除商户名称", 409)
        require(not (merchant_matches and amount_gt is not None),
                "REMINDER_FILTER_CONFLICT",
                "当前规则不能同时限定商户和金额门槛，请分开设置", 422)
        subscription_id = merchant_matches[0]["id"] if len(merchant_matches) == 1 else None
        scope = "SUBSCRIPTION" if subscription_id else "AMOUNT_GT" if amount_gt is not None else "ALL_VERIFIED"
        if amount_gt is not None or intent.get("month"):
            _forecast_event(context, planning, month=intent.get("month"), amount_gt=amount_gt)
        if not intent.get("lead_days"):
            clarification_id = planning.create_clarification(context.user, {
                "scope": scope, "subscription_id": subscription_id,
                "amount_gt": amount_gt, "month": intent.get("month"),
            })
            events.append(SubscriptionClarificationEvent(data={
                "clarification_id": clarification_id,
                "question": "你希望在预计扣费前几天提醒？请选择提前1天、3天、7天，或组合设置。",
                "options": [1, 3, 7],
            }))
            return {"status": "clarification_required"}
        rule, reused = planning.create_reminder_rule(
            context.user, scope=scope, subscription_id=subscription_id,
            amount_gt=amount_gt, month=intent.get("month"),
            lead_days=intent["lead_days"], key=uuid4().hex,
        )
        events.append(SubscriptionReminderRuleSavedEvent(data={
            "rule_id": rule["id"], "scope": rule["scope"],
            "month": rule["month"], "lead_days": rule["lead_days"],
            "amount_gt": rule["amount_gt"], "reused": reused,
        }))
        return {"status": "reminder_saved"}

    if kind == "CONTINUATION":
        rule, reused = planning.complete_clarification(
            context.user, intent["clarification_id"], intent["lead_days"], uuid4().hex
        )
        if rule["scope"] == "AMOUNT_GT" or rule["month"]:
            _forecast_event(context, planning, month=rule["month"], amount_gt=rule["amount_gt"])
        events.append(SubscriptionReminderRuleSavedEvent(data={
            "rule_id": rule["id"], "scope": rule["scope"],
            "month": rule["month"], "lead_days": rule["lead_days"],
            "amount_gt": rule["amount_gt"], "reused": reused,
        }))
        return {"status": "reminder_saved"}

    raise DomainError("SUBSCRIPTION_INTENT_UNSUPPORTED", "暂不支持这项订阅请求", 422)
