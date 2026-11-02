from agent.prompts.base import BASE_PROMPT


def compose_system_prompt(*domain_prompts: str) -> str:
    """按本次启用的业务域组合系统 Prompt。"""
    parts = [BASE_PROMPT]
    parts.extend(
        prompt.strip()
        for prompt in domain_prompts
        if prompt.strip()
    )
    return "\n\n".join(parts)
