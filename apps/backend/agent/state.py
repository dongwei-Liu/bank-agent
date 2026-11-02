from operator import add
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from schemas.agent import AgentEvent


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    events: Annotated[list[AgentEvent], add]
