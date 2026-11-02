"""Subscription forecasts, user-owned reminder rules and in-app delivery."""
import calendar
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from clients.fineract import FineractError
from core.errors import DomainError, require
from core.security import SHANGHAI, aware, fingerprint, now
from models import (
    Merchant, Subscription, SubscriptionAgentResult, SubscriptionBudgetRule,
    SubscriptionClarification, SubscriptionMutationKey, SubscriptionNotification,
    SubscriptionReminderRule, User,
)
from services.account_service import AccountService
from services.common import audit, lock_user, owned, safe_json
from services.subscription_service import SubscriptionService, normalized_merchant
from services.transaction_service import TransactionService

CENT = Decimal("0.01")
ALLOWED_LEADS = {1, 3, 7}


def _month_dates(month: str) -> tuple[date, date]:
    try:
        year, number = (int(part) for part in month.split("-", 1))
        start = date(year, number, 1)
    except (ValueError, AttributeError):
        raise DomainError("INVALID_MONTH", "月份格式应为 YYYY-MM", 422)
    return start, date(year, number, calendar.monthrange(year, number)[1])


def _add_months(anchor: date, offset: int, anchor_day: int) -> date:
    index = anchor.year * 12 + anchor.month - 1 + offset
    year, month0 = divmod(index, 12)
    month = month0 + 1
    return date(year, month, min(anchor_day, calendar.monthrange(year, month)[1]))


def _add_years(anchor: date, offset: int, month: int, day: int) -> date:
    year = anchor.year + offset
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _month_for(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def _amount(value) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(CENT)
    except Exception as exc:
        raise DomainError("INVALID_AMOUNT", "金额格式无效", 422) from exc
    require(amount.is_finite() and amount > 0, "INVALID_AMOUNT", "金额必须大于0", 422)
    return amount


class SubscriptionPlanningService:
    def __init__(self, db, fineract, settings):
        self.db, self.fineract, self.settings = db, fineract, settings
        self.subscriptions = SubscriptionService(db, fineract, settings)
        self.transactions = TransactionService(db, fineract, settings)

    def forecast(self, user, *, month=None, from_date=None, to_date=None, today=None):
        today = today or now().astimezone(SHANGHAI).date()
        if month is not None:
            require(from_date is None and to_date is None, "INVALID_RANGE", "月份与起止日期不能同时指定", 422)
            start, end = _month_dates(month)
        elif from_date is None and to_date is None:
            start, end = today, today + timedelta(days=3)
        else:
            require(from_date is not None and to_date is not None, "INVALID_RANGE", "起止日期必须同时提供", 422)
            start, end = from_date, to_date
        require(start <= end, "INVALID_RANGE", "开始日期不能晚于结束日期", 422)
        require((end - start).days < 366, "INVALID_RANGE", "查询范围最多366天", 422)

        rows = self.db.scalars(
            select(Subscription)
            .where(Subscription.user_id == user.id, Subscription.status == "VERIFIED")
            .order_by(Subscription.next_charge_at, Subscription.id)
        ).all()
        items, needs_review = [], []
        complete = True
        for row in rows:
            if row.next_charge_at is None:
                needs_review.append({"subscription_id": row.id, "reason": "MISSING_PREDICTION"})
                complete = False
                continue
            if row.next_charge_at < today:
                needs_review.append({
                    **self.subscriptions.view(row),
                    "reason": "PREDICTION_EXPIRED",
                })
                complete = False
                continue
            merchant = self.db.get(Merchant, row.merchant_id)
            anchor_day = row.next_charge_at.day
            anchor_month = row.next_charge_at.month
            evidence_rows = (row.evidence or {}).get("occurrences") or []
            if evidence_rows:
                try:
                    anchor = date.fromisoformat(evidence_rows[-1]["occurred_on"])
                    anchor_day, anchor_month = anchor.day, anchor.month
                except (KeyError, ValueError, TypeError):
                    pass
            charge = row.next_charge_at
            offset = 0
            while charge < start:
                offset += 1
                if row.cadence == "MONTHLY":
                    charge = _add_months(row.next_charge_at, offset, anchor_day)
                elif row.cadence == "YEARLY":
                    charge = _add_years(row.next_charge_at, offset, anchor_month, anchor_day)
                else:
                    complete = False
                    break
                if offset > 13:
                    break
            while start <= charge <= end:
                if merchant:
                    items.append({
                        "subscription_id": row.id,
                        "merchant": merchant.name,
                        "cadence": row.cadence,
                        "amount": row.expected_amount,
                        "charge_date": charge,
                        "label": "预计",
                    })
                offset += 1
                if row.cadence == "MONTHLY":
                    charge = _add_months(row.next_charge_at, offset, anchor_day)
                elif row.cadence == "YEARLY":
                    charge = _add_years(row.next_charge_at, offset, anchor_month, anchor_day)
                else:
                    complete = False
                    break
                if offset > 13:
                    break
        items.sort(key=lambda item: (item["charge_date"], item["subscription_id"]))
        return safe_json({
            "as_of": today,
            "timezone": "Asia/Shanghai",
            "from_date": start,
            "to_date": end,
            "last_scan_at": self.subscriptions.last_scan_at(user),
            "items": items,
            "projected_total": sum((Decimal(str(item["amount"])) for item in items), Decimal("0.00")),
            "needs_review": needs_review,
            "complete": complete,
            "status": "complete" if complete else "incomplete",
        })

    def _actual_spend(self, user, month: str):
        start, end = _month_dates(month)
        all_subscriptions = self.db.scalars(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status.in_({"VERIFIED", "CANCELLED"}),
            )
        ).all()
        by_merchant = {}
        for row in all_subscriptions:
            merchant = self.db.get(Merchant, row.merchant_id)
            if merchant:
                by_merchant.setdefault(normalized_merchant(merchant.name), set()).add(row.id)
        accounts = AccountService(self.fineract).list_accounts(user)
        transactions = []
        for account in accounts:
            transactions.extend(self.transactions.all(user, account.id, start, end))
        seen, entries, uncertain = set(), [], False
        total = Decimal("0.00")
        for row in transactions:
            identity = (row["account_id"], row["transaction_id"])
            if identity in seen:
                continue
            seen.add(identity)
            if row.get("reversed") or row.get("kind") != "expense" or not row.get("merchant"):
                continue
            merchant_key = normalized_merchant(row["merchant"])
            matches = by_merchant.get(merchant_key, set())
            if not matches:
                continue
            if len(matches) != 1:
                uncertain = True
                continue
            amount = Decimal(str(row["amount"]))
            total += amount
            entries.append({
                "subscription_id": next(iter(matches)),
                "merchant": row["merchant"], "date": row["date"],
                "amount": amount, "account_id": row["account_id"],
                "transaction_id": row["transaction_id"],
            })
        entries.sort(key=lambda item: (item["date"], item["account_id"], item["transaction_id"]))
        return {"total": total, "items": entries, "complete": not uncertain,
                "status": "ambiguous_matches" if uncertain else "complete"}

    def evaluate_budget(self, user, budget: SubscriptionBudgetRule, *, today=None):
        today = today or now().astimezone(SHANGHAI).date()
        forecast = self.forecast(user, month=budget.month, today=today)
        start, end = _month_dates(budget.month)
        try:
            actual = self._actual_spend(user, budget.month)
            previous = self._actual_spend(user, _month_for(start - timedelta(days=1)))
            history_status = previous["status"]
            actual_status = actual["status"]
        except (FineractError, DomainError) as exc:
            actual = {"total": None, "items": [], "complete": False, "status": "unavailable"}
            previous = {"total": None, "items": [], "complete": False, "status": "unavailable"}
            history_status = actual_status = "unavailable"

        forecast_items = forecast["items"]
        projected = [item for item in forecast_items if date.fromisoformat(item["charge_date"]) >= today]
        actual_sub_ids = {item["subscription_id"] for item in actual["items"]}
        # An observed debit in the target month accounts for that subscription's
        # monthly occurrence and suppresses a duplicate estimate for that month.
        projected = [item for item in projected if item["subscription_id"] not in actual_sub_ids]
        projected_total = sum((Decimal(str(item["amount"])) for item in projected), Decimal("0.00"))
        complete = bool(forecast["complete"] and actual["complete"] and previous["complete"])
        known_total = None if actual["total"] is None else actual["total"] + projected_total
        over = ((known_total > budget.amount) if known_total is not None
                else projected_total > budget.amount)
        options = {}
        for item in projected:
            key = item["subscription_id"]
            current = options.setdefault(key, {
                "subscription_id": key, "merchant": item["merchant"],
                "amount": Decimal("0.00"), "demo_cancellable": False,
            })
            current["amount"] += Decimal(str(item["amount"]))
            sub = self.db.get(Subscription, key)
            merchant = self.db.get(Merchant, sub.merchant_id) if sub else None
            current["demo_cancellable"] = bool(merchant and merchant.adapter_type == "demo_subscription")
        suggestions = sorted(options.values(), key=lambda item: (-item["amount"], item["subscription_id"]))
        result = safe_json({
            "month": budget.month, "budget": budget.amount,
            "actual_total": actual["total"], "actual_status": actual_status,
            "projected_remaining": projected_total,
            "projected_items": projected,
            "known_total": known_total,
            "previous_month": _month_for(start - timedelta(days=1)),
            "previous_actual_total": previous["total"], "history_status": history_status,
            "complete": complete, "needs_review": forecast["needs_review"],
            "over_budget": over,
            "under_budget_confirmed": bool(complete and known_total is not None and known_total <= budget.amount),
            "suggestions": suggestions,
        })
        self._upsert_budget_notification(user, budget, result)
        budget.last_evaluated_on = today
        self.db.flush()
        return result

    def evaluate_active_budgets(self, user, *, commit=True):
        today = now().astimezone(SHANGHAI).date()
        rows = self.db.scalars(select(SubscriptionBudgetRule).where(
            SubscriptionBudgetRule.user_id == user.id,
            SubscriptionBudgetRule.status == "ACTIVE",
        )).all()
        results = [self.evaluate_budget(user, row, today=today) for row in rows]
        if commit and rows:
            self.db.commit()
        return results

    def _upsert_budget_notification(self, user, budget, result):
        key = f"budget:{budget.month}"
        row = self.db.scalar(select(SubscriptionNotification).where(
            SubscriptionNotification.user_id == user.id,
            SubscriptionNotification.dedupe_key == key,
        ))
        if result["over_budget"]:
            payload = {"title": f"{budget.month} 订阅预计支出超出预算",
                       "message": "已知金额已超过预算；数据完整性请查看详情。",
                       "budget": result}
            if row is None:
                row = SubscriptionNotification(user_id=user.id, kind="BUDGET",
                    dedupe_key=key, payload=payload, status="ACTIVE")
                self.db.add(row)
            else:
                if row.status in {"RESOLVED", "INVALIDATED"}:
                    row.read_at = None
                row.payload, row.status = payload, "ACTIVE"
                row.invalidated_at = None
        elif row is not None:
            row.payload = {"title": f"{budget.month} 订阅预算监测已更新", "budget": result}
            row.status = "RESOLVED"
            row.invalidated_at = None

    def create_result(self, user, kind, payload):
        row = SubscriptionAgentResult(
            user_id=user.id, kind=kind, payload=payload,
            expires_at=now() + timedelta(minutes=30),
        )
        self.db.add(row)
        self.db.flush()
        return row.id

    def execute_agent_query(self, user, request):
        """Execute only the query frozen into a confirmed YELLOW Action."""
        query_kind = request.get("query_kind")
        if query_kind == "FORECAST":
            start = date.fromisoformat(request["from_date"])
            end = date.fromisoformat(request["to_date"])
            as_of = date.fromisoformat(request["as_of"])
            result = self.forecast(user, from_date=start, to_date=end, today=as_of)
            amount_gt = request.get("amount_gt")
            if amount_gt is not None:
                threshold = Decimal(str(amount_gt))
                result["items"] = [item for item in result["items"]
                                   if Decimal(str(item["amount"])) > threshold]
                result["projected_total"] = str(sum(
                    (Decimal(str(item["amount"])) for item in result["items"]),
                    Decimal("0.00"),
                ))
            result["filters"] = {"amount_gt": str(amount_gt) if amount_gt is not None else None}
            result_id = self.create_result(user, "forecast", result)
            return {"result_id": result_id, "result_kind": "forecast"}

        if query_kind == "RULES":
            data = {
                "reminder_rules": self.list_reminder_rules(user),
                "budget_rules": self.list_budget_rules(user),
            }
            result_id = self.create_result(user, "rules", data)
            return {"result_id": result_id, "result_kind": "rules"}

        if query_kind in {"LIST", "DETAIL"}:
            rows = self.subscriptions.list(user)
            if query_kind == "DETAIL":
                target = normalized_merchant(request.get("merchant", ""))
                rows = [row for row in rows
                        if normalized_merchant(row.get("merchant", "")) == target]
                if len(rows) == 1:
                    rows = [self.subscriptions.detail(user, rows[0]["id"])]
            result_kind = "subscriptions" if query_kind == "LIST" else "subscription_detail"
            result = {
                "items": rows,
                "status": "NOT_FOUND" if query_kind == "DETAIL" and not rows else (
                    "AMBIGUOUS" if query_kind == "DETAIL" and len(rows) > 1 else "READY"
                ),
            }
            result_id = self.create_result(user, result_kind, result)
            return {"result_id": result_id, "result_kind": result_kind}

        raise DomainError("SUBSCRIPTION_QUERY_UNSUPPORTED", "不支持这类订阅查询", 422)

    def get_result(self, user, result_id):
        row = owned(self.db, SubscriptionAgentResult, result_id, user)
        require(aware(row.expires_at) > now(), "SUBSCRIPTION_RESULT_EXPIRED", "续费结果已过期，请重新查询", 410)
        return safe_json({"id": row.id, "kind": row.kind, "created_at": row.created_at,
                          "expires_at": row.expires_at, "data": row.payload})

    def _record_key(self, user, key, body_hash, resource_type, resource_id):
        self.db.add(SubscriptionMutationKey(user_id=user.id, idempotency_key=key,
            request_hash=body_hash, resource_type=resource_type, resource_id=resource_id))

    def _replay_key(self, user, key, body_hash):
        record = self.db.scalar(select(SubscriptionMutationKey).where(
            SubscriptionMutationKey.user_id == user.id,
            SubscriptionMutationKey.idempotency_key == key,
        ))
        if record is None:
            return None
        require(record.request_hash == body_hash, "IDEMPOTENCY_CONFLICT", "同一幂等键已用于不同请求", 409)
        model = SubscriptionReminderRule if record.resource_type == "reminder" else SubscriptionBudgetRule
        return owned(self.db, model, record.resource_id, user)

    @staticmethod
    def _validate_leads(lead_days):
        require(bool(lead_days) and len(lead_days) == len(set(lead_days))
                and set(lead_days).issubset(ALLOWED_LEADS),
                "INVALID_LEAD_DAYS", "提前天数只支持1、3、7天及其组合", 422)
        return sorted(lead_days)

    def _rule_payload(self, user, scope, subscription_id, amount_gt, month, lead_days):
        require(scope in {"ALL_VERIFIED", "SUBSCRIPTION", "AMOUNT_GT"}, "INVALID_SCOPE", "提醒范围无效", 422)
        if scope == "SUBSCRIPTION":
            require(subscription_id is not None and amount_gt is None, "INVALID_SCOPE", "单个订阅提醒参数无效", 422)
        elif scope == "AMOUNT_GT":
            require(amount_gt is not None and subscription_id is None, "INVALID_SCOPE", "金额筛选提醒参数无效", 422)
        else:
            require(subscription_id is None and amount_gt is None, "INVALID_SCOPE", "全部订阅提醒参数无效", 422)
        if subscription_id:
            owned(self.db, Subscription, subscription_id, user)
        if amount_gt is not None:
            amount_gt = _amount(amount_gt)
        if month is not None:
            _month_dates(month)
        return {"scope": scope, "subscription_id": subscription_id,
                "amount_gt": str(amount_gt) if amount_gt is not None else None,
                "month": month, "lead_days": self._validate_leads(lead_days)}

    def create_reminder_rule(self, user, *, scope, subscription_id=None,
                             amount_gt=None, month=None, lead_days, key):
        payload = self._rule_payload(user, scope, subscription_id, amount_gt, month, lead_days)
        request_hash = fingerprint(payload)
        lock_user(self.db, user)
        replay = self._replay_key(user, key, request_hash)
        if replay:
            return self.rule_view(replay), True
        if subscription_id is not None:
            current = owned(self.db, Subscription, subscription_id, user)
            require(current.status == "VERIFIED", "SUBSCRIPTION_NOT_VERIFIED",
                    "仅能为本人已核实订阅设置提醒", 409)
        active_rules = self.db.scalars(select(SubscriptionReminderRule).where(
            SubscriptionReminderRule.user_id == user.id,
            SubscriptionReminderRule.status == "ACTIVE",
        )).all()
        rule = next((row for row in active_rules if row.scope == scope
            and row.subscription_id == subscription_id
            and row.amount_gt == (Decimal(payload["amount_gt"]) if payload["amount_gt"] else None)
            and row.month == month and row.lead_days == payload["lead_days"]), None)
        reused = rule is not None
        if rule is None:
            stored = {**payload, "amount_gt": Decimal(payload["amount_gt"])
                      if payload["amount_gt"] else None}
            rule = SubscriptionReminderRule(user_id=user.id, **stored,
                status="ACTIVE", idempotency_key=key, request_hash=request_hash)
            self.db.add(rule)
            self.db.flush()
        self._record_key(user, key, request_hash, "reminder", rule.id)
        audit(self.db, user, "SUBSCRIPTION_REMINDER_RULE_CREATED" if not reused else "SUBSCRIPTION_REMINDER_RULE_REUSED",
              resource_type="subscription_reminder_rule", resource_id=rule.id,
              scope=scope, month=month, lead_days=payload["lead_days"])
        self.db.commit()
        return self.rule_view(rule), reused

    def rule_view(self, row):
        return safe_json({key: getattr(row, key) for key in (
            "id", "scope", "subscription_id", "amount_gt", "month", "lead_days",
            "status", "created_at", "updated_at")})

    def list_reminder_rules(self, user):
        return [self.rule_view(row) for row in self.db.scalars(select(SubscriptionReminderRule)
            .where(SubscriptionReminderRule.user_id == user.id)
            .order_by(SubscriptionReminderRule.created_at.desc(), SubscriptionReminderRule.id))]

    def get_reminder_rule(self, user, rule_id):
        return self.rule_view(owned(self.db, SubscriptionReminderRule, rule_id, user))

    def command_reminder_rule(self, user, rule_id, command, key):
        lock_user(self.db, user)
        body_hash = fingerprint({"rule_id": rule_id, "command": command})
        replay = self._replay_key(user, key, body_hash)
        if replay:
            return self.rule_view(replay)
        row = owned(self.db, SubscriptionReminderRule, rule_id, user)
        targets = {"pause": "PAUSED", "resume": "ACTIVE", "delete": "DELETED"}
        require(command in targets, "INVALID_COMMAND", "规则操作无效", 422)
        row.status = targets[command]
        row.updated_at = now()
        if row.status != "ACTIVE":
            self._invalidate_stale_reminders(user)
        self._record_key(user, key, body_hash, "reminder", row.id)
        audit(self.db, user, "SUBSCRIPTION_REMINDER_RULE_" + command.upper(),
              resource_type="subscription_reminder_rule", resource_id=row.id)
        self.db.commit()
        return self.rule_view(row)

    def edit_reminder_rule(self, user, rule_id, *, scope, subscription_id=None,
                           amount_gt=None, month=None, lead_days, key):
        payload = self._rule_payload(user, scope, subscription_id, amount_gt, month, lead_days)
        body_hash = fingerprint({"rule_id": rule_id, **payload})
        lock_user(self.db, user)
        replay = self._replay_key(user, key, body_hash)
        if replay:
            return self.rule_view(replay), True
        if subscription_id is not None:
            current = owned(self.db, Subscription, subscription_id, user)
            require(current.status == "VERIFIED", "SUBSCRIPTION_NOT_VERIFIED",
                    "仅能为本人已核实订阅设置提醒", 409)
        row = owned(self.db, SubscriptionReminderRule, rule_id, user)
        stored = {**payload, "amount_gt": Decimal(payload["amount_gt"])
                  if payload["amount_gt"] else None}
        for name, value in stored.items():
            setattr(row, name, value)
        row.status, row.updated_at = "ACTIVE", now()
        self._record_key(user, key, body_hash, "reminder", row.id)
        self._invalidate_stale_reminders(user)
        audit(self.db, user, "SUBSCRIPTION_REMINDER_RULE_UPDATED",
              resource_type="subscription_reminder_rule", resource_id=row.id)
        self.db.commit()
        return self.rule_view(row), False

    def create_clarification(self, user, payload):
        row = SubscriptionClarification(user_id=user.id, payload=payload,
            expires_at=now() + timedelta(minutes=30))
        self.db.add(row)
        self.db.flush()
        return row.id

    def complete_clarification(self, user, clarification_id, lead_days, key):
        lock_user(self.db, user)
        row = owned(self.db, SubscriptionClarification, clarification_id, user)
        require(row.status == "PENDING" and aware(row.expires_at) > now(),
                "CLARIFICATION_EXPIRED", "提醒设置确认已过期，请重新发起", 410)
        payload = dict(row.payload)
        row.status, row.consumed_at = "COMPLETED", now()
        result, reused = self.create_reminder_rule(user, **payload,
            lead_days=self._validate_leads(lead_days), key=key)
        self.db.commit()
        return result, reused

    def upsert_budget_rule(self, user, *, month, amount, key):
        _month_dates(month)
        amount = _amount(amount)
        body_hash = fingerprint({"month": month, "amount": str(amount)})
        lock_user(self.db, user)
        replay = self._replay_key(user, key, body_hash)
        if replay:
            if replay.status == "ACTIVE":
                result = self.evaluate_budget(user, replay)
                self.db.commit()
            else:
                result = safe_json({"month": replay.month, "budget": replay.amount,
                                    "status": replay.status, "complete": False,
                                    "over_budget": False, "known_total": None,
                                    "suggestions": []})
            return replay, True, result
        row = self.db.scalar(select(SubscriptionBudgetRule).where(
            SubscriptionBudgetRule.user_id == user.id,
            SubscriptionBudgetRule.month == month))
        reused = row is not None
        if row is None:
            row = SubscriptionBudgetRule(user_id=user.id, month=month,
                amount=amount, status="ACTIVE", idempotency_key=key,
                request_hash=body_hash)
            self.db.add(row)
            self.db.flush()
        else:
            row.amount, row.status = amount, "ACTIVE"
            row.updated_at = now()
        self._record_key(user, key, body_hash, "budget", row.id)
        row.last_evaluated_on = None
        result = self.evaluate_budget(user, row)
        audit(self.db, user, "SUBSCRIPTION_BUDGET_RULE_SAVED",
            resource_type="subscription_budget_rule", resource_id=row.id,
            month=month, amount=str(amount))
        self.db.commit()
        return row, reused, result

    def list_budget_rules(self, user):
        return [safe_json({"id": row.id, "month": row.month, "amount": row.amount,
            "status": row.status, "last_evaluated_on": row.last_evaluated_on,
            "created_at": row.created_at, "updated_at": row.updated_at})
            for row in self.db.scalars(select(SubscriptionBudgetRule)
                .where(SubscriptionBudgetRule.user_id == user.id)
                .order_by(SubscriptionBudgetRule.month.desc()))]

    def get_budget_rule(self, user, rule_id):
        row = owned(self.db, SubscriptionBudgetRule, rule_id, user)
        return safe_json({"id": row.id, "month": row.month, "amount": row.amount,
            "status": row.status, "last_evaluated_on": row.last_evaluated_on,
            "created_at": row.created_at, "updated_at": row.updated_at})

    def edit_budget_rule(self, user, rule_id, *, month, amount, key):
        _month_dates(month)
        amount = _amount(amount)
        body_hash = fingerprint({"rule_id": rule_id, "month": month, "amount": str(amount)})
        lock_user(self.db, user)
        replay = self._replay_key(user, key, body_hash)
        if replay:
            evaluation = self.evaluate_budget(user, replay) if replay.status == "ACTIVE" else {
                "month": replay.month, "status": replay.status, "complete": False,
                "over_budget": False, "suggestions": [],
            }
            return self.get_budget_rule(user, replay.id), True, safe_json(evaluation)
        row = owned(self.db, SubscriptionBudgetRule, rule_id, user)
        duplicate = self.db.scalar(select(SubscriptionBudgetRule.id).where(
            SubscriptionBudgetRule.user_id == user.id,
            SubscriptionBudgetRule.month == month,
            SubscriptionBudgetRule.id != row.id,
        ))
        require(duplicate is None, "BUDGET_RULE_EXISTS",
                "目标月份已存在另一条预算规则，请编辑那条规则", 409)
        old_month = row.month
        row.month, row.amount, row.status = month, amount, "ACTIVE"
        row.last_evaluated_on, row.updated_at = None, now()
        if old_month != month:
            old_notice = self.db.scalar(select(SubscriptionNotification).where(
                SubscriptionNotification.user_id == user.id,
                SubscriptionNotification.dedupe_key == f"budget:{old_month}",
            ))
            if old_notice is not None:
                old_notice.status, old_notice.invalidated_at = "INVALIDATED", now()
        self._record_key(user, key, body_hash, "budget", row.id)
        evaluation = self.evaluate_budget(user, row)
        audit(self.db, user, "SUBSCRIPTION_BUDGET_RULE_UPDATED",
            resource_type="subscription_budget_rule", resource_id=row.id,
            month=month, amount=str(amount))
        self.db.commit()
        return self.get_budget_rule(user, row.id), False, evaluation

    def command_budget_rule(self, user, rule_id, command, key):
        lock_user(self.db, user)
        body_hash = fingerprint({"rule_id": rule_id, "command": command})
        replay = self._replay_key(user, key, body_hash)
        if replay:
            return safe_json({"id": replay.id, "month": replay.month,
                              "amount": replay.amount, "status": replay.status,
                              "updated_at": replay.updated_at})
        row = owned(self.db, SubscriptionBudgetRule, rule_id, user)
        require(command in {"pause", "resume", "delete"}, "INVALID_COMMAND", "规则操作无效", 422)
        row.status = {"pause": "PAUSED", "resume": "ACTIVE", "delete": "DELETED"}[command]
        row.updated_at = now()
        if row.status == "ACTIVE":
            row.last_evaluated_on = None
            self.evaluate_budget(user, row)
        else:
            notification = self.db.scalar(select(SubscriptionNotification).where(
                SubscriptionNotification.user_id == user.id,
                SubscriptionNotification.dedupe_key == f"budget:{row.month}",
            ))
            if notification is not None:
                notification.status = "INVALIDATED"
                notification.invalidated_at = now()
        self._record_key(user, key, body_hash, "budget", row.id)
        self.db.commit()
        return safe_json({"id": row.id, "month": row.month, "amount": row.amount,
                          "status": row.status, "updated_at": row.updated_at})

    def list_notifications(self, user, *, unread_only=False):
        query = select(SubscriptionNotification).where(SubscriptionNotification.user_id == user.id)
        if unread_only:
            query = query.where(SubscriptionNotification.read_at.is_(None))
        rows = self.db.scalars(query.order_by(SubscriptionNotification.created_at.desc(),
                                              SubscriptionNotification.id).limit(100)).all()
        return [safe_json({"id": row.id, "kind": row.kind, "status": row.status,
            "payload": row.payload, "read_at": row.read_at,
            "created_at": row.created_at, "invalidated_at": row.invalidated_at}) for row in rows]

    def unread_count(self, user):
        return self.db.scalar(select(func.count()).select_from(SubscriptionNotification)
            .where(SubscriptionNotification.user_id == user.id,
                   SubscriptionNotification.read_at.is_(None))) or 0

    def mark_notification_read(self, user, notification_id):
        row = owned(self.db, SubscriptionNotification, notification_id, user)
        if row.read_at is None:
            row.read_at = now()
            self.db.commit()
        return {"id": row.id, "read": True}

    def _matching_rules(self, user, sub, charge_date, lead=None):
        candidates = self.db.scalars(select(SubscriptionReminderRule).where(
            SubscriptionReminderRule.user_id == user.id,
            SubscriptionReminderRule.status == "ACTIVE",
        )).all()
        result = []
        for rule in candidates:
            if lead is not None and lead not in rule.lead_days:
                continue
            if rule.month and rule.month != _month_for(charge_date):
                continue
            if rule.scope == "SUBSCRIPTION" and rule.subscription_id != sub.id:
                continue
            if rule.scope == "AMOUNT_GT" and not (sub.expected_amount > rule.amount_gt):
                continue
            result.append(rule)
        return result

    def tick_notifications(self, *, instant=None):
        instant = instant or now()
        local = aware(instant).astimezone(SHANGHAI)
        today = local.date()
        if local.time().replace(tzinfo=None) < time(9, 0):
            return {"reminders": 0, "budgets": 0}
        users = self.db.scalars(select(User).where(User.active.is_(True)).order_by(User.id)).all()
        reminder_count = budget_count = 0
        for user in users:
            try:
                lock_user(self.db, user)
                rules = self.db.scalars(select(SubscriptionReminderRule).where(
                    SubscriptionReminderRule.user_id == user.id,
                    SubscriptionReminderRule.status == "ACTIVE")).all()
                for rule in rules:
                    if rule.month and rule.month < _month_for(today):
                        rule.status = "EXPIRED"
                        rule.updated_at = instant
                subscriptions = self.db.scalars(select(Subscription).where(
                    Subscription.user_id == user.id,
                    Subscription.status == "VERIFIED")).all()
                for sub in subscriptions:
                    if sub.next_charge_at is None or sub.next_charge_at < today:
                        continue
                    for charge in self._next_dates(sub, today, today + timedelta(days=366)):
                        matches = self._matching_rules(user, sub, charge)
                        if not matches:
                            continue
                        due, missed_due = [], []
                        for lead in sorted({d for rule in matches for d in rule.lead_days}):
                            planned = charge - timedelta(days=lead)
                            if planned > today or (planned == today and local.time().replace(tzinfo=None) < time(9, 0)):
                                continue
                            if charge < today:
                                continue
                            (missed_due if planned < today else due).append((lead, planned))
                        deliveries = []
                        if due:
                            deliveries.extend(([(lead, planned)], False) for lead, planned in due)
                        if missed_due:
                            missed_due.sort(key=lambda item: item[1])
                            deliveries.append((missed_due, True))
                        for planned_group, missed in deliveries:
                            lead, planned = planned_group[0]
                            dedupe = f"reminder:{sub.id}:{charge.isoformat()}:{'catchup' if missed else lead}"
                            exists = self.db.scalar(select(SubscriptionNotification.id).where(
                                SubscriptionNotification.user_id == user.id,
                                SubscriptionNotification.dedupe_key == dedupe))
                            if exists:
                                continue
                            rule = matches[0]
                            merchant = self.db.get(Merchant, sub.merchant_id)
                            planned_times = [
                                datetime.combine(day, time(9), SHANGHAI).isoformat()
                                for _, day in planned_group
                            ]
                            payload = {"title": f"{merchant.name if merchant else '订阅'}预计续费提醒",
                                "message": f"预计于{charge.isoformat()}扣费，金额{Decimal(sub.expected_amount):.2f}元。",
                                "merchant": merchant.name if merchant else "订阅",
                                "amount": str(sub.expected_amount), "charge_date": charge.isoformat(),
                                "lead_days": sorted(value for value, _ in planned_group), "catch_up": missed,
                                "planned_at": planned_times[0], "original_planned_times": planned_times,
                                "subscription_id": sub.id}
                            self.db.add(SubscriptionNotification(user_id=user.id,
                                rule_id=rule.id, subscription_id=sub.id, kind="REMINDER",
                                dedupe_key=dedupe, occurrence_date=charge, lead_days=lead,
                                planned_at=datetime.combine(planned, time(9), SHANGHAI).astimezone(timezone.utc),
                                payload=payload, status="ACTIVE"))
                            reminder_count += 1
                self._invalidate_stale_reminders(user)
                budgets = self.db.scalars(select(SubscriptionBudgetRule).where(
                    SubscriptionBudgetRule.user_id == user.id,
                    SubscriptionBudgetRule.status == "ACTIVE",
                    (SubscriptionBudgetRule.last_evaluated_on.is_(None)
                     | (SubscriptionBudgetRule.last_evaluated_on < today)),
                )).all()
                for budget in budgets:
                    self.evaluate_budget(user, budget, today=today)
                    budget_count += 1
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
        return {"reminders": reminder_count, "budgets": budget_count}

    @staticmethod
    def _next_dates(sub, start, end):
        charge = sub.next_charge_at
        if charge is None or charge < start:
            return []
        evidence = (sub.evidence or {}).get("occurrences") or []
        anchor_day, anchor_month = charge.day, charge.month
        if evidence:
            try:
                anchor = date.fromisoformat(evidence[-1]["occurred_on"])
                anchor_day, anchor_month = anchor.day, anchor.month
            except (KeyError, ValueError, TypeError):
                pass
        offset, result = 0, []
        while charge <= end and offset <= 13:
            if charge >= start:
                result.append(charge)
            offset += 1
            charge = (_add_months(sub.next_charge_at, offset, anchor_day)
                      if sub.cadence == "MONTHLY" else
                      _add_years(sub.next_charge_at, offset, anchor_month, anchor_day)
                      if sub.cadence == "YEARLY" else end + timedelta(days=1))
        return result

    def _invalidate_stale_reminders(self, user):
        rows = self.db.scalars(select(SubscriptionNotification).where(
            SubscriptionNotification.user_id == user.id,
            SubscriptionNotification.kind == "REMINDER",
            SubscriptionNotification.status == "ACTIVE",
        )).all()
        for notification in rows:
            sub = self.db.get(Subscription, notification.subscription_id) if notification.subscription_id else None
            charge = notification.occurrence_date
            if (sub and sub.status == "VERIFIED" and charge
                    and charge < now().astimezone(SHANGHAI).date()):
                continue
            predicted = bool(sub and charge and sub.status == "VERIFIED"
                             and charge in self._next_dates(sub, charge, charge))
            rules = self._matching_rules(user, sub, charge, notification.lead_days) if predicted else []
            if not rules:
                notification.status = "INVALIDATED"
                notification.invalidated_at = now()
            else:
                merchant = self.db.get(Merchant, sub.merchant_id)
                if merchant:
                    payload = dict(notification.payload or {})
                    payload.update({
                        "merchant": merchant.name,
                        "amount": str(sub.expected_amount),
                        "message": f"预计于{charge.isoformat()}扣费，金额{Decimal(sub.expected_amount):.2f}元。",
                    })
                    notification.payload = payload
                    notification.rule_id = rules[0].id

