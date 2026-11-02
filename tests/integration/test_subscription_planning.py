import calendar
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select
from fastapi.testclient import TestClient

import agent.graph as graph_module
from api.agent import get_agent_graph_factory, get_agent_router
from api.agent import execute_agent_message
from agent.context import parse_subscription_intent
from core.security import SHANGHAI, now
from models import (
    Action,
    AgentEvent,
    Merchant,
    Subscription,
    SubscriptionAgentResult,
    SubscriptionBudgetRule,
    SubscriptionClarification,
    SubscriptionNotification,
    SubscriptionReminderRule,
)
from services.subscription_planning_service import SubscriptionPlanningService
from services.agent_conversation_service import AgentConversationService


def add_subscription(bank, *, user="alice", name="Stream Box", status="VERIFIED",
                     cadence="MONTHLY", amount="80.00", next_charge=None,
                     occurrences=None, adapter="demo_subscription"):
    with bank["db"]() as db:
        user_id = bank["ids"][{"alice": 0, "bob": 1, "charlie": 2}[user]]
        merchant = Merchant(
            external_key=f"planning:{user}:{name}:{cadence}:{status}:{next_charge}",
            name=name, category="订阅", adapter_type=adapter,
        )
        db.add(merchant)
        db.flush()
        row = Subscription(
            user_id=user_id, merchant_id=merchant.id, status=status,
            cadence=cadence, expected_amount=Decimal(amount),
            amount_tolerance=Decimal("0.10"), next_charge_at=next_charge,
            evidence={"occurrences": occurrences or []}, rule_version="test-v1",
        )
        db.add(row)
        db.commit()
        return row.id


def rule_body(*, month=None, leads=None, scope="ALL_VERIFIED", amount_gt=None):
    return {
        "scope": scope,
        "subscription_id": None,
        "amount_gt": amount_gt,
        "month": month,
        "lead_days": leads or [3],
    }


def test_forecast_month_end_leap_year_stale_and_unverified(bank):
    monthly = add_subscription(
        bank, next_charge=date(2026, 11, 30),
        occurrences=[{"occurred_on": "2026-10-31"}],
    )
    yearly = add_subscription(
        bank, name="Annual App", cadence="YEARLY", amount="120.00",
        next_charge=date(2028, 2, 29),
        occurrences=[{"occurred_on": "2024-02-29"}],
    )
    stale = add_subscription(bank, name="Old App", next_charge=date(2026, 10, 26))
    add_subscription(bank, name="Candidate", status="CANDIDATE", next_charge=date(2026, 12, 1))

    with bank["db"]() as db:
        user = db.get(__import__("models").User, bank["ids"][0])
        planning = SubscriptionPlanningService(db, bank["core"], bank["settings"])
        december = planning.forecast(user, month="2026-12", today=date(2026, 10, 27))
        february = planning.forecast(user, month="2029-02", today=date(2026, 10, 27))

    assert [(item["subscription_id"], item["charge_date"]) for item in december["items"]] == [
        (monthly, "2026-12-31")
    ]
    assert february["items"][0]["subscription_id"] == yearly
    assert february["items"][0]["charge_date"] == "2029-02-28"
    assert stale not in {item["subscription_id"] for item in december["items"]}
    assert any(item["id"] == stale and item["reason"] == "PREDICTION_EXPIRED"
               for item in december["needs_review"])
    assert december["complete"] is False


def test_forecast_api_validates_range_and_is_not_cacheable(bank):
    add_subscription(bank, next_charge=date(2026, 11, 15))
    headers = bank["headers"]["alice"]
    response = bank["http"].get("/api/subscriptions/forecast?month=2026-11", headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["items"]
    with bank["db"]() as db:
        assert db.scalar(select(Action).where(Action.kind == "subscription_query")) is None
    for query in (
        "month=2026-11&from_date=2026-11-01&to_date=2026-11-30",
        "from_date=2026-11-01",
        "from_date=2026-01-01&to_date=2027-01-02",
    ):
        assert bank["http"].get(f"/api/subscriptions/forecast?{query}", headers=headers).status_code == 422


def test_reminder_rule_idempotency_strict_days_and_user_isolation(bank):
    add_subscription(bank)
    url = "/api/subscriptions/reminder-rules"
    headers = {**bank["headers"]["alice"], "Idempotency-Key": "reminder-rule-key"}
    body = rule_body(month="2026-11", leads=[1, 3])
    first = bank["http"].post(url, headers=headers, json=body)
    second = bank["http"].post(url, headers=headers, json=body)
    assert first.status_code == 201, first.text
    assert second.status_code == 201 and second.json()["reused"] is True
    assert bank["http"].post(url, headers=headers,
        json={**body, "lead_days": [7]}).json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    strict = bank["http"].post(url,
        headers={**bank["headers"]["alice"], "Idempotency-Key": "strict-days"},
        json={**body, "lead_days": [True]})
    assert strict.status_code == 422
    assert bank["http"].get(url, headers=bank["headers"]["bob"]).json() == []
    detail = bank["http"].get(f"{url}/{first.json()['id']}", headers=bank["headers"]["alice"])
    assert detail.status_code == 200 and detail.headers["cache-control"] == "no-store"
    assert bank["http"].get(f"{url}/{first.json()['id']}", headers=bank["headers"]["bob"]).status_code == 404
    with bank["db"]() as db:
        assert len(db.scalars(select(SubscriptionReminderRule)).all()) == 1


def test_worker_waits_for_shanghai_nine_and_catches_missed_leads_once(bank):
    subscription_id = add_subscription(
        bank, next_charge=date(2026, 10, 30),
    )
    headers = {**bank["headers"]["alice"], "Idempotency-Key": "multi-lead"}
    created = bank["http"].post("/api/subscriptions/reminder-rules", headers=headers,
        json=rule_body(leads=[1, 3, 7]))
    assert created.status_code == 201, created.text

    with bank["db"]() as db:
        user = db.get(__import__("models").User, bank["ids"][0])
        planning = SubscriptionPlanningService(db, bank["core"], bank["settings"])
        before_nine = planning.tick_notifications(instant=datetime(2026, 10, 29, 8, 59, tzinfo=SHANGHAI))
        assert before_nine == {"reminders": 0, "budgets": 0}
        db.rollback()
    with bank["db"]() as db:
        planning = SubscriptionPlanningService(db, bank["core"], bank["settings"])
        after_nine = planning.tick_notifications(instant=datetime(2026, 10, 29, 9, 0, tzinfo=SHANGHAI))
        rows = db.scalars(select(SubscriptionNotification).where(
            SubscriptionNotification.subscription_id == subscription_id,
            SubscriptionNotification.kind == "REMINDER",
        )).all()
        assert after_nine["reminders"] == 2  # today's node plus one merged catch-up
        catch_up = next(row for row in rows if row.payload["catch_up"])
        assert catch_up.payload["lead_days"] == [3, 7]
        assert len(catch_up.payload["original_planned_times"]) == 2
        catch_up_id = catch_up.id
        db.commit()
    own_notices = bank["http"].get("/api/notifications", headers=bank["headers"]["alice"])
    assert own_notices.status_code == 200 and own_notices.headers["cache-control"] == "no-store"
    assert len(own_notices.json()) == 2
    assert bank["http"].get("/api/notifications", headers=bank["headers"]["bob"]).json() == []
    assert bank["http"].post(f"/api/notifications/{catch_up_id}/read", headers=bank["headers"]["bob"]).status_code == 404
    assert bank["http"].post(f"/api/notifications/{catch_up_id}/read", headers=bank["headers"]["alice"]).json()["read"] is True
    with bank["db"]() as db:
        repeated = SubscriptionPlanningService(db, bank["core"], bank["settings"]).tick_notifications(
            instant=datetime(2026, 10, 29, 9, 30, tzinfo=SHANGHAI))
        assert repeated["reminders"] == 0
        assert db.scalar(select(SubscriptionNotification.id).where(
            SubscriptionNotification.subscription_id == subscription_id,
            SubscriptionNotification.kind == "REMINDER").limit(2)) is not None


def test_budget_uses_actual_debit_plus_forecast_and_deduplicates_notification(bank):
    sub_id = add_subscription(bank, next_charge=date(2026, 10, 31))
    today = now().astimezone(SHANGHAI).date()
    bank["core"].tx[1] = [{
        "id": 501, "accountId": 1, "date": [today.year, today.month, 10],
        "amount": "80.00", "currency": {"code": "CNY"}, "entryType": "DEBIT",
        "transactionType": {"withdrawal": True, "code": "withdrawal"},
        "note": "[Merchant] Stream Box",
    }]
    month = today.strftime("%Y-%m")
    headers = {**bank["headers"]["alice"], "Idempotency-Key": "budget-month"}
    response = bank["http"].post("/api/subscriptions/budget-rules", headers=headers,
        json={"month": month, "amount": "50.00"})
    assert response.status_code == 201, response.text
    evaluation = response.json()["evaluation"]
    assert evaluation["actual_total"] == "80.00"
    assert evaluation["projected_remaining"] == "0.00"
    assert evaluation["known_total"] == "80.00"
    assert evaluation["over_budget"] is True
    with bank["db"]() as db:
        rows = db.scalars(select(SubscriptionNotification).where(
            SubscriptionNotification.user_id == bank["ids"][0],
            SubscriptionNotification.kind == "BUDGET")).all()
        assert len(rows) == 1 and rows[0].status == "ACTIVE"
        assert db.scalar(select(SubscriptionBudgetRule).where(
            SubscriptionBudgetRule.month == month)).status == "ACTIVE"
        budget_id = db.scalar(select(SubscriptionBudgetRule.id).where(
            SubscriptionBudgetRule.month == month))
    response2 = bank["http"].post("/api/subscriptions/budget-rules", headers=headers,
        json={"month": month, "amount": "50.00"})
    assert response2.status_code == 201 and response2.json()["reused"] is True
    detail = bank["http"].get(f"/api/subscriptions/budget-rules/{budget_id}", headers=headers)
    assert detail.status_code == 200 and detail.headers["cache-control"] == "no-store"
    assert bank["http"].get(f"/api/subscriptions/budget-rules/{budget_id}", headers=bank["headers"]["bob"]).status_code == 404
    edited = bank["http"].put(f"/api/subscriptions/budget-rules/{budget_id}",
        headers={**bank["headers"]["alice"], "Idempotency-Key": "budget-edit"},
        json={"month": month, "amount": "90.00"})
    assert edited.status_code == 200 and edited.json()["rule"]["amount"] == "90.00"
    with bank["db"]() as db:
        assert len(db.scalars(select(SubscriptionNotification).where(
            SubscriptionNotification.user_id == bank["ids"][0],
            SubscriptionNotification.kind == "BUDGET")).all()) == 1
    assert sub_id


class NoInvokeModel:
    def bind_tools(self, tools):
        self.tools = tools
        return self

    def invoke(self, messages):
        raise AssertionError("确定性订阅请求不应调用模型选择 Tool")


def install_deterministic_agent(bank, monkeypatch):
    monkeypatch.setattr(graph_module, "ChatOpenAI", lambda **kwargs: NoInvokeModel())
    bank["http"].app.dependency_overrides[get_agent_graph_factory] = lambda: graph_module.build_agent_graph


def test_tell_me_query_filters_amount_without_creating_reminder(bank, monkeypatch):
    today = now().astimezone(SHANGHAI).date()
    next_month = today.replace(day=1) + timedelta(days=32)
    charge = date(next_month.year, next_month.month, 15)
    for name, amount in (("Below", "14.53"), ("Equal", "15.00"), ("Above", "20.79")):
        add_subscription(bank, name=name, amount=amount, next_charge=charge)
    install_deterministic_agent(bank, monkeypatch)
    headers = bank["headers"]["alice"]
    response = bank["http"].post("/api/agent/messages", headers=headers,
        json={"message": "帮我看看下个月有哪些自动扣费，超过15元都告诉我"})
    assert response.status_code == 200, response.text
    events = response.json()["events"]
    assert [event["type"] for event in events] == ["SUBSCRIPTION_QUERY_REQUESTED"]
    request = events[0]["data"]
    assert request["query_type"] == "FORECAST" and request["risk_level"] == "YELLOW"
    assert request["conditions"] == [
        f"期间：{next_month.year:04d}-{next_month.month:02d}-01 至 {next_month.year:04d}-{next_month.month:02d}-{calendar.monthrange(next_month.year, next_month.month)[1]:02d}（上海时间）",
        "金额严格大于 15 元",
    ]
    with bank["db"]() as db:
        action = db.get(Action, request["action_id"])
        assert action.status == "WAITING_CONFIRMATION" and action.risk_level == "YELLOW"
        assert db.scalar(select(SubscriptionAgentResult)) is None
    result_action = bank["http"].post(
        f"/api/actions/{request['action_id']}/confirm", headers=headers,
        json={"request_hash": action.request_hash},
    )
    assert result_action.status_code == 200, result_action.text
    assert result_action.json()["status"] == "SUCCEEDED"
    assert result_action.json()["risk_level"] == "YELLOW"
    assert set(result_action.json()["result"]) == {"result_id", "result_kind"}
    audit_events = bank["http"].get(
        f"/api/actions/{request['action_id']}/audit", headers=headers
    ).json()
    assert {row["event"] for row in audit_events} >= {
        "ACTION_CREATED", "SUBSCRIPTION_QUERY_SUCCEEDED",
    }
    result = bank["http"].get(
        f"/api/agent/subscription-results/{result_action.json()['result']['result_id']}", headers=headers
    ).json()["data"]
    assert result["filters"]["amount_gt"] == "15"
    assert [(item["merchant"], item["amount"]) for item in result["items"]] == [("Above", "20.79")]
    assert result["projected_total"] == "20.79"
    repeated = bank["http"].post(
        f"/api/actions/{request['action_id']}/confirm", headers=headers,
        json={"request_hash": action.request_hash},
    )
    assert repeated.status_code == 200
    assert repeated.json()["result"] == result_action.json()["result"]
    with bank["db"]() as db:
        assert len(db.scalars(select(SubscriptionAgentResult)).all()) == 1
    with bank["db"]() as db:
        assert db.scalar(select(SubscriptionReminderRule)) is None


@pytest.mark.parametrize(("message", "query_type", "result_kind"), [
    ("查看我的订阅列表", "LIST", "subscriptions"),
    ("查看我的订阅提醒规则", "RULES", "rules"),
    ("查询 Stream Box 订阅详情", "DETAIL", "subscription_detail"),
])
def test_subscription_query_types_wait_for_yellow_confirmation(bank, monkeypatch, message, query_type, result_kind):
    add_subscription(bank)
    install_deterministic_agent(bank, monkeypatch)
    headers = bank["headers"]["alice"]
    response = bank["http"].post("/api/agent/messages", headers=headers, json={"message": message})
    assert response.status_code == 200, response.text
    event, = response.json()["events"]
    assert event["type"] == "SUBSCRIPTION_QUERY_REQUESTED"
    assert event["data"]["query_type"] == query_type
    with bank["db"]() as db:
        action = db.get(Action, event["data"]["action_id"])
        assert action.status == "WAITING_CONFIRMATION"
        assert action.risk_level == "YELLOW"
        assert action.expires_at - action.created_at <= timedelta(minutes=30, seconds=1)
        assert db.scalar(select(SubscriptionAgentResult)) is None

    confirmed = bank["http"].post(
        f"/api/actions/{action.id}/confirm", headers=headers,
        json={"request_hash": action.request_hash},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "SUCCEEDED"
    assert confirmed.json()["result"]["result_kind"] == result_kind
    result_id = confirmed.json()["result"]["result_id"]
    private = bank["http"].get(f"/api/agent/subscription-results/{result_id}", headers=headers)
    assert private.status_code == 200
    assert private.headers["cache-control"] == "no-store"
    assert private.json()["kind"] == result_kind
    assert bank["http"].get(
        f"/api/agent/subscription-results/{result_id}", headers=bank["headers"]["bob"]
    ).status_code == 404


def test_subscription_detail_reports_not_found_and_disambiguates_duplicates(bank, monkeypatch):
    add_subscription(bank, name="Stream Box")
    add_subscription(bank, name="Stream Box", cadence="YEARLY", amount="120.00")
    install_deterministic_agent(bank, monkeypatch)
    headers = bank["headers"]["alice"]
    response = bank["http"].post("/api/agent/messages", headers=headers,
        json={"message": "查询 Stream Box 订阅详情"})
    assert response.status_code == 200, response.text
    event = response.json()["events"][0]
    with bank["db"]() as db:
        action = db.get(Action, event["data"]["action_id"])
        assert db.scalar(select(SubscriptionAgentResult)) is None
        request_hash = action.request_hash
        action_id = action.id
    confirmed = bank["http"].post(f"/api/actions/{action_id}/confirm", headers=headers,
        json={"request_hash": request_hash})
    assert confirmed.status_code == 200, confirmed.text
    result = bank["http"].get(
        f"/api/agent/subscription-results/{confirmed.json()['result']['result_id']}", headers=headers
    ).json()
    assert result["data"]["status"] == "AMBIGUOUS"
    assert {item["cadence"] for item in result["data"]["items"]} == {"MONTHLY", "YEARLY"}

    missing = bank["http"].post("/api/agent/messages", headers=headers,
        json={"message": "查询 Missing App 订阅详情"})
    assert missing.status_code == 200, missing.text
    missing_event = missing.json()["events"][0]
    with bank["db"]() as db:
        missing_action = db.get(Action, missing_event["data"]["action_id"])
        missing_hash = missing_action.request_hash
    missing_confirmed = bank["http"].post(
        f"/api/actions/{missing_event['data']['action_id']}/confirm", headers=headers,
        json={"request_hash": missing_hash},
    )
    assert missing_confirmed.status_code == 200
    missing_result = bank["http"].get(
        f"/api/agent/subscription-results/{missing_confirmed.json()['result']['result_id']}", headers=headers
    ).json()
    assert missing_result["data"] == {"items": [], "status": "NOT_FOUND"}


@pytest.mark.parametrize("failure", ["cross_user", "modified_conditions", "expired", "cancelled"])
def test_subscription_query_rejects_unauthorized_or_expired_confirmation(bank, monkeypatch, failure):
    install_deterministic_agent(bank, monkeypatch)
    headers = bank["headers"]["alice"]
    response = bank["http"].post("/api/agent/messages", headers=headers,
        json={"message": "告诉我下个月预计订阅总额"})
    assert response.status_code == 200, response.text
    event = response.json()["events"][0]
    action_id = event["data"]["action_id"]
    with bank["db"]() as db:
        action = db.get(Action, action_id)
        request_hash = action.request_hash
        if failure == "modified_conditions":
            action.payload = {**action.payload, "to_date": "2099-01-01"}
        elif failure == "expired":
            action.expires_at = now() - timedelta(seconds=1)
        db.commit()

    if failure == "cancelled":
        cancelled = bank["http"].post(f"/api/actions/{action_id}/cancel", headers=headers)
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
        confirm_headers = headers
        expected = "ACTION_STATE"
    else:
        confirm_headers = bank["headers"]["bob"] if failure == "cross_user" else headers
        expected = {"cross_user": "NOT_FOUND", "modified_conditions": "CONFIRMATION_CHANGED", "expired": "ACTION_EXPIRED"}[failure]
    confirmed = bank["http"].post(f"/api/actions/{action_id}/confirm", headers=confirm_headers,
        json={"request_hash": request_hash})
    assert confirmed.status_code in {404, 409}
    assert confirmed.json()["error"]["code"] == expected
    with bank["db"]() as db:
        assert db.scalar(select(SubscriptionAgentResult)) is None


def test_subscription_query_failure_can_retry_without_saving_a_partial_result(bank, monkeypatch):
    from core.errors import DomainError
    from services.subscription_planning_service import SubscriptionPlanningService

    install_deterministic_agent(bank, monkeypatch)
    headers = bank["headers"]["alice"]
    response = bank["http"].post("/api/agent/messages", headers=headers,
        json={"message": "告诉我下个月预计订阅总额"})
    assert response.status_code == 200, response.text
    event = response.json()["events"][0]
    with bank["db"]() as db:
        action = db.get(Action, event["data"]["action_id"])
        request_hash = action.request_hash

    original = SubscriptionPlanningService.execute_agent_query
    monkeypatch.setattr(SubscriptionPlanningService, "execute_agent_query", lambda *args, **kwargs: (_ for _ in ()).throw(DomainError("READ_TEMPORARY", "读取失败", 503)))
    failed = bank["http"].post(
        f"/api/actions/{event['data']['action_id']}/confirm", headers=headers,
        json={"request_hash": request_hash},
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "AUTHORIZED"
    assert failed.json()["error_code"] == "READ_TEMPORARY"
    with bank["db"]() as db:
        assert db.scalar(select(SubscriptionAgentResult)) is None

    monkeypatch.setattr(SubscriptionPlanningService, "execute_agent_query", original)
    recovered = bank["http"].post(
        f"/api/actions/{event['data']['action_id']}/confirm", headers=headers,
        json={"request_hash": request_hash},
    )
    assert recovered.status_code == 200 and recovered.json()["status"] == "SUCCEEDED"
    with bank["db"]() as db:
        assert len(db.scalars(select(SubscriptionAgentResult)).all()) == 1


def test_expired_subscription_query_result_requires_a_new_request(bank, monkeypatch):
    install_deterministic_agent(bank, monkeypatch)
    headers = bank["headers"]["alice"]
    response = bank["http"].post("/api/agent/messages", headers=headers,
        json={"message": "告诉我下个月预计订阅总额"})
    event = response.json()["events"][0]
    with bank["db"]() as db:
        action = db.get(Action, event["data"]["action_id"])
        request_hash = action.request_hash
    confirmed = bank["http"].post(
        f"/api/actions/{event['data']['action_id']}/confirm", headers=headers,
        json={"request_hash": request_hash},
    )
    result_id = confirmed.json()["result"]["result_id"]
    with bank["db"]() as db:
        result = db.scalar(select(SubscriptionAgentResult).where(
            SubscriptionAgentResult.id == result_id,
        ))
        result.expires_at = now() - timedelta(seconds=1)
        db.commit()

    expired = bank["http"].get(
        f"/api/agent/subscription-results/{result_id}", headers=headers
    )
    assert expired.status_code == 410
    assert expired.json()["error"]["code"] == "SUBSCRIPTION_RESULT_EXPIRED"
    assert "重新查询" in expired.json()["error"]["message"]
    assert bank["http"].get(
        f"/api/actions/{event['data']['action_id']}", headers=headers
    ).json()["status"] == "SUCCEEDED"


def test_subscription_query_confirm_cancel_and_result_are_persisted_to_originating_chat(bank, monkeypatch):
    install_deterministic_agent(bank, monkeypatch)
    headers = bank["headers"]["alice"]
    conversation = bank["http"].post("/api/agent/conversations", headers=headers,
        json={"title": "订阅查询"})
    assert conversation.status_code == 201, conversation.text
    conversation_id = conversation.json()["id"]
    queued = bank["http"].post(
        f"/api/agent/conversations/{conversation_id}/messages",
        headers={**headers, "Idempotency-Key": "subscription-chat-query-1"},
        json={"message": "查看我的订阅列表"},
    )
    assert queued.status_code == 202, queued.text

    with bank["db"]() as db:
        service = AgentConversationService(db, bank["settings"])
        run_id = service.claim_one()
        run, user, body = service.execution_input(run_id)
        answer = execute_agent_message(
            body, user, db, lambda *args, **kwargs: ("subscriptions",),
            graph_module.build_agent_graph, trace_id=run.trace_id, run_id=run.id,
            conversation_id=run.conversation_id,
        )
        service.complete(run.id, answer)

    request = next(item for item in answer.events if item.type == "SUBSCRIPTION_QUERY_REQUESTED")
    with bank["db"]() as db:
        action = db.get(Action, request.data.action_id)
        request_hash = action.request_hash
    confirmed = bank["http"].post(
        f"/api/actions/{request.data.action_id}/confirm", headers=headers,
        json={"request_hash": request_hash},
    )
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "SUCCEEDED"

    detail = bank["http"].get(f"/api/agent/conversations/{conversation_id}", headers=headers)
    assert detail.status_code == 200
    stored_types = [event["type"] for event in detail.json()["events"]]
    assert "SUBSCRIPTION_QUERY_REQUESTED" in stored_types
    assert "SUBSCRIPTION_QUERY_COMPLETED" in stored_types
    assert detail.json()["events"][-1]["data"]["result_id"] == confirmed.json()["result"]["result_id"]


def test_concurrent_subscription_query_confirmation_creates_one_private_result(bank, monkeypatch):
    if bank["settings"].database_url.startswith("sqlite:"):
        pytest.skip("并发确认需要 PostgreSQL 行锁")
    install_deterministic_agent(bank, monkeypatch)
    headers = bank["headers"]["alice"]
    response = bank["http"].post("/api/agent/messages", headers=headers,
        json={"message": "告诉我下个月预计订阅总额"})
    assert response.status_code == 200, response.text
    event = response.json()["events"][0]
    with bank["db"]() as db:
        request_hash = db.get(Action, event["data"]["action_id"]).request_hash

    def confirm():
        with TestClient(bank["http"].app, raise_server_exceptions=False) as client:
            return client.post(
                f"/api/actions/{event['data']['action_id']}/confirm", headers=headers,
                json={"request_hash": request_hash},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = [future.result(timeout=20) for future in (
            pool.submit(confirm), pool.submit(confirm),
        )]
    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "SUCCEEDED"
    assert first.json()["result"] == second.json()["result"]
    with bank["db"]() as db:
        assert len(db.scalars(select(SubscriptionAgentResult)).all()) == 1


@pytest.mark.parametrize("message", ["下个月的订阅扣费提前3天告诉我", "下个月的扣费提前3天告诉我"])
def test_tell_me_ahead_creates_reminder(bank, monkeypatch, message):
    install_deterministic_agent(bank, monkeypatch)
    response = bank["http"].post("/api/agent/messages", headers=bank["headers"]["alice"],
                                 json={"message": message})
    assert response.status_code == 200, response.text
    event = next(e for e in response.json()["events"] if e["type"] == "SUBSCRIPTION_REMINDER_RULE_SAVED")
    assert event["data"]["lead_days"] == [3]
    assert event["data"]["scope"] == "ALL_VERIFIED"
    with bank["db"]() as db:
        rule = db.scalar(select(SubscriptionReminderRule))
        assert rule.month == event["data"]["month"] and rule.lead_days == [3]


def test_tell_me_negation_and_unsupported_lead_are_safe(bank, monkeypatch):
    today = now().astimezone(SHANGHAI).date()
    assert parse_subscription_intent("不要提前3天告诉我订阅扣费", today) is None
    install_deterministic_agent(bank, monkeypatch)
    response = bank["http"].post("/api/agent/messages", headers=bank["headers"]["alice"],
        json={"message": "下个月的扣费提前2天告诉我"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REMINDER_LEAD_DAYS"
    with bank["db"]() as db:
        assert db.scalar(select(SubscriptionReminderRule)) is None


@pytest.mark.parametrize("message", [
    "未来三天哪些订阅要续费？",
    "未来三天哪些订阅会续费？",
    "哪些订阅快续费了？",
])
def test_subscription_forecast_phrasing_is_recognized(message):
    today = now().astimezone(SHANGHAI).date()
    assert parse_subscription_intent(message, today) == {
        "kind": "FORECAST", "month": None, "amount_gt": None,
    }


def test_next_month_subscription_total_is_forecast():
    today = date(2026, 10, 31)
    assert parse_subscription_intent("告诉我下个月预计订阅总额。", today) == {
        "kind": "FORECAST", "month": "2026-11", "amount_gt": None,
    }


@pytest.mark.parametrize("amount", ["十", "15.999"])
def test_unrecognized_amount_filter_is_not_silently_dropped(bank, monkeypatch, amount):
    install_deterministic_agent(bank, monkeypatch)
    response = bank["http"].post("/api/agent/messages", headers=bank["headers"]["alice"],
        json={"message": f"下个月有哪些自动扣费，超过{amount}元都告诉我"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_AMOUNT_FILTER"
    with bank["db"]() as db:
        assert db.scalar(select(SubscriptionReminderRule)) is None


def test_model_cannot_execute_subscription_workflow_without_parsed_intent(bank, monkeypatch):
    class UntrustedModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            return AIMessage(content="", tool_calls=[{
                "name": "manage_subscription_request", "args": {}, "id": "untrusted"
            }])

    monkeypatch.setattr(graph_module, "ChatOpenAI", lambda **kwargs: UntrustedModel())
    app = bank["http"].app
    app.dependency_overrides[get_agent_router] = lambda: lambda *args, **kwargs: ("subscriptions",)
    app.dependency_overrides[get_agent_graph_factory] = lambda: graph_module.build_agent_graph
    response = bank["http"].post("/api/agent/messages", headers=bank["headers"]["alice"],
                                 json={"message": "不要提前3天告诉我订阅扣费"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SUBSCRIPTION_INTENT_UNSUPPORTED"
    with bank["db"]() as db:
        assert db.scalar(select(SubscriptionReminderRule)) is None


def test_agent_month_filter_asks_lead_then_saves_and_result_is_private(bank, monkeypatch):
    add_subscription(bank, next_charge=date(2026, 11, 30))
    install_deterministic_agent(bank, monkeypatch)
    headers = bank["headers"]["alice"]
    first = bank["http"].post("/api/agent/messages", headers=headers,
        json={"message": "帮我看看下个月有哪些自动扣费，超过50元的都提醒我"})
    assert first.status_code == 200, first.text
    body = first.json()
    types = {event["type"] for event in body["events"]}
    assert types == {"SUBSCRIPTION_FORECAST_READY", "SUBSCRIPTION_CLARIFICATION_REQUIRED"}
    forecast_event = next(event for event in body["events"] if event["type"] == "SUBSCRIPTION_FORECAST_READY")
    clarification = next(event for event in body["events"] if event["type"] == "SUBSCRIPTION_CLARIFICATION_REQUIRED")
    next_month = now().astimezone(SHANGHAI).date().replace(day=1) + timedelta(days=32)
    private = bank["http"].get(f"/api/agent/subscription-results/{forecast_event['data']['result_id']}", headers=headers)
    assert private.status_code == 200 and private.headers["cache-control"] == "no-store"
    assert private.json()["data"]["filters"]["amount_gt"] == "50"
    assert len(private.json()["data"]["items"]) == 1
    assert bank["http"].get(f"/api/agent/subscription-results/{forecast_event['data']['result_id']}", headers=bank["headers"]["bob"]).status_code == 404

    completed = bank["http"].post("/api/agent/messages", headers=headers,
        json={"message": "提前1、3、7天", "continuation_ref": clarification["data"]["clarification_id"]})
    assert completed.status_code == 200, completed.text
    saved = next(event for event in completed.json()["events"]
                 if event["type"] == "SUBSCRIPTION_REMINDER_RULE_SAVED")
    assert saved["data"]["month"] == f"{next_month.year:04d}-{next_month.month:02d}"
    assert saved["data"]["lead_days"] == [1, 3, 7]
    with bank["db"]() as db:
        rules = db.scalars(select(SubscriptionReminderRule)).all()
        pending = db.scalars(select(SubscriptionClarification).where(
            SubscriptionClarification.status == "PENDING")).all()
        assert len(rules) == 1 and rules[0].month == f"{next_month.year:04d}-{next_month.month:02d}"
        assert pending == []


def test_changed_conditions_do_not_consume_prior_clarification(bank, monkeypatch):
    install_deterministic_agent(bank, monkeypatch)
    headers = bank["headers"]["alice"]
    first = bank["http"].post("/api/agent/messages", headers=headers,
        json={"message": "帮我看看下个月有哪些自动扣费，超过50元的都提醒我"})
    assert first.status_code == 200, first.text
    clarification = next(event for event in first.json()["events"]
                         if event["type"] == "SUBSCRIPTION_CLARIFICATION_REQUIRED")
    response = bank["http"].post("/api/agent/messages", headers=headers, json={
        "message": "提前3天告诉我下个月的订阅扣费超过70元",
        "continuation_ref": clarification["data"]["clarification_id"],
    })
    assert response.status_code == 200, response.text
    saved = next(event for event in response.json()["events"]
                 if event["type"] == "SUBSCRIPTION_REMINDER_RULE_SAVED")
    assert saved["data"]["amount_gt"] == "70.00"
    with bank["db"]() as db:
        old = db.get(SubscriptionClarification, clarification["data"]["clarification_id"])
        assert old.status == "PENDING" and old.payload["amount_gt"] == "50"
        assert db.scalar(select(SubscriptionReminderRule)).amount_gt == Decimal("70.00")


def test_agent_monthly_budget_is_deterministic_and_returns_private_result(bank, monkeypatch):
    install_deterministic_agent(bank, monkeypatch)
    response = bank["http"].post("/api/agent/messages", headers=bank["headers"]["alice"],
        json={"message": "下个月订阅费用不要超过200元"})
    assert response.status_code == 200, response.text
    event = next(item for item in response.json()["events"] if item["type"] == "SUBSCRIPTION_BUDGET_READY")
    next_month = now().astimezone(SHANGHAI).date().replace(day=1) + timedelta(days=32)
    assert event["data"]["month"] == f"{next_month.year:04d}-{next_month.month:02d}"
    result = bank["http"].get(
        f"/api/agent/subscription-results/{event['data']['result_id']}",
        headers=bank["headers"]["alice"],
    )
    assert result.status_code == 200
    assert result.json()["data"]["budget"] == "200.00"
    assert result.json()["data"]["under_budget_confirmed"] is True
    assert bank["http"].get(
        f"/api/agent/subscription-results/{event['data']['result_id']}",
        headers=bank["headers"]["bob"],
    ).status_code == 404
