"""Durable, user-owned Agent conversations and worker run lifecycle."""

from __future__ import annotations

import re
import secrets
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select, update

from core.config import Settings
from core.errors import DomainError, require
from core.security import aware, fingerprint, now
from models import (
    AgentConversation,
    AgentEvent,
    AgentMessage,
    AgentRun,
    SecurityEvent,
    SecurityLock,
    User,
)
from schemas.agent import (
    AgentConversationDetail,
    AgentConversationMessageRequest,
    AgentConversationSummary,
    AgentMessageRequest,
    AgentMessageResponse,
    AgentRunResponse,
    AgentStoredMessage,
    AgentStreamEvent,
)
from services.common import lock_user, redact_audit_data


TERMINAL_RUN_STATUSES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})
ACTIVE_RUN_STATUSES = frozenset({"QUEUED", "RUNNING"})
AGENT_SECURITY_FAILURE_THRESHOLD = 5
AGENT_SECURITY_FAILURE_WINDOW = timedelta(minutes=10)
AGENT_SECURITY_LOCK_DURATION = timedelta(minutes=15)

_INJECTION_PATTERNS = {
    "IGNORE_INSTRUCTIONS": re.compile(
        r"(?:ignore|disregard|forget).{0,30}(?:previous|system|developer|instructions?)"
        r"|(?:忽略|无视|忘掉).{0,20}(?:之前|系统|开发者|指令|规则|限制|必须)",
        re.IGNORECASE,
    ),
    "REVEAL_PROMPT": re.compile(
        r"(?:reveal|print|show).{0,25}(?:system prompt|hidden prompt|instructions?)"
        r"|(?:输出|泄露|显示|告诉我|打印).{0,20}(?:系统提示词|隐藏提示词|内部指令)"
        r"|(?:系统提示词|隐藏提示词|内部指令).{0,20}(?:输出|泄露|显示|告诉我|打印)",
        re.IGNORECASE,
    ),
    "BYPASS_CONTROL": re.compile(
        r"(?:bypass|skip|disable).{0,30}(?:otp|confirmation|authorization|permission|safety|action|verification)"
        r"|(?:绕过|跳过|关闭|不要).{0,20}(?:验证码|OTP|确认|授权|权限|风控|安全检查|Action|核对)"
        r"|(?:不要走|不经过).{0,10}(?:Action|确认|授权|核对)",
        re.IGNORECASE,
    ),
    "FORGE_AUTHORITY": re.compile(
        r"(?:pretend|act as).{0,20}(?:admin|system|developer)"
        r"|(?:假装|扮演|现在是).{0,20}(?:管理员|系统|开发者)"
        r"|(?:管理员|系统|开发者)\s*(?:命令|模式)",
        re.IGNORECASE,
    ),
    "FORGE_BANK_FACT": re.compile(
        r"(?:伪造|编造|编一个|编一份|假装).{0,25}(?:成功|余额|账单|流水|结果)"
        r"|(?:工具|tool).{0,20}(?:已经|已).{0,10}(?:返回|成功).{0,30}(?:不要核对|直接告诉|直接说)"
        r"|(?:不要真的查询|不要查询).{0,20}(?:成功|结果)?",
        re.IGNORECASE,
    ),
    "FORCE_TOOL_OR_DOMAIN": re.compile(
        r"(?:强制调用|调用所有|启用全部).{0,30}(?:工具|领域|domains?)"
        r"|domains?\s*=\s*\[",
        re.IGNORECASE,
    ),
    "UNSAFE_EXECUTION": re.compile(
        r"(?:执行|运行).{0,15}(?:SQL|Shell|脚本|命令)"
        r"|(?:任意|通用).{0,10}DAG.{0,30}(?:Shell|代码|股票|酒店)",
        re.IGNORECASE,
    ),
    "MODEL_DECIDES_MONEY": re.compile(
        r"(?:总预算|预算).{0,20}(?:你自己|自动).{0,15}(?:拆分|决定|分配)"
        r"|(?:你自己|自动).{0,15}(?:拆分|决定|分配).{0,20}(?:金额|预算|鲜花|蛋糕)",
        re.IGNORECASE,
    ),
}

_SENSITIVE_INPUT_PATTERNS = {
    "OTP": re.compile(r"(?:验证码|动态码|otp)\s*[:：=]?\s*\d{4,8}", re.IGNORECASE),
    "PASSWORD": re.compile(
        r"(?:密码|password|passcode)\s*[:：=]\s*\S+", re.IGNORECASE
    ),
    "TOKEN": re.compile(
        r"(?:bearer\s+[A-Za-z0-9._~+/=-]{12,}|(?:access|refresh|api)[_-]?token\s*[:：=]\s*\S+)",
        re.IGNORECASE,
    ),
    "FULL_CARD_NUMBER": re.compile(r"(?<!\d)(?:\d[ -]?){15,18}\d(?!\d)"),
}


def detect_prompt_injection(message: str) -> list[str]:
    """Return rule identifiers only; never persist or audit the raw message."""

    return [name for name, pattern in _INJECTION_PATTERNS.items() if pattern.search(message)]


def detect_sensitive_input(message: str) -> list[str]:
    return [
        name for name, pattern in _SENSITIVE_INPUT_PATTERNS.items() if pattern.search(message)
    ]


class AgentConversationService:
    def __init__(self, db, settings: Settings):
        self.db = db
        self.settings = settings

    @staticmethod
    def _message_view(row: AgentMessage | None):
        if row is None:
            return None
        return AgentStoredMessage(
            id=row.id,
            role=row.role,
            content=row.content,
            sequence=row.sequence,
            created_at=aware(row.created_at),
        )

    @staticmethod
    def _event_view(row: AgentEvent):
        return AgentStreamEvent(
            event_id=str(row.id),
            conversation_id=row.conversation_id,
            run_id=row.run_id,
            trace_id=row.trace_id,
            type=row.type,
            created_at=aware(row.created_at),
            data=row.data,
        )

    def _run_view(self, row: AgentRun | None):
        if row is None:
            return None
        assistant = (
            self.db.get(AgentMessage, row.assistant_message_id)
            if row.assistant_message_id
            else None
        )
        return AgentRunResponse(
            id=row.id,
            conversation_id=row.conversation_id,
            trace_id=row.trace_id,
            status=row.status,
            attempts=row.attempts,
            error_code=row.error_code,
            error_message=row.error_message,
            created_at=aware(row.created_at),
            started_at=aware(row.started_at) if row.started_at else None,
            completed_at=aware(row.completed_at) if row.completed_at else None,
            assistant_message=self._message_view(assistant),
        )

    def _owned_conversation(self, user: User, conversation_id: str, *, lock=False):
        query = select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.user_id == user.id,
            AgentConversation.status == "ACTIVE",
        )
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = self.db.scalar(query)
        require(row is not None, "NOT_FOUND", "会话不存在", 404)
        return row

    def create(self, user: User, title: str):
        timestamp = now()
        row = AgentConversation(
            user_id=user.id,
            title=title,
            status="ACTIVE",
            trusted_refs={},
            created_at=timestamp,
            updated_at=timestamp,
            expires_at=timestamp
            + timedelta(days=self.settings.agent_conversation_retention_days),
        )
        self.db.add(row)
        self.db.commit()
        return self._summary(row, None)

    def _summary(self, row: AgentConversation, latest: AgentRun | None):
        return AgentConversationSummary(
            id=row.id,
            title=row.title,
            status=row.status,
            created_at=aware(row.created_at),
            updated_at=aware(row.updated_at),
            expires_at=aware(row.expires_at),
            latest_run_status=latest.status if latest else None,
        )

    def list(self, user: User, limit: int = 30):
        rows = self.db.scalars(
            select(AgentConversation)
            .where(
                AgentConversation.user_id == user.id,
                AgentConversation.status == "ACTIVE",
                AgentConversation.expires_at > now(),
            )
            .order_by(AgentConversation.updated_at.desc(), AgentConversation.id.desc())
            .limit(limit)
        ).all()
        result = []
        for row in rows:
            latest = self.db.scalar(
                select(AgentRun)
                .where(AgentRun.conversation_id == row.id)
                .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
                .limit(1)
            )
            result.append(self._summary(row, latest))
        return result

    def detail(self, user: User, conversation_id: str):
        row = self._owned_conversation(user, conversation_id)
        messages = self.db.scalars(
            select(AgentMessage)
            .where(AgentMessage.conversation_id == row.id)
            .order_by(AgentMessage.sequence)
            .limit(500)
        ).all()
        events = self.db.scalars(
            select(AgentEvent)
            .where(AgentEvent.conversation_id == row.id)
            .order_by(AgentEvent.id)
            .limit(1000)
        ).all()
        current = self.db.scalar(
            select(AgentRun)
            .where(AgentRun.conversation_id == row.id)
            .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
            .limit(1)
        )
        summary = self._summary(row, current).model_dump()
        return AgentConversationDetail(
            **summary,
            messages=[self._message_view(item) for item in messages],
            events=[self._event_view(item) for item in events],
            current_run=self._run_view(current),
        )

    def delete(self, user: User, conversation_id: str):
        row = self._owned_conversation(user, conversation_id, lock=True)
        run_ids = select(AgentRun.id).where(AgentRun.conversation_id == row.id)
        self.db.execute(
            update(SecurityEvent)
            .where(SecurityEvent.conversation_id == row.id)
            .values(conversation_id=None)
        )
        self.db.execute(
            update(SecurityEvent)
            .where(SecurityEvent.run_id.in_(run_ids))
            .values(run_id=None)
        )
        self.db.execute(delete(AgentEvent).where(AgentEvent.conversation_id == row.id))
        self.db.execute(delete(AgentRun).where(AgentRun.conversation_id == row.id))
        self.db.execute(
            delete(AgentMessage).where(AgentMessage.conversation_id == row.id)
        )
        self.db.delete(row)
        self.db.commit()

    def enqueue(
        self,
        user: User,
        conversation_id: str,
        body: AgentConversationMessageRequest,
        idempotency_key: str,
    ):
        sensitive = detect_sensitive_input(body.message)
        if sensitive:
            conversation = self._owned_conversation(user, conversation_id)
            AgentSecurityService(self.db).record_failure(
                user,
                kind="SENSITIVE_CHAT_INPUT_BLOCKED",
                severity="HIGH",
                outcome="BLOCKED",
                conversation_id=conversation.id,
                secret_types=sensitive,
            )
            self.db.commit()
            raise DomainError(
                "SENSITIVE_INPUT_NOT_ALLOWED",
                "请勿在对话中发送验证码、密码、Token 或完整卡号；验证码请仅在安全验证页面输入",
                422,
            )

        request_payload = {
            "conversation_id": conversation_id,
            "message": body.message,
            "query_context": (
                body.query_context.model_dump(mode="json")
                if body.query_context is not None
                else None
            ),
            "continuation_ref": body.continuation_ref,
            "option_ref": body.option_ref,
        }
        request_hash = fingerprint(request_payload)
        existing = self.db.scalar(
            select(AgentRun).where(
                AgentRun.user_id == user.id,
                AgentRun.idempotency_key == idempotency_key,
            )
        )
        if existing:
            require(
                existing.request_hash == request_hash,
                "IDEMPOTENCY_KEY_REUSED",
                "同一幂等键不能用于不同消息",
                409,
            )
            return self._run_view(existing)

        conversation = self._owned_conversation(user, conversation_id, lock=True)
        active = self.db.scalar(
            select(AgentRun.id).where(
                AgentRun.conversation_id == conversation.id,
                AgentRun.status.in_(ACTIVE_RUN_STATUSES),
            )
        )
        if active is not None:
            raise DomainError(
                "AGENT_RUN_IN_PROGRESS",
                "上一条消息仍在处理中，请等待完成后再发送",
                409,
                True,
            )

        trusted_option = None
        if body.option_ref:
            trusted_option = self.resolve_reference(
                user, conversation.id, body.option_ref, lock=False
            )
            request_payload["trusted_option"] = {
                "kind": trusted_option["kind"],
                "label": trusted_option["label"],
            }

        next_sequence = (
            self.db.scalar(
                select(func.max(AgentMessage.sequence)).where(
                    AgentMessage.conversation_id == conversation.id
                )
            )
            or 0
        ) + 1
        message = AgentMessage(
            conversation_id=conversation.id,
            role="user",
            content=body.message,
            sequence=next_sequence,
        )
        self.db.add(message)
        self.db.flush()
        timestamp = now()
        run = AgentRun(
            conversation_id=conversation.id,
            user_id=user.id,
            user_message_id=message.id,
            trace_id=secrets.token_hex(16),
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            request=request_payload,
            status="QUEUED",
            attempts=0,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.db.add(run)
        conversation.updated_at = timestamp
        conversation.expires_at = timestamp + timedelta(
            days=self.settings.agent_conversation_retention_days
        )
        if conversation.title == "新对话" and next_sequence == 1:
            conversation.title = " ".join(body.message.split())[:40]
        self.db.flush()

        findings = detect_prompt_injection(body.message)
        if findings:
            AgentSecurityService(self.db).record_failure(
                user,
                kind="PROMPT_INJECTION_SUSPECTED",
                severity="MEDIUM",
                outcome="CONTROLS_ENFORCED",
                conversation_id=conversation.id,
                run_id=run.id,
                trace_id=run.trace_id,
                rule_ids=findings,
            )
        self.db.commit()
        return self._run_view(run)

    def run(self, user: User, run_id: str):
        row = self.db.scalar(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user.id)
        )
        require(row is not None, "NOT_FOUND", "运行记录不存在", 404)
        return self._run_view(row)

    def events_after(self, user: User, conversation_id: str, after_id: int):
        self._owned_conversation(user, conversation_id)
        rows = self.db.scalars(
            select(AgentEvent)
            .where(
                AgentEvent.conversation_id == conversation_id,
                AgentEvent.id > after_id,
            )
            .order_by(AgentEvent.id)
            .limit(200)
        ).all()
        return [self._event_view(row) for row in rows]

    def latest_run_status(self, user: User, conversation_id: str):
        self._owned_conversation(user, conversation_id)
        return self.db.scalar(
            select(AgentRun.status)
            .where(AgentRun.conversation_id == conversation_id)
            .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
            .limit(1)
        )

    def issue_reference(
        self,
        user: User,
        conversation_id: str,
        kind: str,
        resource_id: str,
        label: str,
    ) -> str:
        conversation = self._owned_conversation(user, conversation_id, lock=True)
        refs = dict(conversation.trusted_refs or {})
        for reference, data in refs.items():
            if data.get("kind") == kind and data.get("resource_id") == str(resource_id):
                return reference
        reference = secrets.token_hex(16)
        if len(refs) >= 100:
            oldest = next(iter(refs))
            refs.pop(oldest, None)
        refs[reference] = {
            "kind": kind,
            "resource_id": str(resource_id),
            "label": label[:120],
            "created_at": now().isoformat(),
        }
        conversation.trusted_refs = refs
        return reference

    def resolve_reference(
        self,
        user: User,
        conversation_id: str,
        reference: str,
        *,
        kind: str | None = None,
        lock: bool = False,
    ) -> dict[str, Any]:
        conversation = self._owned_conversation(user, conversation_id, lock=lock)
        item = (conversation.trusted_refs or {}).get(reference)
        require(
            item is not None and (kind is None or item.get("kind") == kind),
            "INVALID_OPTION_REFERENCE",
            "该选项已失效，请重新查询候选项",
            422,
        )
        return item

    def claim_one(self):
        timestamp = now()
        exhausted = self.db.scalars(
            select(AgentRun)
            .where(
                AgentRun.status == "RUNNING",
                AgentRun.lease_until < timestamp,
                AgentRun.attempts >= self.settings.agent_run_max_attempts,
            )
            .with_for_update(skip_locked=True)
        ).all()
        for row in exhausted:
            row.status = "FAILED"
            row.error_code = "AGENT_RETRY_EXHAUSTED"
            row.error_message = "Agent 多次恢复失败，请重新发送"
            row.completed_at = timestamp
            row.lease_until = None
            self._add_event(row, "ERROR", {
                "code": row.error_code,
                "message": row.error_message,
                "retryable": False,
            })

        row = self.db.scalar(
            select(AgentRun)
            .where(
                or_(
                    AgentRun.status == "QUEUED",
                    (
                        (AgentRun.status == "RUNNING")
                        & (AgentRun.lease_until < timestamp)
                    ),
                ),
                AgentRun.attempts < self.settings.agent_run_max_attempts,
            )
            .order_by(AgentRun.created_at, AgentRun.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            self.db.commit()
            return None
        row.status = "RUNNING"
        row.attempts += 1
        row.started_at = row.started_at or timestamp
        row.updated_at = timestamp
        row.lease_until = timestamp + timedelta(
            seconds=self.settings.agent_run_lease_seconds
        )
        row.error_code = None
        row.error_message = None
        self._add_event(row, "EXECUTING", {"attempt": row.attempts})
        self.db.commit()
        return row.id

    def execution_input(self, run_id: str):
        run = self.db.get(AgentRun, run_id)
        require(run is not None, "NOT_FOUND", "运行记录不存在", 404)
        user = self.db.get(User, run.user_id)
        message = self.db.get(AgentMessage, run.user_message_id)
        require(user is not None and message is not None, "AGENT_RUN_INVALID", "运行上下文不完整", 500)
        history_rows = self.db.scalars(
            select(AgentMessage)
            .where(
                AgentMessage.conversation_id == run.conversation_id,
                AgentMessage.role == "user",
                AgentMessage.sequence < message.sequence,
            )
            .order_by(AgentMessage.sequence.desc())
            .limit(8)
        ).all()
        payload = run.request
        body = AgentMessageRequest(
            message=message.content,
            history=[item.content for item in reversed(history_rows)],
            query_context=payload.get("query_context"),
            continuation_ref=payload.get("continuation_ref"),
        )
        return run, user, body

    def complete(self, run_id: str, response: AgentMessageResponse):
        run = self.db.scalar(
            select(AgentRun)
            .where(AgentRun.id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        require(run is not None, "NOT_FOUND", "运行记录不存在", 404)
        if run.status == "SUCCEEDED":
            return self._run_view(run)
        conversation = self.db.scalar(
            select(AgentConversation)
            .where(AgentConversation.id == run.conversation_id)
            .with_for_update()
        )
        next_sequence = (
            self.db.scalar(
                select(func.max(AgentMessage.sequence)).where(
                    AgentMessage.conversation_id == run.conversation_id
                )
            )
            or 0
        ) + 1
        assistant = AgentMessage(
            conversation_id=run.conversation_id,
            role="assistant",
            content=response.message,
            sequence=next_sequence,
        )
        self.db.add(assistant)
        self.db.flush()
        run.assistant_message_id = assistant.id
        run.status = "SUCCEEDED"
        run.completed_at = now()
        run.updated_at = run.completed_at
        run.lease_until = None
        self._add_event(
            run,
            "TEXT_COMPLETE",
            {"message_id": assistant.id, "text": response.message},
        )
        for event in response.events:
            payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else event
            self._add_event(run, payload["type"], payload.get("data", {}))
        self._add_event(run, "SUCCESS", {"message_id": assistant.id})
        if conversation is not None:
            conversation.updated_at = run.completed_at
            conversation.expires_at = run.completed_at + timedelta(
                days=self.settings.agent_conversation_retention_days
            )
        self.db.commit()
        return self._run_view(run)

    def fail(
        self,
        run_id: str,
        code: str,
        message: str,
        *,
        retryable: bool,
    ):
        run = self.db.scalar(
            select(AgentRun)
            .where(AgentRun.id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if run is None or run.status in TERMINAL_RUN_STATUSES:
            return self._run_view(run)
        retry = retryable and run.attempts < self.settings.agent_run_max_attempts
        run.status = "QUEUED" if retry else "FAILED"
        run.error_code = code
        run.error_message = message[:500]
        run.lease_until = None
        run.updated_at = now()
        if not retry:
            run.completed_at = run.updated_at
        self._add_event(
            run,
            "ERROR",
            {"code": code, "message": message[:500], "retryable": retry},
        )
        self.db.commit()
        return self._run_view(run)

    def _add_event(self, run: AgentRun, type_: str, data: dict[str, Any]):
        self.db.add(
            AgentEvent(
                conversation_id=run.conversation_id,
                run_id=run.id,
                trace_id=run.trace_id,
                type=type_,
                data=redact_audit_data(data),
            )
        )

    def cleanup_expired(self):
        rows = self.db.scalars(
            select(AgentConversation.id).where(AgentConversation.expires_at <= now())
        ).all()
        count = 0
        for conversation_id in rows:
            owner_id = self.db.scalar(
                select(AgentConversation.user_id).where(
                    AgentConversation.id == conversation_id
                )
            )
            user = self.db.get(User, owner_id) if owner_id else None
            if user:
                self.delete(user, conversation_id)
                count += 1
        return count


class AgentSecurityService:
    """Deterministic security lock primitives; model output cannot override them."""

    def __init__(self, db):
        self.db = db

    @staticmethod
    def is_counted_failure(exc) -> bool:
        if not isinstance(exc, DomainError) or exc.code == "SECURITY_LOCKED":
            return False
        return exc.status == 403 or exc.code in {
            "FORBIDDEN_DOMAIN",
            "AGENT_TOOL_NOT_ALLOWED",
            "IDEMPOTENCY_KEY_REUSED",
            "SENSITIVE_INPUT_NOT_ALLOWED",
            "INVALID_ACCOUNT_REFERENCE",
            "INVALID_OPTION_REFERENCE",
        }

    def require_unlocked(self, user: User, scope: str = "AGENT_WRITE"):
        row = self.db.scalar(
            select(SecurityLock).where(
                SecurityLock.user_id == user.id, SecurityLock.scope == scope
            )
        )
        require(
            row is None or row.locked_until is None or aware(row.locked_until) <= now(),
            "SECURITY_LOCKED",
            "写操作因连续安全校验失败暂时锁定，请稍后再试",
            423,
        )

    def record_event(
        self,
        user: User,
        kind: str,
        outcome: str,
        *,
        severity: str = "INFO",
        conversation_id: str | None = None,
        run_id: str | None = None,
        trace_id: str | None = None,
        **data,
    ):
        self.db.add(
            SecurityEvent(
                user_id=user.id,
                conversation_id=conversation_id,
                run_id=run_id,
                trace_id=trace_id,
                kind=kind,
                severity=severity,
                outcome=outcome,
                data=redact_audit_data(data),
            )
        )

    def record_failure(
        self,
        user: User,
        kind: str,
        outcome: str,
        *,
        severity: str = "HIGH",
        conversation_id: str | None = None,
        run_id: str | None = None,
        trace_id: str | None = None,
        **data,
    ) -> bool:
        """Record one controlled failure and lock later Agent writes at threshold."""

        timestamp = now()
        lock_user(self.db, user)
        row = self.db.scalar(
            select(SecurityLock)
            .where(
                SecurityLock.user_id == user.id,
                SecurityLock.scope == "AGENT_WRITE",
            )
            .with_for_update()
        )
        if row is None:
            row = SecurityLock(
                user_id=user.id,
                scope="AGENT_WRITE",
                reason=kind,
                failure_count=1,
                window_started_at=timestamp,
            )
            self.db.add(row)
        elif aware(row.window_started_at) + AGENT_SECURITY_FAILURE_WINDOW <= timestamp:
            row.reason = kind
            row.failure_count = 1
            row.window_started_at = timestamp
            row.locked_until = None
        else:
            row.reason = kind
            row.failure_count += 1

        locked = row.failure_count >= AGENT_SECURITY_FAILURE_THRESHOLD
        if locked:
            candidate = timestamp + AGENT_SECURITY_LOCK_DURATION
            if row.locked_until is None or aware(row.locked_until) < candidate:
                row.locked_until = candidate

        self.record_event(
            user,
            kind,
            outcome,
            severity=severity,
            conversation_id=conversation_id,
            run_id=run_id,
            trace_id=trace_id,
            failure_count=row.failure_count,
            write_locked=locked,
            **data,
        )
        return locked
