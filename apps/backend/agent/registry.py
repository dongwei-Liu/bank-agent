from dataclasses import dataclass

from langchain_core.tools import BaseTool

from agent.prompts import compose_system_prompt
from agent.prompts.accounts import ACCOUNTS_PROMPT
from agent.prompts.subscriptions import SUBSCRIPTIONS_PROMPT
from agent.tools.subscriptions import (
    request_subscription_cancel,
    scan_subscriptions,
    manage_subscription_request,
)
from agent.tools.accounts import get_my_balance, get_my_transactions
from agent.prompts.insights import INSIGHTS_PROMPT
from agent.tools.insights import (
    generate_bill_report,
    get_spending_anomalies,
    get_spending_statistics,
    view_bill_report,
)
from agent.prompts.payments import PAYMENTS_PROMPT
from agent.tools.payments import list_my_recipients, search_my_recipients, request_transfer, request_internal_transfer
from agent.prompts.cards import CARDS_PROMPT
from agent.tools.cards import (
    list_my_cards, get_my_card, request_card, activate_my_card,
    change_card_limits, change_card_channels, lock_my_card, unlock_my_card,
    report_my_card_lost, replace_my_card, request_card_number_view,
)
from agent.prompts.payment_plans import PAYMENT_PLANS_PROMPT
from agent.tools.payment_plans import (
    request_scheduled_transfer, list_my_scheduled_transfers,
    manage_my_scheduled_transfer, create_aa_collection,
    list_my_aa_requests, process_my_aa_request,
)
from agent.prompts.wealth import WEALTH_PROMPT
from agent.tools.wealth import (
    list_fixed_deposit_products,
    list_my_fixed_deposits,
    recommend_fixed_deposits,
    request_fixed_deposit_redemption,
    request_fixed_deposit_subscription,
)
from agent.prompts.orchestration import ORCHESTRATION_PROMPT
from agent.tools.orchestration import (
    list_my_birthday_tasks,
    request_birthday_orchestration,
)


@dataclass(frozen=True)
class AgentDomain:
    prompt: str
    tools: tuple[BaseTool, ...]


@dataclass(frozen=True)
class ResolvedAgent:
    system_prompt: str
    tools: tuple[BaseTool, ...]


DOMAIN_REGISTRY: dict[str, AgentDomain] = {
    "subscriptions": AgentDomain(
        prompt=SUBSCRIPTIONS_PROMPT,
        tools=(scan_subscriptions, request_subscription_cancel,
               manage_subscription_request),
    ),
    "accounts": AgentDomain(
        prompt=ACCOUNTS_PROMPT,
        tools=(get_my_balance, get_my_transactions),
    ),
    "insights": AgentDomain(
        prompt=INSIGHTS_PROMPT,
        tools=(
            get_spending_statistics,
            get_spending_anomalies,
            generate_bill_report,
            view_bill_report,
        ),
    ),
    "payments": AgentDomain(
        prompt=PAYMENTS_PROMPT,
        tools=(list_my_recipients, search_my_recipients, request_transfer, request_internal_transfer),
    ),
    "cards": AgentDomain(
        prompt=CARDS_PROMPT,
        tools=(list_my_cards, get_my_card, request_card, activate_my_card,
               change_card_limits, change_card_channels, lock_my_card, unlock_my_card,
               report_my_card_lost, replace_my_card, request_card_number_view),
    ),
    "payment_plans": AgentDomain(
        prompt=PAYMENT_PLANS_PROMPT,
        tools=(request_scheduled_transfer, list_my_scheduled_transfers,
               manage_my_scheduled_transfer, create_aa_collection,
               list_my_aa_requests, process_my_aa_request),
    ),
    "wealth": AgentDomain(
        prompt=WEALTH_PROMPT,
        tools=(
            list_fixed_deposit_products,
            recommend_fixed_deposits,
            list_my_fixed_deposits,
            request_fixed_deposit_subscription,
            request_fixed_deposit_redemption,
        ),
    ),
    "orchestration": AgentDomain(
        prompt=ORCHESTRATION_PROMPT,
        tools=(list_my_birthday_tasks, request_birthday_orchestration),
    ),
}


def resolve_agent(domains: tuple[str, ...]) -> ResolvedAgent:
    """解析本次请求由可信中端策略启用的业务域。"""
    if not domains:
        raise ValueError("至少启用一个 Agent 业务域")
    if len(set(domains)) != len(domains):
        raise ValueError("Agent 业务域不能重复")

    unknown = set(domains) - DOMAIN_REGISTRY.keys()
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"未知 Agent 业务域: {names}")

    selected = tuple(DOMAIN_REGISTRY[name] for name in domains)
    tools = tuple(tool for domain in selected for tool in domain.tools)
    tool_names = [tool.name for tool in tools]
    if len(set(tool_names)) != len(tool_names):
        raise ValueError("Agent Tool 名称不能重复")

    return ResolvedAgent(
        system_prompt=compose_system_prompt(
            *(domain.prompt for domain in selected)
        ),
        tools=tools,
    )
