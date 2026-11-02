from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select
from core.security import now, aware, fingerprint, SHANGHAI
from models import (
    Action,
    User,
    Schedule,
    ScheduleRun,
    ProductMetadata,
    RiskAssessment,
    DailyUsage,
    BankCard,
    CardAuthorization,
    Merchant,
    Subscription,
    SubscriptionOccurrence,
    Audit,
)
from core.card_crypto import decrypt_pan
from services.schedule_service import ScheduleService, next_occurrence
from services.aa_service import split_cents
from services.common import audit


def req(bank, method, path, body=None, user="alice", key=None, status=200):
    headers = {**bank["headers"][user], **({"Idempotency-Key": key} if key else {})}
    r = bank["http"].request(method, path, json=body, headers=headers)
    assert r.status_code == status, r.text
    return r.json()


def transfer(bank, amount="100", key="one", user="alice"):
    recipient = req(
        bank,
        "POST",
        "/api/recipients",
        {"name": "Bob", "account_id": 2},
        user,
        status=201,
    )
    return req(
        bank,
        "POST",
        "/api/transfers",
        {"from_account_id": 1, "recipient_id": recipient["id"], "amount": amount},
        user,
        key,
        status=201,
    )


def confirm(bank, a, user="alice"):
    return req(
        bank,
        "POST",
        f"/api/actions/{a['id']}/confirm",
        {"request_hash": a["request_hash"]},
        user,
    )


def verify(bank, a, user="alice"):
    req(bank, "POST", f"/api/actions/{a['id']}/otp", user=user)
    code = req(bank, "GET", f"/api/dev/otp-inbox/{a['id']}", user=user)["code"]
    return req(bank, "POST", f"/api/actions/{a['id']}/verify", {"code": code}, user)


def apply_card(bank, key="card-one", alias="日常消费"):
    return req(
        bank,
        "POST",
        "/api/cards",
        {"product_name": "智汇借记卡", "alias": alias},
        key=key,
        status=201,
    )


def active_card(bank, key="card-active"):
    application = apply_card(bank, key=key)
    assert confirm(bank, application)["status"] == "SUCCEEDED"
    card = req(bank, "GET", "/api/cards")[-1]
    activation = req(
        bank,
        "POST",
        f"/api/cards/{card['id']}/activate",
        key=f"{key}-activate",
        status=201,
    )
    assert verify(bank, confirm(bank, activation))["status"] == "SUCCEEDED"
    return req(bank, "GET", f"/api/cards/{card['id']}")


def test_card_application_creates_one_zero_balance_account_and_otp_activation(bank):
    action = apply_card(bank)
    assert action["kind"] == "card_application"
    assert action["status"] == "WAITING_CONFIRMATION"
    assert apply_card(bank)["id"] == action["id"]

    done = confirm(bank, action)
    assert done["status"] == "SUCCEEDED"
    cards = req(bank, "GET", "/api/cards")
    assert len(cards) == 1
    card = cards[0]
    assert card["status"] == "PENDING_ACTIVATION"
    assert card["alias"] == "日常消费"
    assert card["masked_number"].endswith(card["last4"])
    assert card["available_balance"] == "0"
    account_id = card["account_id"]
    assert bank["core"].owners[account_id] == 1
    assert bank["core"].account_statuses[account_id] == "active"
    assert len(
        [
            value
            for value in bank["core"].account_external_ids.values()
            if value == f"BANK-CARD-{action['id']}"
        ]
    ) == 1
    assert req(bank, "GET", "/api/cards", user="bob") == []
    req(bank, "GET", f"/api/cards/{card['id']}", user="bob", status=404)

    with bank["db"]() as db:
        stored = db.get(BankCard, card["id"])
        pan = decrypt_pan(bank["settings"].card_encryption_key, stored.id, stored.pan_ciphertext)
        assert len(pan) == 16 and pan.isdigit() and pan.endswith(stored.last4)
        assert pan not in stored.pan_ciphertext

    activation = req(
        bank,
        "POST",
        f"/api/cards/{card['id']}/activate",
        key="activate-card-one",
        status=201,
    )
    assert activation["kind"] == "card_activate"
    assert confirm(bank, activation)["status"] == "WAITING_VERIFICATION"
    assert verify(bank, activation)["status"] == "SUCCEEDED"
    assert req(bank, "GET", f"/api/cards/{card['id']}")["status"] == "ACTIVE"


def test_card_application_recovers_timeout_without_duplicate_account(bank):
    bank["core"].fail_savings_create_after_post = True
    action = apply_card(bank, key="card-timeout", alias="备用")
    uncertain = confirm(bank, action)
    assert uncertain["status"] == "RECONCILING"
    external_id = f"BANK-CARD-{action['id']}"
    assert list(bank["core"].account_external_ids.values()).count(external_id) == 1

    bank["core"].fail_savings_create_after_post = False
    resumed = req(bank, "POST", f"/api/actions/{action['id']}/resume")
    assert resumed["status"] == "WAITING_CONFIRMATION"
    done = confirm(bank, resumed)
    assert done["status"] == "SUCCEEDED"
    assert list(bank["core"].account_external_ids.values()).count(external_id) == 1
    assert len(req(bank, "GET", "/api/cards")) == 1


def test_card_number_reveal_requires_otp_expires_and_is_not_persisted(bank):
    import json

    card = active_card(bank, key="reveal-card")
    reveal = req(
        bank,
        "POST",
        f"/api/cards/{card['id']}/reveal",
        key="reveal-number",
        status=201,
    )
    assert reveal["kind"] == "card_reveal"
    assert confirm(bank, reveal)["status"] == "WAITING_VERIFICATION"
    done = verify(bank, reveal)
    assert done["status"] == "SUCCEEDED"
    assert "number" not in done["result"]
    assert (
        req(
            bank,
            "POST",
            f"/api/cards/{card['id']}/reveal",
            key="reveal-number",
            status=201,
        )["id"]
        == reveal["id"]
    )

    response = bank["http"].get(
        f"/api/cards/{card['id']}/reveal?action_id={reveal['id']}",
        headers=bank["headers"]["alice"],
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store, max-age=0"
    number = response.json()["number"]
    assert len(number) == 16 and number.isdigit() and number.endswith(card["last4"])
    req(
        bank,
        "GET",
        f"/api/cards/{card['id']}/reveal?action_id={reveal['id']}",
        user="bob",
        status=404,
    )
    with bank["db"]() as db:
        action = db.get(Action, reveal["id"])
        assert number not in json.dumps(action.result)
        assert number not in json.dumps(action.steps)
        assert all(number not in json.dumps(row.data) for row in db.scalars(select(Audit)))
        action.steps = {
            **action.steps,
            "reveal_expires_at": (now() - timedelta(seconds=1)).isoformat(),
        }
        db.commit()
    req(
        bank,
        "GET",
        f"/api/cards/{card['id']}/reveal?action_id={reveal['id']}",
        status=409,
    )


def test_card_application_rejects_missing_encryption_key_before_side_effect(bank):
    original = bank["settings"].card_encryption_key
    bank["settings"].card_encryption_key = ""
    before_accounts = set(bank["core"].owners)
    try:
        error = req(
            bank,
            "POST",
            "/api/cards",
            {"product_name": "智汇借记卡", "alias": "不可创建"},
            key="card-missing-key",
            status=503,
        )
    finally:
        bank["settings"].card_encryption_key = original
    assert error["error"]["code"] == "CARD_ENCRYPTION_UNCONFIGURED"
    assert set(bank["core"].owners) == before_accounts
    with bank["db"]() as db:
        assert db.scalar(
            select(Action).where(Action.idempotency_key == "card-missing-key")
        ) is None


def test_card_controls_state_changes_and_replacement_reuse_account(bank, monkeypatch):
    card = active_card(bank)
    card_id = card["id"]
    account_id = card["account_id"]
    account_count = len(bank["core"].owners)

    decrease = req(
        bank,
        "POST",
        f"/api/cards/{card_id}/limits",
        {
            "single_limit": "2000.00",
            "daily_limit": "3000.00",
            "online_enabled": False,
        },
        key="card-controls-decrease",
        status=201,
    )
    assert decrease["payload"]["risk"] == "YELLOW"
    assert confirm(bank, decrease)["status"] == "SUCCEEDED"
    assert (
        req(
            bank,
            "POST",
            f"/api/cards/{card_id}/limits",
            {
                "single_limit": "2000.00",
                "daily_limit": "3000.00",
                "online_enabled": False,
            },
            key="card-controls-decrease",
            status=201,
        )["id"]
        == decrease["id"]
    )
    changed = req(bank, "GET", f"/api/cards/{card_id}")
    assert changed["single_limit"] == "2000.00"
    assert changed["daily_limit"] == "3000.00"
    assert changed["online_enabled"] is False

    increase = req(
        bank,
        "POST",
        f"/api/cards/{card_id}/limits",
        {
            "single_limit": "5000.00",
            "daily_limit": "20000.00",
            "online_enabled": True,
        },
        key="card-controls-increase",
        status=201,
    )
    assert increase["payload"]["risk"] == "RED"
    assert confirm(bank, increase)["status"] == "WAITING_VERIFICATION"
    assert verify(bank, increase)["status"] == "SUCCEEDED"

    lock = req(
        bank,
        "POST",
        f"/api/cards/{card_id}/lock",
        key="card-lock",
        status=201,
    )
    assert confirm(bank, lock)["status"] == "SUCCEEDED"
    assert (
        req(
            bank,
            "POST",
            f"/api/cards/{card_id}/lock",
            key="card-lock",
            status=201,
        )["id"]
        == lock["id"]
    )
    assert req(bank, "GET", f"/api/cards/{card_id}")["status"] == "LOCKED"

    unlock = req(
        bank,
        "POST",
        f"/api/cards/{card_id}/unlock",
        key="card-unlock",
        status=201,
    )
    assert confirm(bank, unlock)["status"] == "WAITING_VERIFICATION"
    assert verify(bank, unlock)["status"] == "SUCCEEDED"

    lost = req(
        bank,
        "POST",
        f"/api/cards/{card_id}/report-lost",
        key="card-lost",
        status=201,
    )
    assert verify(bank, confirm(bank, lost))["status"] == "SUCCEEDED"
    req(
        bank,
        "POST",
        f"/api/cards/{card_id}/unlock",
        key="lost-cannot-unlock",
        status=409,
    )

    replacement_action = req(
        bank,
        "POST",
        f"/api/cards/{card_id}/replace",
        key="card-replace",
        status=201,
    )
    assert confirm(bank, replacement_action)["status"] == "WAITING_VERIFICATION"
    req(bank, "POST", f"/api/actions/{replacement_action['id']}/otp")
    code = req(
        bank, "GET", f"/api/dev/otp-inbox/{replacement_action['id']}"
    )["code"]
    original_get_account = bank["core"].get_savings_account

    from clients.fineract import FineractUnavailableError

    def response_lost_after_local_commit(account_id):
        raise FineractUnavailableError(503, "card response unavailable")

    monkeypatch.setattr(
        bank["core"], "get_savings_account", response_lost_after_local_commit
    )
    uncertain = req(
        bank,
        "POST",
        f"/api/actions/{replacement_action['id']}/verify",
        {"code": code},
    )
    assert uncertain["status"] == "RECONCILING"
    monkeypatch.setattr(bank["core"], "get_savings_account", original_get_account)
    assert (
        req(
            bank,
            "POST",
            f"/api/actions/{replacement_action['id']}/reconcile",
        )["status"]
        == "SUCCEEDED"
    )
    cards = req(bank, "GET", "/api/cards")
    old = next(item for item in cards if item["id"] == card_id)
    replacement = next(item for item in cards if item["replaces_card_id"] == card_id)
    assert old["status"] == "REPLACED"
    assert replacement["status"] == "PENDING_ACTIVATION"
    assert replacement["account_id"] == account_id
    assert replacement["last4"] != old["last4"]
    assert len(bank["core"].owners) == account_count


def test_concurrent_card_mutations_only_one_wins(bank):
    if bank["engine"].dialect.name != "postgresql":
        pytest.skip("requires PostgreSQL row locks")
    card = active_card(bank, key="concurrent-card")
    card_id = card["id"]
    with bank["db"]() as db:
        initial_version = db.get(BankCard, card_id).version

    limits = req(
        bank,
        "POST",
        f"/api/cards/{card_id}/limits",
        {"single_limit": "2000.00", "daily_limit": "3000.00"},
        key="concurrent-card-limits",
        status=201,
    )
    lock = req(
        bank,
        "POST",
        f"/api/cards/{card_id}/lock",
        key="concurrent-card-lock",
        status=201,
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda action: confirm(bank, action), [limits, lock]))

    assert sorted(result["status"] for result in results) == ["FAILED", "SUCCEEDED"]
    assert next(result for result in results if result["status"] == "FAILED")["error_code"] == "CARD_CHANGED"
    with bank["db"]() as db:
        stored = db.get(BankCard, card_id)
        assert stored.version == initial_version + 1
        assert (stored.status, stored.single_limit, stored.daily_limit) in {
            ("LOCKED", Decimal("5000.00"), Decimal("20000.00")),
            ("ACTIVE", Decimal("2000.00"), Decimal("3000.00")),
        }


def test_demo_card_transaction_settles_in_fineract_and_replays_once(bank):
    card = active_card(bank, key="purchase-card")
    bank["core"].balances[card["account_id"]] = Decimal("1000.00")
    merchant = req(bank, "GET", "/api/demo/merchants")[0]
    body = {
        "card_id": card["id"],
        "merchant_id": merchant["id"],
        "amount": "120.50",
        "channel": "ONLINE",
        "country_code": "CN",
    }
    action = req(
        bank,
        "POST",
        "/api/demo/card-transactions",
        body,
        key="purchase-one",
        status=201,
    )
    assert action["kind"] == "card_transaction"
    done = confirm(bank, action)
    assert done["status"] == "SUCCEEDED"
    assert done["result"]["status"] == "APPROVED"
    assert bank["core"].balances[card["account_id"]] == Decimal("879.50")
    assert bank["core"].balances[99] == Decimal("120.50")
    assert len(bank["core"].transfers) == 1

    replay = req(
        bank,
        "POST",
        "/api/demo/card-transactions",
        body,
        key="purchase-one",
        status=201,
    )
    assert replay["id"] == action["id"]
    assert confirm(bank, replay)["status"] == "SUCCEEDED"
    assert len(bank["core"].transfers) == 1
    conflict = {**body, "amount": "121.00"}
    assert (
        req(
            bank,
            "POST",
            "/api/demo/card-transactions",
            conflict,
            key="purchase-one",
            status=409,
        )["error"]["code"]
        == "IDEMPOTENCY_CONFLICT"
    )

    rows = req(bank, "GET", f"/api/cards/{card['id']}/transactions")
    assert len(rows) == 1
    assert rows[0]["status"] == "APPROVED"
    assert rows[0]["merchant_name"] == "智汇 Demo 商城"
    assert rows[0]["fineract_transfer_id"] == 1
    day = now().astimezone(SHANGHAI).date()
    transactions = req(
        bank,
        "GET",
        f"/api/accounts/{card['account_id']}/transactions?from_date={day}&to_date={day}",
    )
    purchase = next(
        row for row in transactions["items"] if row["transfer_reference"] == 1
    )
    assert purchase["kind"] == "expense"
    assert purchase["components"] == {"expense": "120.50"}
    assert purchase["merchant"] == "智汇 Demo 商城"
    assert purchase["category"] == "购物"
    statistics = req(
        bank,
        "GET",
        f"/api/billing/statistics?account_id={card['account_id']}&from_date={day}&to_date={day}",
    )
    assert Decimal(statistics["totals"]["expense"]) == Decimal("120.50")
    assert Decimal(statistics["categories"]["购物"]) == Decimal("120.50")
    req(
        bank,
        "POST",
        "/api/demo/card-transactions",
        body,
        user="bob",
        key="bob-foreign-card",
        status=404,
    )


@pytest.mark.parametrize(
    ("mutation", "amount", "country", "expected"),
    [
        ({"status": "LOCKED"}, "10.00", "CN", "CARD_LOCKED"),
        ({"online_enabled": False}, "10.00", "CN", "CARD_CHANNEL_BLOCKED"),
        ({"single_limit": Decimal("5.00")}, "10.00", "CN", "CARD_SINGLE_LIMIT_EXCEEDED"),
        ({"international_enabled": False}, "10.00", "US", "CARD_INTERNATIONAL_DISABLED"),
    ],
)
def test_demo_card_transaction_policy_declines_without_core_write(
    bank, mutation, amount, country, expected
):
    card = active_card(bank, key=f"decline-{expected.lower()}")
    bank["core"].balances[card["account_id"]] = Decimal("1000.00")
    with bank["db"]() as db:
        stored = db.get(BankCard, card["id"])
        for field, value in mutation.items():
            setattr(stored, field, value)
        stored.version += 1
        db.commit()
    merchant = req(bank, "GET", "/api/demo/merchants")[0]
    action = req(
        bank,
        "POST",
        "/api/demo/card-transactions",
        {
            "card_id": card["id"],
            "merchant_id": merchant["id"],
            "amount": amount,
            "channel": "ONLINE",
            "country_code": country,
        },
        key=f"decline-{expected}",
        status=201,
    )
    before = len(bank["core"].transfers)
    failed = confirm(bank, action)
    assert failed["status"] == "FAILED"
    assert failed["error_code"] == expected
    assert len(bank["core"].transfers) == before
    with bank["db"]() as db:
        authorization = db.scalar(
            select(CardAuthorization).where(CardAuthorization.action_id == action["id"])
        )
        assert authorization.status == "DECLINED"
        assert authorization.decline_code == expected


def test_demo_card_transaction_counts_uncertain_amount_and_recovers_lost_response(bank):
    card = active_card(bank, key="purchase-reconcile")
    bank["core"].balances[card["account_id"]] = Decimal("1000.00")
    with bank["db"]() as db:
        stored = db.get(BankCard, card["id"])
        stored.daily_limit = Decimal("100.00")
        stored.version += 1
        db.commit()
    merchant = req(bank, "GET", "/api/demo/merchants")[0]
    body = {
        "card_id": card["id"],
        "merchant_id": merchant["id"],
        "amount": "80.00",
        "channel": "POS",
        "country_code": "CN",
    }
    action = req(
        bank,
        "POST",
        "/api/demo/card-transactions",
        body,
        key="purchase-timeout",
        status=201,
    )
    bank["core"].fail_transfer = True
    uncertain = confirm(bank, action)
    assert uncertain["status"] == "RECONCILING"
    assert len(bank["core"].transfers) == 1
    with bank["db"]() as db:
        authorization = db.scalar(
            select(CardAuthorization).where(CardAuthorization.action_id == action["id"])
        )
        assert authorization.status == "EXECUTING"
        assert authorization.fineract_transfer_id is None

    second = req(
        bank,
        "POST",
        "/api/demo/card-transactions",
        {**body, "amount": "30.00"},
        key="purchase-over-daily-after-timeout",
        status=201,
    )
    daily_failed = confirm(bank, second)
    assert daily_failed["status"] == "FAILED"
    assert daily_failed["error_code"] == "CARD_DAILY_LIMIT_EXCEEDED"
    assert len(bank["core"].transfers) == 1

    bank["core"].fail_transfer = False
    done = req(bank, "POST", f"/api/actions/{action['id']}/reconcile")
    assert done["status"] == "SUCCEEDED"
    assert done["result"]["status"] == "APPROVED"
    assert len(bank["core"].transfers) == 1


def test_demo_card_routes_are_hidden_outside_development(bank):
    bank["settings"].environment = "production"
    try:
        req(bank, "GET", "/api/demo/merchants", status=404)
        req(
            bank,
            "GET",
            "/api/cards/not-a-card/transactions",
            status=404,
        )
    finally:
        bank["settings"].environment = "development"


def test_auth_ownership_rotation_and_logout(bank):
    h = bank["http"]
    assert h.get("/api/accounts").status_code == 401
    assert (
        h.post(
            "/api/auth/login", json={"username": "alice", "password": "wrong"}
        ).status_code
        == 401
    )
    req(bank, "GET", "/api/accounts/2/balance", status=404)
    tokens = h.post(
        "/api/auth/login", json={"username": "alice", "password": "test-password-123"}
    ).json()
    rotated = h.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert rotated.status_code == 200
    assert (
        h.post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        h.get(
            "/api/me", headers={"Authorization": "Bearer " + tokens["access_token"]}
        ).status_code
        == 401
    )
    headers = {"Authorization": "Bearer " + rotated.json()["access_token"]}
    assert h.post("/api/auth/logout", headers=headers).status_code == 200
    assert h.get("/api/me", headers=headers).status_code == 401


def test_audit_recursively_redacts_credentials_otp_and_full_card_number(bank):
    import json

    secrets = {
        "password": "plain-password",
        "access_token": "plain-access-token",
        "refresh_token": "plain-refresh-token",
        "otp_code": "654321",
        "card_number": "6222021234567890",
        "api_key": "plain-api-key",
    }
    with bank["db"]() as db:
        user = db.get(User, bank["ids"][0])
        audit(
            db,
            user,
            "SENSITIVE_DATA_TEST",
            trace_id="redaction-test",
            credentials={
                "password": secrets["password"],
                "tokens": [
                    {
                        "access-token": secrets["access_token"],
                        "refresh_token": secrets["refresh_token"],
                    }
                ],
            },
            verification={"otp_code": secrets["otp_code"], "attempts": 2},
            payment={"card_number": secrets["card_number"], "last4": "7890"},
            api_key=secrets["api_key"],
        )
        db.commit()
        row = db.scalar(select(Audit).where(Audit.trace_id == "redaction-test"))
        serialized = json.dumps(row.data)

    assert row.data["credentials"]["password"] == "[REDACTED]"
    assert row.data["credentials"]["tokens"][0]["access-token"] == "[REDACTED]"
    assert row.data["credentials"]["tokens"][0]["refresh_token"] == "[REDACTED]"
    assert row.data["verification"] == {"otp_code": "[REDACTED]", "attempts": 2}
    assert row.data["payment"] == {"card_number": "[REDACTED]", "last4": "7890"}
    assert row.data["api_key"] == "[REDACTED]"
    assert all(value not in serialized for value in secrets.values())


def test_transfer_boundary_replay_and_conflict(bank):
    a = transfer(bank, "1000")
    assert a["risk_level"] == "YELLOW"
    assert a["source"] == "API"
    assert a["expires_at"]
    assert a["version"] == 1
    for field in ("created_at", "updated_at", "expires_at"):
        assert datetime.fromisoformat(a[field]).utcoffset() is not None
    req(bank, "GET", f"/api/actions/{a['id']}", user="bob", status=404)
    req(
        bank,
        "POST",
        f"/api/actions/{a['id']}/confirm",
        {"request_hash": "0" * 64},
        status=409,
    )
    done = confirm(bank, a)
    assert done["status"] == "SUCCEEDED"
    assert done["version"] > a["version"]
    records = req(bank, "GET", f"/api/actions/{a['id']}/audit")
    assert records[0]["summary"] == "请求已创建"
    assert records[0]["trace_id"] == a["id"]
    assert records[0]["resource_type"] == "transfer"
    assert records[0]["resource_id"] == a["id"]
    assert records[0]["data"] == {}
    assert datetime.fromisoformat(records[0]["created_at"]).utcoffset() is not None
    assert bank["core"].balances[1] == 9000
    assert confirm(bank, a)["id"] == a["id"]
    assert len(bank["core"].transfers) == 1
    bank["core"].balances[1] = Decimal(0)
    body = {
        "from_account_id": 1,
        "recipient_id": a["payload"]["recipient_id"],
        "amount": "1000",
    }
    assert (
        req(bank, "POST", "/api/transfers", body, key="one", status=201)["id"]
        == a["id"]
    )
    req(
        bank, "POST", "/api/transfers", {**body, "amount": "999"}, key="one", status=409
    )
    assert (
        req(
            bank,
            "POST",
            "/api/transfers",
            {**body, "amount": "1000.00"},
            key="one",
            status=201,
        )["id"]
        == a["id"]
    )
    bank["core"].balances[1] = Decimal(9000)
    b = transfer(bank, ".01", "two")
    assert b["risk_level"] == "RED"
    assert confirm(bank, b)["status"] == "WAITING_VERIFICATION"
    assert verify(bank, b)["status"] == "SUCCEEDED"
    assert bank["core"].balances[1] == Decimal("8999.99")


def test_account_summary_and_internal_transfer_are_user_scoped(bank):
    bank["core"].balances[4] = Decimal("2500")
    bank["core"].owners[4] = 1
    bank["core"].tx[4] = []

    summary = req(bank, "GET", "/api/accounts/summary")
    assert summary == {
        "currency": "CNY",
        "total": "12500",
        "account_count": 2,
        "complete": True,
    }
    body = {
        "from_account_id": 1,
        "to_account_id": 4,
        "amount": "125.50",
        "remark": "本人账户调拨",
    }
    action = req(
        bank,
        "POST",
        "/api/internal-transfers",
        body,
        key="internal-one",
        status=201,
    )
    assert action["kind"] == "internal_transfer"
    assert confirm(bank, action)["status"] == "SUCCEEDED"
    assert bank["core"].balances[1] == Decimal("9874.50")
    assert bank["core"].balances[4] == Decimal("2625.50")
    assert Decimal(req(bank, "GET", "/api/accounts/summary")["total"]) == 12500
    assert req(bank, "GET", "/api/transfers")[0]["kind"] == "internal_transfer"

    day = now().astimezone(SHANGHAI).date()
    transactions = req(bank, "GET", "/api/accounts/1/transactions")
    assert transactions["items"][0]["kind"] == "internal_transfer"
    statistics = req(
        bank,
        "GET",
        f"/api/billing/statistics?account_id=1&from_date={day}&to_date={day}",
    )
    assert Decimal(statistics["totals"]["internal_transfer"]) == Decimal("125.50")
    assert "expense" not in statistics["totals"]
    aggregate = req(
        bank,
        "GET",
        f"/api/billing/statistics?from_date={day}&to_date={day}",
    )
    assert aggregate["account_id"] is None
    assert aggregate["account_ids"] == [1, 4]
    assert aggregate["complete"] is True
    assert "expense" not in aggregate["totals"]
    assert "income" not in aggregate["totals"]

    req(
        bank,
        "POST",
        "/api/internal-transfers",
        {**body, "to_account_id": 2},
        key="not-owned",
        status=404,
    )


def test_otp_expiry_lock_replay_and_inbox_ownership(bank):
    a = confirm(bank, transfer(bank, "1001"))
    req(bank, "POST", f"/api/actions/{a['id']}/otp")
    req(bank, "GET", f"/api/dev/otp-inbox/{a['id']}", user="bob", status=404)
    code = req(bank, "GET", f"/api/dev/otp-inbox/{a['id']}")["code"]
    wrong = "000000" if code != "000000" else "111111"
    for i in range(5):
        req(bank, "POST", f"/api/actions/{a['id']}/verify", {"code": wrong}, status=400)
    req(bank, "POST", f"/api/actions/{a['id']}/otp", status=429)
    with bank["db"]() as db:
        u = db.get(User, bank["ids"][0])
        u.otp_locked_until = now() - timedelta(seconds=1)
        row = db.get(Action, a["id"])
        row.otp_expires = now() - timedelta(seconds=1)
        db.commit()
    req(bank, "POST", f"/api/actions/{a['id']}/verify", {"code": code}, status=400)
    assert verify(bank, a)["status"] == "SUCCEEDED"
    req(bank, "POST", f"/api/actions/{a['id']}/verify", {"code": code}, status=409)


def test_timeout_keeps_quota_and_never_reposts(bank):
    bank["core"].fail_transfer = True
    a = confirm(bank, transfer(bank, "100"))
    assert a["status"] == "RECONCILING"
    assert bank["core"].balances[1] == 9900
    assert confirm(bank, a)["status"] == "RECONCILING"
    assert len(bank["core"].transfers) == 1
    assert (
        req(bank, "POST", f"/api/actions/{a['id']}/reconcile")["status"] == "SUCCEEDED"
    )
    with bank["db"]() as db:
        assert db.scalar(select(DailyUsage)).amount == 100


def test_aa_precision_freeze_participant_payment_and_cancel(bank):
    assert split_cents("10", 3) == [Decimal("3.34"), Decimal("3.33"), Decimal("3.33")]
    c = req(
        bank,
        "POST",
        "/api/aa-collections",
        {
            "account_id": 1,
            "title": "Dinner",
            "amount": "10",
            "participants": [{"user_id": id} for id in bank["ids"]],
        },
        status=201,
    )
    shares = c["shares"]
    bob = next(s for s in shares if s["user_id"] == bank["ids"][1])
    path = f"/api/aa-collections/{c['id']}/shares/{bob['id']}/pay"
    req(
        bank,
        "POST",
        path,
        {"from_account_id": 3},
        user="charlie",
        key="pay",
        status=404,
    )
    a = req(bank, "POST", path, {"from_account_id": 2}, user="bob", key="pay")
    assert confirm(bank, a, "bob")["status"] == "SUCCEEDED"
    assert (
        req(bank, "POST", path, {"from_account_id": 2}, user="bob", key="pay")["id"]
        == a["id"]
    )
    req(
        bank,
        "PUT",
        f"/api/aa-collections/{c['id']}",
        {
            "account_id": 1,
            "title": "Changed",
            "amount": "10",
            "participants": [{"user_id": id} for id in bank["ids"]],
        },
        status=409,
    )
    closed = req(bank, "DELETE", f"/api/aa-collections/{c['id']}")
    assert sorted(s["status"] for s in closed["shares"]) == [
        "CANCELLED",
        "PAID",
        "SELF_PAID",
    ]


def schedule(bank, recurrence="once"):
    recipient = req(
        bank, "POST", "/api/recipients", {"name": "Bob", "account_id": 2}, status=201
    )
    start = (now() + timedelta(minutes=2)).replace(second=0, microsecond=0)
    p = {
        "from_account_id": 1,
        "recipient_id": recipient["id"],
        "amount": "10",
        "execute_at": start.isoformat(),
        "recurrence": recurrence,
        "daily_limit": "10",
        "valid_until": (start + timedelta(days=10)).isoformat(),
    }
    s = req(bank, "POST", "/api/transfer-schedules", p, status=201)
    a = req(bank, "POST", f"/api/transfer-schedules/{s['id']}/authorize", key="auth")
    assert verify(bank, confirm(bank, a))["status"] == "SUCCEEDED"
    return s, p


def test_schedule_pause_restart_and_unique_worker(bank):
    s, p = schedule(bank)
    req(bank, "POST", f"/api/transfer-schedules/{s['id']}/pause")
    with bank["db"]() as db:
        assert (
            ScheduleService(db, bank["core"], bank["settings"]).tick(
                now() + timedelta(minutes=5)
            )
            == []
        )
    req(bank, "POST", f"/api/transfer-schedules/{s['id']}/resume")
    for i in range(2):
        with bank["db"]() as db:
            ScheduleService(db, bank["core"], bank["settings"]).tick(
                now() + timedelta(minutes=5)
            )
    assert len(bank["core"].transfers) == 1
    runs = req(bank, "GET", f"/api/transfer-schedules/{s['id']}/runs")
    assert len(runs) == 1 and runs[0]["status"] == "SUCCEEDED"


def test_schedule_month_end_and_expiry(bank):
    jan = datetime(2026, 1, 31, 12, tzinfo=SHANGHAI)
    feb = next_occurrence(jan, "monthly", 31)
    march = next_occurrence(feb, "monthly", 31)
    assert feb.astimezone(SHANGHAI).day == 28 and march.astimezone(SHANGHAI).day == 31
    s, p = schedule(bank)
    with bank["db"]() as db:
        row = db.get(Schedule, s["id"])
        row.payload = {
            **row.payload,
            "valid_until": (now() - timedelta(seconds=1)).isoformat(),
        }
        row.authorization_hash = fingerprint(row.payload)
        db.commit()
        ScheduleService(db, bank["core"], bank["settings"]).tick(
            now() + timedelta(minutes=5)
        )
    assert not bank["core"].transfers


def raw_tx(id, day, amount="10", **extra):
    return {
        "id": id,
        "accountId": 1,
        "date": [day.year, day.month, day.day],
        "amount": amount,
        "currency": {"code": "CNY"},
        "entryType": "DEBIT",
        "transactionType": {"withdrawal": True, "code": "withdrawal"},
        **extra,
    }


def test_billing_pages_annotations_rules_and_report_totals(bank):
    day = now().astimezone(SHANGHAI).date()
    bank["core"].tx[1] = [raw_tx(i, day) for i in range(1, 206)]
    bank["core"].tx[1] += [
        raw_tx(206, day, "999", reversed=True),
        raw_tx(207, day, "500", transfer={"id": 1}),
    ]
    bank["core"].transfers[1] = {
        "fromAccount": {"id": 1},
        "toAccount": {"id": 2},
    }
    category = req(bank, "POST", "/api/categories", {"name": "餐饮"}, status=201)
    req(
        bank,
        "POST",
        "/api/classification-rules",
        {"category_id": category["id"], "field": "merchant", "contains": "Cafe"},
        status=201,
    )
    req(
        bank,
        "POST",
        "/api/transaction-annotations",
        {"account_id": 1, "transaction_id": 1, "merchant": "Cafe"},
        status=201,
    )
    req(
        bank,
        "POST",
        "/api/transaction-annotations",
        {"account_id": 1, "transaction_id": 2, "merchant": "Cafe"},
        status=201,
    )
    stats = req(
        bank,
        "GET",
        f"/api/billing/statistics?account_id=1&from_date={day}&to_date={day}",
    )
    assert (
        Decimal(stats["totals"]["expense"]) == 2050
        and Decimal(stats["totals"]["transfer"]) == 500
    )
    assert (
        Decimal(stats["categories"]["餐饮"]) == 20
        and Decimal(stats["categories"]["未分类"]) == 2030
    )
    anomalies = req(
        bank,
        "GET",
        f"/api/billing/anomalies?account_id=1&from_date={day}&to_date={day}",
    )
    assert len(anomalies) == 1 and anomalies[0]["rule"] == "DUPLICATE_V1"
    report = req(
        bank,
        "POST",
        "/api/bill-reports",
        {"account_id": 1, "period": day.strftime("%Y-%m")},
        status=201,
    )
    assert report["payload"]["totals"] == stats["totals"]
    req(bank, "GET", f"/api/bill-reports/{report['id']}", user="bob", status=404)
    req(bank, "DELETE", f"/api/bill-reports/{report['id']}")


def test_billing_aggregate_spans_owned_accounts_and_preserves_single_shape(bank):
    day = now().astimezone(SHANGHAI).date()
    bank["core"].balances[4] = Decimal("2500")
    bank["core"].owners[4] = 1
    bank["core"].tx[4] = [raw_tx(1, day, "10", accountId=4)]
    bank["core"].tx[1] = [raw_tx(1, day, "10")]
    category = req(bank, "POST", "/api/categories", {"name": "餐饮"}, status=201)
    req(
        bank,
        "POST",
        "/api/classification-rules",
        {"category_id": category["id"], "field": "merchant", "contains": "Cafe"},
        status=201,
    )
    for current_account_id in (1, 4):
        req(
            bank,
            "POST",
            "/api/transaction-annotations",
            {
                "account_id": current_account_id,
                "transaction_id": 1,
                "merchant": "Cafe",
            },
            status=201,
        )

    stats = req(
        bank,
        "GET",
        f"/api/billing/statistics?from_date={day}&to_date={day}",
    )
    assert stats["account_ids"] == [1, 4]
    assert Decimal(stats["totals"]["expense"]) == 20
    assert Decimal(stats["categories"]["餐饮"]) == 20

    aggregate = req(
        bank,
        "GET",
        f"/api/billing/anomalies?from_date={day}&to_date={day}",
    )
    assert aggregate["account_ids"] == [1, 4]
    assert aggregate["complete"] is True
    assert aggregate["items"][0]["rule"] == "DUPLICATE_V1"
    assert aggregate["items"][0]["transactions"] == [
        {"account_id": 1, "transaction_id": 1},
        {"account_id": 4, "transaction_id": 1},
    ]

    single = req(
        bank,
        "GET",
        f"/api/billing/anomalies?account_id=1&from_date={day}&to_date={day}",
    )
    assert isinstance(single, list)
    assert single == []
    bob_stats = req(
        bank,
        "GET",
        f"/api/billing/statistics?from_date={day}&to_date={day}",
        user="bob",
    )
    assert bob_stats["account_ids"] == [2]
    assert "expense" not in bob_stats["totals"]


def test_subscription_scan_review_cancel_and_blocked_demo_charge(bank):
    day = now().astimezone(SHANGHAI).date()
    dates = [day - timedelta(days=89), day - timedelta(days=59), day - timedelta(days=29)]
    bank["core"].tx[1] = [
        {
            **raw_tx(index, occurred, "100"),
            "note": "[Merchant] Demo Video",
        }
        for index, occurred in enumerate(dates, 1)
    ]

    scan = req(bank, "POST", "/api/subscriptions/scan")
    assert scan["created"] == 1 and scan["found"] == 1
    subscription = scan["items"][0]
    assert subscription["status"] == "CANDIDATE"
    assert subscription["cadence"] == "MONTHLY"
    assert Decimal(subscription["expected_amount"]) == 100
    assert subscription["next_charge_at"] == (day + timedelta(days=1)).isoformat()
    assert subscription["occurrence_count"] == 3

    subscription_id = subscription["id"]
    detail = req(bank, "GET", f"/api/subscriptions/{subscription_id}")
    assert len(detail["occurrences"]) == 3
    req(bank, "GET", f"/api/subscriptions/{subscription_id}", user="bob", status=404)
    verified = req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/verify",
        key="verify-subscription",
    )
    assert verified["status"] == "VERIFIED"
    assert (
        req(
            bank,
            "POST",
            f"/api/subscriptions/{subscription_id}/verify",
            key="verify-subscription-again",
        )["verified_at"].replace("+00:00", "")
        == verified["verified_at"].replace("+00:00", "")
    )

    action = req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="cancel-subscription",
        status=201,
    )
    assert action["kind"] == "subscription_cancel"
    assert confirm(bank, action)["status"] == "SUCCEEDED"
    cancelled = req(bank, "GET", f"/api/subscriptions/{subscription_id}")
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["next_charge_at"] is None
    replay = req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="another-cancel-key",
        status=201,
    )
    assert replay["id"] == action["id"]
    balances_before_charge = dict(bank["core"].balances)
    req(
        bank,
        "POST",
        f"/api/demo/subscriptions/{subscription_id}/charge",
        key="blocked-charge",
        status=409,
    )
    assert bank["core"].balances == balances_before_charge
    assert req(bank, "POST", "/api/subscriptions/scan")["items"][0]["status"] == "CANCELLED"


def verified_subscription(bank, merchants=("Demo Video",)):
    day = now().astimezone(SHANGHAI).date()
    rows = []
    transaction_id = 1
    for merchant in merchants:
        for age in (89, 59, 29):
            rows.append(
                {
                    **raw_tx(transaction_id, day - timedelta(days=age), "100"),
                    "note": f"[Merchant] {merchant}",
                }
            )
            transaction_id += 1
    bank["core"].tx[1] = rows
    found = req(bank, "POST", "/api/subscriptions/scan")["items"]
    ids = []
    for merchant in merchants:
        row = next(item for item in found if item["merchant"] == merchant)
        req(
            bank,
            "POST",
            f"/api/subscriptions/{row['id']}/verify",
            key=f"verify-{row['id']}",
        )
        ids.append(row["id"])
    return ids


def test_subscription_scan_reports_successful_empty_scan_and_preserves_candidates(bank):
    result = req(bank, "POST", "/api/subscriptions/scan")
    assert result["created"] == result["updated"] == result["matched_candidates"] == 0
    assert result["found"] == 0 and result["items"] == []
    assert result["from_date"] == (now().astimezone(SHANGHAI).date() - timedelta(days=800)).isoformat()
    assert result["to_date"] == now().astimezone(SHANGHAI).date().isoformat()
    assert datetime.fromisoformat(result["scanned_at"]).tzinfo is not None


def test_subscription_renewals_are_server_scoped_and_read_only(bank, monkeypatch):
    import services.subscription_service as subscription_module

    fixed_now = datetime(2026, 10, 26, 16, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(subscription_module, "now", lambda: fixed_now)
    scan = req(bank, "POST", "/api/subscriptions/scan")
    assert scan["matched_candidates"] == 0
    assert req(bank, "GET", "/api/subscriptions/renewals")["last_scan_at"] == scan["scanned_at"]

    as_of = date(2026, 10, 27)  # UTC has not crossed midnight; Shanghai has.
    rows = {}
    with bank["db"]() as db:
        alice = db.get(User, bank["ids"][0])
        bob = db.get(User, bank["ids"][1])
        for owner, key, charge_date, status in [
            (alice, "today", as_of, "VERIFIED"),
            (alice, "third", as_of + timedelta(days=3), "VERIFIED"),
            (alice, "overdue", as_of - timedelta(days=1), "VERIFIED"),
            (alice, "later", as_of + timedelta(days=4), "VERIFIED"),
            (alice, "candidate", as_of + timedelta(days=1), "CANDIDATE"),
            (alice, "ignored", as_of + timedelta(days=1), "IGNORED"),
            (bob, "bob", as_of + timedelta(days=1), "VERIFIED"),
        ]:
            merchant = Merchant(
                external_key=f"renewal-test:{key}",
                name=f"Renewal {key}",
                category="娱乐",
                adapter_type="demo_subscription",
                active=True,
            )
            db.add(merchant)
            db.flush()
            row = Subscription(
                user_id=owner.id,
                merchant_id=merchant.id,
                status=status,
                cadence="MONTHLY",
                expected_amount=Decimal("12.34"),
                amount_tolerance=Decimal("0.10"),
                next_charge_at=charge_date,
                evidence={},
                verified_at=fixed_now if status == "VERIFIED" else None,
            )
            db.add(row)
            db.flush()
            rows[key] = row.id
        db.commit()
        before_audits = db.query(Audit).count()

    result = req(bank, "GET", "/api/subscriptions/renewals?days=3")
    assert result["as_of"] == "2026-10-27"
    assert result["timezone"] == "Asia/Shanghai"
    assert result["to_date"] == "2026-10-30"
    assert [row["id"] for row in result["upcoming"]] == [rows["today"], rows["third"]]
    assert [row["id"] for row in result["needs_review"]] == [rows["overdue"]]
    assert rows["later"] not in [row["id"] for row in result["upcoming"]]
    assert rows["candidate"] not in [row["id"] for row in result["upcoming"]]
    assert rows["ignored"] not in [row["id"] for row in result["upcoming"]]
    assert rows["bob"] not in [row["id"] for row in result["upcoming"]]
    assert req(bank, "GET", "/api/subscriptions/renewals?days=1")["upcoming"] == [
        row for row in result["upcoming"] if row["id"] == rows["today"]
    ]
    for value in ("0", "91", "1.5", "bad"):
        req(bank, "GET", f"/api/subscriptions/renewals?days={value}", status=422)
    with bank["db"]() as db:
        assert db.query(Audit).count() == before_audits


def test_subscription_renewals_use_shanghai_day_at_utc_boundary(bank, monkeypatch):
    import services.subscription_service as subscription_module

    monkeypatch.setattr(
        subscription_module,
        "now",
        lambda: datetime(2026, 10, 26, 16, 30, tzinfo=timezone.utc),
    )
    result = req(bank, "GET", "/api/subscriptions/renewals?days=1")
    assert result["as_of"] == "2026-10-27"
    assert result["from_date"] == "2026-10-27"
    assert result["to_date"] == "2026-10-28"


def test_concurrent_subscription_scans_merge_candidates_once(bank):
    if bank["engine"].dialect.name != "postgresql":
        pytest.skip("requires PostgreSQL row locks")
    day = now().astimezone(SHANGHAI).date()
    bank["core"].tx[1] = [
        {**raw_tx(index, day - timedelta(days=30 * index), "100"), "note": "[Merchant] Parallel Stream"}
        for index in range(3, 0, -1)
    ]

    def scan(_):
        with bank["db"]() as db:
            user = db.get(User, bank["ids"][0])
            from services.subscription_service import SubscriptionService

            return SubscriptionService(db, bank["core"], bank["settings"]).scan(user)

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(scan, range(2)))
    assert sorted(result["created"] for result in results) == [0, 1]
    with bank["db"]() as db:
        rows = db.scalars(select(Subscription)).all()
        assert len(rows) == 1
        assert db.query(Audit).filter_by(event="SUBSCRIPTIONS_SCANNED").count() == 2
        assert len(rows[0].evidence["occurrences"]) == 3


def test_subscription_scan_uses_all_accounts_excludes_reversals_and_accepts_ten_percent_boundary(bank):
    day = now().astimezone(SHANGHAI).date()
    bank["core"].owners[4] = 1
    bank["core"].balances[4] = Decimal("0")
    bank["core"].account_statuses[4] = "active"
    bank["core"].account_external_ids[4] = "AGENT-ALICE-SECOND-SAV"
    bank["core"].tx[4] = [
        {**raw_tx(1, day, "110"), "accountId": 4, "note": "[Merchant] Split Account Service"},
        {**raw_tx(2, day - timedelta(days=60), "89"), "accountId": 4, "note": "[Merchant] Unstable Service"},
        {**raw_tx(3, day - timedelta(days=30), "100"), "accountId": 4, "note": "[Merchant] Unstable Service"},
        {**raw_tx(4, day, "100"), "accountId": 4, "note": "[Merchant] Unstable Service"},
    ]
    bank["core"].tx[1] = [
        {**raw_tx(1, day - timedelta(days=60), "90"), "note": "[Merchant] Split Account Service"},
        {**raw_tx(2, day - timedelta(days=30), "100"), "note": "[Merchant] Split Account Service"},
        {**raw_tx(3, day, "1000"), "reversed": True, "note": "[Merchant] Split Account Service"},
    ]

    result = req(bank, "POST", "/api/subscriptions/scan")
    assert result["matched_candidates"] == 1
    assert result["found"] == 1
    row = result["items"][0]
    assert row["merchant"] == "Split Account Service"
    assert Decimal(row["expected_amount"]) == 100
    assert row["occurrence_count"] == 3
    detail = req(bank, "GET", f"/api/subscriptions/{row['id']}")
    assert [item["account_id"] for item in detail["occurrences"]] == [1, 1, 4]
    assert all(item["transaction_id"] != 3 for item in detail["occurrences"])


def test_subscription_scan_upstream_failure_does_not_save_partial_candidates_or_scan_time(bank):
    from clients.fineract import FineractUnavailableError

    day = now().astimezone(SHANGHAI).date()
    bank["core"].owners[4] = 1
    bank["core"].balances[4] = Decimal("0")
    bank["core"].account_statuses[4] = "active"
    bank["core"].account_external_ids[4] = "AGENT-ALICE-SECOND-SAV"
    bank["core"].tx[1] = [
        {**raw_tx(index, day - timedelta(days=30 * age), "20"), "note": "[Merchant] Partial Candidate"}
        for index, age in enumerate((2, 1, 0), 1)
    ]
    search = bank["core"].search_transactions

    def fail_second_account(account_id, *args, **kwargs):
        if account_id == 4:
            raise FineractUnavailableError(503, "second account unavailable")
        return search(account_id, *args, **kwargs)

    bank["core"].search_transactions = fail_second_account
    failure = req(bank, "POST", "/api/subscriptions/scan", status=503)
    assert failure["error"]["code"] == "UPSTREAM_ERROR"
    with bank["db"]() as db:
        assert db.query(Subscription).count() == 0
        assert db.query(SubscriptionOccurrence).count() == 0
        assert db.query(Audit).filter_by(event="SUBSCRIPTIONS_SCANNED").count() == 0
    renewals = req(bank, "GET", "/api/subscriptions/renewals")
    assert renewals["last_scan_at"] is None


def test_subscription_cancel_expired_or_user_cancelled_action_can_be_replaced(bank):
    subscription_id = verified_subscription(bank)[0]
    expired = req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="cancel-expiring",
        status=201,
    )
    with bank["db"]() as db:
        action = db.get(Action, expired["id"])
        action.expires_at = now() - timedelta(seconds=1)
        db.commit()

    replacement = req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="cancel-after-expiry",
        status=201,
    )
    assert replacement["id"] != expired["id"]
    assert replacement["status"] == "WAITING_CONFIRMATION"
    with bank["db"]() as db:
        closed_expired = db.get(Action, expired["id"])
        assert closed_expired.status == "CANCELLED"
        assert closed_expired.error_code == "ACTION_EXPIRED"
    assert req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="cancel-expiring",
        status=201,
    )["id"] == expired["id"]
    assert req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="cancel-after-expiry",
        status=201,
    )["id"] == replacement["id"]

    req(bank, "POST", f"/api/actions/{replacement['id']}/cancel")
    after_user_cancel = req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="cancel-after-user-cancel",
        status=201,
    )
    assert after_user_cancel["id"] not in {expired["id"], replacement["id"]}
    assert confirm(bank, after_user_cancel)["status"] == "SUCCEEDED"


def test_subscription_cancel_action_retries_after_explicit_failure(bank):
    subscription_id = verified_subscription(bank)[0]
    with bank["db"]() as db:
        sub = db.get(Subscription, subscription_id)
        merchant = db.get(Merchant, sub.merchant_id)
        merchant.active = False
        db.commit()
    failed = req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="cancel-failed",
        status=201,
    )
    assert confirm(bank, failed)["status"] == "FAILED"
    with bank["db"]() as db:
        sub = db.get(Subscription, subscription_id)
        db.get(Merchant, sub.merchant_id).active = True
        db.commit()
    retry = req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="cancel-retry",
        status=201,
    )
    assert retry["id"] != failed["id"]
    assert confirm(bank, retry)["status"] == "SUCCEEDED"


def test_subscription_cancel_rejects_another_users_subscription(bank):
    subscription_id = verified_subscription(bank)[0]
    req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        user="bob",
        key="cross-user-cancel",
        status=404,
    )


def test_subscription_cancel_reads_legacy_action_confirmation_fields(bank):
    subscription_id = verified_subscription(bank)[0]
    with bank["db"]() as db:
        user = db.get(User, bank["ids"][0])
        subscription = db.get(Subscription, subscription_id)
        merchant = db.get(Merchant, subscription.merchant_id)
        from services.action_service import ActionService

        action = ActionService(db, bank["core"], bank["settings"]).create(
            user,
            "subscription_cancel",
            {
                "subscription_id": subscription.id,
                "merchant": merchant.name,
                "expected_amount": str(subscription.expected_amount),
                "cadence": subscription.cadence,
                "next_charge_at": subscription.next_charge_at.isoformat(),
                "demo_only": True,
            },
            "legacy-cancel-without-snapshot",
            commit=False,
        )
        subscription.action_id = action.id
        db.commit()

    replay = req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="new-key-while-legacy-confirmation-is-open",
        status=201,
    )
    assert "subscription_snapshot" not in replay["payload"]
    assert confirm(bank, replay)["status"] == "SUCCEEDED"


def test_subscription_cancel_confirmation_rejects_changed_snapshot_and_retries(bank):
    subscription_id = verified_subscription(bank)[0]
    stale = req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="cancel-stale-snapshot",
        status=201,
    )
    with bank["db"]() as db:
        db.get(Subscription, subscription_id).expected_amount = Decimal("125.00")
        db.commit()
    result = confirm(bank, stale)
    assert result["status"] == "FAILED"
    assert result["error_code"] == "SUBSCRIPTION_CHANGED"
    assert req(bank, "GET", f"/api/subscriptions/{subscription_id}")["status"] == "VERIFIED"
    refreshed = req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="cancel-current-snapshot",
        status=201,
    )
    assert refreshed["id"] != stale["id"]
    assert refreshed["payload"]["expected_amount"] == "125.00"
    assert confirm(bank, refreshed)["status"] == "SUCCEEDED"


def test_subscription_cancel_same_key_cannot_cross_subscriptions(bank):
    first, second = verified_subscription(bank, ("Demo Video", "Demo Music"))
    request = req(
        bank,
        "POST",
        f"/api/subscriptions/{first}/cancel",
        key="cancel-key-bound-to-one-subscription",
        status=201,
    )
    conflict = req(
        bank,
        "POST",
        f"/api/subscriptions/{second}/cancel",
        key="cancel-key-bound-to-one-subscription",
        status=409,
    )
    assert conflict["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert req(
        bank,
        "POST",
        f"/api/subscriptions/{first}/cancel",
        key="cancel-key-bound-to-one-subscription",
        status=201,
    )["id"] == request["id"]


def test_subscription_cancel_does_not_replace_unknown_in_flight_result(bank):
    subscription_id = verified_subscription(bank)[0]
    action = req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="cancel-in-flight",
        status=201,
    )
    with bank["db"]() as db:
        db.get(Action, action["id"]).status = "RECONCILING"
        db.commit()
    replay = req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/cancel",
        key="do-not-retry-unknown-result",
        status=201,
    )
    assert replay["id"] == action["id"]
    assert replay["status"] == "RECONCILING"


def test_demo_subscription_charge_is_hidden_outside_development(bank, monkeypatch):
    from types import SimpleNamespace
    import api.subscriptions

    monkeypatch.setattr(
        api.subscriptions,
        "get_settings",
        lambda: SimpleNamespace(environment="production"),
    )
    req(
        bank,
        "POST",
        "/api/demo/subscriptions/not-visible/charge",
        key="hidden-demo-charge",
        status=404,
    )


def test_subscription_ignore_is_stable_until_evidence_changes(bank):
    day = now().astimezone(SHANGHAI).date()
    bank["core"].tx[1] = [
        raw_tx(index + 1, day - timedelta(days=90 - index * 30), "20")
        for index in range(3)
    ]
    for transaction_id in range(1, 4):
        req(
            bank,
            "POST",
            "/api/transaction-annotations",
            {
                "account_id": 1,
                "transaction_id": transaction_id,
                "merchant": "Demo Music",
            },
            status=201,
        )
    subscription_id = req(bank, "POST", "/api/subscriptions/scan")["items"][0]["id"]
    req(
        bank,
        "POST",
        f"/api/subscriptions/{subscription_id}/ignore",
        key="ignore-subscription",
    )
    unchanged = req(bank, "POST", "/api/subscriptions/scan")["items"][0]
    assert unchanged["status"] == "IGNORED"

    bank["core"].tx[1].append(raw_tx(4, day, "20"))
    req(
        bank,
        "POST",
        "/api/transaction-annotations",
        {"account_id": 1, "transaction_id": 4, "merchant": "Demo Music"},
        status=201,
    )
    changed = req(bank, "POST", "/api/subscriptions/scan")["items"][0]
    assert changed["status"] == "CANDIDATE"


def test_subscription_scan_supports_three_yearly_occurrences(bank):
    day = now().astimezone(SHANGHAI).date()
    bank["core"].tx[1] = [
        raw_tx(1, day - timedelta(days=730), "50"),
        raw_tx(2, day - timedelta(days=365), "51"),
        raw_tx(3, day, "50"),
    ]
    for transaction_id in range(1, 4):
        req(
            bank,
            "POST",
            "/api/transaction-annotations",
            {
                "account_id": 1,
                "transaction_id": transaction_id,
                "merchant": "Demo Annual",
            },
            status=201,
        )
    items = req(bank, "POST", "/api/subscriptions/scan")["items"]
    assert len(items) == 1
    assert items[0]["cadence"] == "YEARLY"
    assert Decimal(items[0]["expected_amount"]) == 50


def test_large_anomaly_evidence(bank):
    day = now().astimezone(SHANGHAI).date()
    bank["core"].tx[1] = [
        raw_tx(i, day - timedelta(days=i), "100") for i in range(1, 11)
    ] + [raw_tx(20, day, "1000")]
    anomalies = req(
        bank,
        "GET",
        f"/api/billing/anomalies?account_id=1&from_date={day}&to_date={day}",
    )
    assert (
        anomalies[0]["rule"] == "LARGE_V1" and anomalies[0]["evidence"]["samples"] == 10
    )
    req(
        bank,
        "POST",
        "/api/billing/anomaly-reviews",
        {"anomaly_key": anomalies[0]["anomaly_key"], "status": "ignored"},
    )
    assert (
        req(
            bank,
            "GET",
            f"/api/billing/anomalies?account_id=1&from_date={day}&to_date={day}",
        )[0]["status"]
        == "ignored"
    )


def configure_product(bank):
    with bank["db"]() as db:
        db.add(
            ProductMetadata(
                product_id=10,
                tenant="default",
                risk_level=2,
                enabled=True,
                allows_premature=True,
            )
        )
        db.commit()
    return req(
        bank, "POST", "/api/risk-assessments", {"answers": [5] * 5}, status=201
    )


def test_fixed_subscription_redemption_and_replay(bank):
    configure_product(bank)
    p = {"product_id": 10, "from_account_id": 1, "amount": "100", "term_months": 1}
    a = req(
        bank, "POST", "/api/investments/subscriptions", p, key="subscribe", status=201
    )
    a = verify(bank, confirm(bank, a))
    assert a["status"] == "SUCCEEDED"
    assert bank["core"].balances[1] == 9900
    assert (
        req(
            bank,
            "POST",
            "/api/investments/subscriptions",
            p,
            key="subscribe",
            status=201,
        )["id"]
        == a["id"]
    )
    hid = a["steps"]["holding_id"]
    q = req(
        bank,
        "GET",
        f"/api/investments/redemption-quotes?holding_id={hid}&to_account_id=1",
    )
    r = req(
        bank,
        "POST",
        "/api/investments/redemptions",
        {"holding_id": hid, "to_account_id": 1, "quote_hash": q["quote_hash"]},
        key="redeem",
        status=201,
    )
    assert verify(bank, confirm(bank, r))["status"] == "SUCCEEDED"
    assert bank["core"].balances[1] == 10000


def test_each_subscription_consumes_one_short_lived_assessment(bank):
    assessment = configure_product(bank)
    assert assessment["purpose"] == "subscription"
    assert assessment["used_at"] is None and assessment["action_id"] is None
    assert aware(datetime.fromisoformat(assessment["expires_at"])) <= now() + timedelta(
        minutes=16
    )
    body = {
        "product_id": 10,
        "from_account_id": 1,
        "amount": "100",
        "term_months": 1,
        "assessment_id": assessment["id"],
    }
    action = req(
        bank,
        "POST",
        "/api/investments/subscriptions",
        body,
        key="assessment-once",
        status=201,
    )
    with bank["db"]() as db:
        stored = db.get(RiskAssessment, assessment["id"])
        assert stored.used_at is not None and stored.action_id == action["id"]

    assert (
        req(
            bank,
            "POST",
            "/api/investments/subscriptions",
            body,
            key="assessment-once",
            status=201,
        )["id"]
        == action["id"]
    )
    reused = req(
        bank,
        "POST",
        "/api/investments/subscriptions",
        body,
        key="assessment-reuse",
        status=409,
    )
    assert reused["error"]["code"] == "ASSESSMENT_ALREADY_USED"


def test_fixed_failure_resume_no_duplicate_open(bank):
    configure_product(bank)
    bank["core"].fail_approve = True
    a = req(
        bank,
        "POST",
        "/api/investments/subscriptions",
        {"product_id": 10, "from_account_id": 1, "amount": "100", "term_months": 1},
        key="subscribe",
        status=201,
    )
    a = verify(bank, confirm(bank, a))
    assert a["status"] == "RECONCILING" and a["steps"]["holding_id"]
    bank["core"].fail_approve = False
    a = req(bank, "POST", f"/api/actions/{a['id']}/resume")
    assert a["status"] == "WAITING_CONFIRMATION"
    with bank["db"]() as db:
        db.get(Action, a["id"]).otp_expires = now() - timedelta(seconds=1)
        db.commit()
    assert verify(bank, confirm(bank, a))["status"] == "SUCCEEDED"
    assert len(bank["core"].holdings) == 1 and bank["core"].balances[1] == 9900


@pytest.mark.parametrize(
    "answers,level",
    [([1] * 5, 1), ([2] * 5, 2), ([3] * 5, 3), ([4] * 5, 4), ([5] * 5, 5)],
)
def test_risk_score_bounds(bank, answers, level):
    assert (
        req(bank, "POST", "/api/risk-assessments", {"answers": answers}, status=201)[
            "level"
        ]
        == level
    )


def test_prod_inbox_forbidden():
    from core.config import Settings
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", dev_otp_inbox=True)


def test_concurrent_transfer_quota_reservation(bank):
    if bank["engine"].dialect.name != "postgresql":
        pytest.skip("requires PostgreSQL row locks")
    a = transfer(bank, "600", "first")
    b = transfer(bank, "600", "second")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda x: confirm(bank, x), [a, b]))
    assert sorted(r["status"] for r in results) == ["SUCCEEDED", "WAITING_VERIFICATION"]
    assert len(bank["core"].transfers) == 1
    with bank["db"]() as db:
        assert db.scalar(select(DailyUsage)).amount == 600


def test_concurrent_workers_only_one_payment(bank):
    if bank["engine"].dialect.name != "postgresql":
        pytest.skip("requires PostgreSQL row locks")
    s, p = schedule(bank)

    def tick(_):
        with bank["db"]() as db:
            return ScheduleService(db, bank["core"], bank["settings"]).tick(
                now() + timedelta(minutes=5)
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(tick, [1, 2]))
    assert len(bank["core"].transfers) == 1
    with bank["db"]() as db:
        assert len(db.scalars(select(ScheduleRun)).all()) == 1


def test_schedule_restart_authorized_intent_and_limit(bank):
    s, p = schedule(bank, "daily")
    from services.action_service import ActionService

    with bank["db"]() as db:
        row = db.get(Schedule, s["id"])
        u = db.get(User, row.user_id)
        due = aware(row.next_run)
        payload = {
            k: row.payload[k]
            for k in [
                "from_account_id",
                "to_account_id",
                "amount",
                "currency",
                "remark",
                "to_client_id",
            ]
        }
        payload["schedule_id"] = s["id"]
        payload["scheduled_at"] = due.isoformat()
        a = ActionService(db, bank["core"], bank["settings"]).create(
            u,
            "transfer",
            payload,
            f"schedule:{s['id']}:{due.isoformat()}",
            10,
            commit=False,
        )
        a.status = "AUTHORIZED"
        a.confirmed_at = now()
        db.add(
            ScheduleRun(
                schedule_id=s["id"], scheduled_at=due, status="CREATED", action_id=a.id
            )
        )
        db.commit()
    with bank["db"]() as db:
        ScheduleService(db, bank["core"], bank["settings"]).tick(
            now() + timedelta(minutes=5)
        )
    assert len(bank["core"].transfers) == 1
    # Next occurrence is due but happens on the same real business day in this clock-injection test.
    with bank["db"]() as db:
        ScheduleService(db, bank["core"], bank["settings"]).tick(
            now() + timedelta(days=1, minutes=5)
        )
    assert len(bank["core"].transfers) == 1
    assert (
        req(bank, "GET", f"/api/transfer-schedules/{s['id']}")["status"]
        == "WAITING_AUTHORIZATION"
    )


def test_aa_cancel_pending_action_cannot_pay(bank):
    c = req(
        bank,
        "POST",
        "/api/aa-collections",
        {
            "account_id": 1,
            "title": "Split",
            "amount": "10",
            "participants": [{"user_id": bank["ids"][1]}],
        },
        status=201,
    )
    a = req(
        bank,
        "POST",
        f"/api/aa-collections/{c['id']}/shares/{c['shares'][0]['id']}/pay",
        {"from_account_id": 2},
        user="bob",
        key="pending",
    )
    req(bank, "DELETE", f"/api/aa-collections/{c['id']}")
    req(
        bank,
        "POST",
        f"/api/actions/{a['id']}/confirm",
        {"request_hash": a["request_hash"]},
        user="bob",
        status=409,
    )
    assert not bank["core"].transfers


def test_risk_expired_and_metadata_required(bank):
    p = {"product_id": 10, "from_account_id": 1, "amount": "100", "term_months": 1}
    req(
        bank, "POST", "/api/investments/subscriptions", p, key="no-metadata", status=400
    )
    configure_product(bank)
    with bank["db"]() as db:
        db.scalar(select(RiskAssessment)).expires_at = now() - timedelta(seconds=1)
        db.commit()
    req(bank, "POST", "/api/investments/subscriptions", p, key="expired", status=409)


def test_legacy_or_old_assessment_cannot_fund_new_subscription(bank):
    assessment = configure_product(bank)
    with bank["db"]() as db:
        row = db.get(RiskAssessment, assessment["id"])
        row.created_at = now() - timedelta(minutes=16)
        row.expires_at = now() + timedelta(days=365)
        db.commit()
    req(
        bank,
        "POST",
        "/api/investments/subscriptions",
        {"product_id": 10, "from_account_id": 1, "amount": "100", "term_months": 1},
        key="old-assessment",
        status=409,
    )


def test_schedule_catchup_only_latest(bank):
    s, p = schedule(bank, "daily")
    with bank["db"]() as db:
        ScheduleService(db, bank["core"], bank["settings"]).tick(
            now() + timedelta(days=3, minutes=5)
        )
    runs = req(bank, "GET", f"/api/transfer-schedules/{s['id']}/runs")
    assert len(bank["core"].transfers) == 1 and len(runs) == 4
    assert sum(r["status"] == "MISSED" for r in runs) == 3


def test_fixed_transfer_report_splits_verified_interest(bank):
    day = now().astimezone(SHANGHAI).date()
    bank["core"].holdings[100] = {
        "id": 100,
        "clientId": 1,
        "depositAmount": "100",
        "status": {"closed": True},
        "summary": {"totalWithdrawals": "100.05"},
        "transferInterestToSavings": False,
    }
    bank["core"].transfers[77] = {"fromAccount": {"id": 100}, "toAccount": {"id": 1}}
    bank["core"].tx[1] = [
        raw_tx(
            1,
            day,
            "100.05",
            entryType="CREDIT",
            transactionType={"deposit": True},
            transfer={"id": 77},
        )
    ]
    stats = req(
        bank,
        "GET",
        f"/api/billing/statistics?account_id=1&from_date={day}&to_date={day}",
    )
    assert Decimal(stats["totals"]["fixed_transfer"]) == 100
    assert Decimal(stats["totals"]["interest"]) == Decimal(".05")
    assert "expense" not in stats["totals"]


def test_definite_core_rejection_releases_reserved_quota(bank, monkeypatch):
    from clients.fineract import FineractError

    def reject(*args):
        raise FineractError(400, "validation failure")

    monkeypatch.setattr(bank["core"], "create_transfer", reject)
    a = confirm(bank, transfer(bank, "100"))
    assert a["status"] == "FAILED"
    with bank["db"]() as db:
        assert db.scalar(select(DailyUsage)).amount == 0


def test_money_precision_and_amount_validation(bank):
    recipient = req(
        bank, "POST", "/api/recipients", {"name": "Bob", "account_id": 2}, status=201
    )
    for amount in ["0", "-1", "0.001", "NaN", "Infinity"]:
        req(
            bank,
            "POST",
            "/api/transfers",
            {"from_account_id": 1, "recipient_id": recipient["id"], "amount": amount},
            key=amount,
            status=422,
        )


def test_unconfirmed_timeout_does_not_retry(bank, monkeypatch):
    from clients.fineract import FineractUnavailableError

    def unavailable(*args):
        raise FineractUnavailableError(503, "timeout before acknowledgement")

    monkeypatch.setattr(bank["core"], "create_transfer", unavailable)
    a = confirm(bank, transfer(bank, "100"))
    assert a["status"] == "RECONCILING"
    req(bank, "POST", f"/api/actions/{a['id']}/reconcile", status=409)
    assert bank["core"].balances[1] == 10000 and not bank["core"].transfers


def test_subscription_unknown_response_discovers_application(bank, monkeypatch):
    from clients.fineract import FineractUnavailableError

    configure_product(bank)
    original = bank["core"].create_fixed

    def lost(*args):
        original(*args)
        raise FineractUnavailableError(503, "response lost after create")

    monkeypatch.setattr(bank["core"], "create_fixed", lost)
    a = req(
        bank,
        "POST",
        "/api/investments/subscriptions",
        {"product_id": 10, "from_account_id": 1, "amount": "100", "term_months": 1},
        key="lost-create",
        status=201,
    )
    a = verify(bank, confirm(bank, a))
    assert a["status"] == "RECONCILING" and not a["steps"]
    req(bank, "POST", f"/api/actions/{a['id']}/reconcile", status=409)
    a = req(bank, "POST", f"/api/actions/{a['id']}/resume")
    assert verify(bank, confirm(bank, a))["status"] == "SUCCEEDED"
    assert len(bank["core"].holdings) == 1


def test_contact_detail_resolves_aa_without_disclosing_balance(bank):
    r = req(
        bank, "POST", "/api/recipients", {"name": "Bob", "account_id": 2}, status=201
    )
    data = req(bank, "GET", f"/api/recipients/{r['id']}")
    assert data["participant_user_id"] == bank["ids"][1]
    assert "balance" not in data and "summary" not in data


def test_daily_limit_uses_shanghai_calendar_day(bank):
    with bank["db"]() as db:
        db.add(
            DailyUsage(
                user_id=bank["ids"][0],
                day=now().astimezone(SHANGHAI).date() - timedelta(days=1),
                amount=1000,
            )
        )
        db.commit()
    assert confirm(bank, transfer(bank, "1000"))["status"] == "SUCCEEDED"


def test_resending_otp_invalidates_old_code_without_resetting_failures(
    bank, monkeypatch
):
    import services.action_service

    codes = iter([123456, 654321])
    monkeypatch.setattr(
        services.action_service.secrets, "randbelow", lambda maximum: next(codes)
    )
    a = confirm(bank, transfer(bank, "1001"))
    req(bank, "POST", f"/api/actions/{a['id']}/otp")
    with bank["db"]() as db:
        db.get(Action, a["id"]).otp_expires = now() + timedelta(minutes=4)
        db.commit()
    req(bank, "POST", f"/api/actions/{a['id']}/otp")
    req(bank, "POST", f"/api/actions/{a['id']}/verify", {"code": "123456"}, status=400)
    assert (
        req(bank, "POST", f"/api/actions/{a['id']}/verify", {"code": "654321"})[
            "status"
        ]
        == "SUCCEEDED"
    )


def test_year_boundary_hold_and_reversal_report(bank):
    from services.billing_service import period_range

    assert period_range("2024-02") == (date(2024, 2, 1), date(2024, 2, 29))
    day = now().astimezone(SHANGHAI).date()
    bank["core"].tx[1] = [
        raw_tx(1, date(day.year, 1, 1), "10"),
        raw_tx(2, date(day.year - 1, 12, 31), "99"),
        raw_tx(3, day, "100", transactionType={"amountHold": True}),
        raw_tx(4, day, "90", isReversal=True),
    ]
    report = req(
        bank,
        "POST",
        "/api/bill-reports",
        {"account_id": 1, "period": str(day.year)},
        status=201,
    )
    assert Decimal(report["payload"]["totals"]["expense"]) == 10
    assert Decimal(report["payload"]["totals"]["hold"]) == 100


def test_known_rejected_deposit_step_can_resume_with_new_authorization(
    bank, monkeypatch
):
    from clients.fineract import FineractError

    configure_product(bank)
    original = bank["core"].fixed_command
    rejected_keys = set()
    failed = False

    def cached_rejection(id, command, p, key):
        nonlocal failed
        if command == "approve" and not failed:
            failed = True
            rejected_keys.add(key)
        if key in rejected_keys:
            raise FineractError(400, "cached definitive rejection")
        return original(id, command, p, key)

    monkeypatch.setattr(bank["core"], "fixed_command", cached_rejection)
    a = req(
        bank,
        "POST",
        "/api/investments/subscriptions",
        {"product_id": 10, "from_account_id": 1, "amount": "100", "term_months": 1},
        key="definite-rejection",
        status=201,
    )
    a = verify(bank, confirm(bank, a))
    assert a["status"] == "RECONCILING" and a["steps"]["rejected_step"] == "approve"
    a = req(bank, "POST", f"/api/actions/{a['id']}/resume")
    assert a["steps"]["retry_approve"] == 1
    a = verify(bank, confirm(bank, a))
    assert a["status"] == "SUCCEEDED"
    assert len(bank["core"].holdings) == 1 and bank["core"].balances[1] == 9900


def test_schedule_old_unclaimed_intent_is_missed_after_long_downtime(bank):
    s, p = schedule(bank, "daily")
    from services.action_service import ActionService

    with bank["db"]() as db:
        row = db.get(Schedule, s["id"])
        u = db.get(User, row.user_id)
        due = aware(row.next_run)
        payload = {
            k: row.payload[k]
            for k in [
                "from_account_id",
                "to_account_id",
                "amount",
                "currency",
                "remark",
                "to_client_id",
            ]
        }
        payload["schedule_id"] = s["id"]
        payload["scheduled_at"] = due.isoformat()
        a = ActionService(db, bank["core"], bank["settings"]).create(
            u,
            "transfer",
            payload,
            f"schedule:{s['id']}:{due.isoformat()}",
            10,
            commit=False,
        )
        aid = a.id
        a.status = "AUTHORIZED"
        a.confirmed_at = now()
        db.add(
            ScheduleRun(
                schedule_id=s["id"], scheduled_at=due, status="CREATED", action_id=aid
            )
        )
        db.commit()
    with bank["db"]() as db:
        ScheduleService(db, bank["core"], bank["settings"]).tick(
            now() + timedelta(days=3, minutes=5)
        )
    runs = req(bank, "GET", f"/api/transfer-schedules/{s['id']}/runs")
    assert (
        len(bank["core"].transfers) == 1
        and sum(r["status"] == "MISSED" for r in runs) == 3
    )
    assert req(bank, "GET", f"/api/actions/{aid}")["status"] == "CANCELLED"
