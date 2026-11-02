"""Durable report generation and private immutable bill report snapshots."""
import calendar
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from statistics import median
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import tracing_context
from sqlalchemy import select, or_, func
from sqlalchemy.exc import IntegrityError

from clients.fineract import FineractError
from core.config import get_settings
from core.errors import DomainError, require
from core.security import SHANGHAI, fingerprint, now
from models import Annotation, BillReport, BillReportJob, BillReportTransaction, CardAuthorization, Category, ClassificationRule, Merchant, Subscription, User
from services.account_service import AccountService
from services.billing_service import BillingService, period_range
from services.common import audit, lock_user, owned, safe_json, row_dict
from services.subscription_service import CADENCES, SubscriptionService, normalized_merchant

ZERO = Decimal("0.00")
NARRATIVE_TEXT = {
    "SPENDING_UP": "本期消费高于可比期间。", "SPENDING_DOWN": "本期消费低于可比期间。",
    "INCOME_UP": "本期收入高于可比期间。", "INCOME_DOWN": "本期收入低于可比期间。",
    "WEEKEND_HEAVY": "消费较多集中在周末。", "TOP3_CONCENTRATED": "消费主要集中在少数类别。",
    "RECURRING_PRESENT": "本期包含周期性支出。", "ANOMALY_PRESENT": "本期有待核实的异常候选。",
    "NO_COMPARABLE_BASELINE": "部分收支缺少可比基期，暂不计算变化率。",
    "LIMITED_HISTORY": "可用历史不足，消费习惯结论仅供参考。",
}


def _period_dates(period, today):
    start, end = period_range(period)
    require(start <= today, "FUTURE_REPORT", "不能生成未来账单", 422)
    return start, min(end, today)


def _shift_period(period, years=0, months=0):
    start, end = period_range(period)
    if len(period) == 4:
        year = start.year + years
        return f"{year:04d}"
    index = start.year * 12 + start.month - 1 + years * 12 + months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    return f"{year:04d}-{month:02d}"


def _progress_end(period, cutoff, *, years=0, months=0):
    start, end = period_range(period)
    if len(period) == 4:
        target_year = start.year + years
        day = min(cutoff.day, calendar.monthrange(target_year, cutoff.month)[1])
        return date(target_year, cutoff.month, day)
    target_period = _shift_period(period, years=years, months=months)
    target_start, target_end = period_range(target_period)
    day = min(cutoff.day, calendar.monthrange(target_start.year, target_start.month)[1])
    return min(date(target_start.year, target_start.month, day), target_end)


def _components(rows):
    result = defaultdict(lambda: ZERO)
    internal_transfers = set()
    for row in rows:
        if row["reversed"]:
            continue
        for key, amount in row["components"].items():
            if key == "internal_transfer" and row.get("transfer_reference") is not None:
                reference = row["transfer_reference"]
                if reference in internal_transfers:
                    continue
                internal_transfers.add(reference)
            result[key] += Decimal(str(amount))
    return result


def _facts(rows):
    valid = [row for row in rows if not row["reversed"]]
    expenses = [row for row in valid if row["kind"] == "expense"]
    categories = defaultdict(lambda: ZERO)
    by_date = defaultdict(lambda: defaultdict(lambda: ZERO))
    by_month = defaultdict(lambda: defaultdict(lambda: ZERO))
    weekday = {"weekday": 0, "weekend": 0}
    monthly_internal_refs = set()
    for row in valid:
        day = date.fromisoformat(row["date"])
        for key, amount in row["components"].items():
            if key == "internal_transfer" and row.get("transfer_reference") is not None:
                reference = row["transfer_reference"]
                if reference in monthly_internal_refs:
                    continue
                monthly_internal_refs.add(reference)
            by_date[day.isoformat()][key] += Decimal(str(amount))
            by_month[day.strftime("%Y-%m")][key] += Decimal(str(amount))
        if row["kind"] == "expense":
            amount = Decimal(row["amount"])
            categories[row["category"]] += amount
            weekday["weekend" if day.weekday() >= 5 else "weekday"] += 1
    totals = _components(valid)
    has_observations = bool(valid)
    expense_total = totals["expense"]
    fee_total = totals["fee"]
    shares = {name: (amount / expense_total if expense_total else None) for name, amount in categories.items()}
    sorted_categories = sorted(categories.items(), key=lambda item: (-item[1], item[0]))
    concentration = sum((v for _, v in sorted_categories[:3]), ZERO) / expense_total if expense_total else None
    income = totals["income"] + totals["interest"]
    expense_and_fees = expense_total + fee_total
    return {
        # A fully read range with no valid transactions is still not evidence
        # that the customer's income or spending was zero.
        "totals": {"income": income if has_observations else None,
                   "expense": expense_total if has_observations else None,
                   "fees": fee_total if has_observations else None,
                   "external_transfer": totals["transfer"] if has_observations else None,
                   "internal_transfer": totals["internal_transfer"] if has_observations else None,
                   "principal_flow": totals["fixed_transfer"] if has_observations else None,
                   "net_cash_flow": income - expense_and_fees if has_observations else None},
        "categories": [{"name": name, "amount": amount, "share": shares[name]} for name, amount in sorted_categories],
        "transaction_count": len(valid), "expense_count": len(expenses),
        "average_expense": expense_total / len(expenses) if expenses else None,
        "habits": {"weekday_weekend_expense_count": weekday, "top_category": sorted_categories[0][0] if sorted_categories else None,
                   "top_three_category_share": concentration},
        "daily": dict(by_date), "monthly": dict(by_month),
    }


def _compare(current, baseline):
    output = {}
    for key in ("income", "expense", "fees", "external_transfer", "net_cash_flow"):
        base = baseline["totals"][key]
        current_value = current["totals"][key]
        has_baseline = baseline["transaction_count"] > 0
        has_current = current["transaction_count"] > 0
        available = has_baseline and has_current
        output[key] = {"current": current_value, "baseline": base,
                       "delta": current_value - base if available else None,
                       "change_ratio": (current_value - base) / base if available and base > 0 else None,
                       "available": available,
                       "unavailable_reason": ("no_current_transactions" if not has_current else
                           "no_comparable_transactions" if not has_baseline else
                           "baseline_zero" if base <= 0 else None)}
    return output


class BillReportService:
    def __init__(self, db, fineract, settings=None):
        self.db, self.fineract = db, fineract
        self.settings = settings or get_settings()
        self.billing = BillingService(db, fineract, self.settings)

    def enqueue(self, user, account_id, period, idempotency_key):
        today = now().astimezone(SHANGHAI).date()
        start, cutoff = _period_dates(period, today)
        dependencies = [item.id for item in AccountService(self.fineract).list_accounts(user)]
        require(dependencies, "NO_ACCOUNTS", "没有可用于生成报告的本人储蓄账户", 404)
        if account_id is None:
            account_ids = list(dependencies)
        else:
            AccountService(self.fineract).get_account(user, account_id)
            account_ids = [account_id]
        request_hash = fingerprint({"account_id": account_id, "period": period})
        old = self.db.scalar(select(BillReportJob).where(BillReportJob.user_id == user.id,
                                                         BillReportJob.idempotency_key == idempotency_key))
        if old:
            require(old.request_hash == request_hash, "IDEMPOTENCY_CONFLICT", "该请求键已用于不同账单报告", 409)
            return self.status(user, old.report_id)
        report = BillReport(user_id=user.id, payload={"schema_version": 1, "status": "queued",
            "period": period, "from_date": start.isoformat(), "to_date": cutoff.isoformat(),
            "cutoff_date": cutoff.isoformat(), "partial_period": cutoff < period_range(period)[1],
            "account_ids": account_ids, "account_scope": "all_accounts" if account_id is None else "single_account",
            "scope_account_id": account_id, "sections": {}})
        self.db.add(report)
        self.db.flush()
        job = BillReportJob(report_id=report.id, user_id=user.id, idempotency_key=idempotency_key,
            request_hash=request_hash, account_ids=account_ids, dependency_account_ids=dependencies, period=period, cutoff_date=cutoff,
            status="queued", attempts=0)
        self.db.add(job)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            old = self.db.scalar(select(BillReportJob).where(BillReportJob.user_id == user.id,
                                                             BillReportJob.idempotency_key == idempotency_key))
            if old:
                require(old.request_hash == request_hash, "IDEMPOTENCY_CONFLICT", "该请求键已用于不同账单报告", 409)
                return self.status(user, old.report_id)
            raise
        # The scope and dependencies were already authenticated above.  Return
        # the known queued state directly instead of re-reading the just-created
        # row and repeating every Fineract ownership lookup inside ``status``.
        # Besides avoiding redundant upstream traffic, this keeps report
        # creation atomic when the upstream becomes unavailable immediately
        # after the initial ownership check.
        return {
            "report_id": report.id,
            "status": "queued",
            "period": period,
            "progress": 0,
            "error": None,
            "created_at": report.created_at,
        }

    def view_or_generate(self, user, account_id, period, *, trace_id=None):
        """Open the exact user/period/account-scope report or enqueue it once.

        A user row lock makes parallel natural-language views converge on one
        report. Legacy snapshots are reusable only when their original scope is
        explicit in the stored payload.
        """
        today = now().astimezone(SHANGHAI).date()
        _period_dates(period, today)

        lock_user(self.db, user)
        accounts = AccountService(self.fineract)
        eligible_ids = sorted(item.id for item in accounts.list_accounts(user))
        require(eligible_ids, "NO_ACCOUNTS", "没有可用于查看报告的本人储蓄账户", 404)
        if account_id is None:
            scope_ids = eligible_ids
        else:
            accounts.get_account(user, account_id)
            scope_ids = [account_id]

        reports = self.db.scalars(
            select(BillReport)
            .where(BillReport.user_id == user.id)
            .order_by(BillReport.created_at.desc(), BillReport.id.desc())
        ).all()
        matching = [
            report for report in reports
            if report.payload.get("period") == period
            and self._has_exact_scope(report.payload, account_id, scope_ids)
        ]
        if matching:
            report_ids = [report.id for report in matching]
            jobs = {
                job.report_id: job
                for job in self.db.scalars(
                    select(BillReportJob).where(BillReportJob.report_id.in_(report_ids))
                ).all()
            }

            def report_status(report):
                job = jobs.get(report.id)
                return job.status if job is not None else report.payload.get("status", "complete")

            ordered = [
                report for accepted in (
                    {"complete", "partial"}, {"queued", "running"}, {"failed"},
                )
                for report in matching if report_status(report) in accepted
            ]
            report = next(
                (item for item in ordered if self._dependencies_available(user, item)),
                None,
            )
            if report is not None:
                status = report_status(report)
                result = {
                    "report_id": report.id,
                    "period": period,
                    "status": status,
                    "generated": False,
                    "error": report.payload.get("error"),
                }
                audit(
                    self.db, user, "BILL_REPORT_OPENED", trace_id=trace_id,
                    resource_type="bill_report", resource_id=report.id,
                    period=period, account_scope="all_accounts" if account_id is None else "single_account",
                    status=status, generated=False,
                )
                self.db.commit()
                return result

        queued = self.enqueue(user, account_id, period, uuid4().hex)
        audit(
            self.db, user, "BILL_REPORT_OPENED", trace_id=trace_id,
            resource_type="bill_report", resource_id=queued["report_id"],
            period=period, account_scope="all_accounts" if account_id is None else "single_account",
            status=queued["status"], generated=True,
        )
        self.db.commit()
        return {
            "report_id": queued["report_id"],
            "period": period,
            "status": queued["status"],
            "generated": True,
            "error": queued.get("error"),
        }

    @staticmethod
    def _has_exact_scope(payload, account_id, current_scope_ids):
        saved_ids = payload.get("account_ids")
        scope = payload.get("account_scope")
        if scope == "all_accounts":
            return account_id is None and isinstance(saved_ids, list) and sorted(saved_ids) == current_scope_ids
        if scope == "single_account":
            return account_id is not None and payload.get("scope_account_id") == account_id

        # The synchronous legacy report spread BillingService.statistics into
        # its payload, which records the originally requested account_id.
        if "account_id" in payload:
            recorded_account = payload["account_id"]
            if account_id is None:
                return recorded_account is None and isinstance(saved_ids, list) and sorted(saved_ids) == current_scope_ids
            return recorded_account == account_id
        return False

    def status(self, user, report_id):
        report = owned(self.db, BillReport, report_id, user)
        self._authorize_dependencies(user, report)
        payload = report.payload
        return {"report_id": report.id, "status": payload.get("status", "complete"),
                "period": payload.get("period"), "progress": payload.get("progress", 0),
                "error": payload.get("error"), "created_at": report.created_at}

    def legacy_list(self, user):
        rows = self.db.scalars(select(BillReport).where(BillReport.user_id == user.id)
                               .order_by(BillReport.created_at.desc(), BillReport.id.desc())).all()
        from services.common import row_dict
        return [row_dict(row) for row in rows if self._dependencies_available(user, row)]

    def list(self, user, *, period=None, period_from=None, period_to=None, status=None,
             account_id=None, page=1, page_size=20):
        require(1 <= page <= 5000 and 1 <= page_size <= 100, "INVALID_PAGE", "分页参数无效", 422)
        require(not (period_from and period_to) or period_from <= period_to,
                "INVALID_PERIOD_RANGE", "报告期间范围无效", 422)
        for value in (period, period_from, period_to):
            if value is not None:
                period_range(value)
        require(not (period_from and period_to) or len(period_from) == len(period_to),
                "INVALID_PERIOD_RANGE", "月度与年度筛选范围不能混用", 422)
        require(status is None or status in {"queued", "running", "complete", "partial", "failed"},
                "INVALID_REPORT_STATUS", "报告状态筛选无效", 422)
        rows = self.db.scalars(select(BillReport).where(BillReport.user_id == user.id).order_by(BillReport.created_at.desc(), BillReport.id.desc())).all()
        items = []
        for row in rows:
            data = row.payload
            if not self._dependencies_available(user, row):
                continue
            if period and data.get("period") != period:
                continue
            if period_from and data.get("period", "") < period_from:
                continue
            if period_to and data.get("period", "") > period_to:
                continue
            if status and data.get("status", "complete") != status:
                continue
            if account_id is not None and account_id not in data.get("account_ids", []):
                continue
            items.append({"id": row.id, "period": data.get("period"), "status": data.get("status", "complete"),
                          "created_at": row.created_at, "cutoff_date": data.get("cutoff_date"),
                          "account_ids": data.get("account_ids", []), "account_scope": data.get("account_scope"),
                          "scope_account_id": data.get("scope_account_id"),
                          "transaction_count": data.get("summary", {}).get("transaction_count")})
        total = len(items)
        return {"items": items[(page-1)*page_size:page*page_size], "page": page, "page_size": page_size, "total": total}

    def detail(self, user, report_id):
        report = owned(self.db, BillReport, report_id, user)
        payload = dict(report.payload)
        require(payload.get("status") not in {"queued", "running"}, "REPORT_NOT_READY", "账单报告仍在生成中", 409)
        self._authorize_dependencies(user, report)
        return {"id": report.id, "created_at": report.created_at, **payload}

    def _dependencies_available(self, user, report):
        from core.errors import DomainError
        try:
            self._authorize_dependencies(user, report)
            return True
        except DomainError as exc:
            if exc.status == 404:
                return False
            raise

    def _authorize_dependencies(self, user, report):
        job = self.db.scalar(select(BillReportJob).where(BillReportJob.report_id == report.id))
        ids = (job.dependency_account_ids if job else
               report.payload.get("dependency_account_ids", report.payload.get("account_ids", [])))
        accounts = AccountService(self.fineract)
        for account_id in ids:
            accounts.get_account(user, account_id)

    def transactions(self, user, report_id, *, page=1, page_size=50, direction=None,
                     category=None, from_date=None, to_date=None):
        require(1 <= page <= 100000 and 1 <= page_size <= 100, "INVALID_PAGE", "分页参数无效", 422)
        require(not (from_date and to_date) or from_date <= to_date,
                "INVALID_DATE", "明细日期范围无效", 422)
        data = self.detail(user, report_id)
        query = select(BillReportTransaction).where(BillReportTransaction.report_id == report_id)
        if direction:
            require(direction in {"credit", "debit", "unknown"}, "INVALID_DIRECTION", "流水方向无效", 422)
            query = query.where(BillReportTransaction.direction == direction)
        if category:
            query = query.where(BillReportTransaction.category == category)
        if from_date:
            query = query.where(BillReportTransaction.occurred_on >= from_date)
        if to_date:
            query = query.where(BillReportTransaction.occurred_on <= to_date)
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.db.scalars(query.order_by(BillReportTransaction.occurred_on.desc(),
            BillReportTransaction.account_id, BillReportTransaction.transaction_id)
            .offset((page-1)*page_size).limit(page_size)).all()
        return {"items": [row.payload for row in rows], "page": page, "page_size": page_size, "total": total}

    def delete(self, user, report_id):
        report = owned(self.db, BillReport, report_id, user)
        job = self.db.scalar(select(BillReportJob).where(BillReportJob.report_id == report_id))
        if job and job.status in {"queued", "running"}:
            job.status = "cancelled"
        self.db.query(BillReportTransaction).filter(BillReportTransaction.report_id == report_id).delete()
        if job:
            self.db.delete(job)
        self.db.delete(report)
        self.db.commit()
        return {"deleted": True}

    def _claim(self):
        now_utc = now()
        job = self.db.scalar(select(BillReportJob).where(or_(BillReportJob.status == "queued",
            ((BillReportJob.status == "running") & (BillReportJob.lease_until < now_utc))))
            .order_by(BillReportJob.created_at).with_for_update(skip_locked=True).limit(1))
        if job is None:
            return None
        job.status = "running"
        job.attempts += 1
        job.lease_until = now_utc + timedelta(minutes=10)
        report_id = job.report_id
        report = self.db.get(BillReport, report_id)
        if report:
            report.payload = {**report.payload, "status": "running", "progress": 10}
        self.db.commit()
        return report_id

    def run_one(self):
        report_id = self._claim()
        if report_id is None:
            return False
        job = self.db.scalar(select(BillReportJob).where(BillReportJob.report_id == report_id))
        report = self.db.get(BillReport, report_id)
        if report is None or job is None:
            self.db.rollback()
            return True
        user = self.db.get(User, job.user_id)
        if user is None:
            self.db.rollback()
            return True
        try:
            payload = self._build(user, job)
            if self.db.get(BillReport, report_id) is None or self.db.get(BillReportJob, job.id) is None:
                self.db.rollback()
                return True
            transactions = payload.pop("_transaction_rows")
            self.db.query(BillReportTransaction).filter(BillReportTransaction.report_id == report_id).delete()
            for item in transactions:
                self.db.add(BillReportTransaction(report_id=report_id, account_id=item["account_id"],
                    transaction_id=item["transaction_id"], occurred_on=date.fromisoformat(item["date"]),
                    direction=item["direction"], category=item["category"], payload=item))
            report.payload = payload
            job.status = "complete" if payload["status"] == "complete" else payload["status"]
            job.lease_until = None
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            job = self.db.scalar(select(BillReportJob).where(BillReportJob.report_id == report_id))
            report = self.db.get(BillReport, report_id)
            if job is None or report is None:
                self.db.rollback()
                return True
            if job.attempts < 3:
                job.status = "queued"
                job.lease_until = None
                report.payload = {**report.payload, "status": "queued", "progress": 0}
                self.db.commit()
                return True
            report.payload = {**report.payload, "status": "failed", "progress": 100,
                              "error": "CORE_READ_FAILED" if isinstance(exc, (DomainError, FineractError)) else "REPORT_GENERATION_FAILED"}
            job.status = "failed"
            job.error_code = report.payload["error"]
            job.lease_until = None
            self.db.commit()
        return True

    def _build(self, user, job):
        report = self.db.get(BillReport, job.report_id)
        report_scope = report.payload if report is not None else {}
        start, cutoff = period_range(job.period)[0], job.cutoff_date
        target_end = min(period_range(job.period)[1], cutoff)
        if len(job.period) == 4:
            comparison_periods = {"previous_year": _shift_period(job.period, years=-1)}
            comparison_ends = {"previous_year": min(period_range(comparison_periods["previous_year"])[1], _progress_end(job.period, cutoff, years=-1))}
        else:
            comparison_periods = {"previous_period": _shift_period(job.period, months=-1),
                                  "previous_year": _shift_period(job.period, years=-1)}
            comparison_ends = {"previous_period": _progress_end(job.period, cutoff, months=-1),
                               "previous_year": _progress_end(job.period, cutoff, years=-1)}
        history_start = min(start - timedelta(days=1200), *(period_range(value)[0] for value in comparison_periods.values()), cutoff - timedelta(days=1200))
        account_ids = list(job.account_ids)
        dependency_account_ids = list(job.dependency_account_ids)
        # Authorization is rechecked immediately before and after core reads.
        accounts = AccountService(self.fineract)
        for account_id in dependency_account_ids:
            accounts.get_account(user, account_id)
        all_rows = []
        for account_id in dependency_account_ids:
            all_rows.extend(self.billing.transactions.all(user, account_id, history_start, target_end))
            require(len(all_rows) <= self.settings.max_report_transactions,
                    "REPORT_TOO_LARGE", "历史流水过多，无法生成报告", 422)
        for account_id in dependency_account_ids:
            accounts.get_account(user, account_id)
        scope_rows = [row for row in all_rows if row["account_id"] in account_ids]
        current = [row for row in scope_rows if start <= date.fromisoformat(row["date"]) <= target_end]
        current_facts = _facts(current)
        comparisons = {}
        for name, comp_period in comparison_periods.items():
            comp_start = period_range(comp_period)[0]
            comp_end = comparison_ends[name]
            baseline = [row for row in scope_rows if comp_start <= date.fromisoformat(row["date"]) <= comp_end]
            comparisons[name] = {"period": comp_period, "from_date": comp_start, "to_date": comp_end,
                                 "metrics": _compare(current_facts, _facts(baseline))}
        sections = {"summary": "complete", "trends": "complete", "transactions": "complete",
                    "comparison": "complete" if any(value["metrics"]["expense"]["available"] for value in comparisons.values()) else "unavailable", "anomalies": "pending",
                    "recurring": "complete", "narrative": "pending"}
        anomalies = None
        try:
            anomalies = self.billing.anomalies(user, None, start, target_end, include_metadata=True,
                snapshot=(dependency_account_ids, all_rows), selected_account_ids=account_ids,
                dependency_account_ids=dependency_account_ids)
            # Restrict exact payload to user facing evidence; detection internals remain out of report view.
            anomaly_rows = anomalies.get("items", []) if isinstance(anomalies, dict) else anomalies
            def safe_evidence(value):
                if isinstance(value, dict):
                    return {key: safe_evidence(item) for key, item in value.items()
                            if key not in {"score", "threshold", "high_threshold", "severity", "sources", "model_id"}}
                if isinstance(value, list):
                    return [safe_evidence(item) for item in value]
                return value
            anomalies = [{"anomaly_key": row.get("anomaly_key"), "rule": row.get("rule"),
                "anomaly_types": row.get("anomaly_types", []), "status": row.get("status", "unreviewed"),
                "transaction_ids": row.get("transaction_ids", []), "evidence": safe_evidence(row.get("evidence", {})),
                "findings": [{"type": finding.get("type"), "provisional": finding.get("provisional", False),
                    "window": finding.get("window", {}), "evidence": safe_evidence(finding.get("evidence", {}))}
                    for finding in row.get("findings", [])],
                "observation_kind": row.get("observation_kind")} for row in anomaly_rows]
            sections["anomalies"] = "complete"
        except Exception:
            anomalies = []
            sections["anomalies"] = "unavailable"
        try:
            recurring = self._recurring(user, scope_rows, current)
            sections["recurring"] = "complete"
        except Exception:
            recurring = []
            sections["recurring"] = "unavailable"
        first_observation = min((row["date"] for row in scope_rows), default=None)
        coverage = {"history_requested_from": history_start, "first_observed_transaction": first_observation,
                    "observed_days": (cutoff - date.fromisoformat(first_observation)).days + 1 if first_observation else 0,
                    "status": "observed" if first_observation else "no_transactions",
                    "read_complete": True}
        if coverage["observed_days"] < 700 and sections["recurring"] == "complete":
            # Monthly patterns can still be useful, while three annual charges
            # cannot be established from this short history.
            sections["recurring"] = "insufficient_history"
        codes = self._conclusion_codes(current_facts, comparisons, recurring, anomalies)
        narrative, narrative_status = self._narrative(job.period, codes)
        sections["narrative"] = "complete"
        # The model may take several seconds. Recheck authorization after it
        # returns so an account revoked mid-generation cannot be published.
        for dependency_id in dependency_account_ids:
            accounts.get_account(user, dependency_id)
        status = "complete" if all(state == "complete" for state in sections.values()) else "partial"
        transactions = [{"account_id": row["account_id"], "transaction_id": row["transaction_id"], "date": row["date"],
            "direction": row["direction"], "kind": row["kind"], "amount": row["amount"], "category": row["category"],
            "merchant": row["merchant"], "reversed": row["reversed"], "components": row["components"],
            "transfer_reference": row.get("transfer_reference")} for row in current]
        cutoff_time = now()
        if len(account_ids) != len(set(account_ids)):
            raise ValueError("duplicate account scope")
        return safe_json({"schema_version": 1, "status": status, "progress": 100, "period": job.period,
            "from_date": start, "to_date": target_end, "cutoff_date": cutoff, "created_cutoff_at": cutoff_time,
            "partial_period": target_end < period_range(job.period)[1], "account_ids": account_ids,
            "account_scope": report_scope.get("account_scope"),
            "scope_account_id": report_scope.get("scope_account_id"),
            "dependency_account_ids": dependency_account_ids,
            "snapshot_atomic": False, "sections": sections, "summary": current_facts,
            "comparison": comparisons, "historical_coverage": coverage, "anomalies": anomalies,
            "recurring": recurring, "recurring_coverage_days": coverage["observed_days"], "narrative": narrative,
            "versions": {"calculation": "bill-report-v1", "classification": "billing-v1",
                         "classification_config_hash": self._classification_hash(user),
                         "narrative": "controlled-codes-v1"},
            "_transaction_rows": transactions})

    def _classification_hash(self, user):
        """Persist a one-way fingerprint of the classification inputs used by this version."""
        merchant_ids = set(self.db.scalars(select(Subscription.merchant_id).where(Subscription.user_id == user.id)))
        merchant_ids.update(self.db.scalars(select(CardAuthorization.merchant_id).where(CardAuthorization.user_id == user.id)))
        merchants = self.db.scalars(select(Merchant).where(Merchant.id.in_(merchant_ids))).all() if merchant_ids else []
        return fingerprint({
            "categories": self.billing.list_resources(user, Category),
            "rules": self.billing.list_resources(user, ClassificationRule),
            "annotations": self.billing.list_resources(user, Annotation),
            "merchants": [{"id": row.id, "name": row.name, "category": row.category,
                           "adapter_type": row.adapter_type}
                          for row in merchants],
        })

    def _recurring(self, user, history, current):
        groups = defaultdict(list)
        for row in history:
            if row["kind"] != "expense" or row["reversed"] or not row.get("merchant"):
                continue
            groups[normalized_merchant(row["merchant"])].append({"merchant": row["merchant"],
                "account_id": row["account_id"], "transaction_id": row["transaction_id"],
                "occurred_on": date.fromisoformat(row["date"]), "amount": Decimal(row["amount"])})
        known = {}
        for sub in self.db.scalars(select(Subscription).where(Subscription.user_id == user.id)):
            merchant = self.db.get(Merchant, sub.merchant_id)
            if merchant:
                known[(normalized_merchant(merchant.name), sub.cadence)] = {"status": sub.status,
                    "verified_at": sub.verified_at, "id": sub.id}
        period_keys = {(row["account_id"], row["transaction_id"]) for row in current}
        result = []
        for rows in groups.values():
            rows.sort(key=lambda row: (row["occurred_on"], row["account_id"], row["transaction_id"]))
            for cadence, (low, high) in CADENCES.items():
                run = SubscriptionService._best_run(rows, low, high)
                matched = [row for row in run if (row["account_id"], row["transaction_id"]) in period_keys]
                if len(run) < 3 or not matched:
                    continue
                merchant_name = matched[-1]["merchant"]
                known_row = known.get((normalized_merchant(merchant_name), cadence))
                result.append({"merchant": merchant_name, "cadence": cadence, "status": known_row["status"] if known_row else "candidate",
                    "verified_at": known_row["verified_at"] if known_row else None,
                    "occurrences": [{"account_id": row["account_id"], "transaction_id": row["transaction_id"],
                        "date": row["occurred_on"], "amount": row["amount"]} for row in matched],
                    "average_amount": sum((row["amount"] for row in matched), ZERO) / len(matched)})
        return result

    @staticmethod
    def _conclusion_codes(facts, comparisons, recurring, anomalies):
        codes = []
        priority = comparisons.get("previous_period", comparisons.get("previous_year", {})).get("metrics", {})
        for key, up, down in (("expense", "SPENDING_UP", "SPENDING_DOWN"), ("income", "INCOME_UP", "INCOME_DOWN")):
            row = priority.get(key, {"available": False})
            if row["available"] and row["delta"]:
                codes.append(up if row["delta"] > 0 else down)
        counts = facts["habits"]["weekday_weekend_expense_count"]
        if counts["weekend"] > counts["weekday"]:
            codes.append("WEEKEND_HEAVY")
        concentration = facts["habits"]["top_three_category_share"]
        if concentration is not None and concentration >= Decimal("0.8"):
            codes.append("TOP3_CONCENTRATED")
        if recurring:
            codes.append("RECURRING_PRESENT")
        if anomalies:
            codes.append("ANOMALY_PRESENT")
        if not any(value.get("metrics", {}).get("expense", {}).get("available") for value in comparisons.values()):
            codes.append("NO_COMPARABLE_BASELINE")
        if facts["expense_count"] < 5:
            codes.append("LIMITED_HISTORY")
        return list(dict.fromkeys(codes))

    def _narrative(self, period, codes):
        allowed = [code for code in codes if code in NARRATIVE_TEXT]
        selected, status = allowed, "template_fallback"
        if allowed:
            try:
                model = ChatOpenAI(model=self.settings.siliconflow_model, api_key=self.settings.siliconflow_api_key,
                    base_url=self.settings.siliconflow_base_url, temperature=0, max_tokens=160, max_retries=0,
                    timeout=12, callbacks=[])
                prompt = {"period_type": "year" if len(period) == 4 else "month", "allowed_conclusion_codes": allowed}
                with tracing_context(enabled=False):
                    response = model.invoke([SystemMessage(content="只选择输入中的 conclusion code 并排序，输出 JSON: {\"codes\":[...]}. 不得编写自然语言，不得增加结论。"),
                        HumanMessage(content=json.dumps(prompt, ensure_ascii=False))])
                parsed = json.loads(response.content)
                proposal = parsed.get("codes")
                if isinstance(proposal, list) and len(proposal) == len(allowed) and set(proposal) == set(allowed):
                    selected, status = list(dict.fromkeys(proposal)), "complete"
            except Exception:
                pass
        return {"items": [{"code": code, "text": NARRATIVE_TEXT[code]} for code in selected],
                "source": status, "version": "controlled-codes-v1"}, status
