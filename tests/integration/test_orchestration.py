from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from core.security import SHANGHAI, now
from models import OrchestrationTask, TaskNode
from services.orchestration_service import OrchestrationService


def request(bank, method, path, *, user="alice", body=None, key=None, status=200):
    headers = dict(bank["headers"][user])
    if key:
        headers["Idempotency-Key"] = key
    response = bank["http"].request(method, path, headers=headers, json=body)
    assert response.status_code == status, response.text
    return response.json() if response.content else None


def birthday_body(**changes):
    body = {
        "label": "爱人生日",
        "event_date": (
            now().astimezone(SHANGHAI).date() + timedelta(days=30)
        ).isoformat(),
        "from_account_id": 1,
        "flower_amount": "100.00",
        "cake_amount": "200.00",
        "currency": "CNY",
    }
    body.update(changes)
    return body


def create_task(bank, key="birthday-1"):
    return request(
        bank,
        "POST",
        "/api/tasks/birthday",
        body=birthday_body(),
        key=key,
        status=201,
    )


def authorize_task(bank, task):
    action = task["authorization"]
    confirmed = request(
        bank,
        "POST",
        f"/api/actions/{action['action_id']}/confirm",
        body={"request_hash": action["request_hash"]},
    )
    assert confirmed["status"] == "WAITING_VERIFICATION"
    request(bank, "POST", f"/api/actions/{action['action_id']}/otp")
    code = request(bank, "GET", f"/api/dev/otp-inbox/{action['action_id']}")["code"]
    verified = request(
        bank,
        "POST",
        f"/api/actions/{action['action_id']}/verify",
        body={"code": code},
    )
    assert verified["status"] == "SUCCEEDED"
    result = request(bank, "GET", f"/api/tasks/{task['id']}")
    assert result["status"] == "ACTIVE"
    return result


def make_nodes_due(bank, task_id, *, kinds=None):
    with bank["db"]() as db:
        rows = db.scalars(select(TaskNode).where(TaskNode.task_id == task_id)).all()
        for row in rows:
            if row.status == "PENDING" and (kinds is None or row.kind in kinds):
                row.scheduled_at = now()
        db.commit()


def tick(bank, count=1):
    results = []
    for _ in range(count):
        with bank["db"]() as db:
            results.append(
                OrchestrationService(
                    db, bank["core"], bank["settings"]
                ).tick()
            )
    return results


def test_birthday_task_is_idempotent_private_and_requires_red_authorization(bank):
    task = create_task(bank)
    assert task["template"] == "BIRTHDAY_GIFTS_V1"
    assert task["status"] == "WAITING_AUTHORIZATION"
    assert task["authorization"]["risk_level"] == "RED"
    assert len(task["nodes"]) == 7
    assert {row["purpose"] for row in task["reservations"]} == {"FLOWER", "CAKE"}
    assert len(task["orders"]) == 2
    assert create_task(bank)["id"] == task["id"]
    request(bank, "GET", f"/api/tasks/{task['id']}", user="bob", status=404)
    request(
        bank,
        "POST",
        "/api/tasks/birthday",
        body=birthday_body(cake_amount="201.00"),
        key="birthday-1",
        status=409,
    )


def test_authorized_birthday_dag_holds_releases_and_pays_two_demo_merchants_once(bank):
    task = authorize_task(bank, create_task(bank, "birthday-complete"))
    make_nodes_due(bank, task["id"])
    results = tick(bank, 6)
    assert [result["node"] for result in results if result] == [
        "reserve_flower",
        "reserve_cake",
        "purchase_flower",
        "purchase_cake",
        "notify",
    ]
    complete = request(bank, "GET", f"/api/tasks/{task['id']}")
    assert complete["status"] == "SUCCEEDED"
    assert all(row["status"] == "CONSUMED" for row in complete["reservations"])
    assert all(row["status"] == "SUCCEEDED" for row in complete["orders"])
    assert bank["core"].balances[1] == Decimal("9700.00")
    assert bank["core"].balances[98] == Decimal("100.00")
    assert bank["core"].balances[97] == Decimal("200.00")
    before = list(bank["core"].command_calls)
    assert tick(bank)[0] is None
    assert bank["core"].command_calls == before


def test_cancel_releases_unspent_holds_without_paying_merchants(bank):
    task = authorize_task(bank, create_task(bank, "birthday-cancel"))
    make_nodes_due(bank, task["id"], kinds={"RESERVE_FUNDS"})
    tick(bank, 2)
    held = request(bank, "GET", f"/api/tasks/{task['id']}")
    assert all(row["status"] == "HELD" for row in held["reservations"])
    assert bank["core"].get_savings_account(1)["summary"]["availableBalance"] == Decimal("9700.00")
    request(
        bank,
        "POST",
        f"/api/tasks/{task['id']}/cancel",
        key="cancel-birthday",
    )
    tick(bank, 3)
    cancelled = request(bank, "GET", f"/api/tasks/{task['id']}")
    assert cancelled["status"] == "CANCELLED"
    assert all(row["status"] == "RELEASED" for row in cancelled["reservations"])
    assert bank["core"].get_savings_account(1)["summary"]["availableBalance"] == Decimal("10000")
    assert bank["core"].balances[97] == Decimal("0")
    assert bank["core"].balances[98] == Decimal("0")


def test_unknown_hold_is_not_replayed_and_can_be_reconciled_read_only(bank):
    task = authorize_task(bank, create_task(bank, "birthday-reconcile"))
    make_nodes_due(bank, task["id"], kinds={"RESERVE_FUNDS"})
    bank["core"].fail_hold_after_post = True
    result = tick(bank)[0]
    assert result["status"] == "RECONCILING"
    calls = [row for row in bank["core"].command_calls if row[0] == "hold"]
    current = request(bank, "GET", f"/api/tasks/{task['id']}")
    node = next(row for row in current["nodes"] if row["status"] == "RECONCILING")
    bank["core"].fail_hold_after_post = False
    reconciled = request(
        bank,
        "POST",
        f"/api/tasks/{task['id']}/nodes/{node['id']}/reconcile",
        key="reconcile-hold",
    )
    assert reconciled["status"] == "ACTIVE"
    assert next(row for row in reconciled["nodes"] if row["id"] == node["id"])["status"] == "SUCCEEDED"
    assert [row for row in bank["core"].command_calls if row[0] == "hold"] == calls


def test_pause_resume_takeover_and_node_retry_are_idempotent(bank):
    task = authorize_task(bank, create_task(bank, "birthday-commands"))
    paused = request(
        bank, "POST", f"/api/tasks/{task['id']}/pause", key="pause-1"
    )
    assert paused["status"] == "PAUSED"
    assert request(
        bank, "POST", f"/api/tasks/{task['id']}/pause", key="pause-1"
    )["status"] == "PAUSED"
    resumed = request(
        bank, "POST", f"/api/tasks/{task['id']}/resume", key="resume-1"
    )
    assert resumed["status"] == "ACTIVE"
    takeover = request(
        bank, "POST", f"/api/tasks/{task['id']}/takeover", key="takeover-1"
    )
    assert takeover["status"] == "WAITING_USER"
    with bank["db"]() as db:
        stored = db.get(OrchestrationTask, task["id"])
        assert stored.status == "WAITING_USER"
