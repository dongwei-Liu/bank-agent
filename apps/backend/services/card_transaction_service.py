"""Deterministic Demo card authorization and Fineract settlement boundary."""

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from core.errors import DomainError, require
from core.security import SHANGHAI, aware, now
from models import BankCard, CardAuthorization, Merchant
from services.account_service import AccountService
from services.common import audit, lock_user, owned, safe_json


class CardTransactionService:
    def __init__(self, db, fineract, settings):
        self.db, self.fineract, self.settings = db, fineract, settings
        self.accounts = AccountService(fineract)

    @staticmethod
    def merchant_view(merchant):
        return {
            "id": merchant.id,
            "name": merchant.name,
            "category": merchant.category,
        }

    def list_merchants(self):
        rows = self.db.scalars(
            select(Merchant)
            .where(
                Merchant.adapter_type == "demo_card",
                Merchant.active.is_(True),
                Merchant.fineract_account_id.is_not(None),
            )
            .order_by(Merchant.name, Merchant.id)
        ).all()
        return [self.merchant_view(row) for row in rows]

    def authorization_view(self, authorization):
        merchant = self.db.get(Merchant, authorization.merchant_id)
        return {
            "id": authorization.id,
            "card_id": authorization.card_id,
            "merchant_id": authorization.merchant_id,
            "merchant_name": merchant.name if merchant else "未知商户",
            "merchant_category": merchant.category if merchant else "未分类",
            "amount": authorization.amount,
            "currency": authorization.currency,
            "channel": authorization.channel,
            "country_code": authorization.country_code,
            "status": authorization.status,
            "decline_code": authorization.decline_code,
            "action_id": authorization.action_id,
            "fineract_transfer_id": authorization.fineract_transfer_id,
            "from_transaction_id": authorization.from_transaction_id,
            "to_transaction_id": authorization.to_transaction_id,
            "created_at": authorization.created_at,
            "updated_at": authorization.updated_at,
        }

    def list_transactions(self, user, card_id):
        owned(self.db, BankCard, card_id, user)
        rows = self.db.scalars(
            select(CardAuthorization)
            .where(
                CardAuthorization.user_id == user.id,
                CardAuthorization.card_id == card_id,
            )
            .order_by(CardAuthorization.created_at.desc(), CardAuthorization.id.desc())
        ).all()
        return [self.authorization_view(row) for row in rows]

    @staticmethod
    def request_payload(body):
        return {
            "card_id": body.card_id,
            "merchant_id": body.merchant_id,
            "amount": str(body.amount),
            "currency": "CNY",
            "channel": body.channel,
            "country_code": body.country_code,
        }

    def request(self, user, body, key):
        from services.action_service import ActionService

        request = self.request_payload(body)
        actions = ActionService(self.db, self.fineract, self.settings)
        old = actions.replay(user, "card_transaction", request, key)
        if old:
            authorization = self.db.scalar(
                select(CardAuthorization).where(
                    CardAuthorization.user_id == user.id,
                    CardAuthorization.action_id == old.id,
                )
            )
            require(
                authorization is not None,
                "UPSTREAM_DATA",
                "卡片授权记录不完整",
                500,
            )
            return actions.view(old)

        card = owned(self.db, BankCard, body.card_id, user)
        merchant = self.db.get(Merchant, body.merchant_id)
        require(
            merchant is not None
            and merchant.adapter_type == "demo_card"
            and merchant.active
            and merchant.fineract_account_id is not None,
            "MERCHANT_UNAVAILABLE",
            "演示商户不可用",
            409,
        )
        payload = {
            **request,
            "_request": request,
            "card_version": card.version,
            "merchant_account_id": merchant.fineract_account_id,
        }
        action = actions.create(
            user,
            "card_transaction",
            payload,
            key,
            amount=body.amount,
            commit=False,
        )
        authorization = CardAuthorization(
            user_id=user.id,
            card_id=card.id,
            merchant_id=merchant.id,
            idempotency_key=key,
            amount=body.amount,
            currency="CNY",
            channel=body.channel,
            country_code=body.country_code,
            status="PENDING",
            action_id=action.id,
        )
        self.db.add(authorization)
        self.db.flush()
        action.payload = {**action.payload, "authorization_id": authorization.id}
        audit(
            self.db,
            user,
            "CARD_TRANSACTION_REQUESTED",
            action,
            authorization_id=authorization.id,
            card_id=card.id,
            merchant_id=merchant.id,
        )
        self.db.commit()
        return actions.view(action)

    def _authorization(self, user, action, *, lock=False):
        query = select(CardAuthorization).where(
            CardAuthorization.id == action.payload.get("authorization_id"),
            CardAuthorization.user_id == user.id,
            CardAuthorization.action_id == action.id,
        )
        if lock:
            query = query.with_for_update()
        authorization = self.db.scalar(query)
        require(
            authorization is not None,
            "UPSTREAM_DATA",
            "卡片授权记录不存在",
            500,
        )
        return authorization

    def _decline(self, user, action, authorization, code, message):
        authorization.status = "DECLINED"
        authorization.decline_code = code
        audit(
            self.db,
            user,
            "CARD_TRANSACTION_DECLINED",
            action,
            authorization_id=authorization.id,
            card_id=authorization.card_id,
            merchant_id=authorization.merchant_id,
            code=code,
        )
        self.db.commit()
        raise DomainError(code, message, 409)

    def _daily_total(self, authorization):
        local_day = now().astimezone(SHANGHAI).date()
        start = datetime.combine(local_day, time.min, SHANGHAI).astimezone(timezone.utc)
        end = start + timedelta(days=1)
        return self.db.scalar(
            select(func.coalesce(func.sum(CardAuthorization.amount), 0)).where(
                CardAuthorization.user_id == authorization.user_id,
                CardAuthorization.card_id == authorization.card_id,
                CardAuthorization.id != authorization.id,
                CardAuthorization.status.in_(["EXECUTING", "APPROVED"]),
                CardAuthorization.created_at >= start,
                CardAuthorization.created_at < end,
            )
        ) or Decimal("0")

    def _policy(self, user, action, authorization):
        card = owned(self.db, BankCard, authorization.card_id, user)
        merchant = self.db.get(Merchant, authorization.merchant_id)
        if card.version != action.payload.get("card_version"):
            self._decline(
                user,
                action,
                authorization,
                "CARD_CHANGED",
                "卡片设置已变化，请重新发起",
            )
        if card.status != "ACTIVE":
            code, message = {
                "PENDING_ACTIVATION": ("CARD_NOT_ACTIVE", "卡片尚未激活"),
                "LOCKED": ("CARD_LOCKED", "卡片已锁定"),
                "LOST": ("CARD_LOST", "卡片已挂失"),
                "REPLACED": ("CARD_REPLACED", "卡片已补换"),
            }.get(card.status, ("CARD_NOT_ACTIVE", "卡片当前不可交易"))
            self._decline(user, action, authorization, code, message)
        enabled = {
            "ONLINE": card.online_enabled,
            "POS": card.pos_enabled,
            "ATM": card.atm_enabled,
        }[authorization.channel]
        if not enabled:
            self._decline(
                user,
                action,
                authorization,
                "CARD_CHANNEL_BLOCKED",
                "该交易渠道已关闭",
            )
        if authorization.country_code != "CN" and not card.international_enabled:
            self._decline(
                user,
                action,
                authorization,
                "CARD_INTERNATIONAL_DISABLED",
                "境外交易未开启",
            )
        if authorization.amount > card.single_limit:
            self._decline(
                user,
                action,
                authorization,
                "CARD_SINGLE_LIMIT_EXCEEDED",
                "超过卡片单笔限额",
            )
        if self._daily_total(authorization) + authorization.amount > card.daily_limit:
            self._decline(
                user,
                action,
                authorization,
                "CARD_DAILY_LIMIT_EXCEEDED",
                "超过卡片日累计限额",
            )
        if not (
            merchant
            and merchant.active
            and merchant.adapter_type == "demo_card"
            and merchant.fineract_account_id == action.payload.get("merchant_account_id")
        ):
            self._decline(
                user,
                action,
                authorization,
                "MERCHANT_UNAVAILABLE",
                "演示商户不可用",
            )

        sender = self.accounts.get_account(user, card.fineract_account_id)
        self.accounts.require_active(sender)
        target = self.fineract.get_savings_account(merchant.fineract_account_id)
        self.accounts.require_active(target)
        require(
            (target.get("depositType") or {}).get("id") == 100
            and (target.get("currency") or {}).get("code") == "CNY",
            "MERCHANT_UNAVAILABLE",
            "演示商户结算账户不可用",
            409,
        )
        available = Decimal(
            str((sender.get("summary") or {}).get("availableBalance", 0))
        )
        if available < authorization.amount:
            self._decline(
                user,
                action,
                authorization,
                "INSUFFICIENT_FUNDS",
                "余额不足",
            )
        return card, merchant, sender, target

    def description(self, authorization):
        return f"[Card:{authorization.id}] Demo merchant purchase"

    def execute(self, user, action):
        lock_user(self.db, user)
        authorization = self._authorization(user, action, lock=True)
        require(
            authorization.status in {"PENDING", "EXECUTING"},
            "CARD_TRANSACTION_STATE",
            "卡片交易状态不可执行",
            409,
        )
        _card, _merchant, sender, target = self._policy(user, action, authorization)
        authorization.status = "EXECUTING"
        authorization.decline_code = None
        self.db.commit()

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
            "transferAmount": str(authorization.amount),
            "transferDescription": self.description(authorization),
            "locale": "en",
            "dateFormat": "yyyy-MM-dd",
        }
        action.steps = {**action.steps, "card_remote_started": True}
        self.db.commit()
        response = self.fineract.create_transfer(
            payload, f"bank:{action.id}:card-transaction"
        )
        require(
            response.get("resourceId") and not response.get("rollbackTransaction"),
            "EXECUTION_UNCONFIRMED",
            "核心入账尚未确认",
            502,
        )
        authorization.fineract_transfer_id = int(response["resourceId"])
        action.steps = {
            **action.steps,
            "transfer_id": authorization.fineract_transfer_id,
        }
        self.db.commit()
        return self.reconcile(user, action)

    def reconcile(self, user, action):
        authorization = self._authorization(user, action, lock=True)
        transfer_id = authorization.fineract_transfer_id or action.steps.get(
            "transfer_id"
        )
        if not transfer_id:
            start = aware(action.executed_at).astimezone(SHANGHAI).date().isoformat()
            end = now().astimezone(SHANGHAI).date().isoformat()
            ids = set()
            page = 0
            while True:
                data = self.fineract.search_transactions(
                    self.db.get(BankCard, authorization.card_id).fineract_account_id,
                    page,
                    100,
                    fromDate=start,
                    toDate=end,
                )
                for row in data["items"]:
                    transfer = row.get("transfer") or {}
                    if transfer.get("transferDescription") == self.description(authorization):
                        ids.add(int(transfer["id"]))
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
                "未找到唯一核心刷卡转账，保留待核对状态，禁止换键重发",
                409,
            )
            transfer_id = ids.pop()

        result = self.fineract.get_transfer(int(transfer_id))
        card = owned(self.db, BankCard, authorization.card_id, user)
        merchant = self.db.get(Merchant, authorization.merchant_id)
        require(
            not result.get("reversed")
            and not result.get("isReversed")
            and (result.get("fromAccount") or {}).get("id") == card.fineract_account_id
            and (result.get("toAccount") or {}).get("id") == merchant.fineract_account_id
            and Decimal(str(result.get("transferAmount", result.get("amount", "-1"))))
            == authorization.amount,
            "EXECUTION_UNCONFIRMED",
            "核心刷卡转账与授权不匹配",
            502,
        )
        from_tx = self._transaction_reference(
            result,
            "from",
            card.fineract_account_id,
            int(transfer_id),
        )
        to_tx = self._transaction_reference(
            result,
            "to",
            merchant.fineract_account_id,
            int(transfer_id),
        )
        authorization.status = "APPROVED"
        authorization.decline_code = None
        authorization.fineract_transfer_id = int(transfer_id)
        authorization.from_transaction_id = int(from_tx)
        authorization.to_transaction_id = int(to_tx)
        action.steps = {
            **action.steps,
            "transfer_id": int(transfer_id),
            "from_transaction_id": int(from_tx),
            "to_transaction_id": int(to_tx),
        }
        audit(
            self.db,
            user,
            "CARD_TRANSACTION_APPROVED",
            action,
            authorization_id=authorization.id,
            card_id=card.id,
            merchant_id=merchant.id,
            transfer_id=int(transfer_id),
        )
        self.db.commit()
        return safe_json(self.authorization_view(authorization))

    def _transaction_reference(self, transfer, side, account_id, transfer_id):
        direct = transfer.get(side + "SavingsTransaction") or {}
        transaction_id = direct.get("id")
        page = 0
        while transaction_id is None:
            from services.transaction_service import iso_date

            day = iso_date(transfer.get("transferDate"))
            data = self.fineract.search_transactions(
                account_id, page, 100, fromDate=day, toDate=day
            )
            matches = [
                row
                for row in data["items"]
                if int((row.get("transfer") or {}).get("id", -1)) == transfer_id
                and not row.get("reversed")
                and not row.get("isReversal")
            ]
            require(len(matches) <= 1, "UPSTREAM_DATA", "刷卡关联流水不唯一", 502)
            if matches:
                transaction_id = matches[0]["id"]
                break
            require(
                data["items"]
                and (page + 1) * 100 < data["total"]
                and page < 999,
                "EXECUTION_UNCONFIRMED",
                "尚未读取到刷卡双方流水引用",
                502,
            )
            page += 1
        return int(transaction_id)

    def mark_failed(self, user, action, code):
        authorization = self._authorization(user, action, lock=True)
        if authorization.status not in {"APPROVED", "DECLINED"}:
            authorization.status = "DECLINED"
            authorization.decline_code = code
            audit(
                self.db,
                user,
                "CARD_TRANSACTION_DECLINED",
                action,
                authorization_id=authorization.id,
                code=code,
            )

    def cancel(self, user, action):
        authorization = self._authorization(user, action, lock=True)
        if authorization.status == "PENDING":
            authorization.status = "DECLINED"
            authorization.decline_code = "ACTION_CANCELLED"
            audit(
                self.db,
                user,
                "CARD_TRANSACTION_CANCELLED",
                action,
                authorization_id=authorization.id,
            )
