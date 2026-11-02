"""Safely rebuild the local Bank Agent demo with reproducible random history.

The reset is intentionally narrow:

* it only targets exact ``AGENT-*`` Demo identities, Alice's exact analysis
  account, fixed baseline card accounts, UUID-shaped ``BANK-CARD-*`` accounts
  created by this project, and the isolated Demo merchant settlement account;
* it uses supported Fineract APIs (transfer undo and transaction undo), never
  SQL against Fineract's database;
* it preserves middle-tier users and password hashes, but revokes their login
  sessions and clears user-owned business state;
* it refuses to run outside a local development environment or when it finds
  unknown accounts/cross-boundary transfers it cannot safely reset.

Run without ``--execute`` to inspect the plan.  Execution requires typing the
exact confirmation phrase shown by the program.
"""

from __future__ import annotations

import argparse
import dataclasses
import secrets
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import delete, or_, select
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps/backend"))
sys.path.insert(0, str(ROOT / "scripts/fineract"))

from clients.fineract import (
    FineractClient as BankingFineractClient,
    FineractError as BankingFineractError,
)
from core.config import get_settings
from core.database import session_factory
from core.errors import DomainError
from models import (
    AACollection,
    AAShare,
    Action,
    AgentConversation,
    AgentEvent,
    AgentMessage,
    AgentRun,
    Annotation,
    AnalysisResult,
    AnomalyModel,
    AnomalyReview,
    Audit,
    Base,
    BillReport,
    BillReportJob,
    BillReportTransaction,
    BankCard,
    CardAuthorization,
    DemoOrder,
    FundReservation,
    Category,
    ClassificationRule,
    DailyUsage,
    LoginSession,
    Merchant,
    OrchestrationTask,
    PersonalEvent,
    Recipient,
    RiskAssessment,
    Schedule,
    ScheduleRun,
    SecurityEvent,
    SecurityLock,
    Subscription,
    SubscriptionAgentResult,
    SubscriptionBudgetRule,
    SubscriptionClarification,
    SubscriptionMutationKey,
    SubscriptionNotification,
    SubscriptionOccurrence,
    SubscriptionReminderRule,
    TaskEdge,
    TaskEvent,
    TaskNode,
    User,
)
from seed_fineract import (
    CLIENTS,
    DEMO_CARD_ACCOUNTS,
    DEMO_MERCHANT,
    DEMO_ORCHESTRATION_MERCHANTS,
    HISTORY_DAYS,
    STATE_FILE,
    FineractClient,
    FineractConfig,
    FineractError,
    Seeder,
    State,
    first_open_date,
    load_env_file,
)
from services.subscription_service import SubscriptionService
from scripts.development.init_banking import initialize_demo_subscription_fixtures, initialize_users
from demo_history import ANALYSIS_ACCOUNT_EXTERNAL_ID

CONFIRMATION = "RESET BANK_AGENT DEMO"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class ResetRefused(RuntimeError):
    """A safety invariant failed before a destructive reset step."""


@dataclasses.dataclass(frozen=True)
class DemoIdentity:
    key: str
    username: str
    client_external_id: str
    client_id: int
    account_external_id: str
    account_id: int
    mobile: str


@dataclasses.dataclass(frozen=True)
class DemoAccount:
    owner_key: str
    client_id: int
    external_id: str
    account_id: int
    role: str
    close_after_reset: bool = False


@dataclasses.dataclass(frozen=True)
class DemoResetPlan:
    identities: dict[str, DemoIdentity]
    accounts: tuple[DemoAccount, ...]
    transfers: tuple[dict[str, Any], ...]
    direct_transactions: dict[int, tuple[dict[str, Any], ...]]

    @property
    def transaction_count(self) -> int:
        return sum(len(rows) for rows in self.direct_transactions.values())


def refuse(condition: bool, message: str) -> None:
    if not condition:
        raise ResetRefused(message)


def enum_id(value: Any) -> Any:
    return value.get("id") if isinstance(value, dict) else value


def local_hostname(raw_url: str) -> str | None:
    return urlparse(raw_url).hostname


def validate_local_environment() -> None:
    settings = get_settings()
    database = make_url(settings.database_url)
    refuse(settings.environment == "development", "Demo Reset 只允许 development 环境")
    refuse(
        database.database == "bank_agent" and database.username == "bank_agent",
        "Demo Reset 只允许独立 bank_agent 账号和数据库",
    )
    refuse(
        database.host in LOCAL_HOSTS,
        "Demo Reset 只允许本机 PostgreSQL，拒绝远程 DATABASE_URL",
    )
    refuse(
        local_hostname(settings.fineract_base_url) in LOCAL_HOSTS,
        "Demo Reset 只允许本机 Fineract，拒绝远程 FINERACT_BASE_URL",
    )


class FineractDemoResetter:
    def __init__(self, client: FineractClient) -> None:
        self.client = client

    @staticmethod
    def _is_dynamic_card_account(external_id: str) -> bool:
        prefix = "BANK-CARD-"
        if not external_id.startswith(prefix):
            return False
        try:
            UUID(external_id.removeprefix(prefix))
        except ValueError:
            return False
        return True

    @staticmethod
    def _inactive_terminal(row: dict[str, Any]) -> bool:
        status = row.get("status") or {}
        return bool(
            status.get("closed")
            or status.get("rejected")
            or status.get("withdrawnByApplicant")
            or status.get("prematureClosed")
        )

    def _exact_client(self, external_id: str) -> dict[str, Any]:
        page = self.client.get(
            "/clients", params={"externalId": external_id, "limit": 100}
        ) or {}
        matches = [
            row
            for row in page.get("pageItems", [])
            if row.get("externalId") == external_id
        ]
        refuse(
            len(matches) == 1,
            f"必须唯一找到演示客户 {external_id}；请先运行 seed_fineract.py",
        )
        return matches[0]

    def discover(self) -> tuple[dict[str, DemoIdentity], tuple[DemoAccount, ...]]:
        result: dict[str, DemoIdentity] = {}
        scoped: list[DemoAccount] = []
        for spec in CLIENTS:
            client_external = f"AGENT-{spec.key}"
            raw_client = self._exact_client(client_external)
            accounts = (
                self.client.get(f"/clients/{raw_client['id']}/accounts") or {}
            ).get("savingsAccounts", [])
            account_external = f"{client_external}-SAV"
            account_matches = [
                row
                for row in accounts
                if row.get("externalId") == account_external
                and enum_id(row.get("depositType")) == 100
                and (row.get("status") or {}).get("active")
            ]
            refuse(
                len(account_matches) == 1,
                f"必须唯一找到 ACTIVE 主账户 {account_external}",
            )
            expected_cards = {
                external_id
                for external_id, _ in DEMO_CARD_ACCOUNTS[spec.key]
            }
            analysis_external_id = ANALYSIS_ACCOUNT_EXTERNAL_ID
            if spec.key == "ALICE":
                analysis_matches = [
                    row for row in accounts
                    if row.get("externalId") == analysis_external_id
                ]
                refuse(
                    len(analysis_matches) <= 1,
                    f"Alice 分析副账户 {analysis_external_id} 重复，拒绝重置",
                )
            for row in accounts:
                external_id = str(row.get("externalId") or "")
                account_id = int(row["id"])
                active = bool((row.get("status") or {}).get("active"))
                role = None
                close_after_reset = False
                if external_id == account_external:
                    role = "primary"
                elif spec.key == "ALICE" and external_id == analysis_external_id:
                    refuse(
                        active and enum_id(row.get("depositType")) == 100,
                        f"Alice 分析副账户 {analysis_external_id} 必须是 ACTIVE 储蓄账户",
                    )
                    role = "analysis"
                elif external_id in expected_cards:
                    refuse(
                        active,
                        f"固定卡账户 {external_id} 已存在但不是 ACTIVE，无法幂等恢复",
                    )
                    role = "baseline_card"
                elif self._is_dynamic_card_account(external_id):
                    if self._inactive_terminal(row):
                        continue
                    refuse(
                        active,
                        f"动态卡账户 {external_id} 处于不支持自动清理的中间状态",
                    )
                    role = "dynamic_card"
                    close_after_reset = True
                else:
                    raise ResetRefused(
                        f"{client_external} 存在未知储蓄账户 "
                        f"{(account_id, external_id)}；拒绝部分重置"
                    )
                scoped.append(
                    DemoAccount(
                        owner_key=spec.key,
                        client_id=int(raw_client["id"]),
                        external_id=external_id,
                        account_id=account_id,
                        role=role,
                        close_after_reset=close_after_reset,
                    )
                )
            result[spec.key] = DemoIdentity(
                key=spec.key,
                username=spec.key.lower(),
                client_external_id=client_external,
                client_id=int(raw_client["id"]),
                account_external_id=account_external,
                account_id=int(account_matches[0]["id"]),
                mobile=raw_client.get("mobileNo") or spec.mobile,
            )

        merchant_external = f"AGENT-{DEMO_MERCHANT.key}"
        merchant = self._exact_client(merchant_external)
        merchant_accounts = (
            self.client.get(f"/clients/{merchant['id']}/accounts") or {}
        ).get("savingsAccounts", [])
        merchant_account_external = f"{merchant_external}-SAV"
        merchant_matches = [
            row
            for row in merchant_accounts
            if row.get("externalId") == merchant_account_external
            and enum_id(row.get("depositType")) == 100
            and (row.get("status") or {}).get("active")
        ]
        refuse(
            len(merchant_matches) == 1,
            f"必须唯一找到 ACTIVE Demo 商户账户 {merchant_account_external}",
        )
        refuse(
            len(merchant_accounts) == 1,
            f"{merchant_external} 存在未知额外账户，拒绝部分重置",
        )
        merchant_account = merchant_matches[0]
        scoped.append(
            DemoAccount(
                owner_key=DEMO_MERCHANT.key,
                client_id=int(merchant["id"]),
                external_id=merchant_account_external,
                account_id=int(merchant_account["id"]),
                role="merchant",
            )
        )
        for spec in DEMO_ORCHESTRATION_MERCHANTS:
            external_id = f"AGENT-{spec.key}"
            demo_client = self._exact_client(external_id)
            accounts = (
                self.client.get(f"/clients/{demo_client['id']}/accounts") or {}
            ).get("savingsAccounts", [])
            account_external_id = f"{external_id}-SAV"
            matches = [
                row
                for row in accounts
                if row.get("externalId") == account_external_id
                and enum_id(row.get("depositType")) == 100
                and (row.get("status") or {}).get("active")
            ]
            refuse(
                len(matches) == 1 and len(accounts) == 1,
                f"必须唯一找到 ACTIVE Demo 商户账户 {account_external_id}",
            )
            scoped.append(
                DemoAccount(
                    owner_key=spec.key,
                    client_id=int(demo_client["id"]),
                    external_id=account_external_id,
                    account_id=int(matches[0]["id"]),
                    role="orchestration_merchant",
                )
            )
        return result, tuple(scoped)

    def identities(self) -> dict[str, DemoIdentity]:
        return self.discover()[0]

    def all_transfers(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        page_size = 200
        while True:
            payload = self.client.get(
                "/accounttransfers", params={"offset": offset, "limit": page_size}
            ) or {}
            page = payload.get("pageItems")
            refuse(
                isinstance(page, list)
                and payload.get("totalFilteredRecords") is not None,
                "Fineract 转账分页契约不兼容",
            )
            rows.extend(page)
            offset += len(page)
            if offset >= int(payload["totalFilteredRecords"]):
                break
            refuse(bool(page), "Fineract 转账分页未前进")
        return rows

    def transactions(self, account_id: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page_number = 0
        page_size = 200
        while True:
            payload = self.client.get(
                f"/savingsaccounts/{account_id}/transactions/search",
                params={
                    "offset": page_number,
                    "limit": page_size,
                    "orderBy": "transactionDate,id",
                    "sortOrder": "DESC",
                },
            ) or {}
            page = payload.get("content")
            refuse(
                isinstance(page, list) and payload.get("total") is not None,
                "Fineract 流水分页契约不兼容",
            )
            rows.extend(page)
            if (page_number + 1) * page_size >= int(payload["total"]):
                break
            page_number += 1
        return rows

    @staticmethod
    def active(row: dict[str, Any]) -> bool:
        return not row.get("reversed") and not row.get("isReversal")

    @staticmethod
    def transaction_sort_key(row: dict[str, Any]) -> tuple[date, int]:
        raw = row.get("date")
        if isinstance(raw, list) and len(raw) >= 3:
            day = date(int(raw[0]), int(raw[1]), int(raw[2]))
        elif isinstance(raw, str):
            day = date.fromisoformat(raw[:10])
        else:
            raise ResetRefused(f"流水 {row.get('id')} 缺少可识别日期")
        return day, int(row["id"])

    def build_plan(self) -> DemoResetPlan:
        identities, accounts = self.discover()
        scoped_accounts = {item.account_id for item in accounts}

        transfers: list[dict[str, Any]] = []
        for transfer in self.all_transfers():
            if transfer.get("reversed"):
                continue
            source = int((transfer.get("fromAccount") or {}).get("id", -1))
            target = int((transfer.get("toAccount") or {}).get("id", -1))
            touches = source in scoped_accounts or target in scoped_accounts
            if not touches:
                continue
            refuse(
                source in scoped_accounts and target in scoped_accounts,
                f"转账 {transfer.get('id')} 跨出演示账户边界（{source} -> {target}），拒绝自动撤销",
            )
            transfers.append(transfer)
        transfers.sort(
            key=lambda row: (str(row.get("transferDate", "")), int(row["id"])),
            reverse=True,
        )

        direct: dict[int, tuple[dict[str, Any], ...]] = {}
        for account_id in sorted(scoped_accounts):
            rows: list[dict[str, Any]] = []
            for transaction in self.transactions(account_id):
                if not self.active(transaction) or transaction.get("transfer"):
                    continue
                kind = transaction.get("transactionType") or {}
                refuse(
                    bool(kind.get("deposit") or kind.get("withdrawal")),
                    f"账户 {account_id} 的流水 {transaction.get('id')} 类型不支持安全重置",
                )
                rows.append(transaction)
            rows.sort(key=self.transaction_sort_key, reverse=True)
            direct[account_id] = tuple(rows)
        return DemoResetPlan(identities, accounts, tuple(transfers), direct)

    def execute(self, plan: DemoResetPlan) -> None:
        for transfer in plan.transfers:
            self.client.post(
                f"/accounttransfers/{int(transfer['id'])}",
                add_common=False,
                params={"command": "undo"},
                json=None,
            )

        # Refresh after undoing transfers: their paired account transactions
        # should now be reversed and must not be passed to the savings endpoint.
        for account in plan.accounts:
            rows = [
                row
                for row in self.transactions(account.account_id)
                if self.active(row) and not row.get("transfer")
            ]
            rows.sort(key=self.transaction_sort_key, reverse=True)
            for transaction in rows:
                self.client.post(
                    f"/savingsaccounts/{account.account_id}/transactions/{int(transaction['id'])}",
                    add_common=False,
                    params={"command": "undo"},
                    json={},
                )

        for account in plan.accounts:
            active = [
                row
                for row in self.transactions(account.account_id)
                if self.active(row)
            ]
            details = self.client.get(f"/savingsaccounts/{account.account_id}") or {}
            balance = Decimal(str((details.get("summary") or {}).get("availableBalance", "NaN")))
            refuse(
                not active and balance == Decimal("0"),
                f"账户 {account.external_id} 未清零（余额={balance}，有效流水={len(active)}）",
            )
            if account.close_after_reset:
                self.client.post(
                    f"/savingsaccounts/{account.account_id}",
                    add_common=False,
                    params={"command": "close"},
                    json={
                        "closedOnDate": date.today().isoformat(),
                        "withdrawBalance": False,
                        "postInterestValidationOnClosure": False,
                        "note": "Bank Agent Demo Reset",
                        "dateFormat": "yyyy-MM-dd",
                        "locale": "en",
                    },
                )
                closed = self.client.get(
                    f"/savingsaccounts/{account.account_id}"
                ) or {}
                refuse(
                    bool((closed.get("status") or {}).get("closed")),
                    f"动态卡账户 {account.external_id} 未成功关闭",
                )


USER_SCOPED_MODELS = (
    AgentConversation,
    AgentRun,
    SecurityEvent,
    SecurityLock,
    AnalysisResult,
    AnomalyModel,
    LoginSession,
    Recipient,
    Action,
    DailyUsage,
    Schedule,
    AACollection,
    AAShare,
    Category,
    ClassificationRule,
    Annotation,
    BillReport,
    BillReportJob,
    AnomalyReview,
    RiskAssessment,
    Subscription,
    SubscriptionAgentResult,
    SubscriptionBudgetRule,
    SubscriptionClarification,
    SubscriptionMutationKey,
    SubscriptionNotification,
    SubscriptionReminderRule,
    BankCard,
    CardAuthorization,
    PersonalEvent,
    OrchestrationTask,
    FundReservation,
    DemoOrder,
    Audit,
)


def assert_reset_model_coverage() -> None:
    expected = {
        table.name
        for table in Base.metadata.tables.values()
        if "user_id" in table.columns
    }
    covered = {model.__tablename__ for model in USER_SCOPED_MODELS}
    missing = sorted(expected - covered)
    refuse(
        not missing,
        f"发现尚未纳入 Demo Reset 的用户数据表：{missing}；请先更新重置逻辑",
    )


def reset_application_state(db, identities: dict[str, DemoIdentity]) -> dict[str, int]:
    """Clear demo-user state in one transaction while preserving identities."""
    assert_reset_model_coverage()
    usernames = [identity.username for identity in identities.values()]
    users = list(
        db.scalars(
            select(User).where(User.username.in_(usernames)).with_for_update()
        )
    )
    by_name = {user.username: user for user in users}
    refuse(
        set(by_name) == set(usernames),
        "中端缺少完整演示用户；请先运行 init_banking.py",
    )
    for identity in identities.values():
        user = by_name[identity.username]
        refuse(
            user.client_id == identity.client_id,
            f"用户 {identity.username} 的 Fineract client 映射不一致",
        )

    user_ids = [user.id for user in users]
    password_hashes = {user.id: user.password_hash for user in users}
    action_ids = select(Action.id).where(Action.user_id.in_(user_ids))
    schedule_ids = select(Schedule.id).where(Schedule.user_id.in_(user_ids))
    collection_ids = select(AACollection.id).where(AACollection.user_id.in_(user_ids))
    subscription_ids = select(Subscription.id).where(Subscription.user_id.in_(user_ids))
    card_ids = select(BankCard.id).where(BankCard.user_id.in_(user_ids))
    report_ids = select(BillReport.id).where(BillReport.user_id.in_(user_ids))
    task_ids = select(OrchestrationTask.id).where(
        OrchestrationTask.user_id.in_(user_ids)
    )
    conversation_ids = select(AgentConversation.id).where(
        AgentConversation.user_id.in_(user_ids)
    )
    agent_run_ids = select(AgentRun.id).where(
        or_(
            AgentRun.user_id.in_(user_ids),
            AgentRun.conversation_id.in_(conversation_ids),
        )
    )
    counts: dict[str, int] = {}

    def remove(model, predicate) -> None:
        result = db.execute(delete(model).where(predicate))
        counts[model.__tablename__] = int(result.rowcount or 0)

    remove(
        SecurityEvent,
        or_(
            SecurityEvent.user_id.in_(user_ids),
            SecurityEvent.conversation_id.in_(conversation_ids),
            SecurityEvent.run_id.in_(agent_run_ids),
        ),
    )
    remove(
        AgentEvent,
        or_(
            AgentEvent.conversation_id.in_(conversation_ids),
            AgentEvent.run_id.in_(agent_run_ids),
        ),
    )
    remove(AgentRun, AgentRun.id.in_(agent_run_ids))
    remove(AgentMessage, AgentMessage.conversation_id.in_(conversation_ids))
    remove(AgentConversation, AgentConversation.id.in_(conversation_ids))
    remove(SecurityLock, SecurityLock.user_id.in_(user_ids))
    remove(TaskEvent, TaskEvent.task_id.in_(task_ids))
    remove(DemoOrder, DemoOrder.task_id.in_(task_ids))
    remove(FundReservation, FundReservation.task_id.in_(task_ids))
    remove(TaskEdge, TaskEdge.task_id.in_(task_ids))
    remove(TaskNode, TaskNode.task_id.in_(task_ids))
    remove(OrchestrationTask, OrchestrationTask.id.in_(task_ids))
    remove(PersonalEvent, PersonalEvent.user_id.in_(user_ids))
    remove(
        ScheduleRun,
        or_(
            ScheduleRun.schedule_id.in_(schedule_ids),
            ScheduleRun.action_id.in_(action_ids),
        ),
    )
    remove(
        AAShare,
        or_(
            AAShare.collection_id.in_(collection_ids),
            AAShare.user_id.in_(user_ids),
            AAShare.action_id.in_(action_ids),
        ),
    )
    remove(
        SubscriptionOccurrence,
        SubscriptionOccurrence.subscription_id.in_(subscription_ids),
    )
    for model in (
        SubscriptionNotification,
        SubscriptionReminderRule,
        SubscriptionBudgetRule,
        SubscriptionClarification,
        SubscriptionAgentResult,
        SubscriptionMutationKey,
    ):
        remove(model, model.user_id.in_(user_ids))
    remove(
        CardAuthorization,
        or_(
            CardAuthorization.user_id.in_(user_ids),
            CardAuthorization.card_id.in_(card_ids),
            CardAuthorization.action_id.in_(action_ids),
        ),
    )
    remove(ClassificationRule, ClassificationRule.user_id.in_(user_ids))
    remove(AnalysisResult, AnalysisResult.user_id.in_(user_ids))
    remove(BillReportTransaction, BillReportTransaction.report_id.in_(report_ids))
    remove(AnomalyModel, AnomalyModel.user_id.in_(user_ids))
    remove(Annotation, Annotation.user_id.in_(user_ids))
    remove(Schedule, Schedule.user_id.in_(user_ids))
    remove(AACollection, AACollection.user_id.in_(user_ids))
    remove(Subscription, Subscription.user_id.in_(user_ids))
    remove(BankCard, BankCard.user_id.in_(user_ids))
    for model in (
        LoginSession,
        Recipient,
        DailyUsage,
        BillReportJob,
        BillReport,
        AnomalyReview,
        RiskAssessment,
        Audit,
        Category,
    ):
        remove(model, model.user_id.in_(user_ids))
    remove(Action, Action.user_id.in_(user_ids))

    for user in users:
        user.login_failures = 0
        user.login_locked_until = None
        user.otp_locked_until = None

    for source in identities.values():
        source_user = by_name[source.username]
        for target in identities.values():
            if source.key == target.key:
                continue
            db.add(
                Recipient(
                    user_id=source_user.id,
                    name=target.key.title(),
                    phone=target.mobile,
                    alias=target.key.title(),
                    account_id=target.account_id,
                )
            )
    db.commit()

    for user in users:
        db.refresh(user)
        refuse(
            user.password_hash == password_hashes[user.id],
            f"用户 {user.username} 密码哈希发生意外变化",
        )
    counts["recipients_recreated"] = len(identities) * (len(identities) - 1)
    return counts


def rebuild_demo_business_state() -> dict[str, Any]:
    """Restore local card mappings and deterministic subscription candidates."""
    initialize_users()
    settings = get_settings()
    fineract = BankingFineractClient(settings)
    scanned = candidates = 0
    try:
        with session_factory()() as db:
            users = list(
                db.scalars(
                    select(User).where(
                        User.username.in_([spec.key.lower() for spec in CLIENTS])
                    )
                )
            )
            refuse(len(users) == len(CLIENTS), "无法恢复完整 Demo 用户业务基线")
            for user in users:
                result = SubscriptionService(
                    db, fineract, settings
                ).scan(user)
                scanned += 1
                candidates += int(result["found"])
            refuse(
                candidates > 0,
                "确定性 Seed 未生成可识别的订阅候选，Demo 基线不完整",
            )
            card_rows = list(
                db.execute(
                    select(
                        User.username,
                        BankCard.id,
                        BankCard.fineract_account_id,
                        BankCard.status,
                    )
                    .join(BankCard, BankCard.user_id == User.id)
                    .where(User.id.in_([user.id for user in users]))
                    .order_by(User.username, BankCard.fineract_account_id)
                )
            )
            expected_cards = sum(len(rows) for rows in DEMO_CARD_ACCOUNTS.values())
            refuse(
                len(card_rows) == expected_cards
                and all(row.status == "ACTIVE" for row in card_rows),
                "Demo 基线卡片数量或状态不符合预期",
            )
            merchant = db.scalar(
                select(Merchant).where(Merchant.external_key == "demo-card:main")
            )
            refuse(
                merchant is not None
                and merchant.active
                and merchant.fineract_account_id is not None,
                "Demo 商户映射未恢复",
            )
            orchestration_merchants = list(
                db.scalars(
                    select(Merchant).where(
                        Merchant.external_key.in_(
                            (
                                "demo-orchestration:flower",
                                "demo-orchestration:cake",
                            )
                        )
                    )
                )
            )
            refuse(
                len(orchestration_merchants) == 2
                and all(
                    row.active
                    and row.adapter_type == "demo_orchestration"
                    and row.fineract_account_id is not None
                    for row in orchestration_merchants
                ),
                "生日 Demo 商户映射未恢复",
            )
    finally:
        fineract.close()
    demo_subscription_fixtures = initialize_demo_subscription_fixtures()
    return {
        "users_scanned": scanned,
        "subscription_candidates": candidates,
        "demo_subscription_fixtures": demo_subscription_fixtures,
        "baseline_cards": [
            {
                "username": row.username,
                "card_id": row.id,
                "account_id": row.fineract_account_id,
                "status": row.status,
            }
            for row in card_rows
        ],
        "merchant": {
            "merchant_id": merchant.id,
            "account_id": merchant.fineract_account_id,
        },
        "orchestration_merchants": [
            {
                "merchant_id": row.id,
                "external_key": row.external_key,
                "account_id": row.fineract_account_id,
            }
            for row in orchestration_merchants
        ],
    }


def print_plan(plan: DemoResetPlan, config: FineractConfig, history_seed: int, as_of: date) -> None:
    settings = get_settings()
    database = make_url(settings.database_url)
    print("\n=== Demo Reset 计划 ===")
    print(f"Fineract: {config.base_url}  tenant={config.tenant}")
    print(f"历史种子: {history_seed}；截止日: {as_of}；最长历史: {HISTORY_DAYS} 天")
    print(
        "中端数据库: "
        f"{database.drivername}://{database.username}@{database.host}:{database.port or 5432}/{database.database}"
    )
    for identity in plan.identities.values():
        print(
            f"{identity.key:<8} client={identity.client_id:<4} "
            f"account={identity.account_id:<4} externalId={identity.account_external_id}"
        )
    for account in plan.accounts:
        if account.role == "primary":
            continue
        suffix = "（清零后关闭）" if account.close_after_reset else ""
        print(
            f"  {account.role:<14} account={account.account_id:<4} "
            f"externalId={account.external_id}{suffix}"
        )
    print(f"将撤销内部转账: {len(plan.transfers)} 笔")
    print(f"将撤销直接存取流水: {plan.transaction_count} 笔")
    print(
        "将关闭动态办卡账户: "
        f"{sum(1 for account in plan.accounts if account.close_after_reset)} 个"
    )
    print("中端将保留 users/password_hash，清空四名演示用户的会话和业务状态。")


def confirm_execution(provided: str | None) -> None:
    if provided is None:
        print("\n请先停止 FastAPI 与 worker。此操作会撤销上述演示资金流水。")
        provided = input(f"输入 {CONFIRMATION!r} 继续：").strip()
    refuse(provided == CONFIRMATION, "确认短语不匹配，未执行任何写操作")


def main(argv: Iterable[str] | None = None) -> int:
    load_env_file()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行重置；缺省只读取并打印计划",
    )
    parser.add_argument(
        "--confirm",
        help="非交互执行时传入精确确认短语（仍必须同时提供 --execute）",
    )
    parser.add_argument("--history-seed", type=int, help="历史随机种子；预览和执行传入同一值可复现")
    parser.add_argument("--as-of", type=date.fromisoformat, help="历史结束日 YYYY-MM-DD（默认上海时区昨天）")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.confirm and not args.execute:
        parser.error("--confirm 只能与 --execute 一起使用")

    latest_allowed = datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)
    as_of = args.as_of or latest_allowed
    if as_of > latest_allowed:
        parser.error("--as-of 不能晚于上海时区昨天")
    history_seed = args.history_seed if args.history_seed is not None else secrets.randbits(63)

    validate_local_environment()
    config = FineractConfig()
    client = FineractClient(config, timeout=60.0)
    try:
        resetter = FineractDemoResetter(client)
        plan = resetter.build_plan()
        print_plan(plan, config, history_seed, as_of)
        if not args.execute:
            print("\n只读计划完成；未修改 Fineract 或中端数据库。")
            return 0

        confirm_execution(args.confirm)
        resetter.execute(plan)
        seeder = Seeder(client, State(STATE_FILE))
        seeder.history_seed = history_seed
        seeder.as_of = as_of
        seeder.opened = first_open_date(as_of)
        seed_result = seeder.run()
        with session_factory()() as db:
            db_counts = reset_application_state(db, plan.identities)
        baseline_counts = rebuild_demo_business_state()
    except (
        ResetRefused,
        FineractError,
        BankingFineractError,
        DomainError,
    ) as exc:
        print(f"\nDemo Reset 已停止：{exc}", file=sys.stderr)
        return 2
    finally:
        client.close()

    print("\n=== Demo Reset 完成 ===")
    for key, row in seed_result.items():
        print(
            f"{key:<14} account={row['account_id']:<4} balance={row['balance']} "
            f"计划={row.get('planned', 0)} 新建={row['created']} "
            f"已有={row.get('existing', 0)} 余额不足跳过={row.get('skipped_insufficient_funds', 0)}"
        )
    print(f"中端清理/重建统计: {db_counts}")
    print(
        "订阅基线: "
        f"扫描用户={baseline_counts['users_scanned']}，"
        f"候选={baseline_counts['subscription_candidates']}，"
        f"演示已核实={len(baseline_counts['demo_subscription_fixtures']['verified'])}"
    )
    print(
        "Demo 商户: "
        f"merchant={baseline_counts['merchant']['merchant_id']} "
        f"account={baseline_counts['merchant']['account_id']}"
    )
    for card in baseline_counts["baseline_cards"]:
        print(
            f"基线卡: user={card['username']:<8} card={card['card_id']} "
            f"account={card['account_id']} status={card['status']}"
        )
    print("所有旧登录 Token 已失效；请重新登录。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
