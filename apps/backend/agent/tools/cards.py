from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from pydantic import Field

from agent.context import AgentContext
from agent.state import AgentState
from core.errors import require
from schemas.agent import CardActionCreatedEvent, ClarificationRequiredEvent
from schemas.banking import CardApplicationRequest, CardControlsRequest


def _safe_card(context: AgentContext, row: dict) -> dict:
    account = context.account_service.account_detail(context.user, int(row["account_id"]))
    result = {
        "alias": row.get("alias") or "",
        "product_name": row["product_name"],
        "masked_number": row["masked_number"],
        "last4": row["last4"],
        "status": row["status"],
        "account_suffix": account.account_no[-4:],
        "single_limit": row["single_limit"],
        "daily_limit": row["daily_limit"],
        "channels": {
            "online": row["online_enabled"],
            "pos": row["pos_enabled"],
            "atm": row["atm_enabled"],
            "international": row["international_enabled"],
        },
    }
    issuer = getattr(context, "issue_option", None)
    reference = (
        issuer("card", row["id"], row.get("alias") or f"卡片尾号 {row['last4']}")
        if issuer
        else None
    )
    if reference:
        result["option_ref"] = reference
    return result


def _resolve(context: AgentContext, reference: str):
    selected_id = getattr(context, "selected_resource", lambda *args: None)(
        "card", reference
    )
    if selected_id:
        rows = context.card_service.list(context.user)
        selected = [row for row in rows if str(row["id"]) == selected_id]
        require(
            len(selected) == 1,
            "CARD_NOT_FOUND",
            "所选卡片已不可用，请重新选择",
            404,
        )
        return selected[0], None
    value = reference.strip().casefold()
    rows = context.card_service.list(context.user)
    exact = [row for row in rows if value in {str(row.get("alias") or "").casefold(), row["last4"]}]
    if len(exact) == 1:
        return exact[0], None
    partial = exact or [row for row in rows if value and value in str(row.get("alias") or "").casefold()]
    candidates = [_safe_card(context, row) for row in partial[:5]]
    options = [
        {
            "option_ref": row["option_ref"],
            "label": row.get("alias") or f"卡片尾号 {row['last4']}",
            "description": f"尾号 {row['last4']} · {row['status']}",
        }
        for row in candidates
        if row.get("option_ref")
    ]
    if options:
        context.events.append(
            ClarificationRequiredEvent(
                data={
                    "kind": "card",
                    "question": "请选择唯一卡片后继续。",
                    "options": options,
                }
            )
        )
    return None, {
        "status": "needs_clarification" if partial else "not_found",
        "candidates": candidates,
        "message": "请按卡片别名或末四位选择唯一卡片。" if partial else "没有找到本人的对应卡片。",
    }


def _event(context: AgentContext, action: dict, operation: str, last4: str | None) -> dict:
    event = CardActionCreatedEvent(data={"action_id": action["id"], "operation": operation, "card_last4": last4})
    if not any(getattr(old.data, "action_id", None) == action["id"] for old in context.events):
        context.events.append(event)
    return {"status": "action_created", "operation": operation, "card_last4": last4,
            "executed": False, "message": "请求已创建，尚未执行；请在操作页面确认并完成必要验证。"}


def _context(runtime):
    context = runtime.context
    require(context.card_service is not None, "AGENT_CONTEXT_MISSING", "卡片服务未配置", 500)
    return context


@tool
def list_my_cards(runtime: ToolRuntime[AgentContext, AgentState]) -> dict:
    """列出当前登录用户的普通借记卡，仅显示掩码号码和安全字段。"""
    context = _context(runtime)
    rows = context.card_service.list(context.user)
    return {"status": "listed" if rows else "not_found", "cards": [_safe_card(context, row) for row in rows], "count": len(rows)}


@tool
def get_my_card(runtime: ToolRuntime[AgentContext, AgentState], card_ref: Annotated[str, Field(min_length=1, max_length=100)]) -> dict:
    """按本人卡片别名或末四位查询卡片安全展示信息。"""
    context = _context(runtime)
    row, issue = _resolve(context, card_ref)
    return issue or {"status": "matched", "card": _safe_card(context, row)}


@tool
def request_card(runtime: ToolRuntime[AgentContext, AgentState], alias: Annotated[str, Field(default="", max_length=100)] = "") -> dict:
    """创建普通借记卡申请 Action；不会直接开户或制卡。"""
    context = _context(runtime)
    action = context.card_service.request_application(
        context.user,
        CardApplicationRequest(alias=alias),
        f"agent-card:{context.trace_id}:apply",
    )
    return _event(context, action, "申请借记卡", None)


def _card_action(runtime, card_ref, operation, callback):
    context = _context(runtime)
    row, issue = _resolve(context, card_ref)
    if issue:
        return issue
    action = callback(context, row)
    return _event(context, action, operation, row["last4"])


@tool
def activate_my_card(runtime: ToolRuntime[AgentContext, AgentState], card_ref: str) -> dict:
    """创建需要 OTP 的本人借记卡激活 Action。"""
    return _card_action(runtime, card_ref, "激活卡片", lambda c, row: c.card_service.request_activation(
        c.user, row["id"], f"agent-card:{c.trace_id}:activate:{row['id']}"))


@tool
def change_card_limits(
    runtime: ToolRuntime[AgentContext, AgentState],
    card_ref: str,
    single_limit: Annotated[str | None, Field(default=None, pattern=r"^\d{1,5}(?:\.\d{1,2})?$")] = None,
    daily_limit: Annotated[str | None, Field(default=None, pattern=r"^\d{1,6}(?:\.\d{1,2})?$")] = None,
) -> dict:
    """创建本人借记卡限额调整 Action；提额需要 OTP。"""
    if single_limit is None and daily_limit is None:
        return {"status": "needs_clarification", "message": "请提供单笔限额或日累计限额。"}
    return _card_action(runtime, card_ref, "调整限额", lambda c, row: c.card_service.request_controls(
        c.user, row["id"], CardControlsRequest(single_limit=single_limit, daily_limit=daily_limit),
        f"agent-card:{c.trace_id}:limits:{row['id']}"))


@tool
def change_card_channels(
    runtime: ToolRuntime[AgentContext, AgentState],
    card_ref: str,
    online_enabled: bool | None = None,
    pos_enabled: bool | None = None,
    atm_enabled: bool | None = None,
    international_enabled: bool | None = None,
) -> dict:
    """创建本人借记卡渠道开关 Action；开启渠道可能需要 OTP。"""
    values = {key: value for key, value in {
        "online_enabled": online_enabled, "pos_enabled": pos_enabled,
        "atm_enabled": atm_enabled, "international_enabled": international_enabled,
    }.items() if value is not None}
    if not values:
        return {"status": "needs_clarification", "message": "请说明要开启或关闭的渠道。"}
    return _card_action(runtime, card_ref, "调整渠道", lambda c, row: c.card_service.request_controls(
        c.user, row["id"], CardControlsRequest(**values), f"agent-card:{c.trace_id}:channels:{row['id']}"))


def _state_tool(runtime, card_ref, operation, label):
    return _card_action(runtime, card_ref, label, lambda c, row: c.card_service.request_state(
        c.user, row["id"], operation, f"agent-card:{c.trace_id}:{operation}:{row['id']}"))


@tool
def lock_my_card(runtime: ToolRuntime[AgentContext, AgentState], card_ref: str) -> dict:
    """创建本人借记卡锁定 Action。"""
    return _state_tool(runtime, card_ref, "lock", "锁定卡片")


@tool
def unlock_my_card(runtime: ToolRuntime[AgentContext, AgentState], card_ref: str) -> dict:
    """创建需要 OTP 的本人借记卡解锁 Action。"""
    return _state_tool(runtime, card_ref, "unlock", "解锁卡片")


@tool
def report_my_card_lost(runtime: ToolRuntime[AgentContext, AgentState], card_ref: str) -> dict:
    """创建需要 OTP 的本人借记卡永久挂失 Action。"""
    return _state_tool(runtime, card_ref, "report-lost", "挂失卡片")


@tool
def replace_my_card(runtime: ToolRuntime[AgentContext, AgentState], card_ref: str) -> dict:
    """为已挂失的本人借记卡创建补卡 Action。"""
    return _state_tool(runtime, card_ref, "replace", "补办卡片")


@tool
def request_card_number_view(runtime: ToolRuntime[AgentContext, AgentState], card_ref: str) -> dict:
    """创建 OTP 保护的完整 Demo 卡号查看请求；绝不返回卡号。"""
    return _card_action(runtime, card_ref, "安全查看卡号", lambda c, row: c.card_service.request_reveal(
        c.user, row["id"], f"agent-card:{c.trace_id}:reveal:{row['id']}"))
