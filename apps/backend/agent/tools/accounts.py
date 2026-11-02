from datetime import date
from typing import Annotated, Literal

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from pydantic import Field
from agent.context import AgentContext
from agent.state import AgentState
from core.errors import require


@tool
def get_my_balance(runtime: ToolRuntime[AgentContext, AgentState]) -> dict:
    """查询本人普通储蓄账户余额，模型只接收完成状态，精确余额由授权结果卡展示。"""
    context = runtime.context
    require(context.private_results is not None, "AGENT_CONTEXT_MISSING", "分析服务未配置", 500)
    data = context.account_service.summary(context.user, include_scope=True)
    return context.private_results.store(context.user, "balance", data, data["account_ids"])


@tool
def get_my_transactions(
    runtime: ToolRuntime[AgentContext, AgentState],
    limit: Annotated[int, Field(default=10, ge=1, le=20)] = 10,
    from_date: date | None = None,
    to_date: date | None = None,
    direction: Literal["credit", "debit"] | None = None,
) -> dict:
    """查询本人普通储蓄账户近期流水；精确金额和明细仅由授权结果卡展示。"""
    context = runtime.context
    require(context.private_results is not None, "AGENT_CONTEXT_MISSING", "分析服务未配置", 500)
    require(context.transaction_service is not None, "AGENT_CONTEXT_MISSING", "流水服务未配置", 500)
    require(not (from_date and to_date) or from_date <= to_date, "INVALID_DATE", "日期范围无效")
    accounts = [row for row in context.account_service.list_accounts(context.user) if row.status == "ACTIVE"]
    items = []
    for account in accounts:
        page = context.transaction_service.list(
            context.user,
            account.id,
            page=0,
            page_size=limit,
            from_date=from_date,
            to_date=to_date,
            direction=direction,
        )
        items.extend(page["items"])
    items.sort(key=lambda row: (row["date"], row["transaction_id"]), reverse=True)
    items = items[:limit]
    payload = {
        "currency": "CNY",
        "items": items,
        "transaction_count": len(items),
        "complete": True,
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
    }
    return context.private_results.store(
        context.user,
        "transactions",
        payload,
        [account.id for account in accounts],
        from_date,
        to_date,
    )
