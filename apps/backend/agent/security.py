"""Deterministic Agent security policy shared by graph and evaluation code."""

from __future__ import annotations


# These tools can persist a business request, change local business state, or
# enqueue work. The model cannot remove this classification by changing its
# wording or arguments.
AGENT_WRITE_TOOLS = frozenset(
    {
        "generate_bill_report",
        "view_bill_report",
        "scan_subscriptions",
        "request_subscription_cancel",
        "manage_subscription_request",
        "request_transfer",
        "request_internal_transfer",
        "request_card",
        "activate_my_card",
        "change_card_limits",
        "change_card_channels",
        "lock_my_card",
        "unlock_my_card",
        "report_my_card_lost",
        "replace_my_card",
        "request_card_number_view",
        "request_scheduled_transfer",
        "manage_my_scheduled_transfer",
        "create_aa_collection",
        "process_my_aa_request",
        "request_fixed_deposit_subscription",
        "request_fixed_deposit_redemption",
        "request_birthday_orchestration",
    }
)


def contains_agent_write(tool_calls: list[dict]) -> bool:
    return any(str(call.get("name")) in AGENT_WRITE_TOOLS for call in tool_calls)
