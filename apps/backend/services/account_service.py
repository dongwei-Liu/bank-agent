from decimal import Decimal
from clients.fineract import FineractClient, FineractNotFoundError
from core.errors import DomainError, require
from schemas.account import AccountDetail, AccountSummary, BalanceResponse


class AccountNotFoundError(DomainError):
    def __init__(self, message):
        super().__init__("ACCOUNT_NOT_FOUND", message, 404)


class AccountService:
    def __init__(self, fineract: FineractClient):
        self.fineract = fineract

    def get_account(self, user, account_id):
        try:
            raw = self.fineract.get_savings_account(account_id)
        except FineractNotFoundError as exc:
            raise AccountNotFoundError("账户不存在") from exc
        require(
            raw.get("clientId") == user.client_id,
            "ACCOUNT_NOT_FOUND",
            "账户不存在",
            404,
        )
        require(
            (raw.get("depositType") or {}).get("id") == 100,
            "ACCOUNT_TYPE",
            "该接口只支持普通储蓄账户",
        )
        currency = (
            raw.get("currency") or (raw.get("summary") or {}).get("currency") or {}
        ).get("code")
        require(currency == "CNY", "UNSUPPORTED_CURRENCY", "仅支持 CNY 账户")
        return raw

    def get_balance(self, user, account_id):
        raw = self.get_account(user, account_id)
        summary = raw.get("summary") or {}
        require(
            summary.get("availableBalance") is not None,
            "UPSTREAM_DATA",
            "核心银行缺少余额事实",
            502,
        )
        balance = Decimal(str(summary["availableBalance"]))
        require(balance.is_finite(), "UPSTREAM_DATA", "余额无效", 502)
        return BalanceResponse(
            account_id=account_id,
            account_no=raw["accountNo"],
            client_id=raw["clientId"],
            client_name=raw.get("clientName", ""),
            balance=balance,
            currency="CNY",
        )

    @staticmethod
    def _date(value):
        if isinstance(value, list) and len(value) >= 3:
            return f"{int(value[0]):04d}-{int(value[1]):02d}-{int(value[2]):02d}"
        return None

    def _summary(self, raw):
        state = raw.get("status") or {}
        if state.get("active"):
            status = "ACTIVE"
        elif state.get("closed"):
            status = "CLOSED"
        elif state.get("rejected"):
            status = "REJECTED"
        elif state.get("approved"):
            status = "APPROVED"
        else:
            status = "PENDING"
        available = (raw.get("summary") or {}).get("availableBalance")
        require(available is not None, "UPSTREAM_DATA", "核心银行缺少余额事实", 502)
        return AccountSummary(
            id=int(raw["id"]),
            account_no=str(raw["accountNo"]),
            client_id=int(raw["clientId"]),
            client_name=raw.get("clientName", ""),
            product_id=int(raw.get("savingsProductId") or 0),
            product_name=raw.get("savingsProductName", ""),
            deposit_type=(raw.get("depositType") or {}).get("value", "Savings"),
            currency=(raw.get("currency") or {}).get("code", "CNY"),
            status=status,
            available_balance=Decimal(str(available)),
        )

    def account_detail(self, user, account_id):
        raw = self.get_account(user, account_id)
        summary = self._summary(raw)
        timeline = raw.get("timeline") or {}
        return AccountDetail(
            **summary.model_dump(),
            external_id=raw.get("externalId"),
            submitted_on=self._date(timeline.get("submittedOnDate")),
            approved_on=self._date(timeline.get("approvedOnDate")),
            activated_on=self._date(timeline.get("activatedOnDate")),
            nominal_annual_interest_rate=Decimal(
                str(raw.get("nominalAnnualInterestRate") or 0)
            ),
            allow_overdraft=bool(raw.get("allowOverdraft", False)),
        )

    def list_accounts(self, user):
        data = self.fineract.list_client_accounts(user.client_id)
        rows = []
        for item in data.get("savingsAccounts", []):
            if (item.get("depositType") or {}).get("id", 100) != 100:
                continue
            rows.append(self._summary(self.get_account(user, item["id"])))
        return rows

    def summary(self, user, include_scope=False):
        accounts = self.list_accounts(user)
        balances = [a.available_balance for a in accounts]
        return {
            "currency": "CNY",
            "total": str(sum(balances, Decimal(0))),
            "account_count": len(balances),
            "complete": True,
            **({"account_ids": [a.id for a in accounts]} if include_scope else {}),
        }

    def require_active(self, raw):
        require(
            (raw.get("status") or {}).get("active") is True,
            "ACCOUNT_INACTIVE",
            "账户未激活",
        )
