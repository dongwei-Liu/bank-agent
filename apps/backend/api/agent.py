from functools import lru_cache
from collections.abc import Callable
import json
import re
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.responses import StreamingResponse
from langsmith import tracing_context
from langchain_core.messages import AIMessage, BaseMessage
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from agent.context import (
    AgentContext, effective_query_context, explicit_cancel_merchant, is_bill_report_view_request,
    is_bill_report_generate_request, is_lead_only_reply,
    parse_bill_report_generate_intent, parse_bill_report_view_intent,
    parse_card_request_intent, parse_insight_query_intent, parse_lead_days,
    parse_birthday_orchestration_intent, parse_subscription_intent,
    prepare_account_refs, routing_message,
)
from agent.graph import build_agent_graph
from agent.router import DomainRoute, AGENT_DOMAINS, approve_domains, route_domains
from api.context import (
    Actor, Db, DecimalRoute, Key, billing_service, analysis_service,
    bill_report_service, subscription_planning_service, subscription_service,
    transaction_service,
    action_service, transfer_service, schedule_service, aa_service, card_service,
    investment_service, orchestration_service,
)
from clients.fineract import FineractError
from core.deps import get_account_service, get_fineract_client
from core.config import get_settings
from core.errors import DomainError
from core.security import SHANGHAI, now
from schemas.agent import (
    AgentAnalysisResponse,
    AgentConversationCreateRequest,
    AgentConversationDetail,
    AgentConversationMessageRequest,
    AgentConversationSummary,
    AgentMessageRequest,
    AgentMessageResponse,
    AgentRunResponse,
)
from services.common import audit
from services.agent_conversation_service import (
    AgentConversationService,
    AgentSecurityService,
    TERMINAL_RUN_STATUSES,
    detect_sensitive_input,
)
from services.recipient_service import RecipientService
from models import User

router = APIRouter(prefix="/api/agent", tags=["agent"], route_class=DecimalRoute)
stream_router = APIRouter(prefix="/api/agent", tags=["agent"])


@lru_cache(maxsize=8)
def get_agent_graph(domains: tuple[str, ...]):
    """只缓存图，不缓存用户、Service 或数据库 Session。"""
    return build_agent_graph(domains, model_timeout_seconds=60)


def get_agent_router():
    return route_domains


def get_agent_graph_factory():
    return get_agent_graph


def _message_text(message: BaseMessage) -> str:
    if isinstance(message.content, str):
        return message.content.strip()
    parts: list[str] = []
    for block in message.content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "\n".join(part.strip() for part in parts if part.strip())


def _final_answer(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not message.tool_calls:
            answer = _message_text(message)
            if answer:
                return answer
    raise DomainError("AGENT_NO_RESPONSE", "Agent 未生成可用回复", 502, True)


def _tool_names(messages: list[BaseMessage]) -> list[str]:
    names: list[str] = []
    for message in messages:
        if isinstance(message, AIMessage):
            names.extend(str(call.get("name")) for call in message.tool_calls)
    return names


def _routing_input(body: AgentMessageRequest, *, trusted_history: bool = False) -> str:
    """Use persisted history only to keep an obvious short follow-up in-domain."""
    current = routing_message(body.message)
    compact = " ".join(body.message.split())
    account_follow_up = re.fullmatch(
        r"(?:我\s*)?(?:选择\s*)?(?:从\s*)?(?:尾号|末四位)\s*[<＜]?\s*\d{4}\s*[>＞]?"
        r"(?:\s*的)?\s*账户?\s*[。.!！]?",
        compact,
    )
    referential_follow_up = re.fullmatch(
        r"(?:我\s*)?(?:选择\s*)?(?:这个|该|刚才(?:那个)?)\s*(?:账户|选项)?\s*[。.!！]?|"
        r"(?:继续|确认选择)\s*[。.!！]?",
        compact,
    )
    follow_up = len(body.message) <= 40 and bool(
        account_follow_up or referential_follow_up
    )
    if not trusted_history or not follow_up or not body.history:
        return current
    previous = [routing_message(item) for item in body.history[-2:] if item.strip()]
    return "\n".join([*(f"此前请求：{item}" for item in previous), f"当前补充：{current}"])


def execute_agent_message(
    body: AgentMessageRequest,
    user,
    db,
    route: Callable,
    graph_factory: Callable,
    *,
    trace_id: str | None = None,
    run_id: str | None = None,
    conversation_id: str | None = None,
    reference_service=None,
    selected_option_ref: str | None = None,
    trusted_option: dict | None = None,
    trusted_history_routing: bool = False,
):
    """认证后路由到获准业务域；身份与所有写操作授权都由中端控制。"""

    trace_id = trace_id or str(uuid4())
    sensitive = detect_sensitive_input(body.message)
    if sensitive:
        AgentSecurityService(db).record_failure(
            user,
            kind="SENSITIVE_CHAT_INPUT_BLOCKED",
            severity="HIGH",
            outcome="BLOCKED",
            trace_id=trace_id,
            secret_types=sensitive,
        )
        db.commit()
        raise DomainError(
            "SENSITIVE_INPUT_NOT_ALLOWED",
            "请勿在对话中发送验证码、密码、Token 或完整卡号；验证码请仅在安全验证页面输入",
            422,
        )
    domains = ()
    private = None
    context = None
    try:
        current_date = now().astimezone(SHANGHAI).date()
        subscription_intent = None
        continuation_ref = body.continuation_ref
        if continuation_ref:
            leads = parse_lead_days(body.message)
            if is_lead_only_reply(body.message) and leads is not None:
                subscription_intent = {
                    "kind": "CONTINUATION", "clarification_id": continuation_ref,
                    "lead_days": leads,
                }
            elif is_lead_only_reply(body.message):
                subscription_intent = {"kind": "INVALID_CONTINUATION"}
            else:
                continuation_ref = None
        if subscription_intent is None:
            subscription_intent = parse_subscription_intent(body.message, current_date)
        cancellation_service = subscription_service(db) if any(
            token in body.message for token in ("取消", "退订")
        ) else None
        exact_merchant = (
            explicit_cancel_merchant(body.message, cancellation_service, user)
            if cancellation_service else None
        )
        if exact_merchant:
            subscription_intent = None
        option_domain = {
            "recipient": "payments",
            "account": "payments",
            "card": "cards",
            "schedule": "payment_plans",
            "aa": "payment_plans",
            "product": "wealth",
            "holding": "wealth",
            "orchestration_account": "orchestration",
        }.get((trusted_option or {}).get("kind"))
        if exact_merchant or subscription_intent:
            candidate = ("subscriptions",)
        elif option_domain in AGENT_DOMAINS:
            candidate = (option_domain,)
        elif is_bill_report_view_request(body.message) or is_bill_report_generate_request(body.message):
            candidate = ("insights",)
        else:
            candidate = route(
                _routing_input(body, trusted_history=trusted_history_routing),
                allowed_domains=AGENT_DOMAINS,
            )
        domains = approve_domains(DomainRoute(domains=candidate), AGENT_DOMAINS)

        context = None
        if not domains:
            result = {
                "messages": [AIMessage(content=(
                    "目前支持本人账户与流水、消费洞察、账单报告、订阅扣费、联系人和转账、"
                    "借记卡、定时转账、AA 收款与 CNY 定期存款。"
                    "还支持固定的生日鲜花与蛋糕任务及任务状态查询。"
                    "已核实的 Demo 订阅可按商户名称申请取消，并在操作页核对后确认。"
                    "订阅操作需单独发起；列表与人工核实可在订阅管理页操作。"
                    "请说明你希望查询的内容。"
                ))],
                "events": [],
            }
        else:
            accounts = get_account_service()
            query_context = effective_query_context(body.query_context, body.message)
            refs, selected, model_message = prepare_account_refs(
                user,
                accounts,
                query_context,
                body.message,
                reference_factory=(
                    lambda kind, resource_id, label: reference_service.issue_reference(
                        user, conversation_id, kind, resource_id, label
                    )
                )
                if reference_service is not None and conversation_id is not None
                else None,
            )
            report_view_intent = parse_bill_report_view_intent(
                body.message, current_date, query_context, refs,
            ) if "insights" in domains else None
            report_generate_intent = parse_bill_report_generate_intent(
                body.message, current_date, query_context, refs,
            ) if "insights" in domains else None
            insight_query_intent = parse_insight_query_intent(
                body.message, current_date, query_context, refs,
            ) if "insights" in domains else None
            orchestration_intent = parse_birthday_orchestration_intent(
                body.message
            ) if "orchestration" in domains else None
            cards = card_service(db) if "cards" in domains else None
            card_rows = cards.list(user) if cards is not None else []
            card_request_intent = parse_card_request_intent(
                body.message,
                known_aliases=tuple(str(row.get("alias") or "") for row in card_rows),
                has_trusted_target=(trusted_option or {}).get("kind") == "card",
            ) if "cards" in domains else None
            wealth = investment_service(db) if "wealth" in domains else None
            private = analysis_service(db, accounts, wealth)
            needs_payments = bool({"payments", "payment_plans"} & set(domains))
            context = AgentContext(
                user=user,
                account_service=accounts,
                query_context=query_context,
                private_results=private,
                account_refs=refs,
                selected_ref=selected,
                billing_service=(
                    billing_service(db) if "insights" in domains else None
                ),
                bill_reports=(bill_report_service(db) if "insights" in domains else None),
                report_view_intent=report_view_intent,
                report_generate_intent=report_generate_intent,
                insight_query_intent=insight_query_intent,
                subscription_service=((cancellation_service or subscription_service(db)) if "subscriptions" in domains else None),
                subscription_planning_service=(subscription_planning_service(db) if "subscriptions" in domains else None),
                subscription_intent=subscription_intent,
                card_request_intent=card_request_intent,
                continuation_ref=continuation_ref,
                current_date=current_date,
                trace_id=trace_id,
                agent_run_id=run_id,
                user_message=body.message,
                user_history=tuple(body.history),
                explicit_cancel_merchant=exact_merchant,
                conversation_id=conversation_id,
                reference_service=reference_service,
                selected_option_ref=selected_option_ref,
                trusted_option=trusted_option,
                transaction_service=(transaction_service(db) if "accounts" in domains else None),
                recipient_service=(RecipientService(db, get_fineract_client()) if needs_payments else None),
                transfer_service=(transfer_service(db) if "payments" in domains else None),
                action_service=(
                    action_service(db)
                    if {"payments", "wealth", "orchestration", "subscriptions"} & set(domains)
                    else None
                ),
                card_service=cards,
                schedule_service=(schedule_service(db) if "payment_plans" in domains else None),
                aa_service=(aa_service(db) if "payment_plans" in domains else None),
                investment_service=wealth,
                orchestration_service=(
                    orchestration_service(db)
                    if "orchestration" in domains
                    else None
                ),
                orchestration_intent=orchestration_intent,
                security_service=AgentSecurityService(db),
            )
            graph = graph_factory(domains)
            with tracing_context(enabled=False):
                result = graph.invoke(
                    {"messages": [
                        *(("user", item) for item in body.history),
                        ("user", model_message),
                    ], "events": []},
                    context=context,
                    config={"recursion_limit": 8, "max_concurrency": 1},
                )

        messages = result.get("messages", [])
        tool_names = _tool_names(messages)
        report_events = context.report_events if context else []
        subscription_events = context.subscription_events if context else []
        subscription_cancel_events = context.subscription_cancel_events if context else []
        workflow_events = context.subscription_workflow_events if context else []
        subscription_query_events = context.subscription_query_events if context else []
        wealth_events = [
            event
            for event in (context.events if context else [])
            if getattr(event, "type", None)
            in {"WEALTH_RISK_ASSESSMENT_REQUIRED", "WEALTH_ACTION_CREATED"}
        ]
        orchestration_events = [
            event
            for event in (context.events if context else [])
            if getattr(event, "type", None)
            in {"ORCHESTRATION_TASK_CREATED", "ORCHESTRATION_TASKS_READY"}
        ]
        card_events = [
            event
            for event in (context.events if context else [])
            if getattr(event, "type", None) == "CARD_ACTION_CREATED"
        ]
        if subscription_cancel_events:
            status = subscription_cancel_events[0].data.status
            if status == "WAITING_CONFIRMATION":
                answer = (
                    "订阅取消请求已准备好，当前尚未执行取消。"
                    "请前往操作页核对订阅详情，并在确认后继续。"
                )
            elif status == "WAITING_VERIFICATION":
                answer = "订阅取消请求需要额外验证，请前往操作页核对详情并按页面提示继续。"
            elif status in {"AUTHORIZED", "EXECUTING", "RECONCILING"}:
                answer = "订阅取消请求已在处理中，请前往操作页查看当前状态；请勿重复提交。"
            elif status == "SUCCEEDED":
                answer = "这项订阅取消请求已完成，请前往操作页查看结果。"
            else:
                answer = "找到这项订阅的既有取消请求，请前往操作页查看状态和恢复方式。"
        elif subscription_events:
            answer = (
                "订阅扣费识别已完成。本次匹配和保存情况请查看结果卡；"
                "新识别的候选仍需你在订阅管理页核实。"
            )
        elif subscription_query_events:
            answer = "订阅查询请求已准备好。请核对查询条件并点击结果卡中的“确认查询”；确认前不会读取订阅结果。"
        elif workflow_events:
            event_types = {event.type for event in workflow_events}
            if "SUBSCRIPTION_CLARIFICATION_REQUIRED" in event_types:
                answer = "我先展示了符合条件的预计扣费项目。请补充希望提前几天收到提醒，可选1天、3天、7天或组合；补充后才会保存规则。"
            elif "SUBSCRIPTION_BUDGET_READY" in event_types:
                answer = "订阅预算监测已保存，评估结果与可管理项目见结果卡。预算只用于监测，任何取消都需要你逐项确认。"
            elif "SUBSCRIPTION_REMINDER_RULE_SAVED" in event_types:
                answer = "续费提醒规则已保存，生效范围和提前天数见结果卡。"
            elif "SUBSCRIPTION_RULES_READY" in event_types:
                answer = "已读取本人订阅提醒与预算规则，请查看结果卡。"
            else:
                answer = "预计续费查询已完成，详细项目和完整性说明见结果卡。"
        elif card_events:
            answer = (
                "卡片操作请求已准备好，当前尚未执行。"
                "请前往操作页核对卡片与变更内容，并完成确认和必要的 OTP。"
            )
        elif orchestration_events:
            event = orchestration_events[0]
            if event.type == "ORCHESTRATION_TASK_CREATED":
                status = event.data.authorization_status
                if status in {"WAITING_CONFIRMATION", "WAITING_VERIFICATION"}:
                    answer = (
                        "生日任务和 RED 授权请求已准备好，资金尚未冻结或转出。"
                        "请先在任务页核对固定计划，再到操作页完成确认与 OTP。"
                    )
                elif status in {"AUTHORIZED", "EXECUTING", "RECONCILING"}:
                    answer = "生日任务授权正在处理中，请打开任务页查看状态；请勿重复创建。"
                elif status == "SUCCEEDED":
                    answer = "生日任务已完成授权，请在任务页查看后续节点与资金核对状态。"
                else:
                    answer = "已找到这项生日任务，请打开任务页查看状态和可用恢复操作。"
            else:
                answer = "已读取本人生日任务，状态与可用操作请查看结果卡。"
        elif wealth_events:
            event = wealth_events[0]
            if event.type == "WEALTH_RISK_ASSESSMENT_REQUIRED":
                answer = (
                    "继续这项操作前，需要你本人完成本次五题风险测评。"
                    "请打开结果卡中的测评页面；我不会替你作答。"
                )
            else:
                status = event.data.status
                operation = "定存申购" if event.data.operation == "subscription" else "定存赎回"
                if status == "WAITING_CONFIRMATION":
                    answer = f"{operation}请求已准备好，资金尚未变更。请前往操作页核对，并完成确认和 OTP。"
                elif status == "WAITING_VERIFICATION":
                    answer = f"{operation}请求正在等待安全验证，请前往操作页继续。"
                elif status in {"AUTHORIZED", "EXECUTING", "RECONCILING"}:
                    answer = f"{operation}请求正在处理中，请前往操作页核对状态；请勿重复提交。"
                elif status == "SUCCEEDED":
                    answer = f"这项{operation}已经完成，请前往操作页查看核心银行核对结果。"
                else:
                    answer = f"已找到这项{operation}请求，请前往操作页查看状态和恢复方式。"
        elif report_events:
            opened = next((event for event in report_events
                           if getattr(event, "type", None) == "BILL_REPORT_OPENED"), None)
            if opened is not None:
                data = opened.data
                if data.generated:
                    answer = "未找到对应报告，已开始生成；你可以在结果卡查看进度。"
                elif data.status in {"complete", "partial"}:
                    answer = "已找到对应账单报告，结果卡可直接打开。"
                elif data.status in {"queued", "running"}:
                    answer = "已找到对应报告任务，正在生成；结果卡会显示进度。"
                else:
                    answer = "已找到对应报告，但生成失败。请查看结果卡中的失败原因；需要重试时可在报告页面重新生成。"
            else:
                answer = "账单报告已提交后台生成，完成后可在报告页查看。"
        else:
            answer = _final_answer(messages)
            if domains and not tool_names:
                # No Tool means no banking facts have been verified in this request.
                answer = (
                    "本次未执行查询，尚未获得银行数据。请明确账户范围和日期；"
                    "例如：统计我所有账户的消费分类，按金额从高到低列出。"
                    "也可以选择账户和月份后点击“消费统计”，或询问“我还有多少钱”。"
                )
                if "subscriptions" in domains:
                    answer = (
                        "本次没有执行订阅操作。"
                        "请明确说明是识别订阅，还是取消某个具体的 Demo 订阅；"
                        "也可以进入订阅管理页选择具体项目。"
                    )
                elif "orchestration" in domains:
                    answer = (
                        "本次没有创建生日任务。请明确事件名称、完整日期、付款账户，"
                        "以及鲜花和蛋糕各自的金额；也可以直接询问“查看我的生日任务”。"
                    )
                elif "payment_plans" in domains:
                    if "AA" in body.message.upper():
                        answer = (
                            "本次没有创建或修改 AA 请求。创建均分 AA 还需要明确列出参与的已保存联系人，"
                            "并选择本人收款账户；支付或取消既有 AA 时请先从本人请求列表中选择唯一项目。"
                        )
                    elif any(token in body.message for token in ("暂停", "恢复", "取消")):
                        answer = (
                            "本次没有修改定时转账计划。请先列出本人计划并选择唯一项目；"
                            "系统不会根据模糊描述擅自暂停、恢复或取消。"
                        )
                    else:
                        answer = (
                            "本次没有创建定时转账计划。周期计划还需要明确付款账户、精确首次执行时刻、"
                            "每日上限和授权截止时间；这些信息不会由模型猜测。"
                        )
                elif "cards" in domains:
                    answer = (
                        "本次没有创建或修改卡片请求。请先从本人卡片列表选择唯一卡片，"
                        "再说明要调整的限额、渠道或状态；系统不会根据模糊描述擅自选择卡片。"
                    )
            elif private and private.events:
                answer = private.render(answer)
        events = []
        if private and tool_names:
            events.extend(private.events)
        events.extend(report_events)
        events.extend(event.model_dump(mode="json") for event in subscription_events)
        events.extend(event.model_dump(mode="json") for event in subscription_cancel_events)
        events.extend(event.model_dump(mode="json") for event in workflow_events)
        events.extend(event.model_dump(mode="json") for event in subscription_query_events)
        if context:
            events.extend(event.model_dump(mode="json") for event in context.events)
        audit(
            db,
            user,
            "AGENT_MESSAGE_COMPLETED",
            trace_id=trace_id,
            domains=list(domains),
            tools=tool_names,
            tool_calls=[
                {"name": call["name"], "args": {
                    key: value for key, value in call["args"].items()
                    if key in {"account_ref", "from_date", "to_date"}
                }}
                for message in messages if isinstance(message, AIMessage)
                for call in message.tool_calls
            ],
            event_count=len(events),
        )
        db.commit()
        return AgentMessageResponse(
            trace_id=trace_id,
            message=answer,
            events=events,
        )
    except (DomainError, FineractError) as exc:
        recovered = _recover_created_request(db, user, trace_id, domains, context, exc)
        if recovered:
            return recovered
        _audit_failure(db, user, trace_id, domains, exc)
        raise
    except Exception as exc:
        recovered = _recover_created_request(db, user, trace_id, domains, context, exc)
        if recovered:
            return recovered
        _audit_failure(db, user, trace_id, domains, exc)
        raise DomainError(
            "AGENT_UNAVAILABLE", "Agent 服务暂时不可用", 503, True
        ) from exc


@router.post("/messages", response_model=AgentMessageResponse)
def send_message(
    body: AgentMessageRequest,
    user: Actor,
    db: Db,
    route: Callable = Depends(get_agent_router),
    graph_factory: Callable = Depends(get_agent_graph_factory),
):
    """Compatibility endpoint; new clients use durable conversations and SSE."""

    return execute_agent_message(body, user, db, route, graph_factory)


@router.post(
    "/conversations",
    response_model=AgentConversationSummary,
    status_code=201,
)
def create_conversation(body: AgentConversationCreateRequest, user: Actor, db: Db):
    return AgentConversationService(db, get_settings()).create(user, body.title)


@router.get("/conversations", response_model=list[AgentConversationSummary])
def list_conversations(
    user: Actor,
    db: Db,
    limit: int = Query(default=30, ge=1, le=50),
):
    return AgentConversationService(db, get_settings()).list(user, limit)


@router.get(
    "/conversations/{conversation_id}", response_model=AgentConversationDetail
)
def get_conversation(conversation_id: str, user: Actor, db: Db):
    return AgentConversationService(db, get_settings()).detail(user, conversation_id)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, user: Actor, db: Db):
    AgentConversationService(db, get_settings()).delete(user, conversation_id)
    return None


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=AgentRunResponse,
    status_code=202,
)
def enqueue_conversation_message(
    conversation_id: str,
    body: AgentConversationMessageRequest,
    idempotency_key: Key,
    user: Actor,
    db: Db,
):
    return AgentConversationService(db, get_settings()).enqueue(
        user, conversation_id, body, idempotency_key
    )


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
def get_run(run_id: str, user: Actor, db: Db):
    return AgentConversationService(db, get_settings()).run(user, run_id)


@stream_router.get("/conversations/{conversation_id}/events")
def stream_conversation_events(
    conversation_id: str,
    user: Actor,
    db: Db,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    """Replay durable events after Last-Event-ID, then follow the active run."""

    try:
        cursor = int(last_event_id or "0")
    except ValueError as exc:
        raise DomainError("INVALID_EVENT_CURSOR", "事件游标无效", 422) from exc
    if cursor < 0:
        raise DomainError("INVALID_EVENT_CURSOR", "事件游标无效", 422)
    # Authorize before returning a streaming response.
    AgentConversationService(db, get_settings()).events_after(
        user, conversation_id, cursor
    )
    user_id = user.id
    settings = get_settings()
    stream_factory = sessionmaker(db.get_bind(), expire_on_commit=False)

    def generate():
        current = cursor
        started = time.monotonic()
        while time.monotonic() - started < settings.agent_sse_max_seconds:
            with stream_factory() as stream_db:
                stream_user = stream_db.get(User, user_id)
                if stream_user is None:
                    return
                service = AgentConversationService(stream_db, settings)
                events = service.events_after(stream_user, conversation_id, current)
                status = service.latest_run_status(stream_user, conversation_id)
            for event in events:
                current = int(event.event_id)
                payload = json.dumps(
                    event.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                yield f"id: {event.event_id}\nevent: {event.type}\ndata: {payload}\n\n"
            if status in TERMINAL_RUN_STATUSES and not events:
                yield "event: stream.complete\ndata: {}\n\n"
                return
            time.sleep(settings.agent_sse_poll_seconds)
        yield "event: stream.timeout\ndata: {}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/analyses/{analysis_id}", response_model=AgentAnalysisResponse,
            responses={404: {"description": "结果不存在或不属于当前用户"},
                       410: {"description": "结果已过期，请重新分析"}})
def get_analysis(analysis_id: str, user: Actor, db: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return analysis_service(
        db, get_account_service(), investment_service(db)
    ).get(user, analysis_id)


@router.get("/subscription-results/{result_id}")
def get_subscription_result(result_id: str, user: Actor, db: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return subscription_planning_service(db).get_result(user, result_id)


def _audit_failure(db, user, trace_id, domains, exc):
    db.rollback()
    try:
        if AgentSecurityService.is_counted_failure(exc):
            AgentSecurityService(db).record_failure(
                user,
                kind="AGENT_POLICY_FAILURE",
                outcome="BLOCKED",
                severity="HIGH",
                trace_id=trace_id,
                error_code=getattr(exc, "code", type(exc).__name__),
                domains=list(domains),
            )
        audit(db, user, "AGENT_MESSAGE_FAILED", trace_id=trace_id,
              domains=list(domains), error_type=type(exc).__name__,
              error_code=getattr(exc, "code", None))
        db.commit()
    except SQLAlchemyError:
        db.rollback()


def _recover_created_request(db, user, trace_id, domains, context, exc):
    """Never hide a durable write merely because the final model narration failed."""
    if context is None or not context.events:
        return None
    db.rollback()
    events = [event.model_dump() for event in context.events]
    try:
        audit(
            db,
            user,
            "AGENT_MESSAGE_RECOVERED",
            trace_id=trace_id,
            domains=list(domains),
            error_type=type(exc).__name__,
            event_count=len(events),
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
    return AgentMessageResponse(
        trace_id=trace_id,
        message="业务请求已经创建，但智能回复生成失败。资金或状态尚未因此变更，请使用下方卡片继续确认并核对结果。",
        events=events,
    )
