"""Ordinary Demo debit cards backed by real Fineract savings accounts."""

import secrets
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from core.card_crypto import decrypt_pan, encrypt_pan, validate_card_key
from core.errors import require
from core.security import aware, now, SHANGHAI
from models import Action, BankCard, uid
from services.common import audit, lock_user, owned, safe_json

SAVINGS_PRODUCT_NAME = "BANK_AGENT_SAVINGS"
CARD_ACTIONS = {
    "card_application",
    "card_activate",
    "card_reveal",
    "card_controls",
    "card_lock",
    "card_unlock",
    "card_report_lost",
    "card_replace",
}


def _luhn_digit(first_fifteen: str) -> str:
    total = 0
    for index, char in enumerate(first_fifteen):
        value = int(char)
        if index % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return str((10 - total % 10) % 10)


def new_demo_pan() -> str:
    first_fifteen = "622202" + "".join(str(secrets.randbelow(10)) for _ in range(9))
    return first_fifteen + _luhn_digit(first_fifteen)


class CardService:
    def __init__(self, db, fineract, settings):
        self.db, self.fineract, self.settings = db, fineract, settings

    def view(self, card):
        account = self.fineract.get_savings_account(card.fineract_account_id)
        owner = self._user(card)
        require(
            owner is not None and int(account.get("clientId", -1)) == owner.client_id,
            "ACCOUNT_NOT_FOUND",
            "关联账户不可用",
            404,
        )
        summary = account.get("summary") or {}
        return safe_json(
            {
                "id": card.id,
                "account_id": card.fineract_account_id,
                "product_name": card.product_name,
                "alias": card.alias,
                "masked_number": f"•••• •••• •••• {card.last4}",
                "last4": card.last4,
                "status": card.status,
                "currency": (account.get("currency") or {}).get("code", "CNY"),
                "available_balance": str(summary.get("availableBalance", "0")),
                "single_limit": card.single_limit,
                "daily_limit": card.daily_limit,
                "online_enabled": card.online_enabled,
                "pos_enabled": card.pos_enabled,
                "atm_enabled": card.atm_enabled,
                "international_enabled": card.international_enabled,
                "replaces_card_id": card.replaces_card_id,
                "created_at": card.created_at,
                "updated_at": card.updated_at,
            }
        )

    def _user(self, card):
        from models import User

        return self.db.get(User, card.user_id)

    def list(self, user):
        return [
            self.view(row)
            for row in self.db.scalars(
                select(BankCard)
                .where(BankCard.user_id == user.id)
                .order_by(BankCard.created_at, BankCard.id)
            )
        ]

    def detail(self, user, card_id):
        return self.view(owned(self.db, BankCard, card_id, user))

    def rename(self, user, card_id, alias):
        lock_user(self.db, user)
        card = owned(self.db, BankCard, card_id, user)
        card.alias = alias
        card.updated_at = now()
        card.version += 1
        audit(self.db, user, "CARD_ALIAS_CHANGED", card_id=card.id)
        self.db.commit()
        return self.view(card)

    def request_application(self, user, body, key):
        from services.action_service import ActionService

        validate_card_key(self.settings.card_encryption_key)
        request = body.model_dump(mode="json")
        actions = ActionService(self.db, self.fineract, self.settings)
        old = actions.replay(user, "card_application", request, key)
        if old:
            return actions.view(old)
        payload = {**request, "_request": request}
        return actions.view(actions.create(user, "card_application", payload, key))

    def request_activation(self, user, card_id, key):
        from services.action_service import ActionService

        request = {"card_id": card_id}
        actions = ActionService(self.db, self.fineract, self.settings)
        old = actions.replay(user, "card_activate", request, key)
        if old:
            return actions.view(old)
        card = owned(self.db, BankCard, card_id, user)
        require(
            card.status in {"PENDING_ACTIVATION", "ACTIVE"},
            "CARD_STATE",
            "当前卡片状态不可激活",
            409,
        )
        return actions.view(actions.create(user, "card_activate", request, key))

    def request_reveal(self, user, card_id, key):
        from services.action_service import ActionService

        request = {"card_id": card_id}
        actions = ActionService(self.db, self.fineract, self.settings)
        old = actions.replay(user, "card_reveal", request, key)
        if old:
            return actions.view(old)
        card = owned(self.db, BankCard, card_id, user)
        require(card.status == "ACTIVE", "CARD_STATE", "只有正常卡片可以安全查看", 409)
        validate_card_key(self.settings.card_encryption_key)
        return actions.view(actions.create(user, "card_reveal", request, key))

    def reveal_number(self, user, card_id, action_id):
        lock_user(self.db, user)
        card = owned(self.db, BankCard, card_id, user)
        action = owned(self.db, Action, action_id, user)
        require(
            action.kind == "card_reveal"
            and action.status == "SUCCEEDED"
            and action.payload.get("card_id") == card.id,
            "REVEAL_NOT_AUTHORIZED",
            "没有可用的卡号查看授权",
            409,
        )
        expires_at = action.steps.get("reveal_expires_at")
        require(
            expires_at and aware(datetime.fromisoformat(expires_at)) > now(),
            "REVEAL_EXPIRED",
            "卡号查看授权已过期，请重新验证",
            409,
        )
        require(card.status == "ACTIVE", "CARD_STATE", "当前卡片不可查看", 409)
        number = decrypt_pan(
            self.settings.card_encryption_key, card.id, card.pan_ciphertext
        )
        audit(self.db, user, "CARD_NUMBER_REVEALED", action, card_id=card.id)
        self.db.commit()
        return {"number": number, "expires_at": expires_at}

    def request_controls(self, user, card_id, body, key):
        from services.action_service import ActionService

        request = {
            "card_id": card_id,
            **body.model_dump(mode="json", exclude_none=True),
        }
        actions = ActionService(self.db, self.fineract, self.settings)
        old = actions.replay(user, "card_controls", request, key)
        if old:
            return actions.view(old)
        card = owned(self.db, BankCard, card_id, user)
        require(
            card.status in {"ACTIVE", "LOCKED"},
            "CARD_STATE",
            "当前卡片状态不可调整限额或渠道",
            409,
        )
        submitted = body.model_dump(mode="json", exclude_none=True)
        target = {
            "single_limit": Decimal(str(submitted.get("single_limit", card.single_limit))),
            "daily_limit": Decimal(str(submitted.get("daily_limit", card.daily_limit))),
            "online_enabled": submitted.get("online_enabled", card.online_enabled),
            "pos_enabled": submitted.get("pos_enabled", card.pos_enabled),
            "atm_enabled": submitted.get("atm_enabled", card.atm_enabled),
            "international_enabled": submitted.get(
                "international_enabled", card.international_enabled
            ),
        }
        require(
            target["daily_limit"] >= target["single_limit"],
            "CARD_LIMIT_INVALID",
            "日累计限额不得低于单笔限额",
            422,
        )
        enabled = any(
            target[name] and not getattr(card, name)
            for name in (
                "online_enabled",
                "pos_enabled",
                "atm_enabled",
                "international_enabled",
            )
        )
        increased = (
            target["single_limit"] > card.single_limit
            or target["daily_limit"] > card.daily_limit
        )
        risk = "RED" if enabled or increased else "YELLOW"
        values = {
            **{
                key_: str(value) if isinstance(value, Decimal) else value
                for key_, value in target.items()
            },
            "risk": risk,
            "expected_version": card.version,
            "_request": request,
        }
        return actions.view(
            actions.create(
                user,
                "card_controls",
                {"card_id": card.id, **values},
                key,
            )
        )

    def request_state(self, user, card_id, operation, key):
        from services.action_service import ActionService

        rules = {
            "lock": ({"ACTIVE"}, "card_lock"),
            "unlock": ({"LOCKED"}, "card_unlock"),
            "report-lost": ({"ACTIVE", "LOCKED"}, "card_report_lost"),
            "replace": ({"LOST"}, "card_replace"),
        }
        allowed, kind = rules[operation]
        request = {"card_id": card_id}
        actions = ActionService(self.db, self.fineract, self.settings)
        old = actions.replay(user, kind, request, key)
        if old:
            return actions.view(old)
        card = owned(self.db, BankCard, card_id, user)
        require(card.status in allowed, "CARD_STATE", "当前卡片状态不可执行该操作", 409)
        if kind == "card_replace":
            validate_card_key(self.settings.card_encryption_key)
        return actions.view(
            actions.create(
                user,
                kind,
                {
                    **request,
                    "expected_status": card.status,
                    "expected_version": card.version,
                    "_request": request,
                },
                key,
            )
        )

    @staticmethod
    def _external_id(action):
        return f"BANK-CARD-{action.id}"

    def _find_account(self, user, external_id):
        rows = self.fineract.list_client_accounts(user.client_id).get(
            "savingsAccounts", []
        )
        matches = [
            int(row["id"])
            for row in rows
            if row.get("externalId") == external_id
            and int((row.get("depositType") or {}).get("id", 0)) == 100
        ]
        require(
            len(matches) <= 1,
            "MANUAL_RECONCILIATION_REQUIRED",
            "核心银行存在重复卡片账户，禁止继续开户",
            409,
        )
        return matches[0] if matches else None

    def _product_id(self):
        products = self.fineract.savings_products()
        matches = [
            int(row["id"])
            for row in products
            if row.get("name") == SAVINGS_PRODUCT_NAME
            and (row.get("currency") or {}).get("code", "CNY") == "CNY"
        ]
        require(
            len(matches) == 1,
            "CARD_PRODUCT_UNAVAILABLE",
            "未找到唯一的 CNY 演示储蓄产品，请先运行 Fineract Seed",
            503,
        )
        return matches[0]

    @staticmethod
    def _step_key(action, command):
        return f"bank:{action.id}:card:{command}"

    def _ensure_core_account(self, user, action):
        account_id = action.steps.get("account_id")
        external_id = self._external_id(action)
        if not account_id:
            account_id = self._find_account(user, external_id)
        if not account_id:
            today = now().astimezone(SHANGHAI).date().isoformat()
            action.steps = {**action.steps, "pending_step": "create"}
            self.db.commit()
            response = self.fineract.create_savings_account(
                {
                    "clientId": user.client_id,
                    "productId": self._product_id(),
                    "externalId": external_id,
                    "submittedOnDate": today,
                    "nominalAnnualInterestRate": 0.0,
                    "locale": "en",
                    "dateFormat": "yyyy-MM-dd",
                },
                self._step_key(action, "create"),
            )
            account_id = response.get("savingsId") or response.get("resourceId")
            require(
                account_id,
                "EXECUTION_UNCONFIRMED",
                "核心银行开户命令尚未确认",
                502,
            )
        action.steps = {
            **action.steps,
            "account_id": int(account_id),
            "external_id": external_id,
            "pending_step": None,
        }
        self.db.commit()
        return int(account_id)

    def _activate_core_account(self, user, action, account_id):
        today = now().astimezone(SHANGHAI).date().isoformat()
        common = {"locale": "en", "dateFormat": "yyyy-MM-dd"}
        account = self.fineract.get_savings_account(account_id)
        require(
            int(account.get("clientId", -1)) == user.client_id
            and account.get("externalId") == self._external_id(action),
            "ACCOUNT_NOT_FOUND",
            "核心卡片账户归属不匹配",
            404,
        )
        status = account.get("status") or {}
        if status.get("submittedAndPendingApproval"):
            action.steps = {**action.steps, "pending_step": "approve"}
            self.db.commit()
            self.fineract.savings_account_command(
                account_id,
                "approve",
                {**common, "approvedOnDate": today},
                self._step_key(action, "approve"),
            )
            action.steps = {**action.steps, "pending_step": None}
            self.db.commit()
            account = self.fineract.get_savings_account(account_id)
            status = account.get("status") or {}
        if status.get("approved"):
            action.steps = {**action.steps, "pending_step": "activate"}
            self.db.commit()
            self.fineract.savings_account_command(
                account_id,
                "activate",
                {**common, "activatedOnDate": today},
                self._step_key(action, "activate"),
            )
            action.steps = {**action.steps, "pending_step": None}
            self.db.commit()
            account = self.fineract.get_savings_account(account_id)
            status = account.get("status") or {}
        require(
            status.get("active"),
            "EXECUTION_UNCONFIRMED",
            "核心卡片账户尚未激活，需要续办或核对",
            409,
        )
        balance = Decimal(str((account.get("summary") or {}).get("availableBalance", 0)))
        require(balance == 0, "CARD_ACCOUNT_NOT_EMPTY", "新卡账户初始余额必须为零", 409)
        return account

    def _ensure_card(self, user, action, account_id):
        card = self.db.scalar(
            select(BankCard).where(BankCard.application_action_id == action.id)
        )
        if card:
            require(
                card.user_id == user.id and card.fineract_account_id == account_id,
                "CARD_STATE",
                "卡片申请持久化状态不一致",
                409,
            )
            return card
        card_id = uid()
        pan = new_demo_pan()
        card = BankCard(
            id=card_id,
            user_id=user.id,
            fineract_account_id=account_id,
            product_name=action.payload["product_name"],
            alias=action.payload.get("alias", ""),
            pan_ciphertext=encrypt_pan(
                self.settings.card_encryption_key, card_id, pan
            ),
            last4=pan[-4:],
            status="PENDING_ACTIVATION",
            application_action_id=action.id,
        )
        self.db.add(card)
        self.db.flush()
        audit(
            self.db,
            user,
            "CARD_CREATED_PENDING_ACTIVATION",
            action,
            card_id=card.id,
            account_id=account_id,
            last4=card.last4,
        )
        self.db.commit()
        return card

    def execute(self, user, action):
        require(action.kind in CARD_ACTIONS, "UNKNOWN_ACTION", "未知卡片操作", 400)
        if action.kind == "card_reveal":
            card = owned(self.db, BankCard, action.payload["card_id"], user)
            require(card.status == "ACTIVE", "CARD_STATE", "当前卡片不可查看", 409)
            validate_card_key(self.settings.card_encryption_key)
            expires_at = now() + timedelta(seconds=60)
            action.steps = {
                **action.steps,
                "reveal_expires_at": expires_at.isoformat(),
            }
            audit(self.db, user, "CARD_REVEAL_GRANTED", action, card_id=card.id)
            self.db.commit()
            return {"card_id": card.id, "expires_at": expires_at.isoformat()}
        if action.kind == "card_controls":
            card = owned(self.db, BankCard, action.payload["card_id"], user)
            require(
                card.status in {"ACTIVE", "LOCKED"}
                and card.version == action.payload["expected_version"],
                "CARD_CHANGED",
                "卡片设置已变化，请重新提交",
                409,
            )
            card.single_limit = Decimal(action.payload["single_limit"])
            card.daily_limit = Decimal(action.payload["daily_limit"])
            card.online_enabled = action.payload["online_enabled"]
            card.pos_enabled = action.payload["pos_enabled"]
            card.atm_enabled = action.payload["atm_enabled"]
            card.international_enabled = action.payload["international_enabled"]
            card.version += 1
            card.updated_at = now()
            audit(self.db, user, "CARD_CONTROLS_CHANGED", action, card_id=card.id)
            self.db.commit()
            return self.view(card)
        if action.kind in {
            "card_lock",
            "card_unlock",
            "card_report_lost",
            "card_replace",
        }:
            card = owned(self.db, BankCard, action.payload["card_id"], user)
            require(
                card.status == action.payload["expected_status"]
                and card.version == action.payload["expected_version"],
                "CARD_CHANGED",
                "卡片状态已变化，请重新提交",
                409,
            )
            if action.kind == "card_replace":
                validate_card_key(self.settings.card_encryption_key)
                replacement = self.db.scalar(
                    select(BankCard).where(BankCard.application_action_id == action.id)
                )
                if replacement is None:
                    replacement_id = uid()
                    pan = new_demo_pan()
                    replacement = BankCard(
                        id=replacement_id,
                        user_id=user.id,
                        fineract_account_id=card.fineract_account_id,
                        product_name=card.product_name,
                        alias=card.alias,
                        pan_ciphertext=encrypt_pan(
                            self.settings.card_encryption_key, replacement_id, pan
                        ),
                        last4=pan[-4:],
                        status="PENDING_ACTIVATION",
                        single_limit=card.single_limit,
                        daily_limit=card.daily_limit,
                        online_enabled=card.online_enabled,
                        pos_enabled=card.pos_enabled,
                        atm_enabled=card.atm_enabled,
                        international_enabled=card.international_enabled,
                        replaces_card_id=card.id,
                        application_action_id=action.id,
                    )
                    self.db.add(replacement)
                    self.db.flush()
                card.status = "REPLACED"
                event = "CARD_REPLACED"
                result_card = replacement
            else:
                target = {
                    "card_lock": "LOCKED",
                    "card_unlock": "ACTIVE",
                    "card_report_lost": "LOST",
                }[action.kind]
                card.status = target
                event = {
                    "card_lock": "CARD_LOCKED",
                    "card_unlock": "CARD_UNLOCKED",
                    "card_report_lost": "CARD_REPORTED_LOST",
                }[action.kind]
                result_card = card
            card.version += 1
            card.updated_at = now()
            audit(self.db, user, event, action, card_id=card.id)
            self.db.commit()
            return self.view(result_card)
        if action.kind == "card_activate":
            card = owned(self.db, BankCard, action.payload["card_id"], user)
            if card.status == "ACTIVE":
                return self.view(card)
            require(
                card.status == "PENDING_ACTIVATION",
                "CARD_STATE",
                "当前卡片状态不可激活",
                409,
            )
            card.status = "ACTIVE"
            card.updated_at = now()
            card.version += 1
            audit(self.db, user, "CARD_ACTIVATED", action, card_id=card.id)
            self.db.commit()
            return self.view(card)
        if action.kind == "card_reveal":
            card = owned(self.db, BankCard, action.payload["card_id"], user)
            expires_at = action.steps.get("reveal_expires_at")
            require(
                expires_at,
                "MANUAL_RECONCILIATION_REQUIRED",
                "卡号查看授权尚未确认",
                409,
            )
            return {"card_id": card.id, "expires_at": expires_at}
        validate_card_key(self.settings.card_encryption_key)
        account_id = self._ensure_core_account(user, action)
        self._activate_core_account(user, action, account_id)
        return self.view(self._ensure_card(user, action, account_id))

    def reconcile(self, user, action):
        require(action.kind in CARD_ACTIONS, "UNKNOWN_ACTION", "未知卡片操作", 400)
        if action.kind == "card_activate":
            card = owned(self.db, BankCard, action.payload["card_id"], user)
            require(
                card.status == "ACTIVE",
                "MANUAL_RECONCILIATION_REQUIRED",
                "卡片尚未激活",
                409,
            )
            return self.view(card)
        if action.kind == "card_controls":
            card = owned(self.db, BankCard, action.payload["card_id"], user)
            matches = (
                card.single_limit == Decimal(action.payload["single_limit"])
                and card.daily_limit == Decimal(action.payload["daily_limit"])
                and card.online_enabled == action.payload["online_enabled"]
                and card.pos_enabled == action.payload["pos_enabled"]
                and card.atm_enabled == action.payload["atm_enabled"]
                and card.international_enabled
                == action.payload["international_enabled"]
            )
            require(
                matches,
                "MANUAL_RECONCILIATION_REQUIRED",
                "卡片设置尚未确认生效",
                409,
            )
            return self.view(card)
        if action.kind in {
            "card_lock",
            "card_unlock",
            "card_report_lost",
            "card_replace",
        }:
            card = owned(self.db, BankCard, action.payload["card_id"], user)
            if action.kind == "card_replace":
                replacement = self.db.scalar(
                    select(BankCard).where(
                        BankCard.application_action_id == action.id,
                        BankCard.user_id == user.id,
                        BankCard.replaces_card_id == card.id,
                    )
                )
                require(
                    card.status == "REPLACED" and replacement is not None,
                    "MANUAL_RECONCILIATION_REQUIRED",
                    "补卡结果尚未确认",
                    409,
                )
                return self.view(replacement)
            expected = {
                "card_lock": "LOCKED",
                "card_unlock": "ACTIVE",
                "card_report_lost": "LOST",
            }[action.kind]
            require(
                card.status == expected,
                "MANUAL_RECONCILIATION_REQUIRED",
                "卡片状态变更尚未确认",
                409,
            )
            return self.view(card)
        account_id = action.steps.get("account_id") or self._find_account(
            user, self._external_id(action)
        )
        require(
            account_id,
            "MANUAL_RECONCILIATION_REQUIRED",
            "未找到唯一核心卡片账户，禁止重复开户",
            409,
        )
        action.steps = {
            **action.steps,
            "account_id": int(account_id),
            "external_id": self._external_id(action),
        }
        self.db.commit()
        account = self.fineract.get_savings_account(int(account_id))
        require(
            (account.get("status") or {}).get("active"),
            "MANUAL_RECONCILIATION_REQUIRED",
            "核心卡片账户未完成激活，请续办",
            409,
        )
        return self.view(self._ensure_card(user, action, int(account_id)))

    def resume_application(self, user, action):
        require(
            action.kind == "card_application" and action.status in {"EXECUTING", "RECONCILING"},
            "ACTION_STATE",
            "当前卡片申请无需续办",
            409,
        )
        if action.status == "EXECUTING":
            lease = max(300, self.settings.fineract_timeout_seconds * 20)
            require(
                action.executed_at
                and aware(action.executed_at) + timedelta(seconds=lease) < now(),
                "EXECUTION_IN_PROGRESS",
                "执行仍可能进行中，请先等待或只读核对",
                409,
            )
        account_id = action.steps.get("account_id") or self._find_account(
            user, self._external_id(action)
        )
        if account_id:
            action.steps = {
                **action.steps,
                "account_id": int(account_id),
                "external_id": self._external_id(action),
            }
        action.status = "WAITING_CONFIRMATION"
        action.confirmed_at = None
        action.verified_until = None
        action.executed_at = None
        action.steps = {**action.steps, "resumed_at": now().isoformat()}
        action.expires_at = now() + timedelta(days=1)
        audit(self.db, user, "RESUME_REQUIRES_AUTHORIZATION", action)
        self.db.commit()
        return action
