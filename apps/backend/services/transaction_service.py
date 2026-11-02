from datetime import date
from decimal import Decimal
from sqlalchemy import select
from core.errors import require
from models import (
    Annotation,
    CardAuthorization,
    Category,
    ClassificationRule,
    Merchant,
)
from services.account_service import AccountService


MERCHANT_NOTE_PREFIX = "[Merchant] "


def iso_date(value):
    if isinstance(value, list):
        return date(*value[:3]).isoformat()
    if isinstance(value, str):
        return date.fromisoformat(value[:10]).isoformat()
    require(False, "UPSTREAM_DATA", "核心交易缺少日期", 502)


def normalize(raw):
    typ = raw.get("transactionType") or {}
    amount = raw.get("amount")
    require(
        amount is not None and raw.get("id") and raw.get("date"),
        "UPSTREAM_DATA",
        "核心交易字段缺失",
        502,
    )
    amount = Decimal(str(amount))
    require(
        amount.is_finite() and amount >= 0, "UPSTREAM_DATA", "核心交易金额无效", 502
    )
    require(
        (raw.get("currency") or {}).get("code") == "CNY",
        "UNSUPPORTED_CURRENCY",
        "流水币种不支持",
    )
    direction = {"CREDIT": "credit", "DEBIT": "debit"}.get(raw.get("entryType"))
    if not direction:
        if typ.get("deposit") or typ.get("interestPosting"):
            direction = "credit"
        elif typ.get("withdrawal") or typ.get("feeDeduction") or typ.get("withholdTax"):
            direction = "debit"
        else:
            direction = "unknown"
    kind = "unknown"
    if typ.get("amountHold") or typ.get("amountRelease"):
        kind = "hold"
    elif typ.get("accrual"):
        kind = "accrual"
    elif raw.get("transfer") or any(
        typ.get(k)
        for k in [
            "initiateTransfer",
            "approveTransfer",
            "withdrawTransfer",
            "rejectTransfer",
        ]
    ):
        kind = "transfer"
    elif typ.get("interestPosting"):
        kind = "interest"
    elif (
        typ.get("feeDeduction")
        or typ.get("withholdTax")
        or typ.get("overdraftInterest")
    ):
        kind = "fee"
    elif typ.get("withdrawal"):
        kind = "expense"
    elif typ.get("deposit") or typ.get("dividendPayout"):
        kind = "income"
    note = str(raw.get("note") or "").strip()
    merchant = None
    if note.startswith(MERCHANT_NOTE_PREFIX):
        merchant = note.removeprefix(MERCHANT_NOTE_PREFIX).strip() or None
        note = ""
    return {
        "transaction_id": int(raw["id"]),
        "account_id": int(raw["accountId"]),
        "date": iso_date(raw["date"]),
        "submitted_date": iso_date(raw["submittedOnDate"])
        if raw.get("submittedOnDate")
        else None,
        "amount": str(amount),
        "currency": "CNY",
        "direction": direction,
        "kind": kind,
        "type": typ.get("code", "unknown"),
        "reversed": bool(raw.get("reversed") or raw.get("isReversal")),
        "transfer_reference": (raw.get("transfer") or {}).get("id"),
        "category_id": None,
        "category": "未分类",
        "merchant": merchant,
        "note": note,
    }


class TransactionService:
    def __init__(self, db, fineract, settings):
        self.db, self.fineract, self.settings = db, fineract, settings
        self._fixed_ids = None
        self._owned_savings_ids = None
        self._transfer_details = {}
        self._fixed_details = {}

    def enrich(self, user, rows):
        if not rows:
            return rows
        transfer_references = {
            int(row["transfer_reference"])
            for row in rows
            if row.get("transfer_reference") is not None
        }
        card_authorizations = (
            self.db.scalars(
                select(CardAuthorization).where(
                    CardAuthorization.user_id == user.id,
                    CardAuthorization.status == "APPROVED",
                    CardAuthorization.fineract_transfer_id.in_(transfer_references),
                )
            ).all()
            if transfer_references
            else []
        )
        merchant_ids = {row.merchant_id for row in card_authorizations}
        merchants = (
            {
                row.id: row
                for row in self.db.scalars(
                    select(Merchant).where(Merchant.id.in_(merchant_ids))
                ).all()
            }
            if merchant_ids
            else {}
        )
        card_purchases = {
            int(row.fineract_transfer_id): merchants[row.merchant_id]
            for row in card_authorizations
            if row.fineract_transfer_id is not None and row.merchant_id in merchants
        }
        if self._fixed_ids is None:
            accounts = self.fineract.list_client_accounts(user.client_id).get(
                "savingsAccounts", []
            )
            self._fixed_ids = {
                a["id"]
                for a in accounts
                if (a.get("depositType") or {}).get("id") == 200
            }
            self._owned_savings_ids = {
                a["id"]
                for a in accounts
                if (a.get("depositType") or {}).get("id", 100) == 100
            }
        for row in rows:
            reference = row["transfer_reference"]
            row["components"] = {row["kind"]: row["amount"]}
            if not reference:
                continue
            merchant = card_purchases.get(int(reference))
            if merchant and row["direction"] == "debit":
                row["kind"] = "expense"
                row["components"] = {"expense": row["amount"]}
                row["merchant"] = merchant.name
                row["_default_category"] = merchant.category
                continue
            if reference not in self._transfer_details:
                self._transfer_details[reference] = self.fineract.get_transfer(
                    reference
                )
            transfer = self._transfer_details[reference]
            from_id = (transfer.get("fromAccount") or {}).get("id")
            to_id = (transfer.get("toAccount") or {}).get("id")
            if from_id in self._owned_savings_ids and to_id in self._owned_savings_ids:
                row["kind"] = "internal_transfer"
                row["components"] = {"internal_transfer": row["amount"]}
                continue
            fixed_id = (
                from_id
                if from_id in self._fixed_ids
                else to_id
                if to_id in self._fixed_ids
                else None
            )
            if fixed_id is None:
                continue
            row["kind"] = "fixed_transfer"
            row["components"] = {"fixed_transfer": row["amount"]}
            if row["direction"] == "credit" and fixed_id == from_id:
                if fixed_id not in self._fixed_details:
                    self._fixed_details[fixed_id] = self.fineract.fixed_account(
                        fixed_id
                    )
                account = self._fixed_details[fixed_id]
                status = account.get("status") or {}
                principal = Decimal(str(account["depositAmount"]))
                amount = Decimal(row["amount"])
                withdrawals = (account.get("summary") or {}).get("totalWithdrawals")
                if (
                    (status.get("closed") or status.get("prematureClosed"))
                    and not account.get("transferInterestToSavings")
                    and withdrawals is not None
                    and Decimal(str(withdrawals)) == amount
                    and amount >= principal
                ):
                    row["components"] = {
                        "fixed_transfer": str(principal),
                        "interest": str(amount - principal),
                    }
        account_ids = {r["account_id"] for r in rows}
        ids = {r["transaction_id"] for r in rows}
        annotations = self.db.scalars(
            select(Annotation).where(
                Annotation.user_id == user.id,
                Annotation.account_id.in_(account_ids),
                Annotation.transaction_id.in_(ids),
            )
        ).all()
        lookup = {(r.account_id, r.transaction_id): r for r in annotations}
        categories = {
            r.id: r.name
            for r in self.db.scalars(
                select(Category).where(Category.user_id == user.id)
            )
        }
        rules = self.db.scalars(
            select(ClassificationRule)
            .where(ClassificationRule.user_id == user.id)
            .order_by(ClassificationRule.priority.desc(), ClassificationRule.id)
        ).all()
        for row in rows:
            a = lookup.get((row["account_id"], row["transaction_id"]))
            if a:
                row.update(merchant=a.merchant, note=a.note, category_id=a.category_id)
            if not row["category_id"]:
                for rule in rules:
                    if (
                        rule.contains.casefold()
                        in str(row.get(rule.field) or "").casefold()
                    ):
                        row["category_id"] = rule.category_id
                        break
            default_category = row.pop("_default_category", "未分类")
            row["category"] = categories.get(row["category_id"], default_category)
        return rows

    def list(
        self,
        user,
        account_id,
        page=0,
        page_size=20,
        from_date=None,
        to_date=None,
        direction=None,
        min_amount=None,
        max_amount=None,
    ):
        AccountService(self.fineract).get_account(user, account_id)
        require(
            not (from_date and to_date) or from_date <= to_date,
            "INVALID_DATE",
            "日期范围无效",
        )
        require(
            not (min_amount is not None and max_amount is not None)
            or min_amount <= max_amount,
            "INVALID_RANGE",
            "金额范围无效",
        )
        filters = {
            "fromDate": str(from_date) if from_date else None,
            "toDate": str(to_date) if to_date else None,
            "fromAmount": str(min_amount) if min_amount is not None else None,
            "toAmount": str(max_amount) if max_amount is not None else None,
        }
        if direction:
            filters[direction] = True
        data = self.fineract.search_transactions(account_id, page, page_size, **filters)
        data["items"] = self.enrich(user, [normalize(r) for r in data["items"]])
        return data

    def detail(self, user, account_id, transaction_id):
        AccountService(self.fineract).get_account(user, account_id)
        raw = self.fineract.get_transaction(account_id, transaction_id)
        require(
            raw.get("accountId") == account_id, "UPSTREAM_DATA", "交易账户不匹配", 502
        )
        return self.enrich(user, [normalize(raw)])[0]

    def all(self, user, account_id, start, end):
        result = {}
        page = 0
        expected_total = None
        while True:
            data = self.list(user, account_id, page, 100, start, end)
            if expected_total is None:
                expected_total = data["total"]
            require(
                data["total"] == expected_total,
                "TRANSACTIONS_CHANGED",
                "流水读取期间发生变化，请重新生成",
                409,
            )
            for item in data["items"]:
                result[item["transaction_id"]] = item
            require(
                len(result) <= self.settings.max_report_transactions,
                "REPORT_TOO_LARGE",
                "交易过多，请缩小查询范围",
                422,
            )
            if (page + 1) * 100 >= data["total"]:
                break
            require(data["items"], "UPSTREAM_DATA", "流水分页提前终止", 502)
            page += 1
        require(
            len(result) == expected_total,
            "TRANSACTIONS_CHANGED",
            "流水分页不完整，请重新生成",
            409,
        )
        return sorted(result.values(), key=lambda x: (x["date"], x["transaction_id"]))
