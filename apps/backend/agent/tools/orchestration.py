"""Safe entry points for the fixed birthday orchestration template."""

from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from pydantic import Field

from agent.context import AgentContext
from agent.state import AgentState
from core.errors import require
from schemas.agent import (
    ClarificationRequiredEvent,
    OrchestrationTaskCreatedEvent,
    OrchestrationTasksReadyEvent,
)
from schemas.banking import BirthdayTaskRequest


_AMOUNT_PATTERN = r"(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,2})?"


def _context(runtime):
    context = runtime.context
    require(
        context.orchestration_service is not None,
        "AGENT_CONTEXT_MISSING",
        "生日任务服务未配置",
        500,
    )
    return context


def _normalize(text):
    return re.sub(r"\s+", "", str(text or "")).casefold()


def _explicit_date(message: str, value: date) -> bool:
    compact = _normalize(message)
    candidates = {
        value.isoformat(),
        f"{value.year}年{value.month}月{value.day}日",
        f"{value.year}年{value.month}月{value.day}号",
        f"{value.month}月{value.day}日",
        f"{value.month}月{value.day}号",
    }
    return any(item in compact for item in candidates)


def _labeled_amounts(message: str, labels: tuple[str, ...]) -> set[Decimal]:
    label = "(?:" + "|".join(re.escape(item) for item in labels) + ")"
    patterns = (
        rf"{label}(?:预算|金额|花费)?(?:为|是|：|:)?[¥￥]?({_AMOUNT_PATTERN})(?:元|块)?",
        rf"[¥￥]?({_AMOUNT_PATTERN})(?:元|块)?(?:的)?{label}",
    )
    values: set[Decimal] = set()
    compact = _normalize(message)
    for pattern in patterns:
        for raw in re.findall(pattern, compact):
            try:
                values.add(Decimal(raw))
            except InvalidOperation:
                continue
    return values


def _require_explicit_plan(context, label, event_date, flower_amount, cake_amount):
    message = "\n".join((*context.user_history, context.user_message))
    label_is_explicit = _normalize(label) in _normalize(message)
    date_is_explicit = _explicit_date(message, event_date)
    flower_values = _labeled_amounts(message, ("鲜花", "花束", "买花"))
    cake_values = _labeled_amounts(message, ("蛋糕",))
    if not (
        label_is_explicit
        and date_is_explicit
        and flower_amount in flower_values
        and cake_amount in cake_values
    ):
        return {
            "status": "needs_clarification",
            "code": "BIRTHDAY_DETAILS_REQUIRED",
            "message": "请明确写出事件名称、完整日期、付款账户，以及鲜花和蛋糕各自的金额；不能只给总预算。",
        }
    return None


def _account_options(context, accounts):
    options = []
    for account in accounts[:10]:
        suffix = account.account_no[-4:].zfill(4)
        option_ref = context.issue_option(
            "orchestration_account",
            str(account.id),
            f"{account.product_name} · 尾号 {suffix}",
        )
        if option_ref:
            options.append(
                {
                    "option_ref": option_ref,
                    "label": f"账户尾号 {suffix}",
                    "description": "用于生日任务的鲜花和蛋糕支出",
                }
            )
    return options


def _resolve_account(context, suffix=None, option_ref=None):
    accounts = [
        row
        for row in context.account_service.list_accounts(context.user)
        if row.status == "ACTIVE" and row.currency == "CNY"
    ]
    selected_id = None
    if option_ref and option_ref in context.account_refs:
        selected_id = str(context.resolve_account(option_ref))
    elif option_ref:
        selected_id = context.selected_resource("orchestration_account", option_ref)
        require(
            selected_id is not None,
            "INVALID_OPTION_REFERENCE",
            "付款账户选项已失效，请重新选择",
            422,
        )
    if selected_id:
        matches = [row for row in accounts if str(row.id) == selected_id]
    elif suffix:
        matches = [row for row in accounts if row.account_no[-4:].zfill(4) == suffix]
    else:
        matches = []
    if len(matches) == 1:
        return matches[0], None
    options = _account_options(context, accounts)
    if options:
        context.events.append(
            ClarificationRequiredEvent(
                data={
                    "kind": "orchestration_account",
                    "question": "请选择生日任务唯一的本人 ACTIVE CNY 付款账户。",
                    "options": options,
                }
            )
        )
    return None, {
        "status": "needs_clarification" if options else "not_found",
        "message": "请选择唯一付款账户。" if options else "本人没有可用储蓄账户。",
        "candidate_count": len(options),
    }


@tool
def list_my_birthday_tasks(
    runtime: ToolRuntime[AgentContext, AgentState],
) -> dict:
    """查询当前登录用户的生日任务；详情仅通过本人结构化结果卡展示。"""
    context = _context(runtime)
    rows = context.orchestration_service.list(context.user)
    visible = rows[:20]
    items = [
        {
            "task_id": row["id"],
            "label": row["event"]["label"],
            "event_date": row["event"]["event_date"],
            "status": row["status"],
            "route": f"/tasks/{row['id']}",
        }
        for row in visible
    ]
    context.events.append(
        OrchestrationTasksReadyEvent(
            data={"items": items, "has_more": len(rows) > len(visible)}
        )
    )
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    return {
        "status": "ready",
        "task_count": len(rows),
        "status_counts": status_counts,
        "has_more": len(rows) > len(visible),
    }


@tool
def request_birthday_orchestration(
    runtime: ToolRuntime[AgentContext, AgentState],
    label: Annotated[str, Field(min_length=1, max_length=120)],
    event_date: date,
    flower_amount: Annotated[
        str, Field(pattern=rf"^{_AMOUNT_PATTERN}$")
    ],
    cake_amount: Annotated[
        str, Field(pattern=rf"^{_AMOUNT_PATTERN}$")
    ],
    from_account_suffix: Annotated[
        str | None, Field(default=None, pattern=r"^\d{4}$")
    ] = None,
    from_account_ref: Annotated[
        str | None, Field(default=None, min_length=32, max_length=64)
    ] = None,
) -> dict:
    """创建固定生日礼物任务与 RED 授权 Action；不会直接冻结或转移资金。"""
    context = _context(runtime)
    account, issue = _resolve_account(
        context, from_account_suffix, from_account_ref
    )
    if issue:
        return issue
    flower = Decimal(flower_amount)
    cake = Decimal(cake_amount)
    require(flower > 0 and cake > 0, "INVALID_AMOUNT", "分项金额必须大于 0", 422)
    issue = _require_explicit_plan(context, label, event_date, flower, cake)
    if issue:
        return issue
    result = context.orchestration_service.create_birthday_task(
        context.user,
        BirthdayTaskRequest(
            label=label,
            event_date=event_date,
            from_account_id=account.id,
            flower_amount=flower,
            cake_amount=cake,
        ),
        f"agent-orchestration:{context.trace_id}:birthday",
        source="AGENT",
    )
    authorization = result["authorization"]
    event = OrchestrationTaskCreatedEvent(
        data={
            "task_id": result["id"],
            "action_id": authorization["action_id"],
            "task_status": result["status"],
            "authorization_status": authorization["status"],
            "route": f"/tasks/{result['id']}",
        }
    )
    if not any(
        getattr(item, "type", None) == event.type
        and getattr(item.data, "task_id", None) == result["id"]
        for item in context.events
    ):
        context.events.append(event)
    return {
        "status": "authorization_required",
        "executed": result["status"] == "SUCCEEDED",
        "message": "生日任务已保存；请在任务页核对计划，并在操作页完成确认与 OTP。",
    }
