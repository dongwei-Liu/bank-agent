import calendar
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select
from core.errors import DomainError, require
from core.security import aware, fingerprint, now, SHANGHAI
from models import Action, Schedule, ScheduleRun, User
from services.common import owned, lock_user, row_dict, safe_json, audit
from services.transfer_service import TransferService
from services.action_service import ActionService


def next_occurrence(value, recurrence, anchor_day):
    local = aware(value).astimezone(SHANGHAI)
    if recurrence == "once":
        return None
    if recurrence == "daily":
        result = local + timedelta(days=1)
    elif recurrence == "weekly":
        result = local + timedelta(days=7)
    else:
        year = local.year + (local.month == 12)
        month = local.month % 12 + 1
        result = local.replace(
            year=year,
            month=month,
            day=min(anchor_day, calendar.monthrange(year, month)[1]),
        )
    return result.astimezone(timezone.utc)


class ScheduleService:
    def __init__(self, db, fineract, settings):
        self.db, self.fineract, self.settings = db, fineract, settings

    def save(self, user, request, schedule_id=None, *, idempotency_key=None, display_metadata=None):
        lock_user(self.db, user)
        require(request.execute_at > now(), "INVALID_DATE", "执行时间必须在未来")
        request_hash = fingerprint({
            "request": request.model_dump(mode="json"),
            "display_metadata": display_metadata or {},
        })
        if idempotency_key and schedule_id is None:
            require(len(idempotency_key) <= 160, "IDEMPOTENCY_KEY_INVALID", "计划请求幂等键过长")
            existing = self.db.scalar(select(Schedule).where(
                Schedule.user_id == user.id,
                Schedule.idempotency_key == idempotency_key,
            ))
            if existing:
                require(existing.payload.get("_agent_request_hash") == request_hash,
                        "IDEMPOTENCY_CONFLICT", "同一幂等键的计划参数不同", 409)
                return row_dict(existing)
        transfer = TransferService(self.db, self.fineract).prepare(user, request)
        payload = {
            **transfer,
            **request.model_dump(mode="json"),
            "anchor_day": request.execute_at.astimezone(SHANGHAI).day,
            **(display_metadata or {}),
        }
        if idempotency_key:
            require(schedule_id is None, "IDEMPOTENCY_CONFLICT", "更新计划不能复用创建幂等键", 409)
            payload["_agent_request_hash"] = request_hash
        row = (
            owned(self.db, Schedule, schedule_id, user)
            if schedule_id
            else Schedule(user_id=user.id)
        )
        if schedule_id:
            require(
                row.status not in {"CANCELLED", "COMPLETED"},
                "SCHEDULE_STATE",
                "计划已结束",
                409,
            )
            require(
                not self.db.scalar(
                    select(ScheduleRun)
                    .join(Action, Action.id == ScheduleRun.action_id)
                    .where(
                        ScheduleRun.schedule_id == row.id,
                        Action.status.in_(["EXECUTING", "RECONCILING"]),
                    )
                ),
                "SCHEDULE_BUSY",
                "先核对执行中的任务再修改",
                409,
            )
        row.payload = safe_json(payload)
        if idempotency_key and not schedule_id:
            row.idempotency_key = idempotency_key
        row.next_run = request.execute_at
        row.status = "DRAFT"
        row.authorization_hash = None
        row.authorization_action_id = None
        self.db.add(row)
        audit(self.db, user, "SCHEDULE_SAVED")
        self.db.commit()
        return row_dict(row)

    def authorize(self, user, schedule_id, key):
        lock_user(self.db, user)
        row = owned(self.db, Schedule, schedule_id, user)
        require(
            row.status not in {"CANCELLED", "COMPLETED"},
            "SCHEDULE_STATE",
            "计划已结束",
            409,
        )
        require(
            datetime.fromisoformat(row.payload["valid_until"]) > now(),
            "AUTHORIZATION_EXPIRED",
            "计划授权已到期",
        )
        schedule_hash = fingerprint(row.payload)
        pending_actions = self.db.scalars(select(Action).where(
            Action.user_id == user.id,
            Action.kind == "schedule_authorization",
            Action.status.in_(["WAITING_CONFIRMATION", "WAITING_VERIFICATION"]),
        ))
        for pending in pending_actions:
            if pending.payload.get("schedule_id") == row.id and pending.payload.get("schedule_hash") == schedule_hash:
                return ActionService(self.db, self.fineract, self.settings).view(pending)
        action = ActionService(self.db, self.fineract, self.settings).create(
            user,
            "schedule_authorization",
            {"schedule_id": row.id, "schedule_hash": schedule_hash},
            key,
            source="AGENT" if key.startswith("agent-") else "API",
        )
        return ActionService(self.db, self.fineract, self.settings).view(action)

    def confirm_authorization(self, user, schedule, action):
        """在授权 Action 真正执行时复核计划指纹、时效与状态。"""
        self.db.refresh(schedule)
        require(schedule.status in {"DRAFT", "PAUSED", "WAITING_AUTHORIZATION"},
                "SCHEDULE_STATE", "计划当前不能授权", 409)
        require(fingerprint(schedule.payload) == action.payload["schedule_hash"],
                "SCHEDULE_CHANGED", "计划已变化，请重新提交授权", 409)
        require(aware(schedule.next_run) > now(), "SCHEDULE_EXPIRED", "首次执行时间已过，请重新创建计划", 409)
        require(datetime.fromisoformat(schedule.payload["valid_until"]) > now(),
                "AUTHORIZATION_EXPIRED", "计划授权已到期，请重新提交授权", 409)
        self.db.refresh(action)
        require(action.status == "EXECUTING" and action.confirmed_at is not None,
                "ACTION_STATE", "计划授权 Action 尚未通过确认和验证", 409)

    def state(self, user, schedule_id, operation):
        lock_user(self.db, user)
        row = owned(self.db, Schedule, schedule_id, user)
        require(
            row.status not in {"CANCELLED", "COMPLETED"},
            "SCHEDULE_STATE",
            "计划已结束",
            409,
        )
        if operation == "resume":
            require(row.status == "PAUSED", "SCHEDULE_STATE", "计划未暂停", 409)
            self.validate_authorization(user, row)
            row.status = "ACTIVE"
        elif operation == "pause":
            row.status = "PAUSED"
        else:
            row.status = "CANCELLED"
            row.authorization_hash = None
        audit(self.db, user, "SCHEDULE_" + operation.upper())
        self.db.commit()
        return row_dict(row)

    def agent_list(self, user):
        rows = self.db.scalars(select(Schedule).where(
            Schedule.user_id == user.id
        ).order_by(Schedule.next_run)).all()
        return [{
            "schedule_ref": row.id,
            "recipient": row.payload.get("recipient_display_name", ""),
            "from_account_suffix": row.payload.get("from_account_suffix", ""),
            "amount": str(row.payload.get("amount", "")),
            "recurrence": row.payload.get("recurrence", "once"),
            "execute_at": row.payload.get("execute_at"),
            "next_run": row.next_run.isoformat() if row.next_run else None,
            "valid_until": row.payload.get("valid_until"),
            "daily_limit": str(row.payload.get("daily_limit", "")),
            "status": row.status,
        } for row in rows]

    def validate_authorization(self, user, schedule, action=None):
        # Refresh after user row lock; never trust a worker's stale schedule object.
        self.db.refresh(schedule)
        require(
            schedule.status in {"ACTIVE", "PAUSED"},
            "AUTHORIZATION_REQUIRED",
            "计划需重新授权",
            409,
        )
        auth = (
            self.db.get(Action, schedule.authorization_action_id)
            if schedule.authorization_action_id
            else None
        )
        require(
            auth
            and auth.status == "SUCCEEDED"
            and schedule.authorization_hash == fingerprint(schedule.payload),
            "AUTHORIZATION_REQUIRED",
            "预授权缺失或参数已变化",
            409,
        )
        p = schedule.payload
        require(
            datetime.fromisoformat(p["valid_until"]) > now(),
            "AUTHORIZATION_EXPIRED",
            "预授权已到期",
            409,
        )
        if action:
            require(schedule.status == "ACTIVE", "SCHEDULE_PAUSED", "计划不可执行", 409)
            require(
                all(
                    action.payload[k] == p[k]
                    for k in ["from_account_id", "to_account_id", "amount"]
                ),
                "AUTHORIZATION_CHANGED",
                "执行参数不在预授权范围",
                409,
            )
            day = now().astimezone(SHANGHAI).date()
            used = Decimal(0)
            for a in self.db.scalars(
                select(Action)
                .join(ScheduleRun, ScheduleRun.action_id == Action.id)
                .where(
                    ScheduleRun.schedule_id == schedule.id,
                    Action.status.in_(["SUCCEEDED", "EXECUTING", "RECONCILING"]),
                )
            ):
                if (
                    a.executed_at
                    and aware(a.executed_at).astimezone(SHANGHAI).date() == day
                ):
                    used += a.amount
            require(
                used + action.amount <= Decimal(p["daily_limit"]),
                "AUTHORIZATION_LIMIT",
                "超出计划每日授权额度",
                409,
            )

    def tick(self, clock=None):
        clock = clock or now()
        ids = self.db.scalars(
            select(Schedule.id).where(
                Schedule.status == "ACTIVE", Schedule.next_run <= clock
            )
        ).all()
        processed = []
        for sid in ids:
            self.db.rollback()
            schedule = self.db.get(Schedule, sid)
            user = self.db.get(User, schedule.user_id)
            lock_user(self.db, user)
            self.db.refresh(schedule)
            if schedule.status != "ACTIVE" or aware(schedule.next_run) > clock:
                continue
            due = aware(schedule.next_run)
            p = schedule.payload
            # Record skipped old periods; only the latest overdue occurrence is paid.
            while True:
                following = next_occurrence(due, p["recurrence"], p["anchor_day"])
                if following is None or following > clock:
                    break
                old = self.db.scalar(
                    select(ScheduleRun).where(
                        ScheduleRun.schedule_id == sid, ScheduleRun.scheduled_at == due
                    )
                )
                if not old:
                    self.db.add(
                        ScheduleRun(schedule_id=sid, scheduled_at=due, status="MISSED")
                    )
                elif old.action_id:
                    intent = self.db.get(Action, old.action_id)
                    if intent.status in {
                        "AUTHORIZED",
                        "WAITING_CONFIRMATION",
                        "WAITING_VERIFICATION",
                    }:
                        intent.status = "CANCELLED"
                        intent.error_code = "SCHEDULE_MISSED"
                        intent.otp_hash = None
                        intent.dev_otp = None
                        old.status = "MISSED"
                        audit(self.db, user, "SCHEDULE_MISSED", intent)
                due = following
            existing = self.db.scalar(
                select(ScheduleRun).where(
                    ScheduleRun.schedule_id == sid, ScheduleRun.scheduled_at == due
                )
            )
            if existing:
                # AUTHORIZED is a durable local intent: no remote write was claimed yet.
                previous = (
                    self.db.get(Action, existing.action_id)
                    if existing.action_id
                    else None
                )
                if previous and previous.status == "AUTHORIZED":
                    try:
                        result = ActionService(
                            self.db, self.fineract, self.settings
                        ).execute(user, previous.id, schedule=schedule)
                        processed.append(result)
                    except DomainError as exc:
                        schedule.status = "WAITING_AUTHORIZATION"
                        previous.error_code = exc.code
                schedule.next_run = following or due
                if following is None and schedule.status == "ACTIVE":
                    schedule.status = "COMPLETED"
                self.db.commit()
                continue
            try:
                self.validate_authorization(user, schedule)
            except DomainError:
                schedule.status = "WAITING_AUTHORIZATION"
                self.db.commit()
                continue
            service = ActionService(self.db, self.fineract, self.settings)
            payload = {
                k: p[k]
                for k in [
                    "from_account_id",
                    "to_account_id",
                    "amount",
                    "currency",
                    "remark",
                    "to_client_id",
                ]
            }
            payload["schedule_id"] = sid
            payload["scheduled_at"] = due.isoformat()
            action = service.create(
                user,
                "transfer",
                payload,
                f"schedule:{sid}:{due.isoformat()}",
                p["amount"],
                commit=False,
                source="SCHEDULE_WORKER",
            )
            action.confirmed_at = clock
            action.status = "AUTHORIZED"
            run = ScheduleRun(
                schedule_id=sid, scheduled_at=due, status="CREATED", action_id=action.id
            )
            self.db.add(run)
            self.db.commit()
            try:
                result = service.execute(user, action.id, schedule=schedule)
            except DomainError as exc:
                action = self.db.get(Action, action.id)
                action.status = "WAITING_VERIFICATION"
                schedule.status = "WAITING_AUTHORIZATION"
                action.error_code = exc.code
                self.db.commit()
                result = service.view(action)
            lock_user(self.db, user)
            self.db.refresh(schedule)
            run.status = result["status"]
            schedule.next_run = following or due
            if following is None and schedule.status == "ACTIVE":
                schedule.status = "COMPLETED"
            self.db.commit()
            processed.append(result)
        return processed
