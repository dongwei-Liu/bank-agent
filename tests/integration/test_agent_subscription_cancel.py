from datetime import timedelta

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError
from sqlalchemy import select

import agent.graph as graph_module
from agent.tools.subscriptions import RequestSubscriptionCancelInput, request_subscription_cancel
from api.agent import get_agent_graph_factory, get_agent_router
from core.security import SHANGHAI, now
from models import Action, Merchant, Subscription


class CancelModel:
    def __init__(self, calls=None):
        self.calls = calls if calls is not None else [("request_subscription_cancel", {"merchant": "Demo Video"})]
        self.invocations = 0

    def bind_tools(self, tools):
        assert {tool.name for tool in tools} == {
            "scan_subscriptions", "request_subscription_cancel",
            "manage_subscription_request",
        }
        return self

    def invoke(self, messages):
        self.invocations += 1
        return AIMessage(content="伪造取消成功", tool_calls=[
            {"name": name, "args": args, "id": f"call-{index}"}
            for index, (name, args) in enumerate(self.calls)
        ])


def install(bank, monkeypatch, calls=None):
    model = CancelModel(calls)
    monkeypatch.setattr(graph_module, "ChatOpenAI", lambda **kwargs: model)
    bank["http"].app.dependency_overrides[get_agent_router] = lambda: lambda *args, **kwargs: ("subscriptions",)
    bank["http"].app.dependency_overrides[get_agent_graph_factory] = lambda: graph_module.build_agent_graph
    return model


def seed(bank, verified=True):
    today = now().astimezone(SHANGHAI).date()
    bank["core"].tx[1] = [
        {"id": i, "accountId": 1, "date": [day.year, day.month, day.day],
         "amount": "100", "currency": {"code": "CNY"}, "entryType": "DEBIT",
         "transactionType": {"withdrawal": True, "code": "withdrawal"},
         "note": "[Merchant] Demo Video"}
        for i, day in enumerate((today-timedelta(days=89), today-timedelta(days=59), today-timedelta(days=29)), 1)
    ]
    response = bank["http"].post("/api/subscriptions/scan", headers=bank["headers"]["alice"])
    assert response.status_code == 200
    row = response.json()["items"][0]
    if verified:
        response = bank["http"].post(f"/api/subscriptions/{row['id']}/verify",
                                      headers={**bank["headers"]["alice"], "Idempotency-Key": "verify-test"})
        assert response.status_code == 200
    return row["id"]


def send(bank, message="帮我取消 Demo Video 订阅", user="alice"):
    return bank["http"].post("/api/agent/messages", headers=bank["headers"][user], json={"message": message})


def test_cancel_schema():
    schema = request_subscription_cancel.tool_call_schema.model_json_schema()
    assert set(schema["properties"]) == {"merchant"}
    with pytest.raises(ValidationError):
        RequestSubscriptionCancelInput.model_validate({"merchant": "Demo Video", "user_id": "forged"})


def test_cancel_agent_requires_confirmation_and_reuses_action(bank, monkeypatch):
    sid = seed(bank)
    model = install(bank, monkeypatch)
    response = send(bank)
    assert response.status_code == 200, response.text
    body = response.json()
    event = body["events"][0]
    assert event["type"] == "SUBSCRIPTION_CANCEL_REQUESTED"
    assert event["data"]["status"] == "WAITING_CONFIRMATION"
    assert "尚未执行取消" in body["message"]
    assert model.invocations == 1
    action_id = event["data"]["action_id"]
    row = bank["http"].get(f"/api/subscriptions/{sid}", headers=bank["headers"]["alice"]).json()
    assert row["status"] == "VERIFIED"
    assert send(bank).json()["events"][0]["data"]["action_id"] == action_id
    action = bank["http"].get(f"/api/actions/{action_id}", headers=bank["headers"]["alice"]).json()
    result = bank["http"].post(f"/api/actions/{action_id}/confirm", headers=bank["headers"]["alice"],
                               json={"request_hash": action["request_hash"]})
    assert result.status_code == 200 and result.json()["status"] == "SUCCEEDED"
    assert bank["http"].get(f"/api/subscriptions/{sid}", headers=bank["headers"]["alice"]).json()["status"] == "CANCELLED"
    assert send(bank).json()["events"][0]["data"]["status"] == "SUCCEEDED"


@pytest.mark.parametrize("message,user,verified,code", [
    ("帮我取消其他订阅", "alice", True, "SUBSCRIPTION_MERCHANT_NOT_IN_MESSAGE"),
    ("不要取消 Demo Video 订阅", "alice", True, "SUBSCRIPTION_CANCEL_INTENT_UNCLEAR"),
    ("帮我取消 Demo Video 订阅", "bob", True, "SUBSCRIPTION_NOT_FOUND"),
    ("帮我取消 Demo Video 订阅", "alice", False, "SUBSCRIPTION_NOT_VERIFIED"),
])
def test_cancel_agent_rejects_untrusted_target(bank, monkeypatch, message, user, verified, code):
    seed(bank, verified)
    install(bank, monkeypatch)
    response = send(bank, message, user)
    assert response.status_code in (404, 409, 422), response.text
    assert response.json()["error"]["code"] == code
    with bank["db"]() as db:
        assert db.scalar(select(Action).where(Action.kind == "subscription_cancel")) is None


def test_cancel_agent_rejects_ambiguous_merchant(bank, monkeypatch):
    sid = seed(bank)
    with bank["db"]() as db:
        original = db.get(Subscription, sid)
        db.add(Subscription(user_id=original.user_id, merchant_id=original.merchant_id,
                            status="VERIFIED", cadence="YEARLY", expected_amount=100,
                            evidence={}, rule_version="test"))
        db.commit()
    install(bank, monkeypatch)
    response = send(bank)
    assert response.json()["error"]["code"] == "SUBSCRIPTION_MERCHANT_AMBIGUOUS"
    with bank["db"]() as db:
        assert db.scalar(select(Action).where(Action.kind == "subscription_cancel")) is None


def test_cancel_agent_rejects_non_demo(bank, monkeypatch):
    sid = seed(bank)
    with bank["db"]() as db:
        db.get(Merchant, db.get(Subscription, sid).merchant_id).adapter_type = "external"
        db.commit()
    install(bank, monkeypatch)
    assert send(bank).json()["error"]["code"] == "DEMO_MERCHANT_REQUIRED"


def test_cancel_batch_is_rejected_before_any_write(bank, monkeypatch):
    seed(bank)
    install(bank, monkeypatch, [("request_subscription_cancel", {"merchant": "Demo Video"}),
                               ("scan_subscriptions", {})])
    response = send(bank)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AGENT_SUBSCRIPTION_SEPARATE_REQUEST"
    with bank["db"]() as db:
        assert db.scalar(select(Action).where(Action.kind == "subscription_cancel")) is None


def test_cancel_agent_reapplies_after_user_withdraws(bank, monkeypatch):
    seed(bank)
    install(bank, monkeypatch)
    first = send(bank).json()["events"][0]["data"]["action_id"]
    cancelled = bank["http"].post(f"/api/actions/{first}/cancel", headers=bank["headers"]["alice"])
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    second = send(bank)
    assert second.status_code == 200, second.text
    assert second.json()["events"][0]["data"]["action_id"] != first


def test_cancel_agent_confirmation_rechecks_snapshot(bank, monkeypatch):
    sid = seed(bank)
    install(bank, monkeypatch)
    action_id = send(bank).json()["events"][0]["data"]["action_id"]
    action = bank["http"].get(f"/api/actions/{action_id}", headers=bank["headers"]["alice"]).json()
    with bank["db"]() as db:
        db.get(Subscription, sid).expected_amount = 200
        db.commit()
    response = bank["http"].post(f"/api/actions/{action_id}/confirm", headers=bank["headers"]["alice"],
                                 json={"request_hash": action["request_hash"]})
    # The existing Action state machine persists a failed result or returns a domain error.
    if response.status_code == 200:
        assert response.json()["status"] == "FAILED"
        assert response.json()["error_code"] == "SUBSCRIPTION_CHANGED"
    else:
        assert response.json()["error"]["code"] == "SUBSCRIPTION_CHANGED"
    assert bank["http"].get(f"/api/subscriptions/{sid}", headers=bank["headers"]["alice"]).json()["status"] == "VERIFIED"


@pytest.mark.parametrize("calls", [
    [],
    [("request_subscription_cancel", {"merchant": "腾讯视频"})],
])
def test_exact_chinese_merchant_resolves_even_when_model_does_not(bank, monkeypatch, calls):
    sid = seed(bank)
    with bank["db"]() as db:
        sub = db.get(Subscription, sid)
        db.get(Merchant, sub.merchant_id).name = "腾讯视频会员"
        db.commit()
    install(bank, monkeypatch, calls)
    response = send(bank, "帮我取消腾讯视频会员订阅")
    assert response.status_code == 200, response.text
    assert response.json()["events"][0]["data"]["status"] == "WAITING_CONFIRMATION"
    assert bank["http"].get(f"/api/subscriptions/{sid}", headers=bank["headers"]["alice"]).json()["status"] == "VERIFIED"


@pytest.mark.parametrize("message", [
    "不要取消腾讯视频会员订阅",
    "帮我取消腾讯视频会员订阅并查余额",
    "取消腾讯视频会员订阅和其他订阅",
])
def test_exact_cancel_parser_does_not_accept_negation_or_mixed_requests(message):
    from agent.context import explicit_cancel_merchant
    class Service:
        def list(self, user):
            return [{"merchant": "腾讯视频会员", "demo_adapter": True}]
    assert explicit_cancel_merchant(message, Service(), object()) is None
