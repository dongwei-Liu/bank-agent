import hashlib
import json
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.context import AgentContext, parse_birthday_orchestration_intent
from agent.graph import build_agent_graph
from agent.prompts.orchestration import ORCHESTRATION_PROMPT
from agent.registry import resolve_agent
from agent.router import DomainRoute, approve_domains
from agent.tools.orchestration import (
    list_my_birthday_tasks,
    request_birthday_orchestration,
)
from api.agent import get_agent_graph_factory, get_agent_router
from core.security import SHANGHAI, now
from models import Action, OrchestrationTask, User
from services.account_service import AccountService
from services.orchestration_service import OrchestrationService


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
            row["clientId"], "Demo"
        )
        return row

    core.get_savings_account = get


def _event_date():
    return now().astimezone(SHANGHAI).date() + timedelta(days=30)


def _message(day=None):
    day = day or _event_date()
    return (
        f"为爱人生日创建计划：{day.isoformat()}，从尾号0001账户，"
        "鲜花100元，蛋糕200元"
    )


def _runtime(bank, db, user, *, trace="birthday-agent", message=None):
    service = OrchestrationService(db, bank["core"], bank["settings"])
    return SimpleNamespace(
        context=AgentContext(
            user=user,
            account_service=AccountService(bank["core"]),
            orchestration_service=service,
            trace_id=trace,
            user_message=message or _message(),
            conversation_id="birthday-conversation",
            reference_service=_References(),
        )
    )


def test_orchestration_domain_registers_only_fixed_safe_tools():
    tools = resolve_agent(("orchestration",)).tools
    assert {item.name for item in tools} == {
        "list_my_birthday_tasks",
        "request_birthday_orchestration",
    }
    assert approve_domains(
        DomainRoute(domains=["orchestration"]), frozenset({"orchestration"})
    ) == ("orchestration",)
    schema = request_birthday_orchestration.tool_call_schema.model_json_schema()
    serialized = json.dumps(schema)
    assert "user_id" not in serialized
    assert "from_account_id" not in schema["properties"]
    assert set(schema["properties"]) == {
        "label",
        "event_date",
        "flower_amount",
        "cake_amount",
        "from_account_suffix",
        "from_account_ref",
    }


def test_birthday_prompt_marks_complete_natural_language_plan_as_executable():
    assert "已经完整提供全部必填信息" in ORCHESTRATION_PROMPT
    assert "必须调用 request_birthday_orchestration" in ORCHESTRATION_PROMPT
    assert "中文年月日属于完整日期" in ORCHESTRATION_PROMPT


def test_complete_birthday_prompt_has_deterministic_safe_intent():
    assert parse_birthday_orchestration_intent(
        "为爱人生日创建计划：2026年12月20日，从尾号0002账户买300元鲜花和200元蛋糕"
    ) == {
        "label": "爱人生日",
        "event_date": "2026-12-20",
        "flower_amount": "300",
        "cake_amount": "200",
        "from_account_suffix": "0002",
    }
    assert parse_birthday_orchestration_intent(
        "为爱人生日创建计划：2026年12月20日，从尾号0002账户安排500元礼物"
    ) is None


def test_complete_birthday_prompt_executes_without_model_tool_selection(bank, monkeypatch):
    class ModelMustNotRun:
        def __init__(self, **kwargs):
            pass

        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            raise AssertionError("完整固定生日计划不应依赖模型选择工具")

    monkeypatch.setattr("agent.graph.ChatOpenAI", ModelMustNotRun)
    _padded_accounts(bank["core"])
    message = _message()
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        runtime = _runtime(bank, db, alice, message=message)
        runtime.context = replace(
            runtime.context,
            orchestration_intent=parse_birthday_orchestration_intent(message),
        )
        result = build_agent_graph(("orchestration",)).invoke(
            {"messages": [("user", message)], "events": []},
            context=runtime.context,
            config={"recursion_limit": 8, "max_concurrency": 1},
        )
        assert any(
            getattr(item, "type", None) == "ORCHESTRATION_TASK_CREATED"
            for item in runtime.context.events
        )
        assert any(
            call["name"] == "request_birthday_orchestration"
            for item in result["messages"]
            if isinstance(item, AIMessage)
            for call in item.tool_calls
        )
        assert db.query(OrchestrationTask).count() == 1


def test_birthday_tool_requires_explicit_account_and_separate_amounts(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        no_account = _runtime(
            bank,
            db,
            alice,
            message=f"爱人生日 {_event_date().isoformat()}，鲜花100元，蛋糕200元",
        )
        issue = request_birthday_orchestration.func(
            no_account,
            label="爱人生日",
            event_date=_event_date(),
            flower_amount="100.00",
            cake_amount="200.00",
        )
        assert issue["status"] == "needs_clarification"
        assert no_account.context.events[-1].data.kind == "orchestration_account"

        total_only = _runtime(
            bank,
            db,
            alice,
            message=f"爱人生日 {_event_date().isoformat()}，从尾号0001账户留300元买花和蛋糕",
        )
        details = request_birthday_orchestration.func(
            total_only,
            label="爱人生日",
            event_date=_event_date(),
            flower_amount="100.00",
            cake_amount="200.00",
            from_account_suffix="0001",
        )
        assert details["status"] == "needs_clarification"
        assert details["code"] == "BIRTHDAY_DETAILS_REQUIRED"
        assert db.query(OrchestrationTask).count() == 0


def test_birthday_tool_creates_one_red_action_without_moving_money(bank):
    _padded_accounts(bank["core"])
    before = bank["core"].balances[1]
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        runtime = _runtime(bank, db, alice)
        first = request_birthday_orchestration.func(
            runtime,
            label="爱人生日",
            event_date=_event_date(),
            flower_amount="100.00",
            cake_amount="200.00",
            from_account_suffix="0001",
        )
        second = request_birthday_orchestration.func(
            runtime,
            label="爱人生日",
            event_date=_event_date(),
            flower_amount="100.00",
            cake_amount="200.00",
            from_account_suffix="0001",
        )
        assert first == second
        assert first == {
            "status": "authorization_required",
            "executed": False,
            "message": "生日任务已保存；请在任务页核对计划，并在操作页完成确认与 OTP。",
        }
        assert bank["core"].balances[1] == before
        assert db.query(OrchestrationTask).count() == 1
        action = db.query(Action).filter_by(kind="orchestration_authorization").one()
        assert action.risk_level == "RED"
        assert action.source == "AGENT"
        assert action.status == "WAITING_CONFIRMATION"
        assert len(runtime.context.events) == 1
        event = runtime.context.events[0]
        assert event.type == "ORCHESTRATION_TASK_CREATED"
        assert event.data.action_id == action.id


def test_birthday_task_list_is_owner_only_and_exact_data_stays_in_event(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        bob = db.get(User, bank["ids"][1])
        create_runtime = _runtime(bank, db, alice)
        request_birthday_orchestration.func(
            create_runtime,
            label="爱人生日",
            event_date=_event_date(),
            flower_amount="100.00",
            cake_amount="200.00",
            from_account_suffix="0001",
        )

        alice_runtime = _runtime(bank, db, alice, trace="alice-list")
        result = list_my_birthday_tasks.func(alice_runtime)
        assert result["task_count"] == 1
        assert "爱人生日" not in json.dumps(result, ensure_ascii=False)
        assert alice_runtime.context.events[-1].data.items[0].label == "爱人生日"

        bob_runtime = _runtime(bank, db, bob, trace="bob-list")
        other = list_my_birthday_tasks.func(bob_runtime)
        assert other["task_count"] == 0
        assert bob_runtime.context.events[-1].data.items == []


def test_agent_http_returns_deterministic_birthday_event(bank):
    _padded_accounts(bank["core"])

    class BirthdayGraph:
        def invoke(self, state, *, context, config):
            result = request_birthday_orchestration.func(
                SimpleNamespace(context=context),
                label="爱人生日",
                event_date=_event_date(),
                flower_amount="100.00",
                cake_amount="200.00",
                from_account_suffix="0001",
            )
            return {
                "messages": [
                    HumanMessage(content=context.user_message),
                    AIMessage(
                        content="",
                        tool_calls=[{
                            "name": "request_birthday_orchestration",
                            "args": {},
                            "id": "birthday-action",
                        }],
                    ),
                    ToolMessage(content=str(result), tool_call_id="birthday-action"),
                ],
                "events": [],
            }

    app = bank["http"].app
    app.dependency_overrides[get_agent_router] = lambda: (
        lambda *args, **kwargs: ("orchestration",)
    )
    app.dependency_overrides[get_agent_graph_factory] = lambda: (
        lambda domains: BirthdayGraph()
    )
    before = bank["core"].balances[1]
    try:
        response = bank["http"].post(
            "/api/agent/messages",
            headers=bank["headers"]["alice"],
            json={"message": _message()},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["events"][0]["type"] == "ORCHESTRATION_TASK_CREATED"
        assert body["events"][0]["data"]["route"].startswith("/tasks/")
        assert "资金尚未冻结或转出" in body["message"]
        assert bank["core"].balances[1] == before
    finally:
        app.dependency_overrides.pop(get_agent_router, None)
        app.dependency_overrides.pop(get_agent_graph_factory, None)
