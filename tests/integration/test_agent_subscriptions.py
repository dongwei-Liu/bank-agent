from datetime import timedelta

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError
from sqlalchemy import select

import agent.graph as graph_module
from agent.tools.subscriptions import ScanSubscriptionsInput, scan_subscriptions
from api.agent import get_agent_graph_factory, get_agent_router
from clients.fineract import FineractUnavailableError
from core.security import SHANGHAI, now
from models import Audit, Subscription


class ScanModel:
    def __init__(self, requests=None):
        self.requests = [("scan_subscriptions", {})] if requests is None else requests
        self.inputs = []

    def bind_tools(self, tools):
        assert {tool.name for tool in tools} == {
            "scan_subscriptions", "request_subscription_cancel",
            "manage_subscription_request",
        }
        return self

    def invoke(self, messages):
        self.inputs.append(messages)
        assert len(self.inputs) == 1
        return AIMessage(
            content="未受信任的模型说明：会员已核实并取消",
            tool_calls=[{"name": name, "args": args, "id": f"scan-{index}"}
                        for index, (name, args) in enumerate(self.requests)],
        )


def install_scan_model(bank, monkeypatch, requests=None):
    model = ScanModel(requests)
    monkeypatch.setattr(graph_module, "ChatOpenAI", lambda **kwargs: model)
    app = bank["http"].app
    app.dependency_overrides[get_agent_router] = lambda: lambda *args, **kwargs: ("subscriptions",)
    app.dependency_overrides[get_agent_graph_factory] = lambda: graph_module.build_agent_graph
    return model


def seed_history(bank):
    today = now().astimezone(SHANGHAI).date()
    dates = [today - timedelta(days=days) for days in (89, 59, 29)]
    bank["core"].tx[1] = [
        {"id": index, "accountId": 1, "date": [day.year, day.month, day.day],
         "amount": "731.29", "currency": {"code": "CNY"}, "entryType": "DEBIT",
         "transactionType": {"withdrawal": True, "code": "withdrawal"},
         "note": "[Merchant] PRIVATE-SUBSCRIPTION"}
        for index, day in enumerate(dates, 1)
    ]


def assert_no_scan(bank):
    with bank["db"]() as db:
        assert db.scalar(select(Subscription)) is None
        assert db.scalar(select(Audit).where(Audit.event == "SUBSCRIPTIONS_SCANNED")) is None


def test_agent_subscription_schema_hides_identity_and_runtime():
    assert scan_subscriptions.tool_call_schema.model_json_schema()["properties"] == {}
    for field in ("user_id", "client_id", "account_id", "from_date"):
        with pytest.raises(ValidationError):
            ScanSubscriptionsInput.model_validate({field: "forged"})


@pytest.mark.parametrize("username,expected", [("alice", 1), ("bob", 0)])
def test_agent_subscription_scan_uses_current_user(bank, monkeypatch, username, expected):
    seed_history(bank)
    model = install_scan_model(bank, monkeypatch)
    response = bank["http"].post("/api/agent/messages", headers=bank["headers"][username],
                                 json={"message": "帮我识别订阅扣费"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["events"]) == 1
    event = body["events"][0]
    assert event["type"] == "SUBSCRIPTION_SCAN_COMPLETED"
    assert event["data"]["created"] == expected
    assert event["data"]["matched_candidates"] == expected
    assert event["data"]["timezone"] == "Asia/Shanghai"
    assert "items" not in event["data"]
    assert len(model.inputs) == 1
    assert "PRIVATE-SUBSCRIPTION" not in str(model.inputs)
    assert "731.29" not in str(model.inputs)
    assert "会员已核实并取消" not in body["message"]
    subscriptions = bank["http"].get("/api/subscriptions", headers=bank["headers"][username]).json()
    assert len(subscriptions) == expected
    if expected:
        assert subscriptions[0]["status"] == "CANDIDATE"
        assert subscriptions[0]["merchant"] == "PRIVATE-SUBSCRIPTION"
    with bank["db"]() as db:
        scanned = db.scalar(select(Audit).where(Audit.event == "SUBSCRIPTIONS_SCANNED",
                                                Audit.trace_id == body["trace_id"]))
        completed = db.scalar(select(Audit).where(Audit.event == "AGENT_MESSAGE_COMPLETED",
                                                  Audit.trace_id == body["trace_id"]))
        assert scanned is not None
        assert completed is not None
        assert completed.data["tools"] == ["scan_subscriptions"]


def test_agent_subscription_no_tool_cannot_claim_success(bank, monkeypatch):
    install_scan_model(bank, monkeypatch, requests=[])
    response = bank["http"].post("/api/agent/messages", headers=bank["headers"]["alice"],
                                 json={"message": "帮我识别订阅扣费"})
    assert response.status_code == 200
    assert response.json()["events"] == []
    assert "本次没有执行订阅操作" in response.json()["message"]
    assert "会员已核实并取消" not in response.json()["message"]
    assert_no_scan(bank)


@pytest.mark.parametrize("requests,code", [
    ([("scan_subscriptions", {}), ("scan_subscriptions", {})], "AGENT_SUBSCRIPTION_SEPARATE_REQUEST"),
    ([("scan_subscriptions", {}), ("request_transfer", {})], "AGENT_TOOL_NOT_ALLOWED"),
])
def test_agent_subscription_rejects_batch_before_execution(bank, monkeypatch, requests, code):
    seed_history(bank)
    install_scan_model(bank, monkeypatch, requests)
    response = bank["http"].post("/api/agent/messages", headers=bank["headers"]["alice"],
                                 json={"message": "帮我识别订阅扣费"})
    assert response.status_code in {422, 502}
    assert response.json()["error"]["code"] == code
    assert_no_scan(bank)


def test_agent_subscription_upstream_failure_has_no_success(bank, monkeypatch):
    install_scan_model(bank, monkeypatch)
    def unavailable(*args, **kwargs):
        raise FineractUnavailableError(503, "受控测试：核心银行暂时不可用")
    monkeypatch.setattr(bank["core"], "search_transactions", unavailable)
    response = bank["http"].post("/api/agent/messages", headers=bank["headers"]["alice"],
                                 json={"message": "帮我识别订阅扣费"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"
    assert_no_scan(bank)


def test_agent_subscription_forged_arguments_never_scan(bank, monkeypatch):
    install_scan_model(bank, monkeypatch, [("scan_subscriptions", {"user_id": "bob"})])
    response = bank["http"].post("/api/agent/messages", headers=bank["headers"]["alice"],
                                 json={"message": "帮我识别订阅扣费"})
    assert response.status_code >= 400
    assert_no_scan(bank)
