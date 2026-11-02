"""Wealth tools keep exact financial facts outside the model context."""

from decimal import Decimal
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from pydantic import Field

from agent.context import AgentContext
from agent.state import AgentState
from core.errors import DomainError, require
from core.security import fingerprint
from schemas.agent import (
    ClarificationRequiredEvent,
    WealthActionCreatedEvent,
    WealthRiskAssessmentRequiredEvent,
)
from schemas.banking import RedemptionRequest, SubscriptionRequest


TERM_UNITS = {0: "days", 1: "weeks", 2: "months", 3: "years"}


def _enum_id(value):
    return value.get("id") if isinstance(value, dict) else value


def _iso_date(value):
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return f"{int(value[0]):04d}-{int(value[1]):02d}-{int(value[2]):02d}"
    return str(value or "")


def _context(runtime, *, write=False):
    context = runtime.context
    require(
        context.investment_service is not None
        and context.private_results is not None,
        "AGENT_CONTEXT_MISSING",
        "财富服务未配置",
        500,
    )
    if write:
        require(
            context.action_service is not None,
            "AGENT_CONTEXT_MISSING",
            "操作授权服务未配置",
            500,
        )
    return context


def _status(raw):
    value = raw.get("status") or {}
    if isinstance(value, str):
        return value
    if value.get("matured"):
        return "MATURED"
    if value.get("active"):
        return "ACTIVE"
    if value.get("approved"):
        return "APPROVED"
    if value.get("submittedAndPendingApproval"):
        return "PENDING_APPROVAL"
    if value.get("closed") or value.get("prematureClosed"):
        return "CLOSED"
    return str(value.get("value") or value.get("code") or "UNKNOWN")


def _rates(product):
    values = set()
    charts = [product["activeChart"]] if product.get("activeChart") else product.get("interestRateCharts", [])
    for chart in charts:
        for slab in chart.get("chartSlabs", []):
            if slab.get("annualInterestRate") is not None:
                values.add(str(slab["annualInterestRate"]))
    return sorted(values, key=Decimal)


def _product_private(product):
    metadata = product.get("suitability") or {}
    min_unit = _enum_id(product.get("minDepositTermType", product.get("minDepositTermTypeId")))
    max_unit = _enum_id(product.get("maxDepositTermType", product.get("maxDepositTermTypeId")))
    return {
        "product_id": int(product["id"]),
        "name": str(product.get("name") or product.get("shortName") or "定期存款"),
        "currency": str((product.get("currency") or {}).get("code") or ""),
        "min_deposit_amount": str(product.get("minDepositAmount") or ""),
        "max_deposit_amount": str(product.get("maxDepositAmount") or ""),
        "min_term": {
            "value": product.get("minDepositTerm"),
            "unit": TERM_UNITS.get(min_unit, "unknown"),
        },
        "max_term": {
            "value": product.get("maxDepositTerm"),
            "unit": TERM_UNITS.get(max_unit, "unknown"),
        },
        "annual_interest_rates": _rates(product),
        "risk_level": metadata.get("risk_level"),
        "allows_premature": bool(metadata.get("allows_premature")),
        "enabled": bool(metadata.get("enabled")),
    }


def _product_options(context, products):
    result = []
    for product in products[:10]:
        name = str(product.get("name") or product.get("shortName") or "定期存款")
        reference = context.issue_option("product", str(product["id"]), name)
        item = {"name": name}
        if reference:
            item["option_ref"] = reference
        result.append(item)
    return result


def _emit_clarification(context, kind, question, rows, description):
    options = [
        {
            "option_ref": row["option_ref"],
            "label": row["name"],
            "description": description,
        }
        for row in rows
        if row.get("option_ref")
    ]
    if options:
        context.events.append(
            ClarificationRequiredEvent(
                data={"kind": kind, "question": question, "options": options}
            )
        )


def _risk_required(context, reason):
    event = WealthRiskAssessmentRequiredEvent(data={"reason": reason})
    if not any(getattr(item, "type", None) == event.type for item in context.events):
        context.events.append(event)
    return {
        "status": "risk_assessment_required",
        "reason": reason,
        "message": "需要用户本人在结构化页面完成本次五题风险测评。",
    }


def _store(context, kind, payload, *, scope_details=None):
    summary = context.private_results.store(
        context.user,
        kind,
        payload,
        payload.get("dependency_account_ids", []),
        scope_details=scope_details,
    )
    return {
        "status": "ready",
        "analysis_id": summary["analysis_id"],
        "kind": kind,
        "insight_codes": summary["insight_codes"],
    }


def _resolve_product(context, value, option_ref=None):
    products = context.investment_service.products(context.user)
    selected_id = context.selected_resource("product", option_ref or value)
    if option_ref:
        require(
            selected_id is not None,
            "INVALID_OPTION_REFERENCE",
            "产品选项已失效，请重新查询",
            422,
        )
    normalized = (value or "").strip().casefold()
    matches = (
        [row for row in products if str(row["id"]) == selected_id]
        if selected_id
        else [
            row
            for row in products
            if normalized
            and normalized
            == str(row.get("name") or row.get("shortName") or "").casefold()
        ]
    )
    if len(matches) == 1:
        return matches[0], None
    partial = matches or [
        row
        for row in products
        if normalized
        and normalized in str(row.get("name") or row.get("shortName") or "").casefold()
    ]
    choices = _product_options(context, partial or products)
    _emit_clarification(
        context,
        "product",
        "请选择唯一的定存产品后继续。",
        choices,
        "产品条款请查看私有结果卡",
    )
    return None, {
        "status": "needs_clarification" if choices else "not_found",
        "candidates": choices,
        "message": "请选择唯一产品。" if choices else "当前没有可用定存产品。",
    }


def _account_options(context, accounts):
    rows = []
    for account in accounts[:10]:
        suffix = account.account_no[-4:].zfill(4)
        reference = context.issue_option(
            "account", str(account.id), f"{account.product_name} · 尾号 {suffix}"
        )
        row = {"name": f"账户尾号 {suffix}"}
        if reference:
            row["option_ref"] = reference
        rows.append(row)
    return rows


def _resolve_account(context, suffix=None, option_ref=None):
    accounts = [
        row
        for row in context.account_service.list_accounts(context.user)
        if row.status == "ACTIVE"
    ]
    selected_id = None
    if option_ref and option_ref in context.account_refs:
        selected_id = str(context.resolve_account(option_ref))
    elif option_ref:
        selected_id = context.selected_resource("account", option_ref)
        require(
            selected_id is not None,
            "INVALID_OPTION_REFERENCE",
            "账户选项已失效，请重新选择",
            422,
        )
    if selected_id:
        matches = [row for row in accounts if str(row.id) == selected_id]
    elif suffix:
        matches = [row for row in accounts if row.account_no[-4:].zfill(4) == suffix]
    elif len(accounts) == 1:
        matches = accounts
    else:
        matches = []
    if len(matches) == 1:
        return matches[0], None
    choices = _account_options(context, accounts)
    _emit_clarification(
        context,
        "account",
        "请选择唯一的本人 ACTIVE CNY 储蓄账户。",
        choices,
        "用于本次财富操作",
    )
    return None, {
        "status": "needs_clarification" if choices else "not_found",
        "candidates": choices,
        "message": "请选择唯一账户。" if choices else "本人没有可用储蓄账户。",
    }


def _holding_private(context, holding):
    product = context.investment_service.product(
        context.user, int(holding["depositProductId"])
    )
    name = str(product.get("name") or product.get("shortName") or "定期存款")
    account_no = str(holding.get("accountNo") or "")
    return {
        "holding_id": int(holding["id"]),
        "product_id": int(holding["depositProductId"]),
        "product_name": name,
        "account_suffix": account_no[-4:].zfill(4) if account_no else "",
        "principal": str(holding.get("depositAmount") or "0"),
        "currency": str((holding.get("currency") or {}).get("code") or ""),
        "annual_interest_rate": str(holding.get("nominalAnnualInterestRate") or ""),
        "maturity_date": _iso_date(holding.get("maturityDate")),
        "status": _status(holding),
    }


def _holding_options(context, holdings):
    result = []
    for holding in holdings[:10]:
        private = _holding_private(context, holding)
        suffix = private["account_suffix"]
        label = private["product_name"] + (f" · 尾号 {suffix}" if suffix else "")
        reference = context.issue_option("holding", str(holding["id"]), label)
        item = {"name": label}
        if reference:
            item["option_ref"] = reference
        result.append(item)
    return result


def _resolve_holding(context, value, option_ref=None):
    holdings = context.investment_service.holdings(context.user)
    selected_id = context.selected_resource("holding", option_ref or value)
    if option_ref:
        require(
            selected_id is not None,
            "INVALID_OPTION_REFERENCE",
            "持有选项已失效，请重新查询",
            422,
        )
    normalized = (value or "").strip().casefold()
    if selected_id:
        matches = [row for row in holdings if str(row["id"]) == selected_id]
    else:
        matches = []
        for row in holdings:
            private = _holding_private(context, row)
            candidates = {
                private["product_name"].casefold(),
                private["account_suffix"].casefold(),
            }
            if normalized and normalized in candidates:
                matches.append(row)
    if len(matches) == 1:
        return matches[0], None
    choices = _holding_options(context, matches or holdings)
    _emit_clarification(
        context,
        "holding",
        "请选择唯一的定存持有后继续。",
        choices,
        "本金和到期信息请查看私有结果卡",
    )
    return None, {
        "status": "needs_clarification" if choices else "not_found",
        "candidates": choices,
        "message": "请选择唯一持有。" if choices else "当前没有定存持有。",
    }


def _existing(context, kind, key, expected, ignored=()):
    action = context.action_service.find_by_key(context.user, kind, key)
    if action is None:
        return None
    actual = dict(action.payload.get("_request", {}))
    expected = dict(expected)
    for name in ignored:
        actual.pop(name, None)
        expected.pop(name, None)
    require(
        fingerprint(actual) == fingerprint(expected),
        "IDEMPOTENCY_CONFLICT",
        "同一 Agent 运行中的财富请求参数发生变化",
        409,
    )
    return action


def _action_event(context, action, operation):
    event = WealthActionCreatedEvent(
        data={
            "action_id": action.id,
            "operation": operation,
            "status": action.status,
        }
    )
    if not any(
        getattr(item.data, "action_id", None) == action.id
        for item in context.events
    ):
        context.events.append(event)
    return {
        "status": "action_created",
        "operation": operation,
        "executed": action.status == "SUCCEEDED",
        "message": "请求已保存；请在操作页核对状态并完成必要的确认和 OTP。",
    }


@tool
def list_fixed_deposit_products(
    runtime: ToolRuntime[AgentContext, AgentState],
) -> dict:
    """查询可用 CNY 定存产品；精确条款只进入本人私有结果卡。"""
    context = _context(runtime)
    products = context.investment_service.products(context.user)
    private_items = [_product_private(row) for row in products]
    result = _store(
        context,
        "wealth_products",
        {
            "items": private_items,
            "dependency_product_ids": [row["product_id"] for row in private_items],
        },
    )
    result["candidates"] = _product_options(context, products)
    result["candidate_count"] = len(products)
    return result


@tool
def recommend_fixed_deposits(
    runtime: ToolRuntime[AgentContext, AgentState],
    amount: Annotated[
        str,
        Field(pattern=r"^(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,2})?$"),
    ],
    term_months: Annotated[int, Field(ge=1, le=120)],
    needs_liquidity: bool = False,
) -> dict:
    """按本人测评、金额、期限和流动性筛选定存；不返回利率或收益数值。"""
    context = _context(runtime)
    try:
        recommendations = context.investment_service.recommendations(
            context.user, Decimal(amount), term_months, needs_liquidity
        )
    except DomainError as exc:
        if exc.code in {"RISK_ASSESSMENT_REQUIRED", "ASSESSMENT_ALREADY_USED"}:
            return _risk_required(context, "recommendation")
        raise
    private_items = [
        {
            "product": _product_private(row["product"]),
            "term_months": row["term_months"],
            "annual_interest_rate": str(row["annual_interest_rate"]),
            "estimated_interest": str(row["estimated_interest"]),
            "estimate_only": bool(row.get("estimate_only", True)),
            "reason": row["reason"],
        }
        for row in recommendations
    ]
    result = _store(
        context,
        "wealth_recommend",
        {
            "criteria": {
                "amount": amount,
                "term_months": term_months,
                "needs_liquidity": needs_liquidity,
            },
            "items": private_items,
            "dependency_product_ids": [
                row["product"]["product_id"] for row in private_items
            ],
        },
        scope_details={
            "amount": amount,
            "term_months": term_months,
            "needs_liquidity": needs_liquidity,
        },
    )
    products = [row["product"] for row in recommendations]
    result["candidates"] = _product_options(context, products)
    result["candidate_count"] = len(products)
    return result


@tool
def list_my_fixed_deposits(
    runtime: ToolRuntime[AgentContext, AgentState],
) -> dict:
    """查询当前登录用户的定存持有；精确本金和利率只进入私有结果卡。"""
    context = _context(runtime)
    holdings = context.investment_service.holdings(context.user)
    private_items = [_holding_private(context, row) for row in holdings]
    result = _store(
        context,
        "wealth_holdings",
        {
            "items": private_items,
            "dependency_holding_ids": [row["holding_id"] for row in private_items],
            "dependency_product_ids": [row["product_id"] for row in private_items],
        },
    )
    result["candidates"] = _holding_options(context, holdings)
    result["candidate_count"] = len(holdings)
    return result


@tool
def request_fixed_deposit_subscription(
    runtime: ToolRuntime[AgentContext, AgentState],
    product: Annotated[str, Field(min_length=1, max_length=120)],
    amount: Annotated[
        str,
        Field(pattern=r"^(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,2})?$"),
    ],
    term_months: Annotated[int, Field(ge=1, le=120)],
    from_account_suffix: Annotated[
        str | None, Field(default=None, pattern=r"^\d{4}$")
    ] = None,
    product_ref: Annotated[
        str | None, Field(default=None, min_length=32, max_length=64)
    ] = None,
    from_account_ref: Annotated[
        str | None, Field(default=None, min_length=32, max_length=64)
    ] = None,
) -> dict:
    """创建 RED 定存申购 Action；不会直接移动资金。"""
    context = _context(runtime, write=True)
    selected_product, issue = _resolve_product(context, product, product_ref)
    if issue:
        return issue
    account, issue = _resolve_account(
        context, from_account_suffix, from_account_ref
    )
    if issue:
        return issue
    key = f"agent-wealth:{context.trace_id}:subscription"
    base_request = {
        "product_id": int(selected_product["id"]),
        "from_account_id": int(account.id),
        "amount": str(Decimal(amount)),
        "term_months": term_months,
    }
    existing = _existing(
        context, "subscription", key, base_request, ignored=("assessment_id",)
    )
    if existing:
        return _action_event(context, existing, "subscription")
    try:
        assessment = context.investment_service.risk(
            context.user, require_unused=True
        )
    except DomainError as exc:
        if exc.code in {"RISK_ASSESSMENT_REQUIRED", "ASSESSMENT_ALREADY_USED"}:
            return _risk_required(context, "subscription")
        raise
    request = SubscriptionRequest(
        **base_request, assessment_id=assessment.id
    )
    payload = context.investment_service.prepare_subscription(
        context.user, request
    )
    payload["_request"] = request.model_dump(mode="json")
    action = context.action_service.create(
        context.user,
        "subscription",
        payload,
        key,
        request.amount,
        commit=False,
        source="AGENT",
    )
    context.investment_service.consume_assessment(
        context.user, payload["assessment_id"], action
    )
    context.action_service.db.commit()
    return _action_event(context, action, "subscription")


@tool
def request_fixed_deposit_redemption(
    runtime: ToolRuntime[AgentContext, AgentState],
    holding: Annotated[str, Field(min_length=1, max_length=120)],
    to_account_suffix: Annotated[
        str | None, Field(default=None, pattern=r"^\d{4}$")
    ] = None,
    holding_ref: Annotated[
        str | None, Field(default=None, min_length=32, max_length=64)
    ] = None,
    to_account_ref: Annotated[
        str | None, Field(default=None, min_length=32, max_length=64)
    ] = None,
) -> dict:
    """为本人定存创建整笔赎回 RED Action；报价不进入模型上下文。"""
    context = _context(runtime, write=True)
    selected_holding, issue = _resolve_holding(context, holding, holding_ref)
    if issue:
        return issue
    account, issue = _resolve_account(context, to_account_suffix, to_account_ref)
    if issue:
        return issue
    key = f"agent-wealth:{context.trace_id}:redemption"
    base_request = {
        "holding_id": int(selected_holding["id"]),
        "to_account_id": int(account.id),
    }
    existing = _existing(
        context, "redemption", key, base_request, ignored=("quote_hash",)
    )
    if existing:
        return _action_event(context, existing, "redemption")
    quote = context.investment_service.quote(
        context.user, base_request["holding_id"], base_request["to_account_id"]
    )
    request = RedemptionRequest(**base_request, quote_hash=quote["quote_hash"])
    payload = context.investment_service.prepare_redemption(context.user, request)
    payload["_request"] = request.model_dump(mode="json")
    action = context.action_service.create(
        context.user,
        "redemption",
        payload,
        key,
        Decimal(payload["principal"]),
        source="AGENT",
    )
    return _action_event(context, action, "redemption")
