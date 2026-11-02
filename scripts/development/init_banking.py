"""Provision ONLY the independent application database, migrate and map demo users.
Run with apps/backend/.venv/bin/python scripts/development/init_banking.py.
Passwords must be supplied via environment or root .env. No default login passwords.
"""

import argparse
import os
import sys
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/backend"))
sys.path.insert(0, str(ROOT / "scripts/fineract"))
from dotenv import dotenv_values
from sqlalchemy import select
from sqlalchemy.engine import make_url
from psycopg import connect, sql
from alembic import command
from alembic.config import Config
from core.config import get_settings
from core.database import session_factory
from core.card_crypto import encrypt_pan, validate_card_key
from core.security import fingerprint, now, password_hasher
from core.errors import require
from clients.fineract import FineractClient
from models import Action, BankCard, Merchant, ProductMetadata, User, Recipient, uid, Category, ClassificationRule, Subscription, SubscriptionOccurrence
from seed_fineract import CLIENTS, DEMO_CARD_ACCOUNTS, DEMO_ORCHESTRATION_MERCHANTS, FIXED_DEPOSIT_PRODUCTS
from demo_history import CATEGORY_MERCHANTS, MONTHLY_SUBSCRIPTION_MERCHANTS, merchant_category_map
from services.card_service import new_demo_pan
from services.common import audit
from services.subscription_service import SubscriptionService, normalized_merchant


def ensure_local_no_proxy():
    """Keep local PostgreSQL/Fineract traffic out of workstation proxies."""
    for key in ("NO_PROXY", "no_proxy"):
        values = [item.strip() for item in os.environ.get(key, "").split(",") if item.strip()]
        for local in ("localhost", "127.0.0.1", "::1"):
            if local not in values:
                values.append(local)
        os.environ[key] = ",".join(values)


def primary_savings_account(accounts, name):
    """Select the stable demo primary account, never the first account."""
    external_id = f"AGENT-{name.upper()}-SAV"
    matches = [
        account
        for account in accounts
        if account.get("externalId") == external_id
        and (account.get("depositType") or {}).get("id") == 100
        and (account.get("status") or {}).get("active")
    ]
    require(
        len(matches) == 1,
        "DEMO_ACCOUNT_MISSING",
        f"{name} 必须恰有一个 ACTIVE 主账户 {external_id}",
    )
    return matches[0]


def exact_active_savings_account(accounts, external_id):
    matches = [
        account
        for account in accounts
        if account.get("externalId") == external_id
        and (account.get("depositType") or {}).get("id") == 100
        and (account.get("status") or {}).get("active")
    ]
    require(
        len(matches) == 1,
        "DEMO_ACCOUNT_MISSING",
        f"必须恰有一个 ACTIVE 账户 {external_id}",
    )
    return matches[0]


def ensure_demo_cards(db, mappings, client, settings):
    """Create the fixed competition baseline cards without duplicating them."""
    missing = []
    for name, (user, _, _) in mappings.items():
        accounts = client.list_client_accounts(user.client_id).get(
            "savingsAccounts", []
        )
        for external_id, alias in DEMO_CARD_ACCOUNTS[name.upper()]:
            account = exact_active_savings_account(accounts, external_id)
            existing = db.scalar(
                select(BankCard).where(
                    BankCard.user_id == user.id,
                    BankCard.fineract_account_id == int(account["id"]),
                )
            )
            if existing is None:
                missing.append((user, int(account["id"]), external_id, alias))

    if not missing:
        return 0
    validate_card_key(settings.card_encryption_key)
    created = 0
    timestamp = now()
    for user, account_id, external_id, alias in missing:
        request = {
            "product_name": "智汇借记卡",
            "alias": alias,
            "baseline_external_id": external_id,
        }
        key = f"demo-bootstrap:{external_id}"
        action = db.scalar(
            select(Action).where(
                Action.user_id == user.id,
                Action.kind == "card_application",
                Action.idempotency_key == key,
            )
        )
        if action is None:
            action = Action(
                user_id=user.id,
                kind="card_application",
                idempotency_key=key,
                request_hash=fingerprint(request),
                payload={**request, "_request": request, "bootstrap": True},
                status="SUCCEEDED",
                amount=Decimal("0"),
                confirmed_at=timestamp,
                executed_at=timestamp,
                result={},
                steps={"core_account_id": account_id, "bootstrap": True},
            )
            db.add(action)
            db.flush()
        card_id = uid()
        pan = new_demo_pan()
        card = BankCard(
            id=card_id,
            user_id=user.id,
            fineract_account_id=account_id,
            product_name="智汇借记卡",
            alias=alias,
            pan_ciphertext=encrypt_pan(
                settings.card_encryption_key, card_id, pan
            ),
            last4=pan[-4:],
            status="ACTIVE",
            application_action_id=action.id,
        )
        db.add(card)
        db.flush()
        action.result = {
            "card_id": card.id,
            "account_id": account_id,
            "status": card.status,
            "bootstrap": True,
        }
        audit(
            db,
            user,
            "DEMO_CARD_BOOTSTRAPPED",
            action,
            card_id=card.id,
            account_id=account_id,
            external_id=external_id,
        )
        created += 1
    return created


def provision():
    settings = get_settings()
    url = make_url(settings.database_url)
    require(
        url.database == "bank_agent" and url.username == "bank_agent",
        "DATABASE_CONFIG",
        "初始化只支持独立 bank_agent 账号和数据库",
    )
    require(url.password, "DATABASE_CONFIG", "DATABASE_URL 必须提供独立账号密码")
    admin = os.environ.get("POSTGRES_ADMIN_PASSWORD") or dotenv_values(
        ROOT / ".env"
    ).get("POSTGRES_ADMIN_PASSWORD")
    require(admin, "DATABASE_CONFIG", "需要 POSTGRES_ADMIN_PASSWORD")
    with connect(
        host=url.host,
        port=url.port or 5432,
        dbname="postgres",
        user="postgres",
        password=admin,
        autocommit=True,
    ) as db:
        with db.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", ("bank_agent",))
            if not cur.fetchone():
                cur.execute(
                    sql.SQL("CREATE ROLE bank_agent LOGIN PASSWORD {}").format(
                        sql.Literal(url.password)
                    )
                )
            cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", ("bank_agent",))
            if not cur.fetchone():
                cur.execute("CREATE DATABASE bank_agent OWNER bank_agent")
    command.upgrade(Config(str(ROOT / "apps/backend/alembic.ini")), "head")


def initialize_billing_categories(db, user):
    """Idempotently install the demo category vocabulary and merchant rules."""
    categories = {}
    for name in CATEGORY_MERCHANTS:
        row = db.scalar(select(Category).where(Category.user_id == user.id, Category.name == name))
        if row is None:
            row = Category(user_id=user.id, name=name)
            db.add(row)
            db.flush()
        categories[name] = row
    for merchant, category_name in merchant_category_map().items():
        exists = db.scalar(select(ClassificationRule).where(
            ClassificationRule.user_id == user.id,
            ClassificationRule.field == "merchant",
            ClassificationRule.contains == merchant,
        ))
        if exists is None:
            db.add(ClassificationRule(user_id=user.id, category_id=categories[category_name].id,
                field="merchant", contains=merchant, priority=100))
        elif exists.category_id != categories[category_name].id or exists.priority != 100:
            exists.category_id = categories[category_name].id
            exists.priority = 100


def initialize_fixed_product_metadata(db, client, tenant):
    """Map the two stable Fineract Demo products to deterministic suitability rules."""
    products = client.fixed_products()
    mapped = {}
    for spec in FIXED_DEPOSIT_PRODUCTS:
        matches = [row for row in products if row.get("name") == spec["name"]]
        require(
            len(matches) == 1,
            "DEMO_FIXED_PRODUCT_MISSING",
            f"请先运行 --wealth-products-only；未找到 {spec['name']}",
        )
        product_id = int(matches[0]["id"])
        row = db.get(ProductMetadata, product_id)
        require(
            row is None or row.tenant == tenant,
            "PRODUCT_METADATA_CONFLICT",
            f"定存产品 {product_id} 已映射到其他租户",
        )
        row = row or ProductMetadata(product_id=product_id, tenant=tenant)
        row.risk_level = int(spec["risk_level"])
        row.enabled = True
        row.allows_premature = bool(spec["allows_premature"])
        db.add(row)
        mapped[spec["name"]] = product_id
    return mapped


def initialize_demo_subscription_fixtures():
    """Install generated monthly subscription examples without changing user choices."""
    settings = get_settings()
    require(settings.environment == "development", "DEMO_FIXTURE_ENV", "演示账单夹具只允许 development 环境")
    fineract = FineractClient(settings)
    try:
        with session_factory()() as db:
            usernames = [spec.key.lower() for spec in CLIENTS]
            users = list(db.scalars(select(User).where(User.username.in_(usernames))))
            by_username = {user.username: user for user in users}
            require(len(by_username) == len(CLIENTS), "DEMO_USERS_MISSING", "需要先初始化四名演示用户")
            for username in usernames:
                user = by_username[username]
                require(user.active and user.client_id, "DEMO_USER_MAPPING", f"演示用户 {username} 未启用或缺少核心映射")
                accounts = (
                    fineract.request("GET", f"/clients/{user.client_id}/accounts")
                    or {}
                ).get("savingsAccounts", [])
                external_id = f"AGENT-{username.upper()}-SAV"
                matches = [
                    row for row in accounts
                    if row.get("externalId") == external_id
                    and (row.get("depositType") or {}).get("id") == 100
                    and (row.get("status") or {}).get("active")
                ]
                require(len(matches) == 1, "DEMO_ACCOUNT_MISSING", f"未找到唯一 ACTIVE 核心账户 {external_id}")
                account_id = int(matches[0]["id"])
                page = fineract.request(
                    "GET",
                    f"/savingsaccounts/{account_id}/transactions/search",
                    params={"offset": 0, "limit": 1},
                ) or {}
                require(int(page.get("total", 0)) > 0 and page.get("content"), "DEMO_HISTORY_MISSING", f"核心账户 {external_id} 没有实际流水")

            user = by_username["alice"]
            service = SubscriptionService(db, fineract, settings)
            candidates = {
                row["merchant"]: row
                for row in service._candidates(user)
                if row["cadence"] == "MONTHLY" and row["merchant"] in MONTHLY_SUBSCRIPTION_MERCHANTS
            }
            verified, preserved = [], []
            for merchant in MONTHLY_SUBSCRIPTION_MERCHANTS:
                merchant_key = f"subscription:{fingerprint(normalized_merchant(merchant))}"
                merchant_row = db.scalar(select(Merchant).where(Merchant.external_key == merchant_key))
                row = None
                if merchant_row:
                    row = db.scalar(select(Subscription).where(
                        Subscription.user_id == user.id,
                        Subscription.merchant_id == merchant_row.id,
                        Subscription.cadence == "MONTHLY",
                    ))
                is_fixture = bool((row.evidence or {}).get("demo_fixture", {}).get("source") == "generated_history") if row else False
                if row and row.status == "VERIFIED" and is_fixture:
                    verified.append(merchant)
                    continue
                if row and row.status in {"VERIFIED", "IGNORED", "CANCELLED"}:
                    preserved.append({"merchant": merchant, "status": row.status})
                    continue
                candidate = candidates.get(merchant)
                require(candidate is not None, "DEMO_SUBSCRIPTION_MISSING", f"未找到稳定的生成月度样本：{merchant}")
                candidate_rows = candidate["rows"]
                require(len(candidate_rows) >= 3, "DEMO_SUBSCRIPTION_EVIDENCE", f"{merchant} 不足三笔扣费证据")
                last = candidate_rows[-3:]
                gaps = [(b["occurred_on"] - a["occurred_on"]).days for a, b in zip(last, last[1:])]
                mean = sum((item["amount"] for item in last), Decimal("0")) / 3
                stable = mean > 0 and all(25 <= gap <= 35 for gap in gaps) and all(abs(item["amount"] - mean) <= mean * Decimal("0.10") for item in last)
                require(stable, "DEMO_SUBSCRIPTION_EVIDENCE", f"{merchant} 最近三笔扣费不构成稳定月度样本")
                verified_at = datetime.combine(last[-1]["occurred_on"] + timedelta(days=1), time.min, ZoneInfo("Asia/Shanghai"))
                merchant_record, normalized = service._merchant(merchant)
                row = row or Subscription(user_id=user.id, merchant_id=merchant_record.id)
                row.merchant_id = merchant_record.id
                row.status = "VERIFIED"
                row.cadence = candidate["cadence"]
                row.expected_amount = candidate["expected_amount"]
                row.amount_tolerance = Decimal("0.10")
                row.next_charge_at = candidate["next_charge_at"]
                row.verified_at = verified_at
                row.ignored_at = None
                row.evidence = {
                    **candidate["evidence"],
                    "merchant_normalized": normalized,
                    "demo_fixture": {
                        "source": "generated_history",
                        "verified_at": verified_at.isoformat(),
                        "evidence_transaction_ids": [item["transaction_id"] for item in last],
                    },
                }
                row.rule_version = "subscription-v1"
                db.add(row)
                db.flush()
                existing = {
                    (item.account_id, item.transaction_id)
                    for item in db.scalars(select(SubscriptionOccurrence).where(SubscriptionOccurrence.subscription_id == row.id))
                }
                for item in candidate_rows:
                    identity = (item["account_id"], item["transaction_id"])
                    if identity not in existing:
                        db.add(SubscriptionOccurrence(subscription_id=row.id, account_id=item["account_id"],
                            transaction_id=item["transaction_id"], occurred_on=item["occurred_on"], amount=item["amount"]))
                audit(db, user, "DEMO_SUBSCRIPTION_FIXTURE_VERIFIED", subscription_id=row.id,
                    source="generated_history", verified_at=verified_at.isoformat(),
                    evidence_transaction_ids=[item["transaction_id"] for item in last])
                verified.append(merchant)
            db.commit()
    finally:
        fineract.close()
    return {"verified": verified, "preserved": preserved}


def initialize_users(*, demo_billing_fixtures=False):
    settings = get_settings()
    require(
        len(settings.demo_password) >= 12, "PASSWORD_CONFIG", "DEMO_PASSWORD 至少12字符"
    )
    require(
        not settings.admin_password or len(settings.admin_password) >= 12,
        "PASSWORD_CONFIG",
        "ADMIN_PASSWORD 至少12字符",
    )
    client = FineractClient(settings)
    try:
        with session_factory()() as db:
            mappings = {}
            for name in ["Alice", "Bob", "Charlie", "Mom"]:
                data = client.request(
                    "GET",
                    "clients",
                    params={"externalId": f"AGENT-{name.upper()}", "limit": 100},
                )
                candidates = [
                    r
                    for r in data.get("pageItems", [])
                    if r.get("externalId") == f"AGENT-{name.upper()}"
                ]
                require(
                    len(candidates) == 1,
                    "DEMO_CLIENT_MISSING",
                    f"请先运行 Fineract seed；未找到 {name}",
                )
                raw = candidates[0]
                user = db.scalar(select(User).where(User.username == name.lower()))
                if not user:
                    user = User(
                        username=name.lower(),
                        password_hash=password_hasher.hash(settings.demo_password),
                        client_id=raw["id"],
                        tenant=settings.fineract_tenant,
                    )
                    db.add(user)
                    db.flush()
                require(
                    user.client_id == raw["id"]
                    and user.tenant == settings.fineract_tenant,
                    "IDENTITY_CONFLICT",
                    "现有账号映射不一致",
                )
                account = primary_savings_account(
                    client.list_client_accounts(raw["id"]).get(
                        "savingsAccounts", []
                    ),
                    name,
                )
                mappings[name] = (user, account["id"], raw.get("mobileNo", ""))
                initialize_billing_categories(db, user)
            for name, (user, account, phone) in mappings.items():
                for target, (other, to_account, to_phone) in mappings.items():
                    if target == name:
                        continue
                    exists = db.scalar(
                        select(Recipient).where(
                            Recipient.user_id == user.id,
                            Recipient.account_id == to_account,
                            Recipient.deleted == False,
                        )
                    )
                    demo_alias = "妈妈" if target == "Mom" else target
                    if exists:
                        if target == "Mom" and exists.alias in (None, "", "Mom"):
                            exists.alias = demo_alias
                    else:
                        db.add(
                            Recipient(
                                user_id=user.id,
                                name=target,
                                phone=to_phone,
                                alias=demo_alias,
                                account_id=to_account,
                            )
                        )
            alice_user = mappings["Alice"][0]
            for target, alias in (("Bob", "同事小李"), ("Charlie", "同学小李")):
                _, target_account, target_phone = mappings[target]
                duplicate = db.scalar(
                    select(Recipient).where(
                        Recipient.user_id == alice_user.id,
                        Recipient.account_id == target_account,
                        Recipient.name == "小李",
                        Recipient.alias == alias,
                        Recipient.deleted == False,
                    )
                )
                if duplicate is None:
                    db.add(
                        Recipient(
                            user_id=alice_user.id,
                            name="小李",
                            phone=target_phone,
                            alias=alias,
                            account_id=target_account,
                        )
                    )
            merchant_data = client.request(
                "GET",
                "clients",
                params={"externalId": "AGENT-DEMO-MERCHANT", "limit": 100},
            )
            merchant_clients = [
                row
                for row in merchant_data.get("pageItems", [])
                if row.get("externalId") == "AGENT-DEMO-MERCHANT"
            ]
            require(
                len(merchant_clients) == 1,
                "DEMO_MERCHANT_MISSING",
                "请先重新运行 Fineract seed；未找到 Demo 商户",
            )
            merchant_client = merchant_clients[0]
            merchant_account = exact_active_savings_account(
                client.list_client_accounts(merchant_client["id"]).get(
                    "savingsAccounts", []
                ),
                "AGENT-DEMO-MERCHANT-SAV",
            )
            merchant = db.scalar(
                select(Merchant).where(Merchant.external_key == "demo-card:main")
            )
            if not merchant:
                merchant = Merchant(external_key="demo-card:main")
                db.add(merchant)
            merchant.name = "智汇 Demo 商城"
            merchant.category = "购物"
            merchant.adapter_type = "demo_card"
            merchant.fineract_account_id = int(merchant_account["id"])
            merchant.active = True
            orchestration_merchants = {
                "DEMO-FLOWER": (
                    "demo-orchestration:flower",
                    "心意 Demo 花店",
                ),
                "DEMO-CAKE": (
                    "demo-orchestration:cake",
                    "甜蜜 Demo 蛋糕店",
                ),
            }
            for spec in DEMO_ORCHESTRATION_MERCHANTS:
                data = client.request(
                    "GET",
                    "clients",
                    params={"externalId": f"AGENT-{spec.key}", "limit": 100},
                )
                matches = [
                    row
                    for row in data.get("pageItems", [])
                    if row.get("externalId") == f"AGENT-{spec.key}"
                ]
                require(
                    len(matches) == 1,
                    "DEMO_MERCHANT_MISSING",
                    f"请先重新运行 Fineract seed；未找到 {spec.key}",
                )
                account = exact_active_savings_account(
                    client.list_client_accounts(matches[0]["id"]).get(
                        "savingsAccounts", []
                    ),
                    f"AGENT-{spec.key}-SAV",
                )
                external_key, display_name = orchestration_merchants[spec.key]
                row = db.scalar(
                    select(Merchant).where(Merchant.external_key == external_key)
                )
                if row is None:
                    row = Merchant(external_key=external_key)
                    db.add(row)
                row.name = display_name
                row.category = "礼物"
                row.adapter_type = "demo_orchestration"
                row.fineract_account_id = int(account["id"])
                row.active = True
            ensure_demo_cards(db, mappings, client, settings)
            initialize_fixed_product_metadata(db, client, settings.fineract_tenant)
            if settings.admin_password and not db.scalar(
                select(User).where(User.username == "admin")
            ):
                db.add(
                    User(
                        username="admin",
                        password_hash=password_hasher.hash(settings.admin_password),
                        client_id=0,
                        tenant=settings.fineract_tenant,
                        is_admin=True,
                    )
                )
            db.commit()
    finally:
        client.close()
    print(
        "bank_agent migrations and demo identity mappings ready; existing passwords preserved."
    )
    if demo_billing_fixtures:
        result = initialize_demo_subscription_fixtures()
        print("已核实生成的月度订阅：" + "、".join(result["verified"]))
        if result["preserved"]:
            print("保留已有订阅状态：" + "、".join(f"{row['merchant']}({row['status']})" for row in result["preserved"]))


if __name__ == "__main__":
    ensure_local_no_proxy()
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate-only", action="store_true")
    parser.add_argument("--demo-billing-fixtures", action="store_true",
        help="development 专用：扫描实际生成流水并显式登记已核实订阅演示样本")
    args = parser.parse_args()
    provision()
    if not args.migrate_only:
        initialize_users(demo_billing_fixtures=args.demo_billing_fixtures)
