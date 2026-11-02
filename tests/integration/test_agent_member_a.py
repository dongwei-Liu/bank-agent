from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from api.agent import get_agent_graph_factory, get_agent_router
from agent.prompts.payments import PAYMENTS_PROMPT
from agent.registry import resolve_agent
from agent.tools.cards import (
    activate_my_card,
    change_card_channels,
    change_card_limits,
    get_my_card,
    list_my_cards,
    lock_my_card,
    replace_my_card,
    report_my_card_lost,
    request_card,
    request_card_number_view,
    unlock_my_card,
)
from agent.tools.payment_plans import (
    create_aa_collection,
    list_my_aa_requests,
    list_my_scheduled_transfers,
    manage_my_scheduled_transfer,
    process_my_aa_request,
    request_scheduled_transfer,
)
from agent.tools.payments import request_internal_transfer, request_transfer, search_my_recipients
from core.security import now
from models import AACollection, Action, BankCard, Recipient, Schedule, User
from schemas.agent import AgentMessageRequest
from services.aa_service import AAService
from services.account_service import AccountService
from services.action_service import ActionService
from services.card_service import CardService
from services.recipient_service import RecipientService
from services.schedule_service import ScheduleService
from services.transfer_service import TransferService


def _runtime(bank, db, user, trace="member-a"):
    core = bank["core"]
    return SimpleNamespace(context=SimpleNamespace(
        user=user,
        trace_id=trace,
        account_service=AccountService(core),
        recipient_service=RecipientService(db, core),
        transfer_service=TransferService(db, core),
        action_service=ActionService(db, core, bank["settings"]),
        card_service=CardService(db, core, bank["settings"]),
        schedule_service=ScheduleService(db, core, bank["settings"]),
        aa_service=AAService(db, core, bank["settings"]),
        events=[],
    ))


def _padded_accounts(core):
    original = core.get_savings_account

    def get(account_id):
        row = original(account_id)
        row["accountNo"] = str(account_id).zfill(9)
        row["clientName"] = {1: "Alice", 2: "Bob", 3: "Charlie"}.get(row["clientId"], "Alice")
        row["savingsProductName"] = "BANK_AGENT_SAVINGS"
        return row

    core.get_savings_account = get


def _contact(db, owner, name="Bob", alias="房租", account_id=2):
    row = Recipient(user_id=owner.id, name=name, alias=alias, phone="", account_id=account_id)
    db.add(row)
    db.commit()
    return row


def test_payments_prompt_requires_tool_for_complete_transfer_without_source_account():
    assert "给 Bob 转 200 元，备注午餐" in PAYMENTS_PROMPT
    assert "必须调用 request_transfer" in PAYMENTS_PROMPT
    assert "必须调用 request_internal_transfer" in PAYMENTS_PROMPT
    assert "必须先调用 list_my_recipients" in PAYMENTS_PROMPT


def _card(db, owner, *, alias, last4, status):
    action = Action(
        user_id=owner.id,
        kind="card_application",
        idempotency_key=f"fixture-card-{last4}",
        request_hash=last4.zfill(64),
        payload={},
        status="SUCCEEDED",
    )
    db.add(action)
    db.flush()
    card = BankCard(
        user_id=owner.id,
        fineract_account_id=1,
        product_name="BANK_AGENT_DEBIT",
        alias=alias,
        pan_ciphertext="test-ciphertext-never-decrypted",
        last4=last4,
        status=status,
        application_action_id=action.id,
    )
    db.add(card)
    db.commit()
    return card


def test_member_a_domains_register_expected_tools():
    assert {tool.name for tool in resolve_agent(("accounts",)).tools} == {"get_my_balance", "get_my_transactions"}
    assert {tool.name for tool in resolve_agent(("payments",)).tools} == {
        "list_my_recipients", "search_my_recipients", "request_transfer", "request_internal_transfer",
    }
    assert len(resolve_agent(("cards",)).tools) == 11
    assert len(resolve_agent(("payment_plans",)).tools) == 6


def test_history_is_bounded_and_user_only():
    body = AgentMessageRequest(message="继续", history=[f"消息{i}" for i in range(8)])
    assert len(body.history) == 8
    with pytest.raises(ValidationError):
        AgentMessageRequest(message="继续", history=["x"] * 9)
    with pytest.raises(ValidationError):
        AgentMessageRequest(message="继续", history=["x" * 2001])


def test_contact_search_and_transfer_create_action_without_moving_money(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        _contact(db, alice)
        runtime = _runtime(bank, db, alice)
        found = search_my_recipients.func(runtime, "房租")
        result = request_transfer.func(runtime, recipient="房租", amount="20.00")
        assert found["candidates"] == [{"name": "Bob", "alias": "房租"}]
        assert "account_id" not in repr(found)
        assert result["status"] == "created_waiting_confirmation"
        assert bank["core"].balances[1] == Decimal("10000")
        assert runtime.context.events[0].type == "TRANSFER_ACTION_CREATED"
        assert db.query(Action).one().kind == "transfer"


def test_internal_transfer_and_card_application_only_create_actions(bank):
    core = bank["core"]
    core.owners[4] = 1
    core.balances[4] = Decimal("500")
    core.tx[4] = []
    core.account_external_ids[4] = "ALICE-SECOND"
    _padded_accounts(core)
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        runtime = _runtime(bank, db, alice)
        transfer = request_internal_transfer.func(runtime, amount="25.00", from_account_suffix="0001", to_account_suffix="0004")
        card = request_card.func(runtime, alias="旅行")
        assert transfer["status"] == "created_waiting_confirmation"
        assert card["status"] == "action_created"
        assert core.balances[1] == Decimal("10000") and core.balances[4] == Decimal("500")
        assert {event.type for event in runtime.context.events} == {"INTERNAL_TRANSFER_ACTION_CREATED", "CARD_ACTION_CREATED"}
        assert {row.kind for row in db.query(Action).all()} == {"internal_transfer", "card_application"}


def test_card_agent_queries_safe_fields_and_all_operations_create_actions(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        pending = _card(db, alice, alias="待激活", last4="1001", status="PENDING_ACTIVATION")
        active = _card(db, alice, alias="日常", last4="1002", status="ACTIVE")
        active_channels = _card(db, alice, alias="旅行", last4="1003", status="ACTIVE")
        active_lost = _card(db, alice, alias="备用", last4="1004", status="ACTIVE")
        locked = _card(db, alice, alias="已锁", last4="1005", status="LOCKED")
        lost = _card(db, alice, alias="已挂失", last4="1006", status="LOST")
        runtime = _runtime(bank, db, alice, trace="card-operations")

        listed = list_my_cards.func(runtime)
        detail = get_my_card.func(runtime, card_ref="日常")
        assert listed["count"] == 6
        assert detail["card"]["last4"] == "1002"
        assert "card_id" not in repr(listed)
        assert "test-ciphertext" not in repr(listed)

        operations = [
            activate_my_card.func(runtime, card_ref=pending.last4),
            change_card_limits.func(runtime, card_ref=active.last4, single_limit="4000.00"),
            change_card_channels.func(runtime, card_ref=active_channels.last4, international_enabled=True),
            lock_my_card.func(runtime, card_ref=active.last4),
            unlock_my_card.func(runtime, card_ref=locked.last4),
            report_my_card_lost.func(runtime, card_ref=active_lost.last4),
            replace_my_card.func(runtime, card_ref=lost.last4),
            request_card_number_view.func(runtime, card_ref=active_channels.last4),
        ]
        assert all(item["status"] == "action_created" and item["executed"] is False for item in operations)
        created = db.query(Action).filter(Action.status == "WAITING_CONFIRMATION").all()
        assert {row.kind for row in created} == {
            "card_activate", "card_controls", "card_lock", "card_unlock",
            "card_report_lost", "card_replace", "card_reveal",
        }
        assert len(runtime.context.events) == 8


def test_schedule_and_aa_creation_are_idempotent_and_do_not_move_money(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        _contact(db, alice)
        runtime = _runtime(bank, db, alice, trace="plan-idempotency")
        execute = (now() + timedelta(days=2)).replace(second=0, microsecond=0)
        kwargs = dict(recipient="Bob", amount="10.00", execute_at=execute.isoformat(),
                      from_account_suffix="0001", recurrence="once")
        first = request_scheduled_transfer.func(runtime, **kwargs)
        second = request_scheduled_transfer.func(runtime, **kwargs)
        aa_first = create_aa_collection.func(runtime, title="晚餐", amount="12.00",
                                             collector_account_suffix="0001", participants=["Bob"])
        aa_second = create_aa_collection.func(runtime, title="晚餐", amount="12.00",
                                              collector_account_suffix="0001", participants=["Bob"])
        assert first["status"] == second["status"] == "authorization_pending"
        assert aa_first["collection"]["collection_ref"] == aa_second["collection"]["collection_ref"]
        assert db.query(Schedule).count() == 1
        assert db.query(AACollection).count() == 1
        assert bank["core"].balances[1] == Decimal("10000")


def test_schedule_and_aa_agent_management_stays_with_current_user(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        bob = db.get(User, bank["ids"][1])
        charlie = db.get(User, bank["ids"][2])
        _contact(db, alice, name="Bob", alias="同事", account_id=2)
        _contact(db, alice, name="Charlie", alias="室友", account_id=3)
        alice_runtime = _runtime(bank, db, alice, trace="agent-management")
        execute = (now() + timedelta(days=2)).replace(second=0, microsecond=0)
        plan = request_scheduled_transfer.func(
            alice_runtime,
            recipient="Bob",
            amount="10.00",
            execute_at=execute.isoformat(),
            from_account_suffix="0001",
            recurrence="once",
        )
        schedules = list_my_scheduled_transfers.func(alice_runtime)
        schedule_ref = schedules["schedules"][0]["schedule_ref"]
        paused = manage_my_scheduled_transfer.func(
            alice_runtime, schedule_ref=schedule_ref, operation="pause"
        )
        cancelled = manage_my_scheduled_transfer.func(
            alice_runtime, schedule_ref=schedule_ref, operation="cancel"
        )
        assert plan["status"] == "authorization_pending"
        assert paused["schedule"]["status"] == "PAUSED"
        assert cancelled["schedule"]["status"] == "CANCELLED"

        collection = create_aa_collection.func(
            alice_runtime,
            title="聚餐",
            amount="30.00",
            collector_account_suffix="0001",
            participants=["Bob", "Charlie"],
        )["collection"]
        bob_runtime = _runtime(bank, db, bob, trace="bob-aa")
        paid = process_my_aa_request.func(
            bob_runtime,
            collection_ref=collection["collection_ref"],
            operation="pay",
            from_account_suffix="0002",
        )
        charlie_runtime = _runtime(bank, db, charlie, trace="charlie-aa")
        cancelled_share = process_my_aa_request.func(
            charlie_runtime,
            collection_ref=collection["collection_ref"],
            operation="cancel_my_share",
        )
        visible = list_my_aa_requests.func(bob_runtime)
        assert paid["status"] == "payment_confirmation_pending"
        assert cancelled_share["status"] == "cancelled"
        assert visible["count"] == 1
        assert bob_runtime.context.events[0].type == "AA_PAYMENT_ACTION_CREATED"
        assert bank["core"].balances[2] == Decimal("5000")


def test_agent_http_injects_authenticated_services_history_and_action_event(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        _contact(db, alice)

    seen = {}

    class WriteGraph:
        def invoke(self, state, *, context, config):
            seen["messages"] = state["messages"]
            seen["username"] = context.user.username
            result = request_transfer.func(
                SimpleNamespace(context=context), recipient="房租", amount="20.00"
            )
            return {"messages": [
                HumanMessage(content="给房租转 20 元"),
                AIMessage(content="", tool_calls=[{"name": "request_transfer", "args": {}, "id": "write-1"}]),
                ToolMessage(content=str(result), tool_call_id="write-1"),
                AIMessage(content="请求已创建，尚未执行。"),
            ], "events": []}

    app = bank["http"].app
    app.dependency_overrides[get_agent_router] = lambda: (lambda *args, **kwargs: ("payments",))
    app.dependency_overrides[get_agent_graph_factory] = lambda: (lambda domains: WriteGraph())
    try:
        response = bank["http"].post(
            "/api/agent/messages",
            headers=bank["headers"]["alice"],
            json={"message": "给房租转 20 元", "history": ["先查一下联系人"]},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert seen["username"] == "alice"
        assert seen["messages"][0] == ("user", "先查一下联系人")
        assert body["message"] == "请求已创建，尚未执行。"
        assert body["events"][0]["type"] == "TRANSFER_ACTION_CREATED"
        assert body["events"][0]["data"]["recipient_name"] == "Bob"
        assert bank["core"].balances[1] == Decimal("10000")
    finally:
        app.dependency_overrides.pop(get_agent_router, None)
        app.dependency_overrides.pop(get_agent_graph_factory, None)


def test_agent_http_recovers_durable_action_when_final_model_call_fails(bank):
    _padded_accounts(bank["core"])
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        _contact(db, alice)

    class FailingAfterWriteGraph:
        def invoke(self, state, *, context, config):
            request_transfer.func(
                SimpleNamespace(context=context), recipient="房租", amount="20.00"
            )
            raise TimeoutError("model narration timeout")

    app = bank["http"].app
    app.dependency_overrides[get_agent_router] = lambda: (lambda *args, **kwargs: ("payments",))
    app.dependency_overrides[get_agent_graph_factory] = lambda: (lambda domains: FailingAfterWriteGraph())
    try:
        response = bank["http"].post(
            "/api/agent/messages",
            headers=bank["headers"]["alice"],
            json={"message": "给房租转 20 元"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["events"][0]["type"] == "TRANSFER_ACTION_CREATED"
        assert "尚未因此变更" in body["message"]
        assert bank["core"].balances[1] == Decimal("10000")
        with bank["db"]() as db:
            assert db.query(Action).count() == 1
    finally:
        app.dependency_overrides.pop(get_agent_router, None)
        app.dependency_overrides.pop(get_agent_graph_factory, None)
