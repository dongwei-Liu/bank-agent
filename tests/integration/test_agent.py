from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import select

from api.agent import get_agent_router, get_agent_graph_factory
from models import Audit


class FakeAgentGraph:
    def __init__(self):
        self.users: list[str] = []

    def invoke(self, state, *, context, config):
        self.users.append(context.user.username)
        assert state["events"] == []
        assert config == {"recursion_limit": 8, "max_concurrency": 1}
        prompt = state["messages"][0][1]
        return {
            "messages": [
                HumanMessage(content=prompt),
                AIMessage(content="", tool_calls=[{"name": "get_my_balance", "args": {}, "id": "balance-1"}]),
                ToolMessage(content="{}", tool_call_id="balance-1"),
                AIMessage(content=f"已按 {context.user.username} 的登录身份完成查询。"),
            ],
            "events": [],
        }


def test_agent_message_uses_authenticated_user_and_stable_contract(bank):
    graph = FakeAgentGraph()
    app = bank["http"].app
    app.dependency_overrides[get_agent_router] = lambda: (lambda *a, **k: ("accounts",))
    app.dependency_overrides[get_agent_graph_factory] = lambda: (lambda domains: graph)
    try:
        unauthenticated = bank["http"].post(
            "/api/agent/messages", json={"message": "我还有多少钱？"}
        )
        assert unauthenticated.status_code == 401

        response = bank["http"].post(
            "/api/agent/messages",
            json={"message": "  我还有多少钱？  "},
            headers=bank["headers"]["alice"],
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["message"] == "已按 alice 的登录身份完成查询。"
        assert payload["events"] == []
        assert payload["trace_id"]
        assert graph.users == ["alice"]

        forged_identity = bank["http"].post(
            "/api/agent/messages",
            json={"message": "查询余额", "user_id": bank["ids"][1]},
            headers=bank["headers"]["alice"],
        )
        assert forged_identity.status_code == 422

        with bank["db"]() as db:
            records = db.scalars(
                select(Audit).where(Audit.event == "AGENT_MESSAGE_COMPLETED")
            ).all()
            assert len(records) == 1
            assert records[0].user_id == bank["ids"][0]
            assert records[0].data["trace_id"] == payload["trace_id"]
    finally:
        app.dependency_overrides.pop(get_agent_router, None)
        app.dependency_overrides.pop(get_agent_graph_factory, None)


def test_agent_message_rejects_blank_input(bank):
    graph = FakeAgentGraph()
    app = bank["http"].app
    app.dependency_overrides[get_agent_router] = lambda: (lambda *a, **k: ("accounts",))
    app.dependency_overrides[get_agent_graph_factory] = lambda: (lambda domains: graph)
    try:
        response = bank["http"].post(
            "/api/agent/messages",
            json={"message": "   "},
            headers=bank["headers"]["alice"],
        )
        assert response.status_code == 422
        assert graph.users == []
    finally:
        app.dependency_overrides.pop(get_agent_router, None)
        app.dependency_overrides.pop(get_agent_graph_factory, None)
