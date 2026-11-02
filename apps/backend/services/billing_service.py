import calendar
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median
from sqlalchemy import select
from core.errors import require
from core.security import fingerprint, now, SHANGHAI
from models import Annotation, AnomalyReview, BillReport, Category, ClassificationRule
from services.account_service import AccountService
from services.common import owned, lock_user, row_dict, safe_json, audit
from services.transaction_service import TransactionService

RULE_VERSION = "billing-v1"


def period_range(period):
    parts = period.split("-")
    year = int(parts[0])
    require(1900 <= year <= 9998, "INVALID_DATE", "年份超出范围")
    if len(parts) == 1:
        return date(year, 1, 1), date(year, 12, 31)
    month = int(parts[1])
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


class BillingService:
    def __init__(self, db, fineract, settings):
        self.db, self.fineract, self.settings = db, fineract, settings
        self.transactions = TransactionService(db, fineract, settings)

    def list_resources(self, user, model):
        return [
            row_dict(r)
            for r in self.db.scalars(select(model).where(model.user_id == user.id))
        ]

    def save_category(self, user, data, id_=None):
        lock_user(self.db, user)
        row = owned(self.db, Category, id_, user) if id_ else Category(user_id=user.id)
        duplicate = self.db.scalar(
            select(Category).where(
                Category.user_id == user.id, Category.name == data.name
            )
        )
        require(
            not duplicate or duplicate.id == row.id,
            "CATEGORY_EXISTS",
            "类别名称重复",
            409,
        )
        row.name = data.name
        self.db.add(row)
        self.db.flush()
        audit(
            self.db,
            user,
            "CATEGORY_CREATED" if id_ is None else "CATEGORY_UPDATED",
            resource_type="category",
            resource_id=row.id,
            changed_fields=["name"],
        )
        self.db.commit()
        return row_dict(row)

    def save_rule(self, user, data, id_=None):
        lock_user(self.db, user)
        owned(self.db, Category, data.category_id, user)
        row = (
            owned(self.db, ClassificationRule, id_, user)
            if id_
            else ClassificationRule(user_id=user.id)
        )
        previous = {
            "category_id": row.category_id,
            "field": row.field,
            "contains": row.contains,
            "priority": row.priority,
        } if id_ else {}
        for k, v in data.model_dump().items():
            setattr(row, k, v)
        self.db.add(row)
        self.db.flush()
        values = data.model_dump()
        audit(
            self.db,
            user,
            "CLASSIFICATION_RULE_CREATED" if id_ is None else "CLASSIFICATION_RULE_UPDATED",
            resource_type="classification_rule",
            resource_id=row.id,
            changed_fields=[
                key for key, value in values.items() if previous.get(key) != value
            ] if id_ else list(values),
        )
        self.db.commit()
        return row_dict(row)

    def annotate(self, user, data, id_=None):
        lock_user(self.db, user)
        self.transactions.detail(user, data.account_id, data.transaction_id)
        if data.category_id:
            owned(self.db, Category, data.category_id, user)
        row = (
            owned(self.db, Annotation, id_, user)
            if id_
            else self.db.scalar(
                select(Annotation).where(
                    Annotation.user_id == user.id,
                    Annotation.account_id == data.account_id,
                    Annotation.transaction_id == data.transaction_id,
                )
            )
        )
        if id_:
            duplicate = self.db.scalar(
                select(Annotation).where(
                    Annotation.user_id == user.id,
                    Annotation.account_id == data.account_id,
                    Annotation.transaction_id == data.transaction_id,
                    Annotation.id != id_,
                )
            )
            require(not duplicate, "ANNOTATION_EXISTS", "该交易已有标注", 409)
        row = row or Annotation(user_id=user.id)
        created = row.id is None
        previous = {
            "category_id": row.category_id,
            "merchant": row.merchant,
            "note": row.note,
        } if not created else {}
        for k, v in data.model_dump().items():
            setattr(row, k, v)
        self.db.add(row)
        self.db.flush()
        values = data.model_dump()
        audit(
            self.db,
            user,
            "TRANSACTION_ANNOTATION_CREATED" if created else "TRANSACTION_ANNOTATION_UPDATED",
            resource_type="transaction_annotation",
            resource_id=row.id,
            account_id=row.account_id,
            transaction_id=row.transaction_id,
            changed_fields=[
                key for key, value in values.items()
                if key not in {"account_id", "transaction_id"}
                and previous.get(key) != value
            ] if not created else ["category_id", "merchant", "note"],
        )
        self.db.commit()
        return row_dict(row)

    def delete(self, user, model, id_):
        lock_user(self.db, user)
        row = owned(self.db, model, id_, user)
        if model is Category:
            referenced = self.db.scalar(
                select(Annotation.id).where(Annotation.category_id == id_)
            ) or self.db.scalar(
                select(ClassificationRule.id).where(
                    ClassificationRule.category_id == id_
                )
            )
            require(not referenced, "CATEGORY_IN_USE", "类别仍被引用", 409)
        resource_type, event = {
            Category: ("category", "CATEGORY_DELETED"),
            ClassificationRule: ("classification_rule", "CLASSIFICATION_RULE_DELETED"),
            Annotation: ("transaction_annotation", "TRANSACTION_ANNOTATION_DELETED"),
        }.get(model, (model.__tablename__, "BILLING_RESOURCE_DELETED"))
        audit_data = {}
        if model is Annotation:
            audit_data = {
                "account_id": row.account_id,
                "transaction_id": row.transaction_id,
            }
        audit(
            self.db,
            user,
            event,
            resource_type=resource_type,
            resource_id=str(row.id),
            **audit_data,
        )
        self.db.delete(row)
        self.db.commit()
        return {"deleted": True}

    def account_scope(self, user, account_id=None):
        accounts = AccountService(self.fineract)
        if account_id is not None:
            accounts.get_account(user, account_id)
            return [account_id]
        return [row.id for row in accounts.list_accounts(user)]

    def scoped_transactions(self, user, account_id, start, end):
        account_ids = self.account_scope(user, account_id)
        rows = []
        for current_id in account_ids:
            rows.extend(self.transactions.all(user, current_id, start, end))
            require(
                len(rows) <= self.settings.max_report_transactions,
                "REPORT_TOO_LARGE",
                "交易过多，请缩小查询范围",
                422,
            )
        return account_ids, rows

    def statistics(self, user, account_id, start, end, include_private_counts=False):
        account_ids, rows = self.scoped_transactions(user, account_id, start, end)
        totals = defaultdict(lambda: Decimal(0))
        categories = defaultdict(lambda: Decimal(0))
        months = defaultdict(lambda: defaultdict(lambda: Decimal(0)))
        directions = defaultdict(lambda: defaultdict(lambda: Decimal(0)))
        count = 0
        expense_count = 0
        category_counts = defaultdict(int)
        for r in rows:
            if r["reversed"]:
                continue
            count += 1
            amount = Decimal(r["amount"])
            kind = r["kind"]
            for component, value in r["components"].items():
                totals[component] += Decimal(value)
                months[r["date"][:7]][component] += Decimal(value)
                directions[r["direction"]][component] += Decimal(value)
            if kind == "expense":
                categories[r["category"]] += amount
                expense_count += 1
                category_counts[r["category"]] += 1
        return safe_json(
            {
                "account_id": account_id,
                "account_ids": account_ids,
                "complete": True,
                "from_date": start,
                "to_date": end,
                "currency": "CNY",
                "totals": dict(totals),
                "direction_totals": dict(directions),
                "categories": dict(categories),
                "monthly": dict(months),
                "transaction_count": count,
                "data_cutoff": now(),
                "rule_version": RULE_VERSION,
                "configuration_hash": fingerprint(
                    {
                        "categories": self.list_resources(user, Category),
                        "rules": self.list_resources(user, ClassificationRule),
                        "annotations": self.list_resources(user, Annotation),
                    }
                ),
                "snapshot_atomic": False,
                **({"_privacy_expense_count": expense_count, "_privacy_category_counts": dict(category_counts)} if include_private_counts else {}),
            }
        )

    def anomalies(self, user, account_id, start, end, include_metadata=False, **detection_options):
        from services.anomaly_detection_service import AnomalyDetectionService
        result = AnomalyDetectionService(self).analyze(user, account_id, start, end, **detection_options)
        return result if include_metadata or account_id is None else result["items"]

    def rule_anomalies(self, user, account_id, start, end, *, snapshot=None):
        # Detection passes its already-authorized complete request snapshot.
        account_ids, rows = snapshot if snapshot is not None else self.scoped_transactions(
            user, account_id, start - timedelta(days=90), end
        )
        expenses = [r for r in rows if not r["reversed"] and r["kind"] == "expense"]
        found = []
        grouped = defaultdict(list)
        for r in expenses:
            day = date.fromisoformat(r["date"])
            amount = Decimal(r["amount"])
            if start <= day <= end:
                baseline = [
                    Decimal(v["amount"])
                    for v in expenses
                    if day - timedelta(days=90) <= date.fromisoformat(v["date"]) < day
                    and v["category"] == r["category"]
                ]
                if (
                    amount >= 1000
                    and len(baseline) >= 10
                    and amount > median(baseline) * 3
                ):
                    found.append(
                        {
                            "rule": "LARGE_V1",
                            "transaction_ids": [r["transaction_id"]],
                            "transactions": [
                                {
                                    "account_id": r["account_id"],
                                    "transaction_id": r["transaction_id"],
                                }
                            ],
                            "evidence": {
                                "median": str(median(baseline)),
                                "samples": len(baseline),
                                "amount": r["amount"],
                            },
                        }
                    )
                if r["merchant"]:
                    grouped[(r["date"], r["merchant"], amount)].append(
                        {
                            "account_id": r["account_id"],
                            "transaction_id": r["transaction_id"],
                        }
                    )
        for (day, merchant, amount), transactions in grouped.items():
            if len(transactions) > 1:
                transactions = sorted(
                    transactions,
                    key=lambda row: (row["account_id"], row["transaction_id"]),
                )
                found.append(
                    {
                        "rule": "DUPLICATE_V1",
                        "transaction_ids": sorted(
                            row["transaction_id"] for row in transactions
                        ),
                        "transactions": transactions,
                        "evidence": {
                            "date": day,
                            "merchant": merchant,
                            "amount": str(amount),
                        },
                    }
                )
        reviews = {
            r.anomaly_key: r.status
            for r in self.db.scalars(
                select(AnomalyReview).where(AnomalyReview.user_id == user.id)
            )
        }
        for item in found:
            identity = {
                "account": account_id,
                "rule": item["rule"],
                "ids": item["transaction_ids"],
            }
            if account_id is None:
                identity = {
                    "accounts": account_ids,
                    "rule": item["rule"],
                    "transactions": item["transactions"],
                }
            item["anomaly_key"] = fingerprint(identity)
            item["status"] = reviews.get(item["anomaly_key"], "unreviewed")
            item["candidate_only"] = True
        if account_id is not None:
            return found
        return {
            "account_id": account_id,
            "account_ids": account_ids,
            "complete": True,
            "from_date": start,
            "to_date": end,
            "data_cutoff": now(),
            "items": found,
        }

    def review(self, user, data):
        lock_user(self.db, user)
        row = self.db.scalar(
            select(AnomalyReview).where(
                AnomalyReview.user_id == user.id,
                AnomalyReview.anomaly_key == data.anomaly_key,
            )
        )
        created = row is None
        previous_status = row.status if row is not None else "unreviewed"
        row = row or AnomalyReview(user_id=user.id, anomaly_key=data.anomaly_key)
        if previous_status == data.status:
            return row_dict(row)
        row.status = data.status
        self.db.add(row)
        audit(
            self.db,
            user,
            "ANOMALY_REVIEWED" if created else "ANOMALY_REVIEW_CHANGED",
            resource_type="anomaly_review",
            resource_id=data.anomaly_key,
            previous_status=previous_status,
            status=data.status,
        )
        self.db.commit()
        return row_dict(row)

    def report(self, user, request):
        lock_user(self.db, user)
        start, end = period_range(request.period)
        cutoff = min(end, now().astimezone(SHANGHAI).date())
        require(start <= cutoff, "FUTURE_REPORT", "不能生成未来账单")
        statistics = self.statistics(user, request.account_id, start, cutoff)
        anomalies = self.anomalies(user, request.account_id, start, cutoff)
        row = BillReport(
            user_id=user.id,
            payload={"period": request.period, **statistics, "anomalies": anomalies},
        )
        self.db.add(row)
        audit(self.db, user, "REPORT_CREATED")
        self.db.commit()
        return row_dict(row)
