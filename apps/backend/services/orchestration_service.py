"""Deterministic fixed birthday DAG with Fineract-backed fund reservations."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import and_, or_, select

from clients.fineract import FineractError, FineractUnavailableError
from core.errors import DomainError, require
from core.security import SHANGHAI, aware, fingerprint, now
from models import (
    Action,
    DemoOrder,
    FundReservation,
    Merchant,
    OrchestrationTask,
    PersonalEvent,
    TaskEdge,
    TaskEvent,
    TaskNode,
)
from services.account_service import AccountService
from services.common import audit, lock_user, owned, row_dict, safe_json


TEMPLATE = "BIRTHDAY_GIFTS_V1"
FLOWER_MERCHANT = "demo-orchestration:flower"
CAKE_MERCHANT = "demo-orchestration:cake"
TERMINAL_TASKS = {"SUCCEEDED", "FAILED", "CANCELLED"}
TERMINAL_NODES = {"SUCCEEDED", "FAILED", "CANCELLED", "SKIPPED"}


class OrchestrationService:
    def __init__(self, db, fineract, settings):
        self.db, self.fineract, self.settings = db, fineract, settings
        self.accounts = AccountService(fineract)

    # ---- public CRUD -----------------------------------------------------

    def save_event(self, user, request, key):
        lock_user(self.db, user)
        raw = request.model_dump(mode="json")
        old = self.db.scalar(
            select(PersonalEvent).where(
                PersonalEvent.user_id == user.id,
                PersonalEvent.idempotency_key == key,
            )
        )
        if old:
            require(
                old.request_hash == fingerprint(raw),
                "IDEMPOTENCY_CONFLICT",
                "同一幂等键的个人事件参数不同",
                409,
            )
            return self.event_view(old)
        self._validate_event_date(request.event_date)
        event = PersonalEvent(
            user_id=user.id,
            kind="BIRTHDAY",
            label=request.label,
            event_date=request.event_date,
            status="ACTIVE",
            idempotency_key=key,
            request_hash=fingerprint(raw),
        )
        self.db.add(event)
        self.db.flush()
        audit(
            self.db,
            user,
            "PERSONAL_EVENT_CREATED",
            resource_type="personal_event",
            resource_id=event.id,
            kind=event.kind,
        )
        self.db.commit()
        return self.event_view(event)

    def list_events(self, user):
        return [
            self.event_view(row)
            for row in self.db.scalars(
                select(PersonalEvent)
                .where(PersonalEvent.user_id == user.id)
                .order_by(PersonalEvent.event_date, PersonalEvent.created_at)
            )
        ]

    def event_view(self, event):
        return row_dict(event, ("request_hash", "idempotency_key"))

    def create_birthday_task(self, user, request, key, *, source="API"):
        lock_user(self.db, user)
        request_data = request.model_dump(mode="json")
        request_hash = fingerprint(request_data)
        old = self.db.scalar(
            select(OrchestrationTask).where(
                OrchestrationTask.user_id == user.id,
                OrchestrationTask.idempotency_key == key,
            )
        )
        if old:
            require(
                old.request_hash == request_hash,
                "IDEMPOTENCY_CONFLICT",
                "同一幂等键的生日任务参数不同",
                409,
            )
            return self.view(user, old.id)

        self._validate_event_date(request.event_date)
        account = self.accounts.get_account(user, request.from_account_id)
        self.accounts.require_active(account)
        require(
            (account.get("currency") or {}).get("code") == "CNY",
            "UNSUPPORTED_CURRENCY",
            "只支持 CNY 账户",
        )
        total = Decimal(str(request.flower_amount)) + Decimal(str(request.cake_amount))
        require(
            self.accounts.get_balance(user, request.from_account_id).balance >= total,
            "INSUFFICIENT_FUNDS",
            "当前可用余额不足以授权完整生日计划",
        )
        merchants = self._merchants()
        flower_merchant, cake_merchant = merchants["flower"], merchants["cake"]

        event = self.db.scalar(
            select(PersonalEvent)
            .where(
                PersonalEvent.user_id == user.id,
                PersonalEvent.kind == "BIRTHDAY",
                PersonalEvent.label == request.label,
                PersonalEvent.event_date == request.event_date,
                PersonalEvent.status == "ACTIVE",
            )
            .order_by(PersonalEvent.created_at)
        )
        if event is None:
            event = PersonalEvent(
                user_id=user.id,
                kind="BIRTHDAY",
                label=request.label,
                event_date=request.event_date,
                status="ACTIVE",
                idempotency_key="task-event:" + fingerprint({"key": key}),
                request_hash=fingerprint(
                    {"label": request.label, "event_date": request.event_date.isoformat()}
                ),
            )
            self.db.add(event)
            self.db.flush()

        reserve_at = datetime.combine(
            request.event_date.replace(day=1), time(hour=9), tzinfo=SHANGHAI
        )
        purchase_at = datetime.combine(
            request.event_date - timedelta(days=2), time(hour=9), tzinfo=SHANGHAI
        )
        if reserve_at < now():
            reserve_at = now()
        plan = {
            "template": TEMPLATE,
            "event_id": event.id,
            "event_date": request.event_date.isoformat(),
            "label": request.label,
            "from_account_id": request.from_account_id,
            "currency": "CNY",
            "flower": {
                "amount": str(request.flower_amount),
                "merchant_id": flower_merchant.id,
                "merchant_account_id": flower_merchant.fineract_account_id,
                "reserve_at": reserve_at.isoformat(),
                "purchase_at": purchase_at.isoformat(),
            },
            "cake": {
                "amount": str(request.cake_amount),
                "merchant_id": cake_merchant.id,
                "merchant_account_id": cake_merchant.fineract_account_id,
                "reserve_at": reserve_at.isoformat(),
                "purchase_at": purchase_at.isoformat(),
            },
        }
        task = OrchestrationTask(
            user_id=user.id,
            event_id=event.id,
            template=TEMPLATE,
            status="WAITING_AUTHORIZATION",
            from_account_id=request.from_account_id,
            total_amount=total,
            currency="CNY",
            plan_hash=fingerprint(plan),
            idempotency_key=key,
            request_hash=request_hash,
        )
        self.db.add(task)
        self.db.flush()

        nodes = self._create_nodes(
            task,
            reserve_at,
            purchase_at,
            Decimal(str(request.flower_amount)),
            Decimal(str(request.cake_amount)),
            flower_merchant,
            cake_merchant,
        )
        self._create_edges(task, nodes)
        reservations = {}
        for purpose in ("flower", "cake"):
            node = nodes[f"reserve_{purpose}"]
            reservation = FundReservation(
                task_id=task.id,
                node_id=node.id,
                user_id=user.id,
                purpose=purpose.upper(),
                account_id=request.from_account_id,
                amount=node.amount,
                currency="CNY",
                status="PENDING",
                hold_key=f"task:{task.id}:hold:{purpose}",
                release_key=f"task:{task.id}:release:{purpose}",
            )
            self.db.add(reservation)
            reservations[purpose] = reservation
        self.db.flush()
        for purpose, merchant in (("flower", flower_merchant), ("cake", cake_merchant)):
            node = nodes[f"purchase_{purpose}"]
            order_request = {
                "task_id": task.id,
                "purpose": purpose,
                "merchant_id": merchant.id,
                "amount": str(node.amount),
                "currency": "CNY",
            }
            self.db.add(
                DemoOrder(
                    task_id=task.id,
                    node_id=node.id,
                    user_id=user.id,
                    merchant_id=merchant.id,
                    reservation_id=reservations[purpose].id,
                    amount=node.amount,
                    currency="CNY",
                    status="PENDING",
                    idempotency_key=f"task:{task.id}:order:{purpose}",
                    request_hash=fingerprint(order_request),
                )
            )

        from services.action_service import ActionService

        action_payload = {
            "task_id": task.id,
            "template": TEMPLATE,
            "plan_hash": task.plan_hash,
            "plan": plan,
            "_request": request_data,
        }
        action = ActionService(
            self.db, self.fineract, self.settings
        ).create(
            user,
            "orchestration_authorization",
            action_payload,
            f"task-auth:{task.id}",
            total,
            commit=False,
            source=source,
        )
        task.authorization_action_id = action.id
        self._event(task, "TASK_CREATED", {"template": TEMPLATE})
        audit(
            self.db,
            user,
            "ORCHESTRATION_TASK_CREATED",
            action,
            resource_type="orchestration_task",
            resource_id=task.id,
            template=TEMPLATE,
        )
        self.db.commit()
        return self.view(user, task.id)

    def list(self, user):
        rows = self.db.scalars(
            select(OrchestrationTask)
            .where(OrchestrationTask.user_id == user.id)
            .order_by(OrchestrationTask.created_at.desc())
        ).all()
        return [self.view(user, row.id) for row in rows]

    def view(self, user, task_id):
        task = owned(self.db, OrchestrationTask, task_id, user)
        event = self.db.get(PersonalEvent, task.event_id)
        nodes = self.db.scalars(
            select(TaskNode)
            .where(TaskNode.task_id == task.id)
            .order_by(TaskNode.created_at, TaskNode.node_key)
        ).all()
        node_by_id = {node.id: node for node in nodes}
        edges = self.db.scalars(
            select(TaskEdge).where(TaskEdge.task_id == task.id).order_by(TaskEdge.id)
        ).all()
        events = self.db.scalars(
            select(TaskEvent)
            .where(TaskEvent.task_id == task.id)
            .order_by(TaskEvent.id)
        ).all()
        reservations = self.db.scalars(
            select(FundReservation)
            .where(FundReservation.task_id == task.id)
            .order_by(FundReservation.purpose)
        ).all()
        orders = self.db.scalars(
            select(DemoOrder)
            .where(DemoOrder.task_id == task.id)
            .order_by(DemoOrder.created_at)
        ).all()
        action = self.db.get(Action, task.authorization_action_id) if task.authorization_action_id else None
        return safe_json(
            {
                **row_dict(task, ("idempotency_key", "request_hash", "lease_until")),
                "event": self.event_view(event),
                "authorization": {
                    "action_id": action.id,
                    "status": action.status,
                    "risk_level": action.risk_level,
                    "request_hash": action.request_hash,
                }
                if action
                else None,
                "nodes": [
                    row_dict(node, ("fingerprint", "lease_until")) for node in nodes
                ],
                "edges": [
                    {
                        "from": node_by_id[edge.from_node_id].node_key,
                        "to": node_by_id[edge.to_node_id].node_key,
                    }
                    for edge in edges
                ],
                "reservations": [
                    row_dict(row, ("hold_key", "release_key")) for row in reservations
                ],
                "orders": [
                    row_dict(row, ("idempotency_key", "request_hash")) for row in orders
                ],
                "events": [row_dict(row, ("idempotency_key",)) for row in events],
                "allowed_commands": self._allowed_commands(task, nodes),
            }
        )

    # ---- Action authorization and user commands -------------------------

    def authorize(self, user, action):
        lock_user(self.db, user)
        task = owned(self.db, OrchestrationTask, action.payload["task_id"], user)
        require(
            task.authorization_action_id == action.id
            and task.status == "WAITING_AUTHORIZATION",
            "TASK_STATE",
            "生日计划当前不可授权",
            409,
        )
        require(
            action.payload.get("plan_hash") == task.plan_hash
            and fingerprint(action.payload.get("plan")) == task.plan_hash,
            "TASK_PLAN_CHANGED",
            "生日计划内容已变化，请重新创建",
            409,
        )
        account = self.accounts.get_account(user, task.from_account_id)
        self.accounts.require_active(account)
        require(
            self.accounts.get_balance(user, task.from_account_id).balance
            >= task.total_amount,
            "INSUFFICIENT_FUNDS",
            "授权时可用余额不足",
        )
        self._merchants()
        authorization_node = self._node(task.id, "authorize_plan")
        authorization_node.status = "SUCCEEDED"
        authorization_node.result = {"action_id": action.id}
        task.status = "ACTIVE"
        task.error_code = None
        self._refresh_next_run(task)
        self._event(task, "TASK_AUTHORIZED", {"action_id": action.id}, authorization_node)
        self.db.commit()
        return {"task_id": task.id, "authorized": True, "status": task.status}

    def cancel_authorization(self, user, action):
        task = owned(self.db, OrchestrationTask, action.payload["task_id"], user)
        if task.status == "WAITING_AUTHORIZATION":
            task.status = "CANCELLED"
            for node in self._nodes(task.id):
                if node.status not in TERMINAL_NODES:
                    node.status = "CANCELLED"
            self._event(task, "TASK_CANCELLED", {"reason": "authorization_cancelled"})

    def command(self, user, task_id, command, key):
        lock_user(self.db, user)
        task = owned(self.db, OrchestrationTask, task_id, user)
        replay = self.db.scalar(
            select(TaskEvent).where(
                TaskEvent.task_id == task.id,
                TaskEvent.idempotency_key == key,
            )
        )
        if replay:
            return self.view(user, task.id)

        if command == "pause":
            require(task.status in {"ACTIVE", "PARTIAL"}, "TASK_STATE", "当前任务不可暂停", 409)
            task.status = "PAUSED"
            event_type = "TASK_PAUSED"
        elif command == "resume":
            require(
                task.status in {"PAUSED", "WAITING_USER", "PARTIAL"},
                "TASK_STATE",
                "当前任务不可恢复",
                409,
            )
            require(
                not any(node.status == "RECONCILING" for node in self._nodes(task.id)),
                "RECONCILIATION_REQUIRED",
                "存在结果不明节点，请先核对",
                409,
            )
            task.status = "ACTIVE"
            task.error_code = None
            self._refresh_next_run(task)
            event_type = "TASK_RESUMED"
        elif command == "takeover":
            require(
                task.status in {"ACTIVE", "PAUSED", "PARTIAL"},
                "TASK_STATE",
                "当前任务不可人工接管",
                409,
            )
            task.status = "WAITING_USER"
            event_type = "TASK_TAKEN_OVER"
        elif command == "cancel":
            require(task.status not in TERMINAL_TASKS | {"CANCELLING"}, "TASK_STATE", "当前任务不可取消", 409)
            task.status = "CANCELLING"
            for node in self._nodes(task.id):
                if node.status in {"PENDING", "FAILED", "WAITING_USER"}:
                    node.status = "CANCELLED"
            task.next_run_at = now()
            event_type = "TASK_CANCEL_REQUESTED"
        else:
            raise DomainError("TASK_COMMAND", "不支持的任务命令", 422)
        self._event(task, event_type, {}, idempotency_key=key)
        self.db.commit()
        return self.view(user, task.id)

    def retry_node(self, user, task_id, node_id, key):
        lock_user(self.db, user)
        task = owned(self.db, OrchestrationTask, task_id, user)
        replay = self.db.scalar(
            select(TaskEvent).where(TaskEvent.task_id == task.id, TaskEvent.idempotency_key == key)
        )
        if replay:
            return self.view(user, task.id)
        node = self.db.scalar(
            select(TaskNode).where(TaskNode.id == node_id, TaskNode.task_id == task.id)
        )
        require(node is not None and node.status == "FAILED", "TASK_NODE_STATE", "仅可重试明确失败的节点", 409)
        node.status = "PENDING"
        node.error_code = None
        node.scheduled_at = now()
        task.status = "ACTIVE"
        task.error_code = None
        self._event(task, "TASK_NODE_RETRY_REQUESTED", {}, node, key)
        self._refresh_next_run(task)
        self.db.commit()
        return self.view(user, task.id)

    def reconcile_node(self, user, task_id, node_id, key):
        lock_user(self.db, user)
        task = owned(self.db, OrchestrationTask, task_id, user)
        replay = self.db.scalar(
            select(TaskEvent).where(TaskEvent.task_id == task.id, TaskEvent.idempotency_key == key)
        )
        if replay:
            return self.view(user, task.id)
        node = self.db.scalar(
            select(TaskNode).where(TaskNode.id == node_id, TaskNode.task_id == task.id)
        )
        require(node is not None and node.status == "RECONCILING", "TASK_NODE_STATE", "节点无需核对", 409)
        cancel_release = (node.result or {}).get("stage") == "cancel_release"
        if node.kind == "RESERVE_FUNDS":
            self._reconcile_reservation(task, node)
        elif node.kind == "PURCHASE":
            self._reconcile_purchase(user, task, node)
        else:
            raise DomainError("TASK_NODE_STATE", "该节点没有外部结果可核对", 409)
        self._event(task, "TASK_NODE_RECONCILED", {}, node, key)
        if node.status == "SUCCEEDED":
            if cancel_release:
                reservation = self.db.scalar(
                    select(FundReservation).where(FundReservation.node_id == node.id)
                )
                require(
                    reservation.status == "RELEASED",
                    "MANUAL_RECONCILIATION_REQUIRED",
                    "取消时核心资金释放结果仍不明确",
                    409,
                )
                node.status = "CANCELLED"
                task.status = "CANCELLING"
                task.next_run_at = now()
            else:
                task.status = "ACTIVE"
                task.error_code = None
                self._refresh_next_run(task)
        self.db.commit()
        return self.view(user, task.id)

    # ---- worker ----------------------------------------------------------

    def tick(self):
        self._recover_abandoned_node()
        cancelling = self.db.scalar(
            select(OrchestrationTask)
            .where(OrchestrationTask.status == "CANCELLING")
            .order_by(OrchestrationTask.updated_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if cancelling:
            return self._cancel_one(cancelling)

        candidates = self.db.scalars(
            select(TaskNode)
            .join(OrchestrationTask, OrchestrationTask.id == TaskNode.task_id)
            .where(
                OrchestrationTask.status == "ACTIVE",
                TaskNode.status == "PENDING",
                or_(TaskNode.scheduled_at.is_(None), TaskNode.scheduled_at <= now()),
            )
            .order_by(TaskNode.scheduled_at, TaskNode.created_at)
            .with_for_update(skip_locked=True)
            .limit(20)
        ).all()
        node = next((row for row in candidates if self._dependencies_succeeded(row)), None)
        if node is None:
            self.db.rollback()
            return None
        task = self.db.scalar(
            select(OrchestrationTask)
            .where(OrchestrationTask.id == node.task_id)
            .with_for_update()
        )
        node.status = "RUNNING"
        node.attempts += 1
        node.lease_until = now() + timedelta(minutes=5)
        task.lease_until = node.lease_until
        self._event(task, "TASK_NODE_STARTED", {"attempt": node.attempts}, node)
        self.db.commit()
        try:
            if node.kind == "RESERVE_FUNDS":
                result = self._execute_reservation(task, node)
            elif node.kind == "PURCHASE":
                result = self._execute_purchase(task, node)
            elif node.kind == "NOTIFY":
                result = {"notification": "任务处理结果已写入任务中心"}
            else:
                raise DomainError("TASK_NODE_KIND", "不支持的任务节点", 500)
            node.status = "SUCCEEDED"
            node.result = safe_json(result)
            node.error_code = None
            node.lease_until = None
            self._event(task, "TASK_NODE_SUCCEEDED", {}, node)
            if node.kind == "NOTIFY":
                task.status = (
                    "SUCCEEDED"
                    if all(order.status == "SUCCEEDED" for order in self._orders(task.id))
                    else "PARTIAL"
                )
                self._event(task, "TASK_COMPLETED" if task.status == "SUCCEEDED" else "TASK_PARTIAL", {})
            self._refresh_next_run(task)
            task.lease_until = None
            self.db.commit()
            return {"task_id": task.id, "node": node.node_key, "status": node.status}
        except (DomainError, FineractError) as exc:
            self.db.rollback()
            task = self.db.get(OrchestrationTask, node.task_id)
            node = self.db.get(TaskNode, node.id)
            ambiguous = isinstance(exc, FineractUnavailableError) or bool(
                (node.result or {}).get("remote_started")
            )
            node.status = "RECONCILING" if ambiguous else "FAILED"
            node.error_code = exc.code if isinstance(exc, DomainError) else "UPSTREAM_ERROR"
            node.lease_until = None
            task.status = "WAITING_USER"
            task.error_code = node.error_code
            task.lease_until = None
            self._event(
                task,
                "TASK_NODE_RECONCILING" if ambiguous else "TASK_NODE_FAILED",
                {"code": node.error_code},
                node,
            )
            self.db.commit()
            return {"task_id": task.id, "node": node.node_key, "status": node.status}

    # ---- node execution --------------------------------------------------

    def _execute_reservation(self, task, node):
        reservation = self.db.scalar(
            select(FundReservation).where(FundReservation.node_id == node.id)
        )
        require(reservation.status == "PENDING", "RESERVATION_STATE", "资金预留状态无效", 409)
        reservation.status = "HOLDING"
        node.result = {"remote_started": True, "stage": "hold"}
        self.db.commit()
        response = self.fineract.hold_amount(
            reservation.account_id,
            reservation.amount,
            now().astimezone(SHANGHAI).date().isoformat(),
            self._reservation_reason(reservation),
            reservation.hold_key,
        )
        require(response.get("resourceId"), "EXECUTION_UNCONFIRMED", "核心资金预留结果未确认", 502)
        reservation.hold_transaction_id = int(response["resourceId"])
        reservation.status = "HELD"
        reservation.error_code = None
        return {"reservation_id": reservation.id, "status": reservation.status}

    def _execute_purchase(self, task, node):
        order = self.db.scalar(select(DemoOrder).where(DemoOrder.node_id == node.id))
        reservation = self.db.get(FundReservation, order.reservation_id)
        merchant = self.db.get(Merchant, order.merchant_id)
        require(
            merchant and merchant.active and merchant.adapter_type == "demo_orchestration"
            and merchant.fineract_account_id is not None,
            "MERCHANT_UNAVAILABLE",
            "生日 Demo 商户不可用",
            409,
        )
        if reservation.status == "HELD":
            reservation.status = "RELEASING"
            node.result = {"remote_started": True, "stage": "release"}
            self.db.commit()
            response = self.fineract.release_amount(
                reservation.account_id,
                reservation.hold_transaction_id,
                now().astimezone(SHANGHAI).date().isoformat(),
                reservation.release_key,
            )
            require(response.get("resourceId"), "EXECUTION_UNCONFIRMED", "核心资金释放结果未确认", 502)
            reservation.release_transaction_id = int(response["resourceId"])
            reservation.status = "RELEASED"
            self.db.commit()
        require(reservation.status == "RELEASED", "RESERVATION_STATE", "预留资金尚未释放", 409)

        sender = self.accounts.get_account(self._task_user(task), task.from_account_id)
        target = self.fineract.get_savings_account(merchant.fineract_account_id)
        require((target.get("status") or {}).get("active"), "MERCHANT_UNAVAILABLE", "商户结算账户不可用", 409)
        require(
            self.accounts.get_balance(self._task_user(task), task.from_account_id).balance >= order.amount,
            "INSUFFICIENT_FUNDS",
            "释放预留后可用余额不足",
        )
        order.status = "PROCESSING"
        node.result = {"remote_started": True, "stage": "transfer"}
        self.db.commit()
        payload = {
            "fromOfficeId": str(self.fineract.get_client(sender["clientId"])["officeId"]),
            "fromClientId": str(sender["clientId"]),
            "fromAccountType": "2",
            "fromAccountId": str(task.from_account_id),
            "toOfficeId": str(self.fineract.get_client(target["clientId"])["officeId"]),
            "toClientId": str(target["clientId"]),
            "toAccountType": "2",
            "toAccountId": str(target["id"]),
            "transferDate": now().astimezone(SHANGHAI).date().isoformat(),
            "transferAmount": str(order.amount),
            "transferDescription": self._order_description(order),
            "locale": "en",
            "dateFormat": "yyyy-MM-dd",
        }
        response = self.fineract.create_transfer(payload, order.idempotency_key)
        require(
            response.get("resourceId") and not response.get("rollbackTransaction"),
            "EXECUTION_UNCONFIRMED",
            "Demo 商户支付尚未确认",
            502,
        )
        order.fineract_transfer_id = int(response["resourceId"])
        result = self._reconcile_order(task, order, merchant)
        reservation.status = "CONSUMED"
        order.status = "SUCCEEDED"
        order.error_code = None
        return result

    def _reconcile_reservation(self, task, node):
        reservation = self.db.scalar(select(FundReservation).where(FundReservation.node_id == node.id))
        if reservation.hold_transaction_id is None:
            matches = self._find_hold_transactions(reservation)
            require(len(matches) == 1, "MANUAL_RECONCILIATION_REQUIRED", "未找到唯一核心资金预留", 409)
            reservation.hold_transaction_id = int(matches[0]["id"])
        transaction = self.fineract.get_transaction(
            reservation.account_id, reservation.hold_transaction_id
        )
        require(
            Decimal(str(transaction.get("amount"))) == reservation.amount
            and transaction.get("reasonForBlock") == self._reservation_reason(reservation),
            "EXECUTION_UNCONFIRMED",
            "核心资金预留事实不匹配",
            502,
        )
        release_id = transaction.get("releaseIdOfHoldAmountTransaction")
        if release_id:
            reservation.release_transaction_id = int(release_id)
            reservation.status = "RELEASED"
        else:
            reservation.status = "HELD"
        node.status = "SUCCEEDED"
        node.error_code = None
        node.result = {"reservation_id": reservation.id, "status": reservation.status}

    def _reconcile_purchase(self, user, task, node):
        order = self.db.scalar(select(DemoOrder).where(DemoOrder.node_id == node.id))
        reservation = self.db.get(FundReservation, order.reservation_id)
        merchant = self.db.get(Merchant, order.merchant_id)
        if reservation.status in {"RELEASING", "RECONCILING"} and reservation.release_transaction_id is None:
            hold = self.fineract.get_transaction(reservation.account_id, reservation.hold_transaction_id)
            release_id = hold.get("releaseIdOfHoldAmountTransaction")
            require(release_id, "MANUAL_RECONCILIATION_REQUIRED", "核心资金释放结果仍不明确", 409)
            reservation.release_transaction_id = int(release_id)
            reservation.status = "RELEASED"
        if order.fineract_transfer_id is None and order.status == "PROCESSING":
            ids = self._find_order_transfers(task, order)
            require(len(ids) == 1, "MANUAL_RECONCILIATION_REQUIRED", "未找到唯一 Demo 商户转账", 409)
            order.fineract_transfer_id = ids.pop()
        require(order.fineract_transfer_id is not None, "MANUAL_RECONCILIATION_REQUIRED", "尚无可核对的商户转账", 409)
        result = self._reconcile_order(task, order, merchant)
        reservation.status = "CONSUMED"
        order.status = "SUCCEEDED"
        order.error_code = None
        node.status = "SUCCEEDED"
        node.error_code = None
        node.result = result

    def _reconcile_order(self, task, order, merchant):
        result = self.fineract.get_transfer(order.fineract_transfer_id)
        require(
            not result.get("reversed")
            and (result.get("fromAccount") or {}).get("id") == task.from_account_id
            and (result.get("toAccount") or {}).get("id") == merchant.fineract_account_id
            and Decimal(str(result.get("transferAmount", result.get("amount", "-1")))) == order.amount,
            "EXECUTION_UNCONFIRMED",
            "Demo 商户转账事实与任务不匹配",
            502,
        )
        refs = {}
        for side, account_id in (("from", task.from_account_id), ("to", merchant.fineract_account_id)):
            direct = result.get(side + "SavingsTransaction") or {}
            transaction_id = direct.get("id")
            if transaction_id is None:
                day = result.get("transferDate")
                rows = self.fineract.search_transactions(
                    account_id, 0, 100, fromDate=self._iso_date(day), toDate=self._iso_date(day)
                )["items"]
                matches = [
                    row for row in rows
                    if (row.get("transfer") or {}).get("id") == order.fineract_transfer_id
                    and not row.get("reversed") and not row.get("isReversal")
                ]
                require(len(matches) == 1, "EXECUTION_UNCONFIRMED", "未找到唯一商户流水", 502)
                transaction_id = matches[0]["id"]
            refs[side + "_transaction_id"] = int(transaction_id)
        order.from_transaction_id = refs["from_transaction_id"]
        order.to_transaction_id = refs["to_transaction_id"]
        return {
            "order_id": order.id,
            "merchant": merchant.name,
            "status": "SUCCEEDED",
            "transfer_id": order.fineract_transfer_id,
            **refs,
        }

    # ---- cancellation and recovery -------------------------------------

    def _cancel_one(self, task):
        reservation = self.db.scalar(
            select(FundReservation)
            .where(FundReservation.task_id == task.id, FundReservation.status == "HELD")
            .order_by(FundReservation.purpose)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if reservation is None:
            task.status = "PARTIAL" if any(order.status == "SUCCEEDED" for order in self._orders(task.id)) else "CANCELLED"
            task.next_run_at = None
            self._event(task, "TASK_CANCELLED" if task.status == "CANCELLED" else "TASK_PARTIAL", {})
            self.db.commit()
            return {"task_id": task.id, "status": task.status}
        node = self.db.get(TaskNode, reservation.node_id)
        reservation.status = "RELEASING"
        node.status = "RUNNING"
        node.result = {"remote_started": True, "stage": "cancel_release"}
        self.db.commit()
        try:
            response = self.fineract.release_amount(
                reservation.account_id,
                reservation.hold_transaction_id,
                now().astimezone(SHANGHAI).date().isoformat(),
                reservation.release_key,
            )
            require(response.get("resourceId"), "EXECUTION_UNCONFIRMED", "取消时资金释放结果未确认", 502)
            reservation.release_transaction_id = int(response["resourceId"])
            reservation.status = "RELEASED"
            node.status = "CANCELLED"
            node.result = {"reservation_id": reservation.id, "status": "RELEASED"}
            self._event(task, "TASK_RESERVATION_RELEASED", {}, node)
            self.db.commit()
            return {"task_id": task.id, "status": "CANCELLING"}
        except (DomainError, FineractError) as exc:
            self.db.rollback()
            task = self.db.get(OrchestrationTask, task.id)
            reservation = self.db.get(FundReservation, reservation.id)
            node = self.db.get(TaskNode, node.id)
            reservation.status = "RECONCILING"
            reservation.error_code = exc.code if isinstance(exc, DomainError) else "UPSTREAM_ERROR"
            node.status = "RECONCILING"
            node.error_code = reservation.error_code
            task.status = "WAITING_USER"
            task.error_code = reservation.error_code
            self._event(task, "TASK_NODE_RECONCILING", {"code": node.error_code}, node)
            self.db.commit()
            return {"task_id": task.id, "status": task.status}

    def _recover_abandoned_node(self):
        node = self.db.scalar(
            select(TaskNode)
            .where(TaskNode.status == "RUNNING", TaskNode.lease_until < now())
            .order_by(TaskNode.lease_until)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if node is None:
            self.db.rollback()
            return
        task = self.db.get(OrchestrationTask, node.task_id)
        node.status = "RECONCILING"
        node.error_code = "WORKER_INTERRUPTED"
        node.lease_until = None
        task.status = "WAITING_USER"
        task.error_code = node.error_code
        task.lease_until = None
        self._event(task, "TASK_NODE_RECONCILING", {"code": node.error_code}, node)
        self.db.commit()

    # ---- helpers ---------------------------------------------------------

    def _create_nodes(self, task, reserve_at, purchase_at, flower_amount, cake_amount, flower, cake):
        specs = [
            ("confirm_event", "CONFIRM_EVENT", "确认生日事件", "SUCCEEDED", "GREEN", None, Decimal(0), None),
            ("authorize_plan", "AUTHORIZE_PLAN", "授权完整计划", "WAITING_AUTHORIZATION", "RED", None, task.total_amount, None),
            ("reserve_flower", "RESERVE_FUNDS", "预留鲜花资金", "PENDING", "RED", reserve_at, flower_amount, flower.id),
            ("reserve_cake", "RESERVE_FUNDS", "预留蛋糕资金", "PENDING", "RED", reserve_at, cake_amount, cake.id),
            ("purchase_flower", "PURCHASE", "Demo 花店下单", "PENDING", "RED", purchase_at, flower_amount, flower.id),
            ("purchase_cake", "PURCHASE", "Demo 蛋糕店下单", "PENDING", "RED", purchase_at, cake_amount, cake.id),
            ("notify", "NOTIFY", "生成任务通知", "PENDING", "GREEN", purchase_at, Decimal(0), None),
        ]
        result = {}
        for key, kind, label, status, risk, scheduled, amount, merchant_id in specs:
            immutable = {
                "task_id": task.id,
                "node_key": key,
                "kind": kind,
                "scheduled_at": scheduled.isoformat() if scheduled else None,
                "amount": str(amount),
                "merchant_id": merchant_id,
                "risk_level": risk,
            }
            node = TaskNode(
                task_id=task.id,
                node_key=key,
                kind=kind,
                label=label,
                status=status,
                risk_level=risk,
                scheduled_at=scheduled,
                amount=amount,
                merchant_id=merchant_id,
                fingerprint=fingerprint(immutable),
                result={"confirmed": True} if key == "confirm_event" else {},
            )
            self.db.add(node)
            result[key] = node
        self.db.flush()
        return result

    def _create_edges(self, task, nodes):
        pairs = [
            ("confirm_event", "authorize_plan"),
            ("authorize_plan", "reserve_flower"),
            ("authorize_plan", "reserve_cake"),
            ("reserve_flower", "purchase_flower"),
            ("reserve_cake", "purchase_cake"),
            ("purchase_flower", "notify"),
            ("purchase_cake", "notify"),
        ]
        self.db.add_all(
            [
                TaskEdge(task_id=task.id, from_node_id=nodes[source].id, to_node_id=nodes[target].id)
                for source, target in pairs
            ]
        )

    def _dependencies_succeeded(self, node):
        parent_ids = self.db.scalars(
            select(TaskEdge.from_node_id).where(TaskEdge.to_node_id == node.id)
        ).all()
        if not parent_ids:
            return True
        statuses = self.db.scalars(select(TaskNode.status).where(TaskNode.id.in_(parent_ids))).all()
        return len(statuses) == len(parent_ids) and all(status == "SUCCEEDED" for status in statuses)

    def _refresh_next_run(self, task):
        pending = [
            node for node in self._nodes(task.id)
            if node.status == "PENDING" and self._dependencies_succeeded(node)
        ]
        task.next_run_at = min(
            (aware(node.scheduled_at) if node.scheduled_at else now() for node in pending),
            default=None,
        )

    def _validate_event_date(self, event_date):
        today = now().astimezone(SHANGHAI).date()
        require(event_date >= today + timedelta(days=3), "EVENT_DATE", "生日日期至少需要提前三天", 422)
        require(event_date <= today + timedelta(days=366), "EVENT_DATE", "生日任务只支持未来一年内", 422)

    def _merchants(self):
        rows = self.db.scalars(
            select(Merchant).where(
                Merchant.external_key.in_((FLOWER_MERCHANT, CAKE_MERCHANT))
            )
        ).all()
        by_key = {row.external_key: row for row in rows}
        require(
            set(by_key) == {FLOWER_MERCHANT, CAKE_MERCHANT}
            and all(
                row.active
                and row.adapter_type == "demo_orchestration"
                and row.fineract_account_id is not None
                for row in rows
            ),
            "DEMO_MERCHANT_UNCONFIGURED",
            "生日 Demo 花店和蛋糕店尚未配置",
            503,
        )
        return {"flower": by_key[FLOWER_MERCHANT], "cake": by_key[CAKE_MERCHANT]}

    def _event(self, task, type_, data, node=None, idempotency_key=None):
        event = TaskEvent(
            task_id=task.id,
            node_id=node.id if node else None,
            type=type_,
            data=safe_json(data),
            idempotency_key=idempotency_key,
        )
        self.db.add(event)
        return event

    def _node(self, task_id, node_key):
        return self.db.scalar(
            select(TaskNode).where(TaskNode.task_id == task_id, TaskNode.node_key == node_key)
        )

    def _nodes(self, task_id):
        return list(self.db.scalars(select(TaskNode).where(TaskNode.task_id == task_id)))

    def _orders(self, task_id):
        return list(self.db.scalars(select(DemoOrder).where(DemoOrder.task_id == task_id)))

    def _allowed_commands(self, task, nodes):
        commands = []
        if task.status in {"ACTIVE", "PARTIAL"}:
            commands.append("pause")
        if task.status in {"PAUSED", "WAITING_USER", "PARTIAL"} and not any(
            node.status == "RECONCILING" for node in nodes
        ):
            commands.append("resume")
        if task.status in {"ACTIVE", "PAUSED", "PARTIAL"}:
            commands.append("takeover")
        if task.status not in TERMINAL_TASKS | {"CANCELLING"}:
            commands.append("cancel")
        return commands

    def _task_user(self, task):
        from models import User

        return self.db.get(User, task.user_id)

    @staticmethod
    def _reservation_reason(reservation):
        return f"[TaskReservation:{reservation.id}]"

    @staticmethod
    def _order_description(order):
        return f"[TaskOrder:{order.id}] Birthday gift"

    def _find_hold_transactions(self, reservation):
        start = reservation.created_at.astimezone(SHANGHAI).date().isoformat()
        end = now().astimezone(SHANGHAI).date().isoformat()
        matches, page = [], 0
        while True:
            data = self.fineract.search_transactions(
                reservation.account_id, page, 100, fromDate=start, toDate=end
            )
            matches.extend(
                row for row in data["items"]
                if row.get("reasonForBlock") == self._reservation_reason(reservation)
                and Decimal(str(row.get("amount"))) == reservation.amount
            )
            if (page + 1) * 100 >= data["total"]:
                break
            require(data["items"] and page < 999, "UPSTREAM_DATA", "资金预留分页不完整", 502)
            page += 1
        return matches

    def _find_order_transfers(self, task, order):
        start = order.created_at.astimezone(SHANGHAI).date().isoformat()
        end = now().astimezone(SHANGHAI).date().isoformat()
        ids, page = set(), 0
        while True:
            data = self.fineract.search_transactions(
                task.from_account_id, page, 100, fromDate=start, toDate=end
            )
            for row in data["items"]:
                transfer = row.get("transfer") or {}
                if transfer.get("transferDescription") == self._order_description(order):
                    ids.add(int(transfer["id"]))
            if (page + 1) * 100 >= data["total"]:
                break
            require(data["items"] and page < 999, "UPSTREAM_DATA", "商户转账分页不完整", 502)
            page += 1
        return ids

    @staticmethod
    def _iso_date(value):
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            return f"{int(value[0]):04d}-{int(value[1]):02d}-{int(value[2]):02d}"
        return str(value)[:10]
