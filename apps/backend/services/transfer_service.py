from decimal import Decimal
from core.errors import require
from models import Recipient
from services.account_service import AccountService
from services.common import owned, safe_json


class TransferService:
    def __init__(self, db, fineract):
        self.db, self.fineract = db, fineract
        self.accounts = AccountService(fineract)

    def prepare(self, user, request):
        sender = self.accounts.get_account(user, request.from_account_id)
        self.accounts.require_active(sender)
        recipient = owned(self.db, Recipient, request.recipient_id, user)
        require(not recipient.deleted, "RECIPIENT_UNAVAILABLE", "联系人已删除")
        return self.prepare_accounts(
            user,
            request.from_account_id,
            recipient.account_id,
            request.amount,
            request.remark,
        )

    def prepare_internal(self, user, request):
        # Resolve both sides through AccountService so neither account can belong
        # to another customer, even when a caller knows a valid Fineract id.
        self.accounts.get_account(user, request.from_account_id)
        self.accounts.get_account(user, request.to_account_id)
        payload = self.prepare_accounts(
            user,
            request.from_account_id,
            request.to_account_id,
            request.amount,
            request.remark,
        )
        payload["transfer_scope"] = "internal"
        return payload

    def prepare_accounts(self, user, from_id, to_id, amount, remark=""):
        require(from_id != to_id, "SELF_TRANSFER", "不能向同一账户转账")
        sender = self.accounts.get_account(user, from_id)
        self.accounts.require_active(sender)
        target = self.fineract.get_savings_account(to_id)
        self.accounts.require_active(target)
        require(
            (target.get("depositType") or {}).get("id") == 100,
            "ACCOUNT_TYPE",
            "收款账户必须为普通储蓄账户",
        )
        require(
            (target.get("currency") or {}).get("code") == "CNY",
            "UNSUPPORTED_CURRENCY",
            "仅支持同币种转账",
        )
        require(
            self.accounts.get_balance(user, from_id).balance >= Decimal(str(amount)),
            "INSUFFICIENT_FUNDS",
            "余额不足",
        )
        return {
            "from_account_id": from_id,
            "to_account_id": to_id,
            "amount": str(amount),
            "currency": "CNY",
            "remark": remark,
            "to_client_id": target["clientId"],
        }

    def description(self, action):
        return (
            f"[Bank:{action.id}] " + (action.payload.get("remark") or "Transfer")[:50]
        )

    def execute(self, user, action):
        p = action.payload
        self.prepare_accounts(
            user,
            p["from_account_id"],
            p["to_account_id"],
            p["amount"],
            p.get("remark", ""),
        )
        sender = self.accounts.get_account(user, p["from_account_id"])
        target = self.fineract.get_savings_account(p["to_account_id"])
        require(
            target["clientId"] == p["to_client_id"],
            "RECIPIENT_CHANGED",
            "收款账户归属已变化",
        )
        from core.security import now, SHANGHAI

        payload = {
            "fromOfficeId": str(self.fineract.get_client(user.client_id)["officeId"]),
            "fromClientId": str(user.client_id),
            "fromAccountType": "2",
            "fromAccountId": str(sender["id"]),
            "toOfficeId": str(self.fineract.get_client(target["clientId"])["officeId"]),
            "toClientId": str(target["clientId"]),
            "toAccountType": "2",
            "toAccountId": str(target["id"]),
            "transferDate": now().astimezone(SHANGHAI).date().isoformat(),
            "transferAmount": p["amount"],
            "transferDescription": self.description(action),
            "locale": "en",
            "dateFormat": "yyyy-MM-dd",
        }
        response = self.fineract.create_transfer(payload, f"bank:{action.id}:transfer")
        require(
            response.get("resourceId") and not response.get("rollbackTransaction"),
            "EXECUTION_UNCONFIRMED",
            "转账命令尚未确认执行",
            502,
        )
        action.steps = {**action.steps, "transfer_id": int(response["resourceId"])}
        self.db.commit()
        return self.reconcile(user, action)

    def reconcile(self, user, action):
        transfer_id = action.steps.get("transfer_id")
        if not transfer_id:
            from core.security import aware, now, SHANGHAI

            start = aware(action.executed_at).astimezone(SHANGHAI).date().isoformat()
            end = now().astimezone(SHANGHAI).date().isoformat()
            ids = set()
            page = 0
            while True:
                data = self.fineract.search_transactions(
                    action.payload["from_account_id"],
                    page,
                    100,
                    fromDate=start,
                    toDate=end,
                )
                for row in data["items"]:
                    transfer = row.get("transfer") or {}
                    if transfer.get("transferDescription") == self.description(action):
                        ids.add(transfer["id"])
                if (page + 1) * 100 >= data["total"]:
                    break
                require(
                    data["items"] and page < 999,
                    "UPSTREAM_DATA",
                    "核对流水分页不完整",
                    502,
                )
                page += 1
            require(
                len(ids) == 1,
                "MANUAL_RECONCILIATION_REQUIRED",
                "未找到唯一核心转账引用，保留待核对状态，禁止换键重发",
                409,
            )
            transfer_id = ids.pop()
            action.steps = {**action.steps, "transfer_id": transfer_id}

        result = self.fineract.get_transfer(transfer_id)
        p = action.payload
        require(
            not result.get("reversed") and not result.get("isReversed"),
            "TRANSFER_REVERSED",
            "转账已撤销",
            409,
        )
        require(
            (result.get("fromAccount") or {}).get("id") == p["from_account_id"]
            and (result.get("toAccount") or {}).get("id") == p["to_account_id"]
            and Decimal(str(result.get("transferAmount", result.get("amount", "-1"))))
            == Decimal(p["amount"]),
            "EXECUTION_UNCONFIRMED",
            "转账事实与请求不匹配",
            502,
        )
        references = {}
        for side, account_id in [
            ("from", p["from_account_id"]),
            ("to", p["to_account_id"]),
        ]:
            direct = result.get(side + "SavingsTransaction") or {}
            transaction_id = direct.get("id")
            page = 0
            while transaction_id is None:
                day = result.get("transferDate")
                from services.transaction_service import iso_date

                day = iso_date(day)
                data = self.fineract.search_transactions(
                    account_id, page, 100, fromDate=day, toDate=day
                )
                matches = [
                    r
                    for r in data["items"]
                    if (r.get("transfer") or {}).get("id") == transfer_id
                    and not r.get("reversed")
                    and not r.get("isReversal")
                ]
                require(len(matches) <= 1, "UPSTREAM_DATA", "转账关联交易不唯一", 502)
                if matches:
                    transaction_id = matches[0]["id"]
                    break
                require(
                    data["items"] and (page + 1) * 100 < data["total"] and page < 999,
                    "EXECUTION_UNCONFIRMED",
                    "尚未读取到转账双方流水引用",
                    502,
                )
                page += 1
            references[side + "_transaction_id"] = int(transaction_id)
        action.steps = {**action.steps, **references}
        return safe_json({**result, **references})
