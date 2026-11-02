import os, sys
from datetime import date
from decimal import Decimal
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps/backend"))
from core.config import Settings
from core.security import password_hasher
from models import Base, Merchant, User
from main import create_app
from core.database import get_db
from fastapi.testclient import TestClient


class CoreBank:
    def __init__(self):
        self.balances = {
            1: Decimal("10000"),
            2: Decimal("5000"),
            3: Decimal("1000"),
            97: Decimal("0"),
            98: Decimal("0"),
            99: Decimal("0"),
        }
        self.owners = {1: 1, 2: 2, 3: 3, 97: 97, 98: 98, 99: 99}
        self.account_external_ids = {
            1: "AGENT-ALICE-SAV",
            2: "AGENT-BOB-SAV",
            3: "AGENT-CHARLIE-SAV",
            97: "AGENT-DEMO-CAKE-SAV",
            98: "AGENT-DEMO-FLOWER-SAV",
            99: "AGENT-DEMO-MERCHANT-SAV",
        }
        self.account_statuses = {1: "active", 2: "active", 3: "active"}
        self.transfers = {}
        self.keys = {}
        self.tx = {1: [], 2: [], 3: [], 97: [], 98: [], 99: []}
        self.holds = {}
        self.holdings = {}
        self.command_calls = []
        self.fail_transfer = False
        self.fail_hold_after_post = False
        self.fail_release_after_post = False
        self.fail_approve = False
        self.fail_savings_create_after_post = False

    def get_client(self, id):
        return {"id": id, "officeId": 1}

    def get_savings_account(self, id):
        state = self.account_statuses.get(id, "active")
        held = sum(
            row["amount"]
            for row in self.holds.values()
            if row["account_id"] == id and row["status"] == "HELD"
        )
        return {
            "id": id,
            "clientId": self.owners[id],
            "depositType": {"id": 100},
            "officeId": 1,
            "accountNo": str(id),
            "externalId": self.account_external_ids.get(id, f"TEST-{id}"),
            "savingsProductId": 2,
            "savingsProductName": "BANK_AGENT_SAVINGS",
            "currency": {"code": "CNY", "decimalPlaces": 2},
            "status": {
                "active": state == "active",
                "approved": state == "approved",
                "submittedAndPendingApproval": state == "submitted",
            },
            "summary": {
                "accountBalance": self.balances[id],
                "availableBalance": self.balances[id] - held,
                "totalSavingsAmountOnHold": held,
            },
        }

    def list_client_accounts(self, id):
        return {
            "savingsAccounts": [
                {
                    "id": account_id,
                    "depositType": {"id": 100},
                    "externalId": self.account_external_ids.get(account_id, f"TEST-{account_id}"),
                    "status": {"active": self.account_statuses.get(account_id, "active") == "active"},
                }
                for account_id, owner_id in self.owners.items()
                if owner_id == id
            ]
            + [
                {
                    "id": hid,
                    "depositType": {"id": 200},
                    "externalId": h.get("externalId"),
                }
                for hid, h in self.holdings.items()
                if h["clientId"] == id
            ]
        }

    def savings_products(self):
        return [
            {
                "id": 2,
                "name": "BANK_AGENT_SAVINGS",
                "currency": {"code": "CNY"},
            }
        ]

    def create_savings_account(self, p, key):
        from clients.fineract import FineractUnavailableError

        if key in self.keys:
            return self.keys[key]
        account_id = max(self.owners) + 1
        self.owners[account_id] = int(p["clientId"])
        self.balances[account_id] = Decimal("0")
        self.tx[account_id] = []
        self.account_external_ids[account_id] = p["externalId"]
        self.account_statuses[account_id] = "submitted"
        self.keys[key] = {"savingsId": account_id, "resourceId": account_id}
        self.command_calls.append(("create_savings", account_id))
        if self.fail_savings_create_after_post:
            raise FineractUnavailableError(503, "timeout after savings account create")
        return self.keys[key]

    def savings_account_command(self, account_id, command, p, key):
        if key in self.keys:
            return self.keys[key]
        if command == "approve":
            self.account_statuses[account_id] = "approved"
        elif command == "activate":
            self.account_statuses[account_id] = "active"
        self.keys[key] = {"resourceId": account_id}
        self.command_calls.append((command + "_savings", account_id))
        return self.keys[key]

    def create_transfer(self, p, key):
        from clients.fineract import FineractUnavailableError

        if key in self.keys:
            return self.keys[key]
        a, b = int(p["fromAccountId"]), int(p["toAccountId"])
        amount = Decimal(p["transferAmount"])
        self.balances[a] -= amount
        self.balances[b] += amount
        id = len(self.transfers) + 1
        result = {
            "id": id,
            "fromAccount": {"id": a},
            "toAccount": {"id": b},
            "transferAmount": amount,
            "fromSavingsTransaction": {"id": id * 2},
            "toSavingsTransaction": {"id": id * 2 + 1},
        }
        result["transferDescription"] = p["transferDescription"]
        result["transferDate"] = p["transferDate"]
        for account, direction in [(a, "DEBIT"), (b, "CREDIT")]:
            self.tx.setdefault(account, []).append(
                {
                    "id": id * 2 + (account == b),
                    "accountId": account,
                    "date": [int(v) for v in p["transferDate"].split("-")],
                    "amount": str(amount),
                    "currency": {"code": "CNY"},
                    "entryType": direction,
                    "transactionType": {
                        "withdrawal": direction == "DEBIT",
                        "deposit": direction == "CREDIT",
                    },
                    "transfer": {
                        "id": id,
                        "transferDescription": p["transferDescription"],
                    },
                }
            )
        self.transfers[id] = result
        self.keys[key] = {"resourceId": id}
        if self.fail_transfer:
            raise FineractUnavailableError(503, "timeout after posting")
        return self.keys[key]

    def get_transfer(self, id):
        return self.transfers[id]

    def get_transaction(self, a, id):
        return next(t for t in self.tx[a] if t["id"] == id)

    def hold_amount(self, account_id, amount, transaction_date, reason, key):
        from clients.fineract import FineractError, FineractUnavailableError

        if key in self.keys:
            return self.keys[key]
        value = Decimal(str(amount))
        available = Decimal(str(self.get_savings_account(account_id)["summary"]["availableBalance"]))
        if available < value:
            raise FineractError(400, "insufficient available balance")
        transaction_id = 10_000 + len(self.holds) * 2
        row = {
            "id": transaction_id,
            "accountId": account_id,
            "date": [int(part) for part in str(transaction_date).split("-")],
            "amount": str(value),
            "currency": {"code": "CNY"},
            "transactionType": {"amountOnHold": True},
            "reasonForBlock": reason,
            "releaseIdOfHoldAmountTransaction": None,
        }
        self.holds[transaction_id] = {
            "account_id": account_id,
            "amount": value,
            "status": "HELD",
            "release_id": None,
            "row": row,
        }
        self.tx.setdefault(account_id, []).append(row)
        self.keys[key] = {"resourceId": transaction_id}
        self.command_calls.append(("hold", transaction_id))
        if self.fail_hold_after_post:
            raise FineractUnavailableError(503, "timeout after hold")
        return self.keys[key]

    def release_amount(self, account_id, hold_transaction_id, transaction_date, key):
        from clients.fineract import FineractError, FineractUnavailableError

        if key in self.keys:
            return self.keys[key]
        hold = self.holds.get(hold_transaction_id)
        if not hold or hold["account_id"] != account_id:
            raise FineractError(404, "hold transaction missing")
        if hold["status"] != "HELD":
            raise FineractError(409, "hold already released")
        release_id = hold_transaction_id + 1
        hold["status"] = "RELEASED"
        hold["release_id"] = release_id
        hold["row"]["releaseIdOfHoldAmountTransaction"] = release_id
        self.tx.setdefault(account_id, []).append(
            {
                "id": release_id,
                "accountId": account_id,
                "date": [int(part) for part in str(transaction_date).split("-")],
                "amount": str(hold["amount"]),
                "currency": {"code": "CNY"},
                "transactionType": {"amountRelease": True},
            }
        )
        self.keys[key] = {"resourceId": release_id}
        self.command_calls.append(("release", release_id))
        if self.fail_release_after_post:
            raise FineractUnavailableError(503, "timeout after release")
        return self.keys[key]

    def search_transactions(self, a, page=0, page_size=100, **filters):
        rows = [
            t
            for t in self.tx[a]
            if (
                not filters.get("fromDate")
                or str(filters["fromDate"]) <= date(*t["date"]).isoformat()
            )
            and (
                not filters.get("toDate")
                or str(filters["toDate"]) >= date(*t["date"]).isoformat()
            )
        ]
        return {
            "items": rows[page * page_size : (page + 1) * page_size],
            "total": len(rows),
            "page": page,
            "page_size": page_size,
        }

    def fixed_products(self):
        return [{"id": 10}]

    def fixed_product(self, id):
        return {
            "id": id,
            "name": "Fixed Demo",
            "currency": {"code": "CNY"},
            "minDepositTerm": 1,
            "minDepositTermType": {"id": 2},
            "maxDepositTerm": 36,
            "maxDepositTermType": {"id": 2},
            "minDepositAmount": "1",
            "maxDepositAmount": "100000",
            "interestRateCharts": [
                {
                    "fromDate": [2020, 1, 1],
                    "chartSlabs": [
                        {
                            "periodType": {"id": 2},
                            "fromPeriod": 1,
                            "toPeriod": 36,
                            "annualInterestRate": "2.0",
                        }
                    ],
                }
            ],
        }

    def fixed_template(self, *a):
        return {}

    def fixed_account(self, id):
        return self.holdings[id]

    def fixed_closure_template(self, id):
        return {"maturityAmount": self.holdings[id]["depositAmount"]}

    def create_fixed(self, p, key):
        if key in self.keys:
            return self.keys[key]
        id = 100 + len(self.holdings)
        self.holdings[id] = {
            "id": id,
            "clientId": p["clientId"],
            "externalId": p.get("externalId"),
            "depositProductId": p["productId"],
            "currency": {"code": "CNY"},
            "depositAmount": p["depositAmount"],
            "linkAccountId": p["linkAccountId"],
            "status": {"submittedAndPendingApproval": True},
            "maturityDate": [2099, 1, 1],
            "nominalAnnualInterestRate": "2.0",
        }
        self.keys[key] = {"resourceId": id}
        self.command_calls.append(("create", id))
        return self.keys[key]

    def fixed_command(self, id, command, p, key):
        from clients.fineract import FineractUnavailableError

        self.command_calls.append((command, id))
        if command == "calculatePrematureAmount":
            return {"maturityAmount": self.holdings[id]["depositAmount"]}
        if key in self.keys:
            return self.keys[key]
        h = self.holdings[id]
        if command == "approve":
            if self.fail_approve:
                raise FineractUnavailableError(503, "failed approval")
            h["status"] = {"approved": True}
        elif command == "activate":
            self.balances[h["linkAccountId"]] -= Decimal(h["depositAmount"])
            h["status"] = {"active": True}
        else:
            self.balances[p["toSavingsAccountId"]] += Decimal(h["depositAmount"])
            h["status"] = {"closed": True}
        self.keys[key] = {"resourceId": id}
        return self.keys[key]


@pytest.fixture
def bank(monkeypatch):
    url = os.environ.get("BANK_TEST_DATABASE_URL", "sqlite://")
    if not url.startswith("sqlite:"):
        assert url.rsplit("/", 1)[-1].endswith("_test"), "Refuse non-test database"
    engine = create_engine(
        url,
        **(
            {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
            if url.startswith("sqlite:")
            else {}
        ),
    )
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    settings = Settings(
        _env_file=None,
        database_url=url,
        otp_secret="test-secret" * 8,
        dev_otp_inbox=True,
        card_encryption_key="a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=",
    )
    fakecore = CoreBank()
    import core.deps, api.context, api.accounts, api.transfers, api.auth, api.demo_cards, main

    for module in [core.deps, api.context, api.accounts, api.transfers]:
        monkeypatch.setattr(module, "get_fineract_client", lambda: fakecore)
    for module in [core.deps, api.context, api.accounts, api.auth, api.demo_cards, main]:
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    with factory() as db:
        users = []
        hashed = password_hasher.hash("test-password-123")
        for index, name in enumerate(["alice", "bob", "charlie"], 1):
            user = User(
                username=name, password_hash=hashed, client_id=index, tenant="default"
            )
            db.add(user)
            users.append(user)
        db.add(
            Merchant(
                external_key="demo-card:main",
                name="智汇 Demo 商城",
                category="购物",
                adapter_type="demo_card",
                fineract_account_id=99,
                active=True,
            )
        )
        db.add_all(
            [
                Merchant(
                    external_key="demo-orchestration:flower",
                    name="心意 Demo 花店",
                    category="礼物",
                    adapter_type="demo_orchestration",
                    fineract_account_id=98,
                    active=True,
                ),
                Merchant(
                    external_key="demo-orchestration:cake",
                    name="甜蜜 Demo 蛋糕店",
                    category="礼物",
                    adapter_type="demo_orchestration",
                    fineract_account_id=97,
                    active=True,
                ),
            ]
        )
        db.commit()
        user_ids = [u.id for u in users]
    app = create_app()

    def database():
        with factory() as db:
            try:
                yield db
            finally:
                db.rollback()

    app.dependency_overrides[get_db] = database
    with TestClient(app) as http:
        headers = {}
        for name in ["alice", "bob", "charlie"]:
            r = http.post(
                "/api/auth/login",
                json={"username": name, "password": "test-password-123"},
            )
            assert r.status_code == 200, r.text
            headers[name] = {"Authorization": "Bearer " + r.json()["access_token"]}
        yield {
            "http": http,
            "core": fakecore,
            "db": factory,
            "settings": settings,
            "headers": headers,
            "ids": user_ids,
            "engine": engine,
        }
    Base.metadata.drop_all(engine)
    engine.dispose()
