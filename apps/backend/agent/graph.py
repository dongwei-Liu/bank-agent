from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.runtime import Runtime
from langsmith import tracing_context
from uuid import uuid4

from agent.context import AgentContext, query_context_prompt
from agent.registry import resolve_agent
from agent.security import contains_agent_write
from agent.state import AgentState
from core.config import get_settings
from core.errors import DomainError

MAX_TOOL_CALLS = 3


def build_agent_graph(
    enabled_domains: tuple[str, ...] = ("accounts",),
    *,
    model_timeout_seconds: float = 20,
):
    """只为可信中端策略明确启用的业务域构建 Agent 图。"""
    if not 0 < model_timeout_seconds <= 300:
        raise ValueError("模型请求超时必须大于 0 且不超过 300 秒")
    settings = get_settings()
    agent = resolve_agent(enabled_domains)

    model = ChatOpenAI(
        model=settings.siliconflow_model,
        api_key=settings.siliconflow_api_key,
        base_url=settings.siliconflow_base_url,
        temperature=0,
        max_tokens=1024,
        max_retries=0,
        callbacks=[],
        timeout=model_timeout_seconds,
    ).bind_tools(agent.tools)

    def call_model(state: AgentState, runtime: Runtime[AgentContext]) -> dict:
        used_calls = sum(len(m.tool_calls) for m in state["messages"] if isinstance(m, AIMessage))
        response = None
        if runtime.context.subscription_intent and used_calls == 0:
            response = AIMessage(content="", tool_calls=[{
                "name": "manage_subscription_request",
                "args": {},
                "id": uuid4().hex,
            }])
        elif runtime.context.card_request_intent and used_calls == 0:
            intent = runtime.context.card_request_intent
            response = AIMessage(content="", tool_calls=[{
                "name": intent["tool"],
                "args": intent["args"],
                "id": uuid4().hex,
            }])
        elif runtime.context.report_view_intent and used_calls == 0:
            response = AIMessage(content="", tool_calls=[{
                "name": "view_bill_report",
                "args": runtime.context.report_view_intent,
                "id": uuid4().hex,
            }])
        elif runtime.context.report_generate_intent and used_calls == 0:
            response = AIMessage(content="", tool_calls=[{
                "name": "generate_bill_report",
                "args": runtime.context.report_generate_intent,
                "id": uuid4().hex,
            }])
        elif runtime.context.insight_query_intent and used_calls == 0:
            intent = runtime.context.insight_query_intent
            response = AIMessage(content="", tool_calls=[{
                "name": intent["tool"],
                "args": intent["args"],
                "id": uuid4().hex,
            }])
        elif runtime.context.orchestration_intent and used_calls == 0:
            response = AIMessage(content="", tool_calls=[{
                "name": "request_birthday_orchestration",
                "args": runtime.context.orchestration_intent,
                "id": uuid4().hex,
            }])
        rules = (
            "本次请求最多调用工具 3 次。只处理用户明确要求的内容，已有结果足够时直接回答。"
            "可以请求多个互不依赖的只读工具，中端将逐个执行。"
            "订阅扫描和取消请求必须分别单独调用一次；不能与其他工具组成同一批次，也不能在其他工具之后调用。"
            "续费/规则/预算请求统一调用 manage_subscription_request 一次，不与扫描或取消混用。"
            "生日任务创建或查询必须单独调用一个 orchestration 工具，不与任何其他工具混用。"
            "不得重复调用相同工具和参数。写操作工具只创建受控请求，不得把创建请求描述成资金或状态已经变更。"
            "涉及精确银行事实时仅依据成功工具结果；私人结果卡中的精确数据不可见，不得猜测。"
        )
        if response is None:
            with tracing_context(enabled=False):
                response = model.invoke([
                    SystemMessage(content=agent.system_prompt + "\n\n" + rules + "\n\n" + query_context_prompt(runtime.context)),
                    *state["messages"],
                ])
        if response.invalid_tool_calls:
            raise DomainError("AGENT_TOOL_INVALID", "模型工具参数格式无效，请重试", 502)
        calls = response.tool_calls
        merchant = runtime.context.explicit_cancel_merchant
        if merchant and used_calls == 0 and not response.invalid_tool_calls:
            if not calls:
                response = AIMessage(content="", tool_calls=[{
                    "name": "request_subscription_cancel",
                    "args": {"merchant": merchant},
                    "id": uuid4().hex,
                }])
                calls = response.tool_calls
            elif len(calls) == 1 and calls[0]["name"] == "request_subscription_cancel":
                args = calls[0]["args"]
                proposed = args.get("merchant") if set(args) == {"merchant"} else None
                if isinstance(proposed, str) and proposed.strip() and proposed.casefold() in merchant.casefold():
                    response = AIMessage(content="", tool_calls=[{
                        "name": "request_subscription_cancel",
                        "args": {"merchant": merchant},
                        "id": calls[0]["id"],
                    }])
                    calls = response.tool_calls
        if used_calls + len(calls) > MAX_TOOL_CALLS:
            raise DomainError("AGENT_TOOL_LIMIT", "已达到查询调用上限，请缩小查询范围", 422)
        allowed = {tool.name for tool in agent.tools}
        if any(call["name"] not in allowed for call in calls):
            raise DomainError("AGENT_TOOL_NOT_ALLOWED", "Agent 请求了未启用的工具", 502)
        if calls and contains_agent_write(calls) and runtime.context.security_service:
            runtime.context.security_service.require_unlocked(runtime.context.user)
        if any(call["name"] == "manage_subscription_request" for call in calls) and not runtime.context.subscription_intent:
            raise DomainError(
                "SUBSCRIPTION_INTENT_UNSUPPORTED",
                "请明确说明要查询续费，或设置提前1、3、7天的扣费提醒。",
                422,
            )
        subscription_write_tools = {
            "scan_subscriptions",
            "request_subscription_cancel",
        }
        orchestration_tools = {
            "list_my_birthday_tasks",
            "request_birthday_orchestration",
        }

        if any(
            call["name"] in subscription_write_tools
            for call in calls
        ):
            if len(calls) != 1 or used_calls != 0:
                raise DomainError(
                    "AGENT_SUBSCRIPTION_SEPARATE_REQUEST",
                    "请单独发起订阅操作，每次请求只能调用一个订阅工具",
                    422,
                )
        if any(call["name"] in orchestration_tools for call in calls):
            if len(calls) != 1 or used_calls != 0:
                raise DomainError(
                    "AGENT_ORCHESTRATION_SEPARATE_REQUEST",
                    "生日任务请单独发起，每次请求只能调用一个生日任务工具",
                    422,
                )
        if any(call["name"] == "view_bill_report" for call in calls):
            if len(calls) != 1 or used_calls != 0:
                raise DomainError(
                    "AGENT_REPORT_VIEW_SEPARATE_REQUEST",
                    "账单报告查看请单独发起一次",
                    422,
                )
        return {"messages": [response]}

    builder = StateGraph(
        AgentState,
        context_schema=AgentContext,
    )

    builder.add_node("model", call_model)
    builder.add_node(
        "tools",
        ToolNode(agent.tools, handle_tool_errors=False),
    )

    def after_tools(state: AgentState, runtime: Runtime[AgentContext]):
        # A saved report has a deterministic acknowledgement and navigation
        # event; do not hold its DB transaction open for another model call.
        context = runtime.context

        if (
            context.report_events
            or context.subscription_events
            or context.subscription_cancel_events
            or context.subscription_workflow_events
            or context.subscription_query_events
            or any(
                getattr(event, "type", None)
                in {
                    "WEALTH_RISK_ASSESSMENT_REQUIRED",
                    "WEALTH_ACTION_CREATED",
                    "ORCHESTRATION_TASK_CREATED",
                    "ORCHESTRATION_TASKS_READY",
                    "CARD_ACTION_CREATED",
                }
                for event in context.events
            )
        ):
            return END

        return "model"

    builder.add_edge(START, "model")
    builder.add_conditional_edges("model", tools_condition)
    builder.add_conditional_edges("tools", after_tools, {END: END, "model": "model"})

    return builder.compile().with_config({"callbacks": []})
