import hashlib
import json
from decimal import Decimal
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.context import AgentContext
from agent.registry import resolve_agent
from agent.router import DomainRoute, approve_domains
from agent.tools.wealth import (
    list_fixed_deposit_products,
    list_my_fixed_deposits,
    recommend_fixed_deposits,
    request_fixed_deposit_redemption,
    request_fixed_deposit_subscription,
)
from api.agent import get_agent_graph_factory, get_agent_router
from models import Action, AnalysisResult, ProductMetadata, RiskAssessment, User
from schemas.banking import RiskRequest
from services.account_service import AccountService
from services.action_service import ActionService
from services.analysis_result_service import AnalysisResultService
from services.investment_service import InvestmentService


class _References:
    def issue_reference(self, user, conversation_id, kind, resource_id, label):
        value = f"{user.id}:{conversation_id}:{kind}:{resource_id}:{label}"
        return hashlib.sha256(value.encode()).hexdigest()[:32]


def _padded_accounts(core):
    original = core.get_savings_account

    def get(account_id):
        row = original(account_id)
        row["accountNo"] = str(account_id).zfill(9)
        row["clientName"] = {1: "Alice", 2: "Bob", 3: "Charlie"}.get(
            row["clientId"], "Alice"
        )
        return row

    core.get_savings_account = get


def _enable_product(db):
    row = db.get(ProductMetadata, 10)
    if row is None:
        row = ProductMetadata(product_id=10, tenant="default")
        db.add(row)
    row.risk_level = 2
    row.enabled = True
    row.allows_premature = True
    db.commit()


def _runtime(bank, db, user, trace="wealth-run"):
    core = bank["core"]
    accounts = AccountService(core)
    investment = InvestmentService(db, core, bank["settings"])
    context = AgentContext(
        user=user,
        account_service=accounts,
        private_results=AnalysisResultService(
            db, accounts, bank["settings"], investment
        ),
        investment_service=investment,
        action_service=ActionService(db, core, bank["settings"]),
        trace_id=trace,
        conversation_id="wealth-conversation",
        reference_service=_References(),
    )
    return SimpleNamespace(context=context)


def _assess(runtime):
    return runtime.context.investment_service.assess(
        runtime.context.user, RiskRequest(answers=[5, 5, 5, 5, 5])
    )


def _holding(core, *, holding_id=100, owner=1):
    core.holdings[holding_id] = {
        "id": holding_id,
        "clientId": owner,
        "accountNo": str(holding_id).zfill(9),
        "externalId": f"AGENT-HOLDING-{holding_id}",
        "depositProductId": 10,
        "currency": {"code": "CNY"},
        "depositAmount": "800.00",
        "linkAccountId": owner,
        "status": {"active": True},
        "maturityDate": [2099, 1, 1],
        "nominalAnnualInterestRate": "2.0",
    }
    return core.holdings[holding_id]


def test_wealth_domain_registers_only_safe_contracts():
    tools = resolve_agent(("wealth",)).tools
    assert {item.name for item in tools} == {
        "list_fixed_deposit_products",
        "recommend_fixed_deposits",
        "list_my_fixed_deposits",
        "request_fixed_deposit_subscription",
        "request_fixed_deposit_redemption",
    }
    assert approve_domains(
        DomainRoute(domains=["wealth"]), frozenset({"wealth"})
    ) == ("wealth",)
    schema = request_fixed_deposit_subscription.tool_call_schema.model_json_schema()
    assert "user_id" not in json.dumps(schema)
    assert "product_id" not in schema["properties"]
    assert "from_account_id" not in schema["properties"]


def test_product_and_recommendation_numbers_stay_in_private_results(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        _enable_product(db)
        runtime = _runtime(bank, db, alice)

        catalog = list_fixed_deposit_products.func(runtime)
        serialized_catalog = json.dumps(catalog, ensure_ascii=False)
        assert catalog["candidate_count"] == 1
        assert catalog["candidates"][0]["name"] == "Fixed Demo"
        assert "2.0" not in serialized_catalog
        assert "100000" not in serialized_catalog
        stored = db.get(AnalysisResult, catalog["analysis_id"])
        assert stored.kind == "wealth_products"
        assert stored.payload["items"][0]["annual_interest_rates"] == ["2.0"]

        no_assessment = recommend_fixed_deposits.func(
            runtime, amount="1000.00", term_months=3, needs_liquidity=True
        )
        assert no_assessment["status"] == "risk_assessment_required"
        assert runtime.context.events[-1].type == "WEALTH_RISK_ASSESSMENT_REQUIRED"

        _assess(runtime)
        recommended = recommend_fixed_deposits.func(
            runtime, amount="1000.00", term_months=3, needs_liquidity=True
        )
        serialized_recommendation = json.dumps(recommended, ensure_ascii=False)
        assert recommended["candidate_count"] == 1
        assert "2.0" not in serialized_recommendation
        assert "5.00" not in serialized_recommendation
        stored = db.get(AnalysisResult, recommended["analysis_id"])
        assert stored.kind == "wealth_recommend"
        assert stored.payload["items"][0]["annual_interest_rate"] == "2.0"
        assert stored.payload["items"][0]["estimated_interest"] == "5.00"


def test_subscription_is_red_idempotent_and_does_not_move_money(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        _enable_product(db)
        runtime = _runtime(bank, db, alice, trace="wealth-subscription")
        assessment = _assess(runtime)
        before = bank["core"].balances[1]

        first = request_fixed_deposit_subscription.func(
            runtime,
            product="Fixed Demo",
            amount="100.00",
            term_months=3,
            from_account_suffix="0001",
        )
        second = request_fixed_deposit_subscription.func(
            runtime,
            product="Fixed Demo",
            amount="100.00",
            term_months=3,
            from_account_suffix="0001",
        )

        assert first == second
        assert "100.00" not in json.dumps(first)
        assert bank["core"].balances[1] == before
        actions = db.query(Action).filter(Action.kind == "subscription").all()
        assert len(actions) == 1
        action = actions[0]
        assert action.status == "WAITING_CONFIRMATION"
        assert action.risk_level == "RED"
        assert action.source == "AGENT"
        consumed = db.get(RiskAssessment, assessment["id"])
        assert consumed.action_id == action.id and consumed.used_at is not None
        assert runtime.context.events[-1].type == "WEALTH_ACTION_CREATED"


def test_holding_and_redemption_quote_never_enter_tool_result(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        _enable_product(db)
        _holding(bank["core"])
        runtime = _runtime(bank, db, alice, trace="wealth-redemption")

        listed = list_my_fixed_deposits.func(runtime)
        assert listed["candidate_count"] == 1
        assert "800.00" not in json.dumps(listed)
        private = db.get(AnalysisResult, listed["analysis_id"])
        assert private.payload["items"][0]["principal"] == "800.00"

        before = bank["core"].balances[1]
        first = request_fixed_deposit_redemption.func(
            runtime,
            holding="Fixed Demo",
            to_account_suffix="0001",
        )
        second = request_fixed_deposit_redemption.func(
            runtime,
            holding="Fixed Demo",
            to_account_suffix="0001",
        )
        serialized = json.dumps(first)
        assert first == second
        assert "800.00" not in serialized
        assert "quote" not in serialized.casefold()
        assert bank["core"].balances[1] == before
        actions = db.query(Action).filter(Action.kind == "redemption").all()
        assert len(actions) == 1
        assert actions[0].risk_level == "RED"
        assert actions[0].status == "WAITING_CONFIRMATION"


def test_private_wealth_result_is_owner_only_and_revalidated(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        _enable_product(db)
        runtime = _runtime(bank, db, alice)
        result = list_fixed_deposit_products.func(runtime)
        db.commit()

    own = bank["http"].get(
        f"/api/agent/analyses/{result['analysis_id']}",
        headers=bank["headers"]["alice"],
    )
    assert own.status_code == 200
    assert own.json()["data"]["items"][0]["annual_interest_rates"] == ["2.0"]
    other = bank["http"].get(
        f"/api/agent/analyses/{result['analysis_id']}",
        headers=bank["headers"]["bob"],
    )
    assert other.status_code == 404


def test_agent_http_uses_deterministic_risk_event_without_creating_action(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        _enable_product(db)

    class WealthGraph:
        def invoke(self, state, *, context, config):
            result = request_fixed_deposit_subscription.func(
                SimpleNamespace(context=context),
                product="Fixed Demo",
                amount="100.00",
                term_months=3,
                from_account_suffix="0001",
            )
            return {
                "messages": [
                    HumanMessage(content="申购 Fixed Demo"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "request_fixed_deposit_subscription",
                                "args": {},
                                "id": "wealth-risk",
                            }
                        ],
                    ),
                    ToolMessage(content=str(result), tool_call_id="wealth-risk"),
                ],
                "events": [],
            }

    app = bank["http"].app
    app.dependency_overrides[get_agent_router] = lambda: (
        lambda *args, **kwargs: ("wealth",)
    )
    app.dependency_overrides[get_agent_graph_factory] = lambda: (
        lambda domains: WealthGraph()
    )
    try:
        response = bank["http"].post(
            "/api/agent/messages",
            headers=bank["headers"]["alice"],
            json={"message": "申购 Fixed Demo 100 元三个月"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["events"] == [
            {
                "type": "WEALTH_RISK_ASSESSMENT_REQUIRED",
                "data": {
                    "reason": "subscription",
                    "route": "/wealth/risk-assessment",
                },
            }
        ]
        assert "不会替你作答" in body["message"]
        with bank["db"]() as db:
            assert db.query(Action).count() == 0
    finally:
        app.dependency_overrides.pop(get_agent_router, None)
        app.dependency_overrides.pop(get_agent_graph_factory, None)


def test_agent_http_creates_red_action_and_uses_deterministic_event(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        _enable_product(db)
        InvestmentService(db, bank["core"], bank["settings"]).assess(
            alice, RiskRequest(answers=[5, 5, 5, 5, 5])
        )

    seen_tool_result = {}

    class WealthGraph:
        def invoke(self, state, *, context, config):
            result = request_fixed_deposit_subscription.func(
                SimpleNamespace(context=context),
                product="Fixed Demo",
                amount="100.00",
                term_months=3,
                from_account_suffix="0001",
            )
            seen_tool_result.update(result)
            return {
                "messages": [
                    HumanMessage(content="申购 Fixed Demo"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "request_fixed_deposit_subscription",
                                "args": {},
                                "id": "wealth-action",
                            }
                        ],
                    ),
                    ToolMessage(content=str(result), tool_call_id="wealth-action"),
                ],
                "events": [],
            }

    app = bank["http"].app
    app.dependency_overrides[get_agent_router] = lambda: (
        lambda *args, **kwargs: ("wealth",)
    )
    app.dependency_overrides[get_agent_graph_factory] = lambda: (
        lambda domains: WealthGraph()
    )
    before = bank["core"].balances[1]
    try:
        response = bank["http"].post(
            "/api/agent/messages",
            headers=bank["headers"]["alice"],
            json={"message": "申购 Fixed Demo 100 元三个月"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["events"][0]["type"] == "WEALTH_ACTION_CREATED"
        assert body["events"][0]["data"]["operation"] == "subscription"
        assert "资金尚未变更" in body["message"]
        assert "100.00" not in json.dumps(seen_tool_result)
        assert bank["core"].balances[1] == before
        with bank["db"]() as db:
            action = db.query(Action).one()
            assert action.risk_level == "RED" and action.source == "AGENT"
    finally:
        app.dependency_overrides.pop(get_agent_router, None)
        app.dependency_overrides.pop(get_agent_graph_factory, None)
