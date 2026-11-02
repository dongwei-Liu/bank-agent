"""Durable deterministic authorization and execution boundary for every write."""

import hmac
import secrets
from datetime import timedelta
from decimal import Decimal
from sqlalchemy import select
from clients.fineract import FineractError
from core.errors import DomainError, require
from core.security import aware, fingerprint, now, otp_digest, SHANGHAI, token
from models import Action, AgentEvent, DailyUsage, AAShare, AACollection, Schedule
from services.common import owned, lock_user, audit, row_dict, safe_json, redact_audit_data

IN_FLIGHT = {"EXECUTING", "RECONCILING"}
TRANSFER_KINDS = {"transfer", "internal_transfer"}
YELLOW_KINDS = {
    "subscription_cancel",
    "subscription_query",
    "card_application",
    "card_lock",
    "card_transaction",
}


class ActionService:
    def __init__(self, db, fineract, settings):
        self.db, self.fineract, self.settings = db, fineract, settings

    def view(self, action):
        return row_dict(
            action,
            (
                "otp_hash",
                "otp_nonce",
                "otp_expires",
                "otp_attempts",
                "dev_otp",
                "verified_until",
                "reserved",
            ),
        )

    def find_by_key(self, user, kind, key):
        """Return a durable request before any preparatory call with side effects.

        Agent workers can be retried after a request was committed.  Looking up the
        stable key first prevents a consumed risk assessment or a refreshed quote
        from turning that retry into a second request.
        """
        lock_user(self.db, user)
        return self.db.scalar(
            select(Action).where(
                Action.user_id == user.id,
                Action.kind == kind,
                Action.idempotency_key == key,
            )
        )

    def replay(self, user, kind, request, key):
        lock_user(self.db, user)
        old = self.db.scalar(
            select(Action).where(
                Action.user_id == user.id,
                Action.kind == kind,
                Action.idempotency_key == key,
            )
        )
        if old:
            require(
                fingerprint(old.payload.get("_request", old.payload))
                == fingerprint(request),
                "IDEMPOTENCY_CONFLICT",
                "同一幂等键的请求参数不同",
                409,
            )
        return old

    def resume(self, user, action_id):
        lock_user(self.db, user)
        action = owned(self.db, Action, action_id, user)
        if action.kind == "card_application":
            from services.card_service import CardService

            return self.view(
                CardService(self.db, self.fineract, self.settings).resume_application(
                    user, action
                )
            )
        require(
            action.kind == "subscription"
            and action.status in IN_FLIGHT
            and action.steps.get("holding_id"),
            "ACTION_STATE",
            "仅可续办已知的未完成定存申请",
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
        from services.investment_service import InvestmentService

        holding = InvestmentService(self.db, self.fineract, self.settings).holding(
            user, action.steps["holding_id"]
        )
        state = holding.get("status") or {}
        require(
            state.get("submittedAndPendingApproval") or state.get("approved"),
            "ACTION_STATE",
            "账户已激活请核对，不可续办",
            409,
        )
        action.status = "WAITING_CONFIRMATION"
        action.confirmed_at = None
        action.verified_until = None
        action.otp_hash = None
        action.dev_otp = None
        action.otp_expires = None
        steps = {**action.steps, "resumed_at": now().isoformat()}
        steps.pop("pending_step", None)
        rejected = steps.pop("rejected_step", None)
        if rejected:
            steps["retry_" + rejected] = steps.get("retry_" + rejected, 0) + 1
        action.steps = steps
        action.expires_at = now() + timedelta(days=1)
        audit(self.db, user, "RESUME_REQUIRES_AUTHORIZATION", action)
        self.db.commit()
        return self.view(action)

    def risk_level(self, user, kind, payload, amount):
        if kind in TRANSFER_KINDS:
            return (
                "RED"
                if self.usage(user).amount + Decimal(str(amount)) > Decimal("1000")
                else "YELLOW"
            )
        if kind == "card_controls":
            return payload.get("risk", "YELLOW")
        return "YELLOW" if kind in YELLOW_KINDS else "RED"

    def create(
        self,
        user,
        kind,
        payload,
        key,
        amount=0,
        *,
        commit=True,
        source="API",
        expires_in: timedelta | None = None,
    ):
        require(
            key and len(key) <= 160,
            "IDEMPOTENCY_KEY_REQUIRED",
            "需要不超过160字符的幂等键",
        )
        lock_user(self.db, user)
        hash_ = fingerprint(payload)
        old = self.db.scalar(
            select(Action).where(
                Action.user_id == user.id,
                Action.kind == kind,
                Action.idempotency_key == key,
            )
        )
        if old:
            require(
                old.request_hash == hash_,
                "IDEMPOTENCY_CONFLICT",
                "同一幂等键的请求参数不同",
                409,
            )
            return old
        action = Action(
            user_id=user.id,
            kind=kind,
            payload=safe_json(payload),
            request_hash=hash_,
            idempotency_key=key,
            amount=Decimal(str(amount)),
            risk_level=self.risk_level(user, kind, payload, amount),
            source=source,
            expires_at=now() + (expires_in or timedelta(days=1)),
        )
        self.db.add(action)
        self.db.flush()
        audit(self.db, user, "ACTION_CREATED", action, kind=kind)
        if commit:
            self.db.commit()
        return action

    def usage(self, user):
        day = now().astimezone(SHANGHAI).date()
        row = self.db.scalar(
            select(DailyUsage).where(
                DailyUsage.user_id == user.id, DailyUsage.day == day
            )
        )
        if not row:
            row = DailyUsage(user_id=user.id, day=day, amount=Decimal(0))
            self.db.add(row)
            self.db.flush()
        return row

    def needs_otp(self, user, action):
        current = self.risk_level(user, action.kind, action.payload, action.amount)
        if action.risk_level != current:
            action.risk_level = current
        return current == "RED"

    def confirm(self, user, action_id, request_hash):
        lock_user(self.db, user)
        action = owned(self.db, Action, action_id, user)
        require(
            hmac.compare_digest(action.request_hash, request_hash),
            "CONFIRMATION_CHANGED",
            "确认内容不匹配",
            409,
        )
        if action.kind == "subscription_query":
            require(
                hmac.compare_digest(action.request_hash, fingerprint(action.payload)),
                "CONFIRMATION_CHANGED",
                "查询条件已变化，请重新发起查询",
                409,
            )
        if action.status in {"SUCCEEDED", *IN_FLIGHT}:
            return self.view(action)
        require(
            action.status
            in {"WAITING_CONFIRMATION", "WAITING_VERIFICATION", "AUTHORIZED"},
            "ACTION_STATE",
            "当前状态不可确认",
            409,
        )
        require(
            action.expires_at is None or aware(action.expires_at) > now(),
            "ACTION_EXPIRED",
            "请求已过期",
            409,
        )
        action.confirmed_at = now()
        if self.needs_otp(user, action) and not self.is_verified(action):
            action.status = "WAITING_VERIFICATION"
            audit(self.db, user, "CONFIRMED_OTP_REQUIRED", action)
            self.db.commit()
            return self.view(action)
        action.status = "AUTHORIZED"
        self.db.commit()
        return self.execute(user, action.id)

    def is_verified(self, action):
        return (
            action.verified_until is not None and aware(action.verified_until) > now()
        )

    def challenge(self, user, action_id):
        locked = lock_user(self.db, user)
        action = owned(self.db, Action, action_id, user)
        require(
            action.status == "WAITING_VERIFICATION",
            "ACTION_STATE",
            "当前不需要验证码",
            409,
        )
        require(
            not locked.otp_locked_until or aware(locked.otp_locked_until) <= now(),
            "OTP_LOCKED",
            "验证暂时锁定",
            429,
        )
        require(
            len(self.settings.otp_secret) >= 32,
            "OTP_UNCONFIGURED",
            "验证码服务未配置",
            503,
        )
        if action.otp_expires:
            last = aware(action.otp_expires) - timedelta(minutes=5)
            require(
                last + timedelta(seconds=30) <= now(),
                "OTP_RATE_LIMIT",
                "请稍后再申请验证码",
                429,
            )
        code = f"{secrets.randbelow(1000000):06d}"
        action.otp_nonce = token()
        action.otp_hash = otp_digest(
            self.settings.otp_secret, action.id, action.otp_nonce, code
        )
        action.otp_expires = now() + timedelta(minutes=5)
        # Do not reset failed attempts on resend: otherwise the limit is bypassable.
        action.dev_otp = code if self.settings.dev_otp_inbox else None
        require(
            self.settings.dev_otp_inbox,
            "OTP_DELIVERY_UNAVAILABLE",
            "尚未配置真实验证码发送器",
            503,
        )
        audit(self.db, user, "OTP_ISSUED", action)
        self.db.commit()
        return {"expires_in": 300, "delivery": "development_inbox"}

    def verify(self, user, action_id, code):
        locked = lock_user(self.db, user)
        action = owned(self.db, Action, action_id, user)
        require(
            action.status == "WAITING_VERIFICATION", "ACTION_STATE", "当前不可验证", 409
        )
        require(
            not locked.otp_locked_until or aware(locked.otp_locked_until) <= now(),
            "OTP_LOCKED",
            "验证暂时锁定",
            429,
        )
        require(
            action.otp_hash
            and action.otp_expires
            and aware(action.otp_expires) > now(),
            "OTP_EXPIRED",
            "验证码无效或已过期",
            400,
        )
        expected = otp_digest(
            self.settings.otp_secret, action.id, action.otp_nonce, code
        )
        if not hmac.compare_digest(expected, action.otp_hash):
            action.otp_attempts += 1
            if action.otp_attempts >= 5:
                locked.otp_locked_until = now() + timedelta(minutes=15)
                action.otp_hash = None
                action.dev_otp = None
                action.otp_attempts = 0
            audit(self.db, user, "OTP_FAILED", action)
            self.db.commit()
            raise DomainError("OTP_INVALID", "验证码错误", 400)
        action.otp_hash = None
        action.dev_otp = None
        action.otp_attempts = 0
        action.verified_until = now() + timedelta(minutes=5)
        action.status = "AUTHORIZED"
        audit(self.db, user, "OTP_VERIFIED", action)
        self.db.commit()
        return self.execute(user, action.id)

    def cancel(self, user, action_id):
        lock_user(self.db, user)
        action = owned(self.db, Action, action_id, user)
        require(
            action.status not in {"SUCCEEDED", *IN_FLIGHT},
            "ACTION_STATE",
            "已执行或执行中的请求不可取消",
            409,
        )
        action.status = "CANCELLED"
        action.otp_hash = None
        action.dev_otp = None
        if action.kind == "card_transaction":
            from services.card_transaction_service import CardTransactionService

            CardTransactionService(
                self.db, self.fineract, self.settings
            ).cancel(user, action)
        if action.kind == "orchestration_authorization":
            from services.orchestration_service import OrchestrationService

            OrchestrationService(
                self.db, self.fineract, self.settings
            ).cancel_authorization(user, action)
        self.finish_links(action, False)
        audit(self.db, user, "ACTION_CANCELLED", action)
        if action.kind == "subscription_query":
            self._record_subscription_query_event(
                action, "SUBSCRIPTION_QUERY_CANCELLED", {"action_id": action.id}
            )
        self.db.commit()
        return self.view(action)

    def execute(self, user, action_id, *, schedule=None):
        lock_user(self.db, user)
        action = owned(self.db, Action, action_id, user)
        # A schedule worker may still hold an AUTHORIZED instance in its identity
        # map after committing the durable intent. Another worker can execute that
        # intent while this worker is waiting for the per-user lock. Refresh and
        # lock the Action row after acquiring the user lock so status checks never
        # use the stale pre-commit object and start a duplicate execution.
        self.db.refresh(action, with_for_update=True)
        if action.status in {"SUCCEEDED", *IN_FLIGHT}:
            return self.view(action)
        require(action.status == "AUTHORIZED", "ACTION_STATE", "尚未授权执行", 409)
        require(
            action.confirmed_at is not None, "CONFIRMATION_REQUIRED", "缺少确认", 409
        )
        if action.kind == "subscription_query":
            return self._execute_subscription_query(user, action)
        # Recheck policy under the same per-user lock before reserving daily usage.
        if (
            schedule is None
            and self.needs_otp(user, action)
            and not self.is_verified(action)
        ):
            action.status = "WAITING_VERIFICATION"
            self.db.commit()
            return self.view(action)
        if action.kind in TRANSFER_KINDS:
            share_id = action.payload.get("aa_share_id")
            if share_id:
                share = self.db.get(AAShare, share_id)
                collection = self.db.scalar(
                    select(AACollection)
                    .where(AACollection.id == share.collection_id)
                    .with_for_update()
                )
                self.db.refresh(share)
                self.db.refresh(action)
                require(
                    collection.status == "OPEN"
                    and share.status == "PENDING"
                    and share.action_id == action.id
                    and action.status == "AUTHORIZED",
                    "COLLECTION_CLOSED",
                    "收款单已关闭或份额已处理",
                    409,
                )
            from services.transfer_service import TransferService

            p = action.payload
            checked = TransferService(self.db, self.fineract).prepare_accounts(
                user,
                p["from_account_id"],
                p["to_account_id"],
                p["amount"],
                p.get("remark", ""),
            )
            require(
                checked["to_client_id"] == p["to_client_id"],
                "RECIPIENT_CHANGED",
                "收款归属已变化",
                409,
            )
            if action.kind == "internal_transfer":
                require(
                    checked["to_client_id"] == user.client_id
                    and p.get("transfer_scope") == "internal",
                    "ACCOUNT_NOT_FOUND",
                    "目标账户不再属于当前用户",
                    404,
                )
            if schedule is not None:
                from services.schedule_service import ScheduleService

                ScheduleService(
                    self.db, self.fineract, self.settings
                ).validate_authorization(user, schedule, action)
            quota = self.usage(user)
            quota.amount += action.amount
            action.quota_date = quota.day
            action.reserved = True
        if action.kind in {"subscription", "redemption"}:
            from services.investment_service import InvestmentService

            InvestmentService(self.db, self.fineract, self.settings).preflight(
                user, action
            )
        action.status = "EXECUTING"
        action.executed_at = now()
        audit(self.db, user, "EXECUTION_STARTED", action)
        # Durable claim before any remote write. A crash leaves an explicit reconciliation item.
        self.db.commit()
        try:
            result = self.dispatch(user, action)
            lock_user(self.db, user)
            action.status = "SUCCEEDED"
            action.result = safe_json(result)
            action.error_code = None
            self.finish_links(action, True)
            audit(self.db, user, "EXECUTION_SUCCEEDED", action)
            self.db.commit()
        except (DomainError, FineractError) as exc:
            self.db.rollback()
            lock_user(self.db, user)
            action = self.db.get(Action, action_id)
            # An error after a remote command may be ambiguous, even a non-2xx response.
            action.status = "RECONCILING"
            if action.kind == "schedule_authorization" and isinstance(exc, DomainError):
                # Schedule authorization only changes local state; a failed recheck is definitive.
                action.status = "FAILED"
            if action.kind == "orchestration_authorization" and isinstance(
                exc, DomainError
            ):
                # Task authorization only changes local task state.
                action.status = "FAILED"
            if (
                action.kind in TRANSFER_KINDS
                and isinstance(exc, FineractError)
                and exc.status in {400, 403}
                and not action.steps.get("transfer_id")
            ):
                action.status = "FAILED"
                if action.reserved:
                    quota = self.db.scalar(
                        select(DailyUsage).where(
                            DailyUsage.user_id == user.id,
                            DailyUsage.day == action.quota_date,
                        )
                    )
                    quota.amount -= action.amount
                    action.reserved = False
                self.finish_links(action, False)
            if (
                action.kind == "subscription"
                and isinstance(exc, FineractError)
                and exc.status in {400, 403}
                and action.steps.get("holding_id")
                and action.steps.get("pending_step") in {"approve", "activate"}
            ):
                action.steps = {
                    **action.steps,
                    "rejected_step": action.steps["pending_step"],
                    "upstream_status": exc.status,
                }
            if action.kind == "subscription_cancel" and isinstance(
                exc, DomainError
            ):
                action.status = "FAILED"
            if (
                action.kind.startswith("card_")
                and isinstance(exc, DomainError)
                and exc.code
                in {
                    "CARD_CHANGED",
                    "CARD_STATE",
                    "CARD_ENCRYPTION_UNCONFIGURED",
                    "CARD_NOT_ACTIVE",
                    "CARD_LOCKED",
                    "CARD_LOST",
                    "CARD_REPLACED",
                    "CARD_CHANNEL_BLOCKED",
                    "CARD_INTERNATIONAL_DISABLED",
                    "CARD_SINGLE_LIMIT_EXCEEDED",
                    "CARD_DAILY_LIMIT_EXCEEDED",
                    "INSUFFICIENT_FUNDS",
                    "MERCHANT_UNAVAILABLE",
                    "CARD_TRANSACTION_STATE",
                }
            ):
                action.status = "FAILED"
            if (
                action.kind == "card_transaction"
                and isinstance(exc, DomainError)
                and not action.steps.get("card_remote_started")
            ):
                action.status = "FAILED"
            if (
                action.kind == "card_transaction"
                and isinstance(exc, FineractError)
                and exc.status in {400, 403}
                and not action.steps.get("transfer_id")
            ):
                action.status = "FAILED"
            if action.kind == "card_transaction" and action.status == "FAILED":
                from services.card_transaction_service import CardTransactionService

                CardTransactionService(
                    self.db, self.fineract, self.settings
                ).mark_failed(
                    user,
                    action,
                    exc.code if isinstance(exc, DomainError) else "UPSTREAM_REJECTED",
                )
            action.error_code = (
                exc.code if isinstance(exc, DomainError) else "UPSTREAM_ERROR"
            )
            audit(
                self.db,
                user,
                "EXECUTION_" + action.status,
                action,
                code=action.error_code,
            )
            self.db.commit()
        return self.view(action)

    def _record_subscription_query_event(self, action, event_type, data):
        payload = action.payload or {}
        conversation_id = payload.get("conversation_id")
        run_id = payload.get("run_id")
        trace_id = payload.get("trace_id")
        if not conversation_id or not run_id or not trace_id:
            return
        self.db.add(AgentEvent(
            conversation_id=conversation_id,
            run_id=run_id,
            trace_id=trace_id,
            type=event_type,
            data=redact_audit_data(data),
        ))

    def _execute_subscription_query(self, user, action):
        """Run a confirmed read and commit its result and timeline event atomically."""
        from services.subscription_planning_service import SubscriptionPlanningService

        action_id = action.id
        action.status = "EXECUTING"
        action.executed_at = now()
        action.error_code = None
        try:
            result = SubscriptionPlanningService(
                self.db, self.fineract, self.settings
            ).execute_agent_query(user, action.payload)
            action.status = "SUCCEEDED"
            action.result = safe_json({
                "result_id": result["result_id"],
                "result_kind": result["result_kind"],
            })
            audit(self.db, user, "SUBSCRIPTION_QUERY_SUCCEEDED", action)
            self._record_subscription_query_event(action, "SUBSCRIPTION_QUERY_COMPLETED", {
                "action_id": action.id,
                "result_id": result["result_id"],
                "result_kind": result["result_kind"],
            })
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            lock_user(self.db, user)
            action = owned(self.db, Action, action_id, user)
            self.db.refresh(action, with_for_update=True)
            if action.status == "SUCCEEDED":
                # The commit acknowledgement may have been lost after the
                # transaction reached PostgreSQL. Preserve the committed result
                # instead of resetting a completed read for a second execution.
                return self.view(action)
            # This Action performs reads only. A failure is safe to retry with the
            # same confirmation and must never be treated as an unknown write.
            action.status = "AUTHORIZED"
            action.error_code = (
                exc.code if isinstance(exc, DomainError) else "SUBSCRIPTION_QUERY_FAILED"
            )
            audit(self.db, user, "SUBSCRIPTION_QUERY_FAILED", action,
                  code=action.error_code)
            self._record_subscription_query_event(action, "SUBSCRIPTION_QUERY_FAILED", {
                "action_id": action.id,
                "error_code": action.error_code,
            })
            self.db.commit()
        return self.view(action)

    def dispatch(self, user, action):
        if action.kind == "subscription_query":
            from services.subscription_planning_service import SubscriptionPlanningService

            return SubscriptionPlanningService(
                self.db, self.fineract, self.settings
            ).execute_agent_query(user, action.payload)
        if action.kind in TRANSFER_KINDS:
            from services.transfer_service import TransferService

            return TransferService(self.db, self.fineract).execute(user, action)
        if action.kind == "schedule_authorization":
            schedule = owned(self.db, Schedule, action.payload["schedule_id"], user)
            from services.schedule_service import ScheduleService

            ScheduleService(self.db, self.fineract, self.settings).confirm_authorization(
                user, schedule, action
            )
            schedule.authorization_hash = action.payload["schedule_hash"]
            schedule.status = "ACTIVE"
            schedule.authorization_action_id = action.id
            self.db.commit()
            return {"schedule_id": schedule.id, "authorized": True}
        if action.kind == "subscription_cancel":
            from services.subscription_service import SubscriptionService

            return SubscriptionService(
                self.db, self.fineract, self.settings
            ).execute_cancel(user, action)
        if action.kind == "orchestration_authorization":
            from services.orchestration_service import OrchestrationService

            return OrchestrationService(
                self.db, self.fineract, self.settings
            ).authorize(user, action)
        if action.kind == "card_transaction":
            from services.card_transaction_service import CardTransactionService

            return CardTransactionService(
                self.db, self.fineract, self.settings
            ).execute(user, action)
        if action.kind.startswith("card_"):
            from services.card_service import CardService

            return CardService(self.db, self.fineract, self.settings).execute(
                user, action
            )
        from services.investment_service import InvestmentService

        return InvestmentService(self.db, self.fineract, self.settings).execute(
            user, action
        )

    def finish_links(self, action, success):
        if action.kind not in TRANSFER_KINDS:
            return
        share_id = action.payload.get("aa_share_id")
        if share_id:
            share = self.db.get(AAShare, share_id)
            if not share or share.action_id != action.id:
                return
            share.status = "PAID" if success else "UNPAID"
            if not success:
                share.action_id = None
            shares = self.db.scalars(
                select(AAShare).where(AAShare.collection_id == share.collection_id)
            ).all()
            if all(s.status in {"PAID", "SELF_PAID"} for s in shares):
                self.db.get(AACollection, share.collection_id).status = "COMPLETED"

    def reconcile(self, user, action_id):
        lock_user(self.db, user)
        action = owned(self.db, Action, action_id, user)
        require(action.status in IN_FLIGHT, "ACTION_STATE", "无需核对", 409)
        # Read-only reconciliation for transfer, no unguarded retry of a possibly posted payment.
        if action.kind in TRANSFER_KINDS:
            from services.transfer_service import TransferService

            result = TransferService(self.db, self.fineract).reconcile(user, action)
        elif action.kind in {"subscription", "redemption"}:
            from services.investment_service import InvestmentService

            result = InvestmentService(self.db, self.fineract, self.settings).reconcile(
                user, action
            )
        elif action.kind == "subscription_cancel":
            from services.subscription_service import SubscriptionService

            result = SubscriptionService(
                self.db, self.fineract, self.settings
            ).reconcile_cancel(user, action)
        elif action.kind == "card_transaction":
            from services.card_transaction_service import CardTransactionService

            result = CardTransactionService(
                self.db, self.fineract, self.settings
            ).reconcile(user, action)
        elif action.kind.startswith("card_"):
            from services.card_service import CardService

            result = CardService(
                self.db, self.fineract, self.settings
            ).reconcile(user, action)
        else:
            schedule = owned(self.db, Schedule, action.payload["schedule_id"], user)
            require(
                schedule.authorization_action_id == action.id
                and schedule.status == "ACTIVE",
                "MANUAL_RECONCILIATION_REQUIRED",
                "授权未生效",
                409,
            )
            result = {"schedule_id": schedule.id, "authorized": True}
        action.status = "SUCCEEDED"
        action.error_code = None
        action.result = safe_json(result)
        self.finish_links(action, True)
        audit(self.db, user, "RECONCILED", action)
        self.db.commit()
        return self.view(action)
