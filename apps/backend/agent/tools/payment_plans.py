from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from pydantic import Field

from agent.context import AgentContext
from agent.state import AgentState
from core.errors import require
from schemas.agent import AAPaymentActionCreatedEvent, ScheduleAuthorizationCreatedEvent
from schemas.banking import AARequest, AAParticipant, AAPayRequest, ScheduleRequest


def _norm(value: str) -> str:
    return value.strip().casefold()


def _contacts(context, name):
    query = _norm(name)
    rows = context.recipient_service.list(context.user)
    exact = [row for row in rows if query in {_norm(row.get("name", "")), _norm(row.get("alias", ""))}]
    return exact or [row for row in rows if query and any(query in _norm(row.get(field, "")) for field in ("name", "alias"))]


def _accounts(context):
    return [row for row in context.account_service.list_accounts(context.user) if row.status == "ACTIVE"]


def _select_account(context, suffix):
    rows = _accounts(context)
    choices = [{"product_name": row.product_name, "account_suffix": row.account_no[-4:]} for row in rows]
    if not suffix:
        return (rows[0], None) if len(rows) == 1 else (None, {"status": "needs_clarification", "accounts": choices, "message": "请指定本人账户末四位。"})
    matches = [row for row in rows if row.account_no.endswith(suffix)]
    if len(matches) != 1:
        return None, {"status": "needs_clarification", "accounts": choices, "message": "该尾号未唯一匹配本人 ACTIVE 账户。"}
    return matches[0], None


def _append_event(context, event):
    if not any(getattr(old.data, "action_id", None) == event.data.action_id for old in context.events):
        context.events.append(event)


def _require_services(context):
    require(context.recipient_service and context.schedule_service and context.aa_service,
            "AGENT_CONTEXT_MISSING", "计划支付服务未配置", 500)


@tool
def request_scheduled_transfer(
    runtime: ToolRuntime[AgentContext, AgentState],
    recipient: Annotated[str, Field(min_length=1, max_length=100, description="本人已保存联系人的姓名或别名。")],
    amount: Annotated[str, Field(pattern=r"^(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,2})?$")],
    execute_at: Annotated[str, Field(description="含时区的 ISO 8601 首次执行时间。")],
    recurrence: Literal["once", "daily", "weekly", "monthly"] = "once",
    from_account_suffix: Annotated[str | None, Field(default=None, pattern=r"^\d{4}$")] = None,
    daily_limit: Annotated[str | None, Field(default=None, pattern=r"^\d{1,16}(?:\.\d{1,2})?$")] = None,
    valid_until: Annotated[str | None, Field(default=None, description="含时区的授权截止时间。")]=None,
    remark: Annotated[str, Field(max_length=500)] = "",
) -> dict:
    """保存定时转账草稿并创建授权 Action；不会立即转账。"""
    context = runtime.context
    _require_services(context)
    matches = _contacts(context, recipient)
    if len(matches) != 1:
        return {"status": "needs_clarification" if matches else "recipient_not_found",
                "candidates": [{"name": row["name"], "alias": row.get("alias", "")} for row in matches[:5]],
                "message": "请按姓名或别名选择唯一联系人。" if matches else "没有找到本人已保存的联系人。"}
    account, issue = _select_account(context, from_account_suffix)
    if issue:
        return issue
    try:
        first_run = datetime.fromisoformat(execute_at.replace("Z", "+00:00"))
        deadline = datetime.fromisoformat(valid_until.replace("Z", "+00:00")) if valid_until else None
    except ValueError:
        return {"status": "needs_clarification", "message": "时间必须使用含时区的 ISO 8601 格式。"}
    if recurrence == "once":
        daily_limit = daily_limit or amount
        deadline = deadline or first_run + timedelta(days=1)
    elif daily_limit is None or deadline is None:
        return {"status": "needs_clarification", "message": "周期计划还需要每日上限和授权截止时间。"}
    request = ScheduleRequest(
        from_account_id=account.id,
        recipient_id=matches[0]["id"],
        amount=Decimal(amount),
        remark=remark.strip(),
        execute_at=first_run,
        recurrence=recurrence,
        daily_limit=Decimal(daily_limit),
        valid_until=deadline,
    )
    schedule = context.schedule_service.save(
        context.user,
        request,
        idempotency_key=f"agent-schedule:{context.trace_id}",
        display_metadata={"recipient_display_name": matches[0]["name"], "from_account_suffix": account.account_no[-4:]},
    )
    action = context.schedule_service.authorize(
        context.user, schedule["id"], f"agent-schedule-auth:{context.trace_id}"
    )
    event = ScheduleAuthorizationCreatedEvent(data={
        "action_id": action["id"], "recipient_name": matches[0]["name"],
        "from_account_suffix": account.account_no[-4:], "amount": str(request.amount),
        "recurrence": recurrence, "execute_at": first_run.isoformat(),
        "daily_limit": str(request.daily_limit), "valid_until": deadline.isoformat(),
    })
    _append_event(context, event)
    return {"status": "authorization_pending", "recipient": matches[0]["name"],
            "recurrence": recurrence, "executed": False,
            "message": "计划已保存但尚未生效，请在操作页确认并完成 OTP 授权。"}


@tool
def list_my_scheduled_transfers(runtime: ToolRuntime[AgentContext, AgentState]) -> dict:
    """列出当前登录用户自己的定时转账计划。"""
    context = runtime.context
    _require_services(context)
    rows = context.schedule_service.agent_list(context.user)
    return {"status": "listed" if rows else "not_found", "schedules": rows, "count": len(rows)}


@tool
def manage_my_scheduled_transfer(
    runtime: ToolRuntime[AgentContext, AgentState],
    schedule_ref: Annotated[str, Field(min_length=1, max_length=100)],
    operation: Literal["pause", "resume", "cancel"],
) -> dict:
    """暂停、恢复或取消当前登录用户自己的计划。"""
    context = runtime.context
    _require_services(context)
    row = context.schedule_service.state(context.user, schedule_ref, operation)
    safe = next((item for item in context.schedule_service.agent_list(context.user) if item["schedule_ref"] == row["id"]), None)
    return {"status": "updated", "operation": operation, "schedule": safe or {"status": row["status"]}}


def _resolve_collection(context, reference):
    rows = context.aa_service.list(context.user)
    value = _norm(reference)
    exact = [row for row in rows if row["id"].casefold() == value]
    if exact:
        return exact[0], None
    matches = [row for row in rows if _norm(row["title"]) == value]
    if len(matches) == 1:
        return matches[0], None
    safe = [{"collection_ref": row["id"], "title": row["title"], "amount": str(row["amount"]), "status": row["status"]} for row in matches]
    return None, {"status": "needs_clarification" if matches else "not_found", "candidates": safe,
                  "message": "请选择唯一的 AA 收款请求。" if matches else "没有找到本人有权查看的 AA 收款请求。"}


@tool
def create_aa_collection(
    runtime: ToolRuntime[AgentContext, AgentState],
    title: Annotated[str, Field(min_length=1, max_length=100)],
    amount: Annotated[str, Field(pattern=r"^(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,2})?$")],
    collector_account_suffix: Annotated[str, Field(pattern=r"^\d{4}$")],
    participants: Annotated[list[str], Field(min_length=1, max_length=20, description="已保存联系人的姓名或别名。")],
) -> dict:
    """按已保存联系人创建均分 AA 请求；不会向任何参与人扣款。"""
    context = runtime.context
    _require_services(context)
    account, issue = _select_account(context, collector_account_suffix)
    if issue:
        return issue
    participant_ids = []
    labels = []
    unresolved = []
    for name in participants:
        matches = _contacts(context, name)
        if len(matches) != 1:
            unresolved.append(name)
            continue
        detail = context.recipient_service.details(context.user, matches[0]["id"])
        if not detail.get("participant_user_id"):
            unresolved.append(name)
            continue
        participant_ids.append(detail["participant_user_id"])
        labels.append(matches[0]["name"])
    if unresolved:
        return {"status": "participants_unresolved", "unmatched": unresolved,
                "message": "部分联系人未唯一匹配或未映射到可登录用户。"}
    participant_ids.append(context.user.id)
    if len(set(participant_ids)) != len(participant_ids):
        return {"status": "participants_unresolved", "message": "参与人重复，或多个联系人映射到同一用户。"}
    request = AARequest(
        account_id=account.id,
        title=title.strip(),
        amount=Decimal(amount),
        mode="equal",
        participants=[AAParticipant(user_id=user_id) for user_id in participant_ids],
    )
    result = context.aa_service.save(context.user, request, idempotency_key=f"agent-aa:{context.trace_id}")
    safe = next(row for row in context.aa_service.agent_list(context.user) if row["collection_ref"] == result["id"])
    return {"status": "created", "collection": safe, "participants": labels + ["本人"],
            "charged": False, "message": "AA 收款请求已创建，参与人尚未付款。"}


@tool
def list_my_aa_requests(runtime: ToolRuntime[AgentContext, AgentState]) -> dict:
    """列出本人创建或参与的 AA 请求，不暴露内部用户或账户标识。"""
    context = runtime.context
    _require_services(context)
    rows = context.aa_service.agent_list(context.user)
    return {"status": "listed" if rows else "not_found", "collections": rows, "count": len(rows)}


@tool
def process_my_aa_request(
    runtime: ToolRuntime[AgentContext, AgentState],
    collection_ref: Annotated[str, Field(min_length=1, max_length=100)],
    operation: Literal["pay", "cancel_my_share", "cancel_collection"],
    from_account_suffix: Annotated[str | None, Field(default=None, pattern=r"^\d{4}$")] = None,
) -> dict:
    """支付或取消本人份额，或取消本人创建的整张 AA 请求。"""
    context = runtime.context
    _require_services(context)
    collection, issue = _resolve_collection(context, collection_ref)
    if issue:
        return issue
    if operation == "cancel_collection":
        context.aa_service.cancel(context.user, collection["id"])
        return {"status": "cancelled", "title": collection["title"]}
    own_share = next((row for row in collection["shares"] if row["user_id"] == context.user.id), None)
    if not own_share:
        return {"status": "not_your_share", "message": "当前登录用户不是该请求参与人。"}
    if operation == "cancel_my_share":
        share = context.aa_service.cancel_share(context.user, collection["id"], own_share["id"])
        return {"status": "cancelled", "title": collection["title"], "amount": str(share["amount"]), "participant": "本人"}
    retrying = own_share["status"] == "PENDING" and own_share.get("action_id")
    if own_share["status"] != "UNPAID" and not retrying:
        return {"status": "cannot_pay", "share_status": own_share["status"], "message": "本人份额当前不可付款。"}
    account, account_issue = _select_account(context, from_account_suffix)
    if account_issue:
        return account_issue
    action = context.aa_service.pay(
        context.user, collection["id"], own_share["id"], AAPayRequest(from_account_id=account.id),
        f"agent-aa-pay:{context.trace_id}:{own_share['id']}",
    )
    _append_event(context, AAPaymentActionCreatedEvent(data={
        "action_id": action["id"], "title": collection["title"],
        "from_account_suffix": account.account_no[-4:], "amount": str(own_share["amount"]),
    }))
    return {"status": "payment_confirmation_pending", "title": collection["title"],
            "from_account_suffix": account.account_no[-4:], "executed": False}
