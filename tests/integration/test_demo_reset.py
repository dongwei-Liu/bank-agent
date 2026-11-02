from datetime import date, timedelta
from decimal import Decimal
import json

import pytest
from sqlalchemy import func, select

from core.security import now, password_hasher, SHANGHAI
from models import (
    AACollection,
    AAShare,
    Action,
    AgentConversation,
    AgentEvent,
    AgentMessage,
    AgentRun,
    Annotation,
    AnomalyReview,
    Audit,
    BillReport,
    BillReportJob,
    BillReportTransaction,
    BankCard,
    CardAuthorization,
    Category,
    ClassificationRule,
    DailyUsage,
    LoginSession,
    Merchant,
    ProductMetadata,
    Recipient,
    RiskAssessment,
    Schedule,
    ScheduleRun,
    SecurityEvent,
    SecurityLock,
    Subscription,
    SubscriptionOccurrence,
    User,
)
from services.billing_service import BillingService
from services.transaction_service import TransactionService
from scripts.development.reset_demo import (
    DemoIdentity,
    FineractDemoResetter,
    ResetRefused,
    USER_SCOPED_MODELS,
    reset_application_state,
)
from scripts.development.init_banking import (
    ensure_demo_cards,
    initialize_billing_categories,
    primary_savings_account,
)
from scripts.fineract.demo_history import (
    CATEGORY_MERCHANTS,
    MONTHLY_SUBSCRIPTION_MERCHANTS,
    build_random_history,
    merchant_category_map,
    split_history_for_analysis_account,
)
from scripts.fineract.seed_fineract import CLIENTS, ClientSpec, build_history, write_manifest


def identity(key, client_id, account_id):
    return DemoIdentity(
        key=key.upper(),
        username=key.lower(),
        client_external_id=f"AGENT-{key.upper()}",
        client_id=client_id,
        account_external_id=f"AGENT-{key.upper()}-SAV",
        account_id=account_id,
        mobile=f"1380000000{client_id}",
    )


class ResetPlanCore:
    dynamic_external_id = "BANK-CARD-00000000-0000-4000-8000-000000000001"

    def __init__(self, *, cross_boundary=False, unknown_account=False, duplicate_analysis_account=False):
        self.cross_boundary = cross_boundary
        self.unknown_account = unknown_account
        self.duplicate_analysis_account = duplicate_analysis_account
        self.reversed_transactions = set()
        self.closed_accounts = set()
        self.posts = []

    def get(self, path, **kwargs):
        if path == "/clients":
            external = kwargs["params"]["externalId"]
            keys = (
                "ALICE",
                "BOB",
                "CHARLIE",
                "MOM",
                "DEMO-MERCHANT",
                "DEMO-FLOWER",
                "DEMO-CAKE",
            )
            key = external.removeprefix("AGENT-")
            index = keys.index(key) + 1
            return {
                "pageItems": [
                    {
                        "id": index,
                        "externalId": external,
                        "mobileNo": f"1380000000{index}",
                    }
                ]
            }
        if path.startswith("/clients/"):
            index = int(path.split("/")[2])
            if index in {5, 6, 7}:
                merchant = {
                    5: (50, "AGENT-DEMO-MERCHANT-SAV"),
                    6: (51, "AGENT-DEMO-FLOWER-SAV"),
                    7: (52, "AGENT-DEMO-CAKE-SAV"),
                }[index]
                return {
                    "savingsAccounts": [
                        {
                            "id": merchant[0],
                            "externalId": merchant[1],
                            "depositType": {"id": 100},
                            "status": {"active": True},
                        }
                    ]
                }
            key = ("ALICE", "BOB", "CHARLIE", "MOM")[index - 1]
            accounts = [
                {
                    "id": index,
                    "externalId": f"AGENT-{key}-SAV",
                    "depositType": {"id": 100},
                    "status": {"active": True},
                }
            ]
            if key == "ALICE":
                accounts.extend(
                    [
                        {
                            "id": 11,
                            "externalId": "AGENT-ALICE-CARD-1",
                            "depositType": {"id": 100},
                            "status": {"active": True},
                        },
                        {
                            "id": 15,
                            "externalId": "AGENT-ALICE-ANALYSIS-SAV",
                            "depositType": {"id": 100},
                            "status": {"active": True},
                        },
                        {
                            "id": 12,
                            "externalId": self.dynamic_external_id,
                            "depositType": {"id": 100},
                            "status": {"active": True},
                        },
                        {
                            "id": 13,
                            "externalId": "BANK-CARD-00000000-0000-4000-8000-000000000002",
                            "depositType": {"id": 100},
                            "status": {"active": False, "closed": True},
                        },
                    ]
                )
                if self.duplicate_analysis_account:
                    accounts.append({
                        "id": 16,
                        "externalId": "AGENT-ALICE-ANALYSIS-SAV",
                        "depositType": {"id": 100},
                        "status": {"active": True},
                    })
                if self.unknown_account:
                    accounts.append(
                        {
                            "id": 14,
                            "externalId": "UNRELATED-SAVINGS",
                            "depositType": {"id": 100},
                            "status": {"active": True},
                        }
                    )
            return {
                "savingsAccounts": accounts
            }
        if path == "/accounttransfers":
            return {
                "pageItems": [
                    {
                        "id": 9,
                        "reversed": False,
                        "transferDate": "2026-10-14",
                        "fromAccount": {"id": 1},
                        "toAccount": {"id": 999 if self.cross_boundary else 2},
                    }
                ],
                "totalFilteredRecords": 1,
            }
        if path.endswith("/transactions/search"):
            account_id = int(path.split("/")[2])
            content = []
            if account_id == 1:
                content = [
                    {
                        "id": 10,
                        "date": [2026, 10, 14],
                        "reversed": False,
                        "transactionType": {"withdrawal": True},
                        "transfer": {"id": 9},
                    },
                    {
                        "id": 8,
                        "date": [2026, 10, 13],
                        "reversed": False,
                        "transactionType": {"deposit": True},
                    },
                ]
            content = [
                row
                for row in content
                if row["id"] not in self.reversed_transactions
            ]
            return {"content": content, "total": len(content)}
        if path.startswith("/savingsaccounts/"):
            account_id = int(path.split("/")[2])
            return {
                "summary": {"availableBalance": "0"},
                "status": {
                    "active": account_id not in self.closed_accounts,
                    "closed": account_id in self.closed_accounts,
                },
            }
        raise AssertionError(path)

    def post(self, path, **kwargs):
        self.posts.append((path, kwargs.get("params", {}).get("command")))
        if path == "/accounttransfers/9":
            self.reversed_transactions.add(10)
            return {}
        if "/transactions/" in path:
            self.reversed_transactions.add(int(path.rsplit("/", 1)[-1]))
            return {}
        if kwargs.get("params", {}).get("command") == "close":
            self.closed_accounts.add(int(path.rsplit("/", 1)[-1]))
            return {}
        raise AssertionError((path, kwargs))


def test_reset_plan_is_exact_and_rejects_cross_boundary_transfers():
    core = ResetPlanCore()
    resetter = FineractDemoResetter(core)
    plan = resetter.build_plan()
    assert [row["id"] for row in plan.transfers] == [9]
    assert [row["id"] for row in plan.direct_transactions[1]] == [8]
    assert plan.transaction_count == 1
    assert {account.account_id for account in plan.accounts} == {
        1,
        2,
        3,
        4,
        15,
        11,
        12,
        50,
        51,
        52,
    }
    assert [
        account.account_id
        for account in plan.accounts
        if account.close_after_reset
    ] == [12]
    assert [(row.account_id, row.role, row.close_after_reset) for row in plan.accounts if row.account_id == 15] == [
        (15, "analysis", False)
    ]
    resetter.execute(plan)
    assert ("/savingsaccounts/12", "close") in core.posts
    assert ("/savingsaccounts/11", "close") not in core.posts

    with pytest.raises(ResetRefused, match="跨出演示账户边界"):
        FineractDemoResetter(ResetPlanCore(cross_boundary=True)).build_plan()
    with pytest.raises(ResetRefused, match="未知储蓄账户"):
        FineractDemoResetter(ResetPlanCore(unknown_account=True)).build_plan()
    with pytest.raises(ResetRefused, match="分析副账户.*重复"):
        FineractDemoResetter(ResetPlanCore(duplicate_analysis_account=True)).build_plan()


def test_primary_account_selection_is_external_id_based():
    selected = primary_savings_account(
        [
            {
                "id": 88,
                "externalId": "AGENT-ALICE-CARD-1",
                "depositType": {"id": 100},
                "status": {"active": True},
            },
            {
                "id": 1,
                "externalId": "AGENT-ALICE-SAV",
                "depositType": {"id": 100},
                "status": {"active": True},
            },
        ],
        "Alice",
    )
    assert selected["id"] == 1


def test_seed_history_carries_structured_subscription_merchants():
    start = date(2026, 1, 1)
    first = build_random_history(
        spec=CLIENTS[0], start=start, days=200, seed=410,
        opening_balance=Decimal("10000.00"), include_salary=True,
    )
    replay = build_random_history(
        spec=CLIENTS[0], start=start, days=200, seed=410,
        opening_balance=Decimal("10000.00"), include_salary=True,
    )
    changed = build_random_history(
        spec=CLIENTS[0], start=start, days=200, seed=411,
        opening_balance=Decimal("10000.00"), include_salary=True,
    )
    assert first == replay
    assert first.rows != changed.rows
    assert all(isinstance(row[2], Decimal) for row in first.rows)
    assert {row[1] for row in first.rows} <= {"deposit", "withdrawal"}
    balance = Decimal("0")
    for _, kind, amount, _, _ in first.rows:
        balance += amount if kind == "deposit" else -amount
        assert balance >= Decimal("500.00")
    category_by_merchant = merchant_category_map()
    for _, kind, _, _, note in first.rows:
        if kind == "withdrawal":
            assert note.startswith("[Merchant] ")
            assert note.removeprefix("[Merchant] ") in category_by_merchant
    notes = [row[4] for row in first.rows]
    for merchant in MONTHLY_SUBSCRIPTION_MERCHANTS:
        assert notes.count(f"[Merchant] {merchant}") >= 3
        charges = [row[0] for row in first.rows if row[4] == f"[Merchant] {merchant}"]
        assert all(25 <= (right - left).days <= 35 for left, right in zip(charges, charges[1:]))
    assert len(CATEGORY_MERCHANTS) == 8

    unallocated = build_random_history(
        spec=CLIENTS[0], start=start, days=200, seed=410,
        opening_balance=Decimal("10000.00"), include_salary=True,
        apply_balance_guard=False,
    )
    main, analysis = split_history_for_analysis_account(
        unallocated, start=start, seed=410,
    )
    assert (main, analysis) == split_history_for_analysis_account(
        unallocated, start=start, seed=410,
    )
    assert any(row[1] == "withdrawal" for row in main.rows)
    assert any(row[1] == "withdrawal" for row in analysis.rows)
    assert all(isinstance(row[2], Decimal) for row in main.rows + analysis.rows)
    for merchant in MONTHLY_SUBSCRIPTION_MERCHANTS:
        charge_dates = sorted(row[0] for row in main.rows + analysis.rows
                              if row[4] == f"[Merchant] {merchant}")
        assert len(charge_dates) >= 3
        assert all(25 <= (right - left).days <= 35
                   for left, right in zip(charge_dates, charge_dates[1:]))


def test_generated_categories_drive_transaction_and_billing_services(bank):
    day = date(2026, 10, 20)
    bank["core"].tx[1] = [
        {
            "id": 1, "accountId": 1, "date": [day.year, day.month, day.day],
            "amount": "25.00", "currency": {"code": "CNY"}, "entryType": "DEBIT",
            "transactionType": {"withdrawal": True, "code": "withdrawal"},
            "note": "[Merchant] 江南小馆",
        },
        {
            "id": 2, "accountId": 1, "date": [day.year, day.month, day.day],
            "amount": "18.00", "currency": {"code": "CNY"}, "entryType": "DEBIT",
            "transactionType": {"withdrawal": True, "code": "withdrawal"},
            "note": "[Merchant] 腾讯视频会员",
        },
    ]
    with bank["db"]() as db:
        alice = db.scalar(select(User).where(User.username == "alice"))
        initialize_billing_categories(db, alice)
        categories = {row.name: row.id for row in db.scalars(select(Category).where(Category.user_id == alice.id))}
        db.add(Annotation(user_id=alice.id, account_id=1, transaction_id=1,
            merchant="手工备注商户", category_id=categories["购物"]))
        db.commit()

        service = TransactionService(db, bank["core"], bank["settings"])
        first_page = service.list(alice, 1, page=0, page_size=1, from_date=day, to_date=day)
        second_page = service.list(alice, 1, page=1, page_size=1, from_date=day, to_date=day)
        assert first_page["total"] == second_page["total"] == 2
        assert first_page["items"][0]["merchant"] == "手工备注商户"
        assert first_page["items"][0]["category"] == "购物"
        assert second_page["items"][0]["merchant"] == "腾讯视频会员"
        assert second_page["items"][0]["category"] == "娱乐"
        assert service.detail(alice, 1, 2)["amount"] == "18.00"

        summary = BillingService(db, bank["core"], bank["settings"]).statistics(alice, 1, day, day)
        assert summary["categories"] == {"购物": "25.00", "娱乐": "18.00"}


def test_generated_history_respects_alice_analysis_account_ownership(bank):
    start = date(2026, 5, 1)
    primary = build_random_history(spec=CLIENTS[0], start=start, days=30, seed=610,
        opening_balance=Decimal("10000.00"), include_salary=True)
    analysis_spec = ClientSpec("ALICE-ANALYSIS", "Alice", "Chen", "13800000001", 5_000.00, 0.00)
    analysis = build_random_history(spec=analysis_spec, start=start, days=30, seed=611,
        opening_balance=Decimal("5000.00"), include_salary=False)

    def core_rows(plan, account_id, first_id):
        output = []
        for index, (day, kind, amount, _, note) in enumerate(plan.rows):
            output.append({
                "id": first_id + index, "accountId": account_id,
                "date": [day.year, day.month, day.day], "amount": str(amount),
                "currency": {"code": "CNY"}, "entryType": "CREDIT" if kind == "deposit" else "DEBIT",
                "transactionType": {kind: True, "code": kind}, "note": note,
            })
        return output

    bank["core"].owners[4] = 1
    bank["core"].balances[4] = Decimal("1000.00")
    bank["core"].account_external_ids[4] = "AGENT-ALICE-ANALYSIS-SAV"
    bank["core"].tx[1] = core_rows(primary, 1, 1000)
    bank["core"].tx[4] = core_rows(analysis, 4, 2000)
    with bank["db"]() as db:
        alice, bob = db.get(User, bank["ids"][0]), db.get(User, bank["ids"][1])
        initialize_billing_categories(db, alice)
        initialize_billing_categories(db, bob)
        db.commit()
        billing = BillingService(db, bank["core"], bank["settings"])
        primary_stats = billing.statistics(alice, 1, start, start + timedelta(days=29))
        all_stats = billing.statistics(alice, None, start, start + timedelta(days=29))
        bob_stats = billing.statistics(bob, None, start, start + timedelta(days=29))
        assert primary_stats["account_ids"] == [1]
        assert all_stats["account_ids"] == [1, 4]
        assert bob_stats["account_ids"] == [2]
        for category, amount in primary_stats["categories"].items():
            assert Decimal(all_stats["categories"][category]) >= Decimal(amount)
        assert sum(map(Decimal, all_stats["categories"].values())) > sum(map(Decimal, primary_stats["categories"].values()))


def test_seed_helper_has_random_default_and_shared_subscription_catalog(monkeypatch):
    seeds = iter((501, 502))
    monkeypatch.setattr("scripts.fineract.seed_fineract.secrets.randbits", lambda _: next(seeds))
    first = build_history(CLIENTS[0], date(2026, 1, 1), 200)
    second = build_history(CLIENTS[0], date(2026, 1, 1), 200)
    assert first != second
    assert set(MONTHLY_SUBSCRIPTION_MERCHANTS) <= set(merchant_category_map())


def test_generation_manifest_records_replay_scope_and_counts(tmp_path, monkeypatch):
    import scripts.fineract.seed_fineract as seed_fineract
    target = tmp_path / "demo-history-manifest.json"
    monkeypatch.setattr(seed_fineract, "MANIFEST_FILE", target)
    seed_fineract.write_manifest(77, date(2026, 10, 23), {
        "ALICE": {"account_id": 1, "existing": 0, "planned": 20, "created": 18,
                  "skipped_insufficient_funds": 2},
        "ALICE-ANALYSIS": {"account_id": 15, "existing": 0, "planned": 10, "created": 10,
                            "skipped_insufficient_funds": 0},
    })
    manifest = json.loads(target.read_text(encoding="utf-8"))
    assert manifest["seed"] == 77 and manifest["as_of"] == "2026-10-23"
    assert manifest["accounts"]["ALICE-ANALYSIS"]["role"] == "analysis"
    assert manifest["accounts"]["ALICE"]["transactions"] == {
        "existing": 0, "planned": 20, "created": 18, "skipped_insufficient_funds": 2,
    }
    assert len(manifest["categories"]) == 8


def test_demo_subscription_fixture_is_idempotent_and_preserves_user_status(bank, monkeypatch):
    from types import SimpleNamespace
    import scripts.development.init_banking as init_banking
    from core.security import fingerprint
    from services.subscription_service import normalized_merchant

    settings = SimpleNamespace(environment="development")
    with bank["db"]() as db:
        db.add(User(username="mom", password_hash="fixture", client_id=4, tenant="default"))
        alice = db.scalar(select(User).where(User.username == "alice"))
        preserved_name = MONTHLY_SUBSCRIPTION_MERCHANTS[0]
        merchant = Merchant(
            external_key=f"subscription:{fingerprint(normalized_merchant(preserved_name))}",
            name=preserved_name, category="娱乐", adapter_type="demo_subscription",
        )
        db.add(merchant)
        db.flush()
        preserved = Subscription(user_id=alice.id, merchant_id=merchant.id,
            status="IGNORED", cadence="MONTHLY", expected_amount=Decimal("25.00"),
            evidence={"user_choice": True})
        db.add(preserved)
        db.commit()

    candidates = []
    for index, name in enumerate(MONTHLY_SUBSCRIPTION_MERCHANTS):
        amounts = (Decimal("25.00"), Decimal("15.00"), Decimal("21.00"))
        amount = amounts[index]
        occurrences = [
            {"merchant": name, "account_id": 1, "transaction_id": 500 + index * 3 + offset,
             "occurred_on": date(2026, 7, 1) + timedelta(days=30 * offset), "amount": amount}
            for offset in range(3)
        ]
        candidates.append({
            "merchant": name, "cadence": "MONTHLY", "expected_amount": amount,
            "next_charge_at": occurrences[-1]["occurred_on"] + timedelta(days=30),
            "rows": occurrences,
            "evidence": {"rule_version": "subscription-v1", "cadence": "MONTHLY",
                "observed_gaps_days": [30, 30], "occurrences": []},
        })

    class FixtureCore:
        closed = False

        def request(self, method, path, *, params=None, payload=None, key=None):
            assert method == "GET"
            if path.startswith("/clients/"):
                client_id = int(path.split("/")[2])
                return {"savingsAccounts": [{"id": client_id, "externalId": f"AGENT-{('ALICE','BOB','CHARLIE','MOM')[client_id-1]}-SAV", "depositType": {"id": 100}, "status": {"active": True}}]}
            if path.endswith("/transactions/search"):
                return {"total": 1, "content": [{"id": 1}]}
            raise AssertionError(path)

        def close(self):
            self.closed = True

    monkeypatch.setattr(init_banking, "get_settings", lambda: settings)
    monkeypatch.setattr(init_banking, "FineractClient", lambda _: FixtureCore())
    monkeypatch.setattr(init_banking, "session_factory", lambda: bank["db"])
    monkeypatch.setattr(init_banking.SubscriptionService, "_candidates", lambda _self, _user: candidates)

    first = init_banking.initialize_demo_subscription_fixtures()
    second = init_banking.initialize_demo_subscription_fixtures()
    assert first["verified"] == list(MONTHLY_SUBSCRIPTION_MERCHANTS[1:])
    assert first["preserved"] == [{"merchant": preserved_name, "status": "IGNORED"}]
    assert second == first
    with bank["db"]() as db:
        rows = list(db.scalars(select(Subscription).order_by(Subscription.id)))
        ignored = next(row for row in rows if row.status == "IGNORED")
        assert ignored.evidence == {"user_choice": True}
        verified = [row for row in rows if row.status == "VERIFIED"]
        assert len(verified) == 2
        assert all(row.evidence["demo_fixture"]["source"] == "generated_history" for row in verified)
        for row in verified:
            latest_charge = max(item.occurred_on for item in db.scalars(
                select(SubscriptionOccurrence).where(SubscriptionOccurrence.subscription_id == row.id)
            ))
            assert row.verified_at.astimezone(SHANGHAI).date() > latest_charge, (row.verified_at, latest_charge)
        events = list(db.scalars(select(Audit).where(Audit.event == "DEMO_SUBSCRIPTION_FIXTURE_VERIFIED")))
        assert len(events) == 2
        assert all(event.data["source"] == "generated_history" for event in events)


def test_demo_card_baseline_is_idempotent_and_encrypted(bank):
    core = bank["core"]
    for account_id, external_id in (
        (11, "AGENT-ALICE-CARD-1"),
        (12, "AGENT-ALICE-CARD-2"),
    ):
        core.owners[account_id] = 1
        core.balances[account_id] = Decimal("0")
        core.account_statuses[account_id] = "active"
        core.account_external_ids[account_id] = external_id

    with bank["db"]() as db:
        alice = db.scalar(select(User).where(User.username == "alice"))
        mappings = {"Alice": (alice, 1, "13800000001")}
        assert ensure_demo_cards(
            db, mappings, core, bank["settings"]
        ) == 2
        db.commit()
        cards = list(
            db.scalars(
                select(BankCard)
                .where(BankCard.user_id == alice.id)
                .order_by(BankCard.fineract_account_id)
            )
        )
        assert [card.fineract_account_id for card in cards] == [11, 12]
        assert all(card.status == "ACTIVE" for card in cards)
        assert all(card.pan_ciphertext.startswith("v1.") for card in cards)
        assert all(card.last4 not in card.pan_ciphertext for card in cards)
        assert ensure_demo_cards(
            db, mappings, core, bank["settings"]
        ) == 0
        assert db.scalar(
            select(func.count()).select_from(BankCard).where(
                BankCard.user_id == alice.id
            )
        ) == 2


def test_demo_reset_preserves_users_passwords_and_unrelated_rows(bank):
    identities = {
        key.upper(): identity(key, index, index)
        for index, key in enumerate(("alice", "bob", "charlie", "mom"), 1)
    }
    with bank["db"]() as db:
        mom = User(
            username="mom",
            password_hash=password_hasher.hash("mom-password-123"),
            client_id=4,
            tenant="default",
        )
        outsider = User(
            username="outsider",
            password_hash=password_hasher.hash("outsider-password-123"),
            client_id=99,
            tenant="default",
        )
        db.add_all([mom, outsider])
        db.flush()
        alice = db.scalar(select(User).where(User.username == "alice"))
        before = {
            user.username: user.password_hash
            for user in db.scalars(
                select(User).where(User.username.in_(["alice", "bob", "charlie", "mom"]))
            )
        }

        agent_conversation = AgentConversation(
            user_id=alice.id,
            title="reset conversation",
            expires_at=now() + timedelta(days=30),
        )
        db.add(agent_conversation)
        db.flush()
        agent_message = AgentMessage(
            conversation_id=agent_conversation.id,
            role="user",
            content="reset me",
            sequence=1,
        )
        db.add(agent_message)
        db.flush()
        agent_run = AgentRun(
            conversation_id=agent_conversation.id,
            user_id=alice.id,
            user_message_id=agent_message.id,
            trace_id="reset-agent-trace",
            idempotency_key="reset-agent-run",
            request_hash="f" * 64,
            request={"message": "reset me"},
        )
        db.add(agent_run)
        db.flush()
        db.add_all(
            [
                AgentEvent(
                    conversation_id=agent_conversation.id,
                    run_id=agent_run.id,
                    trace_id=agent_run.trace_id,
                    type="EXECUTING",
                    data={},
                ),
                SecurityEvent(
                    user_id=alice.id,
                    conversation_id=agent_conversation.id,
                    run_id=agent_run.id,
                    trace_id=agent_run.trace_id,
                    kind="RESET_TEST",
                    outcome="RECORDED",
                    data={},
                ),
                SecurityLock(
                    user_id=alice.id,
                    scope="AGENT_WRITE",
                    reason="RESET_TEST",
                    failure_count=1,
                    window_started_at=now(),
                ),
            ]
        )

        action = Action(
            user_id=alice.id,
            kind="transfer",
            idempotency_key="reset-action",
            request_hash="0" * 64,
            payload={},
            amount=Decimal("1"),
        )
        db.add(action)
        db.flush()
        schedule = Schedule(
            user_id=alice.id,
            payload={},
            next_run=now(),
            authorization_action_id=action.id,
        )
        collection = AACollection(
            user_id=alice.id,
            account_id=1,
            title="demo",
            amount=Decimal("1"),
        )
        category = Category(user_id=alice.id, name="demo")
        merchant = Merchant(
            external_key="subscription:reset-demo",
            name="Reset Demo",
            category="演示",
            adapter_type="demo_subscription",
        )
        db.add_all([schedule, collection, category, merchant])
        db.flush()
        subscription = Subscription(
            user_id=alice.id,
            merchant_id=merchant.id,
            status="CANDIDATE",
            cadence="MONTHLY",
            expected_amount=Decimal("10"),
            evidence={},
            next_charge_at=now().date(),
            action_id=action.id,
        )
        db.add(subscription)
        db.flush()
        card = BankCard(
            user_id=alice.id,
            fineract_account_id=101,
            product_name="智汇借记卡",
            alias="reset",
            pan_ciphertext="encrypted-only",
            last4="1234",
            application_action_id=action.id,
        )
        db.add(card)
        db.flush()
        report = BillReport(user_id=alice.id, payload={})
        db.add(report)
        db.flush()
        db.add_all(
            [
                ScheduleRun(
                    schedule_id=schedule.id,
                    scheduled_at=now(),
                    status="CREATED",
                    action_id=action.id,
                ),
                AAShare(
                    collection_id=collection.id,
                    user_id=alice.id,
                    amount=Decimal("1"),
                    action_id=action.id,
                ),
                ClassificationRule(
                    user_id=alice.id,
                    category_id=category.id,
                    field="merchant",
                    contains="demo",
                ),
                Annotation(
                    user_id=alice.id,
                    account_id=1,
                    transaction_id=1,
                    category_id=category.id,
                ),
                DailyUsage(user_id=alice.id, day=now().date(), amount=Decimal("1")),
                BillReportJob(report_id=report.id, user_id=alice.id, idempotency_key="reset-report-0001",
                    request_hash="a" * 64, account_ids=[1], dependency_account_ids=[1], period="2025-09",
                    cutoff_date=date(2025, 9, 30), status="queued"),
                BillReportTransaction(report_id=report.id, account_id=1, transaction_id=99,
                    occurred_on=date(2025, 9, 1), direction="debit", category="餐饮", payload={}),
                AnomalyReview(user_id=alice.id, anomaly_key="demo", status="confirmed"),
                RiskAssessment(
                    user_id=alice.id,
                    answers=[1, 1, 1, 1, 1],
                    score=5,
                    level=1,
                    expires_at=now() + timedelta(minutes=15),
                ),
                Audit(user_id=alice.id, action_id=action.id, event="DEMO"),
                SubscriptionOccurrence(
                    subscription_id=subscription.id,
                    account_id=1,
                    transaction_id=1,
                    occurred_on=now().date(),
                    amount=Decimal("10"),
                ),
                CardAuthorization(
                    user_id=alice.id,
                    card_id=card.id,
                    merchant_id=merchant.id,
                    idempotency_key="reset-card-authorization",
                    amount=Decimal("10"),
                    channel="ONLINE",
                    status="APPROVED",
                    action_id=action.id,
                ),
                Recipient(
                    user_id=outsider.id,
                    name="keep",
                    account_id=999,
                ),
                ProductMetadata(
                    product_id=88,
                    tenant="default",
                    risk_level=1,
                    enabled=True,
                    allows_premature=False,
                ),
            ]
        )
        db.commit()

        counts = reset_application_state(db, identities)
        assert counts["recipients_recreated"] == 12
        assert {
            user.username: user.password_hash
            for user in db.scalars(
                select(User).where(User.username.in_(["alice", "bob", "charlie", "mom"]))
            )
        } == before
        assert db.get(ProductMetadata, 88) is not None
        assert db.scalar(
            select(func.count()).select_from(Recipient).where(Recipient.user_id == outsider.id)
        ) == 1

        demo_user_ids = [
            user.id
            for user in db.scalars(
                select(User).where(User.username.in_(["alice", "bob", "charlie", "mom"]))
            )
        ]
        for model in USER_SCOPED_MODELS:
            expected = 12 if model is Recipient else 0
            assert db.scalar(
                select(func.count()).select_from(model).where(model.user_id.in_(demo_user_ids))
            ) == expected
        assert db.scalar(select(func.count()).select_from(ScheduleRun)) == 0
        assert db.scalar(select(func.count()).select_from(BillReportTransaction)) == 0
        assert db.scalar(select(func.count()).select_from(AgentMessage)) == 0
        assert db.scalar(select(func.count()).select_from(AgentEvent)) == 0
