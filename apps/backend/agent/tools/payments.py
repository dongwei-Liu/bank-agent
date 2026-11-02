from decimal import Decimal
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from pydantic import Field

from agent.context import AgentContext
from agent.state import AgentState
from core.errors import require
from schemas.agent import (
    ClarificationRequiredEvent,
    InternalTransferActionCreatedEvent,
    TransferActionCreatedEvent,
)
from schemas.banking import InternalTransferRequest, TransferRequest


def _normalized(value: str) -> str:
    return value.strip().casefold()


def _recipient_options(context: AgentContext, rows: list[dict]) -> list[dict[str, str]]:
    options = []
    for row in rows[:5]:
        item = {"name": row["name"], "alias": row.get("alias") or ""}
        issuer = getattr(context, "issue_option", None)
        reference = (
            issuer("recipient", row["id"], row.get("alias") or row["name"])
            if issuer
            else None
        )
        if reference:
            item["option_ref"] = reference
        options.append(item)
    return options


def _emit_clarification(context, kind, question, choices):
    options = []
    for choice in choices:
        reference = choice.get("option_ref")
        if not reference:
            continue
        label = choice.get("alias") or choice.get("name") or choice.get("label")
        description = choice.get("description") or ""
        options.append(
            {"option_ref": reference, "label": label, "description": description}
        )
    if options:
        context.events.append(
            ClarificationRequiredEvent(
                data={"kind": kind, "question": question, "options": options}
            )
        )


def _active_accounts(context: AgentContext):
    return [row for row in context.account_service.list_accounts(context.user) if row.status == "ACTIVE"]


def _account_choices(context, accounts):
    choices = []
    for row in accounts:
        item = {
            "product_name": row.product_name,
            "account_suffix": row.account_no[-4:],
        }
        issuer = getattr(context, "issue_option", None)
        reference = (
            issuer(
                "account",
                str(row.id),
                f"{row.product_name} · 尾号 {row.account_no[-4:]}",
            )
            if issuer
            else None
        )
        if reference:
            item["option_ref"] = reference
            item["label"] = f"尾号 {row.account_no[-4:]}"
            item["description"] = row.product_name
        choices.append(item)
    return choices


def _append_event(context: AgentContext, event) -> None:
    action_id = event.data.action_id
    if not any(getattr(existing.data, "action_id", None) == action_id for existing in context.events):
        context.events.append(event)


@tool
def list_my_recipients(runtime: ToolRuntime[AgentContext, AgentState]) -> dict:
    """列出当前登录用户保存的联系人；仅返回姓名和别名。"""
    service = runtime.context.recipient_service
    require(service is not None, "AGENT_CONTEXT_MISSING", "联系人服务未配置", 500)
    contacts = service.list(runtime.context.user)
    candidates = _recipient_options(runtime.context, contacts)
    return {"status": "listed" if contacts else "not_found", "candidates": candidates,
            "total_count": len(contacts), "has_more": len(contacts) > len(candidates)}


@tool
def search_my_recipients(
    runtime: ToolRuntime[AgentContext, AgentState],
    query: Annotated[str, Field(min_length=1, max_length=100, description="联系人姓名或已保存别名。")],
) -> dict:
    """按姓名或别名搜索当前登录用户保存的联系人；不返回内部标识或账户资料。"""
    context = runtime.context
    require(context.recipient_service is not None, "AGENT_CONTEXT_MISSING", "联系人服务未配置", 500)
    value = _normalized(query)
    contacts = context.recipient_service.list(context.user)
    exact = [row for row in contacts if value in {_normalized(row.get("name") or ""), _normalized(row.get("alias") or "")}]
    matches = exact or [row for row in contacts if any(value in _normalized(row.get(field) or "") for field in ("name", "alias"))]
    candidates = _recipient_options(context, matches)
    result = {"status": "matched" if matches else "not_found", "candidates": candidates,
              "total_count": len(matches), "has_more": len(matches) > len(candidates)}
    if len(matches) > 1:
        labels = [(item["name"].casefold(), item["alias"].casefold()) for item in candidates]
        result.update(status="needs_clarification", distinguishable=len(set(labels)) == len(labels),
                      reason="请用户按姓名或别名选择联系人。" if len(set(labels)) == len(labels)
                      else "部分联系人姓名和别名相同，请先在支付页面设置不同别名。")
        _emit_clarification(context, "recipient", result["reason"], candidates)
    return result


@tool
def request_transfer(
    runtime: ToolRuntime[AgentContext, AgentState],
    recipient: Annotated[str, Field(min_length=1, max_length=100, description="唯一匹配的联系人姓名或别名。")],
    amount: Annotated[str, Field(pattern=r"^(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,2})?$", description="CNY 十进制金额。")],
    from_account_suffix: Annotated[str | None, Field(default=None, pattern=r"^\d{4}$")] = None,
    remark: Annotated[str, Field(max_length=500)] = "",
    recipient_ref: Annotated[str | None, Field(default=None, min_length=32, max_length=64)] = None,
    from_account_ref: Annotated[str | None, Field(default=None, min_length=32, max_length=64)] = None,
) -> dict:
    """创建需要用户后续确认的本人 CNY 转账 Action；不会直接扣款。"""
    context = runtime.context
    require(context.recipient_service and context.transfer_service and context.action_service,
            "AGENT_CONTEXT_MISSING", "支付服务未配置", 500)
    query = _normalized(recipient)
    contacts = context.recipient_service.list(context.user)
    resolver = getattr(context, "selected_resource", lambda *args: None)
    selected_recipient_id = resolver("recipient", recipient_ref or recipient)
    if recipient_ref:
        require(selected_recipient_id is not None, "INVALID_OPTION_REFERENCE", "联系人选项已失效，请重新搜索", 422)
    exact = (
        [row for row in contacts if str(row["id"]) == selected_recipient_id]
        if selected_recipient_id
        else [row for row in contacts if query in {_normalized(row.get("name") or ""), _normalized(row.get("alias") or "")}]
    )
    if len(exact) != 1:
        partial = exact or [row for row in contacts if any(query in _normalized(row.get(field) or "") for field in ("name", "alias"))]
        candidates = _recipient_options(context, partial)
        _emit_clarification(
            context,
            "recipient",
            "请从候选联系人中选择唯一收款人。",
            candidates,
        )
        return {"status": "needs_clarification",
                "reason": "请让用户从候选联系人中选择。" if partial else "没有找到匹配的已保存联系人，请先在支付页面添加联系人。",
                "candidates": candidates}

    accounts = _active_accounts(context)
    selected = None
    selected_account_id = resolver("account", from_account_ref or from_account_suffix)
    if from_account_ref:
        require(selected_account_id is not None, "INVALID_OPTION_REFERENCE", "账户选项已失效，请重新选择", 422)
    if selected_account_id:
        matches = [row for row in accounts if str(row.id) == selected_account_id]
        require(len(matches) == 1, "ACCOUNT_NOT_FOUND", "所选账户已不可用，请重新选择", 404)
        selected = matches[0]
    elif from_account_suffix:
        matches = [row for row in accounts if row.account_no.endswith(from_account_suffix)]
        if len(matches) == 1:
            selected = matches[0]
        else:
            return {"status": "needs_clarification", "reason": "付款账户末四位未唯一匹配本人 ACTIVE 储蓄账户。",
                    "available_accounts": _account_choices(context, accounts)}
    elif len(accounts) == 1:
        selected = accounts[0]
    elif accounts:
        choices = _account_choices(context, accounts)
        _emit_clarification(
            context, "account", "请选择用于付款的本人账户。", choices
        )
        return {"status": "needs_clarification", "reason": "本人有多个可用付款账户，请指定末四位。",
                "available_accounts": choices}
    else:
        return {"status": "cannot_create", "reason": "本人没有可用的 ACTIVE 储蓄账户。"}

    contact = exact[0]
    request = TransferRequest(from_account_id=selected.id, recipient_id=contact["id"], amount=amount, remark=remark.strip())
    payload = context.transfer_service.prepare(context.user, request)
    payload.update(recipient_id=request.recipient_id, recipient_display_name=contact["name"],
                   from_account_suffix=selected.account_no[-4:], _request=request.model_dump(mode="json"))
    action = context.action_service.create(context.user, "transfer", payload,
                                           f"agent-transfer:{context.trace_id}", request.amount, source="AGENT")
    _append_event(context, TransferActionCreatedEvent(data={"action_id": action.id,
        "recipient_name": contact["name"], "from_account_suffix": selected.account_no[-4:], "amount": str(request.amount)}))
    return {"status": "created_waiting_confirmation", "recipient_name": contact["name"],
            "from_account_suffix": selected.account_no[-4:], "executed": False}


@tool
def request_internal_transfer(
    runtime: ToolRuntime[AgentContext, AgentState],
    amount: Annotated[str, Field(pattern=r"^(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,2})?$")],
    from_account_suffix: Annotated[str | None, Field(default=None, pattern=r"^\d{4}$")] = None,
    to_account_suffix: Annotated[str | None, Field(default=None, pattern=r"^\d{4}$")] = None,
    remark: Annotated[str, Field(max_length=500)] = "",
) -> dict:
    """为当前用户自己的两个账户创建待确认互转 Action；不会直接扣款。"""
    context = runtime.context
    require(context.transfer_service and context.action_service, "AGENT_CONTEXT_MISSING", "支付服务未配置", 500)
    accounts = _active_accounts(context)
    if len(accounts) < 2:
        return {"status": "cannot_create", "reason": "本人至少需要两个 ACTIVE 储蓄账户。", "available_accounts": _account_choices(context, accounts)}
    if not from_account_suffix or not to_account_suffix:
        choices = _account_choices(context, accounts)
        _emit_clarification(context, "account", "请先选择转出账户；随后还需选择不同的转入账户。", choices)
        return {"status": "needs_clarification", "reason": "请指定转出和转入账户末四位。", "available_accounts": choices}
    source = [row for row in accounts if row.account_no.endswith(from_account_suffix)]
    target = [row for row in accounts if row.account_no.endswith(to_account_suffix)]
    if len(source) != 1 or len(target) != 1 or source[0].id == target[0].id:
        return {"status": "needs_clarification", "reason": "账户末四位未唯一匹配两个不同的本人账户。",
                "available_accounts": _account_choices(context, accounts)}
    request = InternalTransferRequest(from_account_id=source[0].id, to_account_id=target[0].id,
                                      amount=Decimal(amount), remark=remark.strip())
    payload = context.transfer_service.prepare_internal(context.user, request)
    payload.update(from_account_suffix=source[0].account_no[-4:], to_account_suffix=target[0].account_no[-4:],
                   _request=request.model_dump(mode="json"))
    action = context.action_service.create(context.user, "internal_transfer", payload,
                                           f"agent-internal-transfer:{context.trace_id}", request.amount, source="AGENT")
    _append_event(context, InternalTransferActionCreatedEvent(data={"action_id": action.id,
        "from_account_suffix": source[0].account_no[-4:], "to_account_suffix": target[0].account_no[-4:],
        "amount": str(request.amount)}))
    return {"status": "created_waiting_confirmation", "from_account_suffix": source[0].account_no[-4:],
            "to_account_suffix": target[0].account_no[-4:], "executed": False}
