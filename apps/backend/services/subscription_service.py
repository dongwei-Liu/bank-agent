"""Deterministic subscription detection and Demo cancellation workflow."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy import func, select

from clients.demo_merchant import DemoMerchantAdapter
from core.errors import DomainError, require
from core.security import aware, fingerprint, now, SHANGHAI
from models import (
    Action, Audit, Merchant, Subscription, SubscriptionBudgetRule,
    SubscriptionOccurrence,
)
from services.account_service import AccountService
from services.common import audit, lock_user, owned, row_dict, safe_json
from services.transaction_service import TransactionService

RULE_VERSION = "subscription-v1"
CADENCES = {"MONTHLY": (25, 35), "YEARLY": (350, 380)}
AMOUNT_TOLERANCE = Decimal("0.10")


def normalized_merchant(value):
    return " ".join(str(value).casefold().split())


class SubscriptionService:
    def __init__(self, db, fineract, settings):
        self.db, self.fineract, self.settings = db, fineract, settings
        self.transactions = TransactionService(db, fineract, settings)
        self.adapter = DemoMerchantAdapter()

    def _merchant(self, name):
        normalized = normalized_merchant(name)
        external_key = f"subscription:{fingerprint(normalized)}"
        merchant = self.db.scalar(
            select(Merchant).where(Merchant.external_key == external_key)
        )
        if merchant is None:
            merchant = Merchant(
                external_key=external_key,
                name=str(name).strip(),
                category="未分类",
                adapter_type="demo_subscription",
            )
            self.db.add(merchant)
            self.db.flush()
        return merchant, normalized

    @staticmethod
    def _best_run(rows, minimum_gap, maximum_gap):
        best = []
        current = []
        for row in rows:
            if not current:
                current = [row]
            else:
                gap = (row["occurred_on"] - current[-1]["occurred_on"]).days
                current = current + [row] if minimum_gap <= gap <= maximum_gap else [row]
            if len(current) >= len(best):
                amounts = [item["amount"] for item in current]
                middle = Decimal(str(median(amounts)))
                if middle > 0 and all(
                    abs(amount - middle) / middle <= AMOUNT_TOLERANCE
                    for amount in amounts
                ):
                    best = list(current)
        return best

    def _candidates(self, user):
        end = now().astimezone(SHANGHAI).date()
        # Three yearly observations can span up to 760 days. Keep a small
        # margin while still bounding the amount of core history read.
        start = end - timedelta(days=800)
        grouped = defaultdict(list)
        transaction_count = 0
        for account in AccountService(self.fineract).list_accounts(user):
            account_rows = self.transactions.all(user, account.id, start, end)
            transaction_count += len(account_rows)
            require(
                transaction_count <= self.settings.max_report_transactions,
                "REPORT_TOO_LARGE",
                "交易过多，请缩小订阅识别范围",
                422,
            )
            for row in account_rows:
                if row["reversed"] or row["kind"] != "expense" or not row["merchant"]:
                    continue
                grouped[normalized_merchant(row["merchant"])].append(
                    {
                        "merchant": row["merchant"],
                        "account_id": row["account_id"],
                        "transaction_id": row["transaction_id"],
                        "occurred_on": date.fromisoformat(row["date"]),
                        "amount": Decimal(row["amount"]),
                    }
                )
        found = []
        for rows in grouped.values():
            rows.sort(
                key=lambda item: (
                    item["occurred_on"],
                    item["account_id"],
                    item["transaction_id"],
                )
            )
            for cadence, (minimum_gap, maximum_gap) in CADENCES.items():
                run = self._best_run(rows, minimum_gap, maximum_gap)
                if len(run) < 3:
                    continue
                amounts = [item["amount"] for item in run]
                expected = Decimal(str(median(amounts))).quantize(Decimal(".01"))
                gaps = [
                    (current["occurred_on"] - previous["occurred_on"]).days
                    for previous, current in zip(run, run[1:])
                ]
                interval = round(median(gaps))
                found.append(
                    {
                        "merchant": run[-1]["merchant"],
                        "cadence": cadence,
                        "expected_amount": expected,
                        "next_charge_at": run[-1]["occurred_on"]
                        + timedelta(days=interval),
                        "rows": run,
                        "evidence": {
                            "rule_version": RULE_VERSION,
                            "cadence": cadence,
                            "gap_range_days": [minimum_gap, maximum_gap],
                            "observed_gaps_days": gaps,
                            "amount_tolerance": str(AMOUNT_TOLERANCE),
                            "expected_amount": str(expected),
                            "occurrences": [
                                {
                                    "account_id": item["account_id"],
                                    "transaction_id": item["transaction_id"],
                                    "occurred_on": item["occurred_on"].isoformat(),
                                    "amount": str(item["amount"]),
                                }
                                for item in run
                            ],
                        },
                    }
                )
        return found, start, end

    def last_scan_at(self, user):
        audit_row = self.db.scalar(
            select(Audit)
            .where(
                Audit.user_id == user.id,
                Audit.event == "SUBSCRIPTIONS_SCANNED",
            )
            .order_by(Audit.created_at.desc(), Audit.id.desc())
            .limit(1)
        )
        if audit_row is None:
            return None
        return audit_row.data.get("scanned_at") or aware(audit_row.created_at).isoformat()

    def renewals(self, user, days=3):
        today = now().astimezone(SHANGHAI).date()
        through = today + timedelta(days=days)
        verified = self.db.scalars(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.status == "VERIFIED",
                Subscription.next_charge_at.is_not(None),
            )
            .order_by(Subscription.next_charge_at, Subscription.id)
        ).all()
        upcoming = []
        needs_review = []
        for row in verified:
            view = self.view(row)
            if row.next_charge_at < today:
                needs_review.append(view)
            elif row.next_charge_at <= through:
                upcoming.append(view)
        return safe_json(
            {
                "as_of": today,
                "timezone": "Asia/Shanghai",
                "days": days,
                "from_date": today,
                "to_date": through,
                "last_scan_at": self.last_scan_at(user),
                "upcoming": upcoming,
                "needs_review": needs_review,
            }
        )

    def view(self, subscription, *, details=False):
        merchant = self.db.get(Merchant, subscription.merchant_id)
        result = {
            **row_dict(subscription),
            "merchant": merchant.name,
            "merchant_category": merchant.category,
            "demo_adapter": merchant.adapter_type == "demo_subscription",
        }
        if details:
            result["occurrences"] = [
                row_dict(row)
                for row in self.db.scalars(
                    select(SubscriptionOccurrence)
                    .where(SubscriptionOccurrence.subscription_id == subscription.id)
                    .order_by(
                        SubscriptionOccurrence.occurred_on,
                        SubscriptionOccurrence.account_id,
                        SubscriptionOccurrence.transaction_id,
                    )
                )
            ]
        else:
            result["occurrence_count"] = self.db.scalar(
                select(func.count())
                .select_from(SubscriptionOccurrence)
                .where(SubscriptionOccurrence.subscription_id == subscription.id)
            )
        return safe_json(result)

    def list(self, user):
        return [
            self.view(row)
            for row in self.db.scalars(
                select(Subscription)
                .where(Subscription.user_id == user.id)
                .order_by(Subscription.updated_at.desc(), Subscription.id)
            )
        ]

    def detail(self, user, subscription_id):
        return self.view(owned(self.db, Subscription, subscription_id, user), details=True)

    def scan(self, user, *, trace_id=None):
        candidates, start, end = self._candidates(user)
        lock_user(self.db, user)
        created = updated = 0
        for candidate in candidates:
            merchant, normalized = self._merchant(candidate["merchant"])
            row = self.db.scalar(
                select(Subscription).where(
                    Subscription.user_id == user.id,
                    Subscription.merchant_id == merchant.id,
                    Subscription.cadence == candidate["cadence"],
                )
            )
            evidence = {**candidate["evidence"], "merchant_normalized": normalized}
            evidence_changed = row is not None and fingerprint(row.evidence) != fingerprint(evidence)
            if row is None:
                row = Subscription(
                    user_id=user.id,
                    merchant_id=merchant.id,
                    status="CANDIDATE",
                    cadence=candidate["cadence"],
                    expected_amount=candidate["expected_amount"],
                    amount_tolerance=AMOUNT_TOLERANCE,
                    next_charge_at=candidate["next_charge_at"],
                    evidence=evidence,
                    rule_version=RULE_VERSION,
                )
                self.db.add(row)
                self.db.flush()
                created += 1
            else:
                if row.status == "IGNORED" and evidence_changed:
                    row.status = "CANDIDATE"
                    row.ignored_at = None
                if row.status != "CANCELLED" and evidence_changed:
                    row.expected_amount = candidate["expected_amount"]
                    row.next_charge_at = candidate["next_charge_at"]
                    row.evidence = evidence
                    row.rule_version = RULE_VERSION
                    row.updated_at = now()
                    updated += 1
            existing = {
                (item.account_id, item.transaction_id)
                for item in self.db.scalars(
                    select(SubscriptionOccurrence).where(
                        SubscriptionOccurrence.subscription_id == row.id
                    )
                )
            }
            for item in candidate["rows"]:
                identity = (item["account_id"], item["transaction_id"])
                if identity not in existing:
                    self.db.add(
                        SubscriptionOccurrence(
                            subscription_id=row.id,
                            account_id=item["account_id"],
                            transaction_id=item["transaction_id"],
                            occurred_on=item["occurred_on"],
                            amount=item["amount"],
                        )
                    )
        scanned_at = now()
        if created or updated:
            self.db.execute(
                SubscriptionBudgetRule.__table__.update()
                .where(SubscriptionBudgetRule.user_id == user.id,
                       SubscriptionBudgetRule.status == "ACTIVE")
                .values(last_evaluated_on=None)
            )
        audit(
            self.db,
            user,
            "SUBSCRIPTIONS_SCANNED",
            trace_id=trace_id,
            created=created,
            updated=updated,
            matched_candidates=len(candidates),
            from_date=start.isoformat(),
            to_date=end.isoformat(),
            scanned_at=scanned_at.isoformat(),
        )
        self.db.commit()
        rows = self.list(user)
        if created or updated:
            try:
                from services.subscription_planning_service import SubscriptionPlanningService
                SubscriptionPlanningService(self.db, self.fineract, self.settings).evaluate_active_budgets(user)
            except Exception:
                self.db.rollback()
        return {
            "created": created,
            "updated": updated,
            "found": len(rows),
            "matched_candidates": len(candidates),
            "from_date": start.isoformat(),
            "to_date": end.isoformat(),
            "scanned_at": scanned_at.isoformat(),
            "items": rows,
        }

    def set_status(self, user, subscription_id, target):
        lock_user(self.db, user)
        row = owned(self.db, Subscription, subscription_id, user)
        require(
            row.status in {"CANDIDATE", target},
            "SUBSCRIPTION_STATE",
            "当前订阅状态不可执行该操作",
            409,
        )
        if row.status == target:
            return self.view(row, details=True)
        row.status = target
        row.updated_at = now()
        if target == "VERIFIED":
            row.verified_at = now()
            row.ignored_at = None
            event = "SUBSCRIPTION_VERIFIED"
        else:
            row.ignored_at = now()
            event = "SUBSCRIPTION_IGNORED"
        self.db.execute(
            SubscriptionBudgetRule.__table__.update()
            .where(SubscriptionBudgetRule.user_id == user.id,
                   SubscriptionBudgetRule.status == "ACTIVE")
            .values(last_evaluated_on=None)
        )
        audit(self.db, user, event, subscription_id=row.id)
        self.db.commit()
        try:
            from services.subscription_planning_service import SubscriptionPlanningService
            SubscriptionPlanningService(self.db, self.fineract, self.settings).evaluate_active_budgets(user)
        except Exception:
            self.db.rollback()
        return self.view(row, details=True)

    def request_cancel(self, user, subscription_id, key):
        from services.action_service import ActionService

        lock_user(self.db, user)
        row = owned(self.db, Subscription, subscription_id, user)
        actions = ActionService(self.db, self.fineract, self.settings)
        # A key always replays the exact Action originally bound to it, even
        # after a newer request has been attached to the subscription.
        replay = self.db.scalar(
            select(Action).where(
                Action.user_id == user.id,
                Action.kind == "subscription_cancel",
                Action.idempotency_key == key,
            )
        )
        if replay is not None:
            require(
                replay.payload.get("subscription_id") == row.id,
                "IDEMPOTENCY_CONFLICT",
                "同一幂等键已用于其他订阅",
                409,
            )
            return actions.view(replay)

        current_action = None
        if row.action_id:
            current_action = owned(self.db, Action, row.action_id, user)
            require(
                current_action.kind == "subscription_cancel"
                and current_action.payload.get("subscription_id") == row.id,
                "SUBSCRIPTION_CHANGED",
                "关联的取消请求与当前订阅不匹配",
                409,
            )
            if current_action.status == "SUCCEEDED":
                return actions.view(current_action)
            if current_action.status in {"AUTHORIZED", "EXECUTING", "RECONCILING"}:
                return actions.view(current_action)
            if current_action.status in {"WAITING_CONFIRMATION", "WAITING_VERIFICATION"}:
                if current_action.expires_at is None or aware(current_action.expires_at) > now():
                    return actions.view(current_action)
                current_action.status = "CANCELLED"
                current_action.error_code = "ACTION_EXPIRED"
                audit(self.db, user, "ACTION_EXPIRED", current_action)

        require(
            row.status == "VERIFIED",
            "SUBSCRIPTION_NOT_VERIFIED",
            "只有已核实的 Demo 订阅可以取消",
            409,
        )
        merchant = self.db.get(Merchant, row.merchant_id)
        payload = {
            "subscription_id": row.id,
            "merchant": merchant.name,
            "expected_amount": str(row.expected_amount),
            "cadence": row.cadence,
            "next_charge_at": row.next_charge_at.isoformat()
            if row.next_charge_at
            else None,
            "demo_only": True,
            "subscription_snapshot": {
                "merchant_id": merchant.id,
                "merchant": merchant.name,
                "expected_amount": str(row.expected_amount),
                "cadence": row.cadence,
                "next_charge_at": row.next_charge_at.isoformat()
                if row.next_charge_at
                else None,
            },
        }
        action = actions.create(
            user, "subscription_cancel", payload, key, commit=False
        )
        row.action_id = action.id
        row.updated_at = now()
        self.db.commit()
        return actions.view(action)

    def execute_cancel(self, user, action):
        row = owned(self.db, Subscription, action.payload["subscription_id"], user)
        require(
            row.action_id == action.id,
            "SUBSCRIPTION_CHANGED",
            "订阅取消请求已变化",
            409,
        )
        if row.status == "CANCELLED":
            return {"subscription_id": row.id, "cancelled": True, "replayed": True}
        require(
            row.status == "VERIFIED",
            "SUBSCRIPTION_NOT_VERIFIED",
            "订阅不再处于可取消状态",
            409,
        )
        merchant = self.db.get(Merchant, row.merchant_id)
        snapshot = action.payload.get("subscription_snapshot")
        if snapshot is not None:
            current = {
                "merchant_id": merchant.id,
                "merchant": merchant.name,
                "expected_amount": str(row.expected_amount),
                "cadence": row.cadence,
                "next_charge_at": row.next_charge_at.isoformat()
                if row.next_charge_at
                else None,
            }
            require(
                fingerprint(current) == fingerprint(snapshot),
                "SUBSCRIPTION_CHANGED",
                "订阅信息在确认期间发生变化，请重新发起取消请求",
                409,
            )
        result = self.adapter.cancel_subscription(merchant, row)
        row.status = "CANCELLED"
        row.cancelled_at = now()
        row.next_charge_at = None
        row.updated_at = now()
        self.db.execute(
            SubscriptionBudgetRule.__table__.update()
            .where(SubscriptionBudgetRule.user_id == user.id,
                   SubscriptionBudgetRule.status == "ACTIVE")
            .values(last_evaluated_on=None)
        )
        audit(self.db, user, "SUBSCRIPTION_CANCELLED", action, subscription_id=row.id)
        return result

    def reconcile_cancel(self, user, action):
        row = owned(self.db, Subscription, action.payload["subscription_id"], user)
        require(
            row.action_id == action.id and row.status == "CANCELLED",
            "MANUAL_RECONCILIATION_REQUIRED",
            "Demo 商户取消结果尚未确认",
            409,
        )
        return {"subscription_id": row.id, "cancelled": True}

    def demo_charge(self, user, subscription_id):
        lock_user(self.db, user)
        row = owned(self.db, Subscription, subscription_id, user)
        if row.status == "CANCELLED":
            audit(
                self.db,
                user,
                "DEMO_SUBSCRIPTION_CHARGE_BLOCKED",
                subscription_id=row.id,
                reason="SUBSCRIPTION_CANCELLED",
            )
            self.db.commit()
            raise DomainError(
                "SUBSCRIPTION_CHARGE_BLOCKED",
                "该 Demo 订阅已取消，扣费已拒绝",
                409,
            )
        require(
            row.status == "VERIFIED",
            "SUBSCRIPTION_NOT_VERIFIED",
            "订阅尚未核实，不能验证扣费",
            409,
        )
        audit(
            self.db,
            user,
            "DEMO_SUBSCRIPTION_CHARGE_ALLOWED",
            subscription_id=row.id,
        )
        self.db.commit()
        return {
            "subscription_id": row.id,
            "allowed": True,
            "funds_moved": False,
            "message": "仅验证 Demo 商户取消规则，未提交真实资金扣款",
        }
