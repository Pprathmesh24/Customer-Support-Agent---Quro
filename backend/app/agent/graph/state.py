from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class _BaseState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_id: str
    user_id: str


class AgentState(_BaseState, total=False):
    # Set by input_guard_node; absent until guard runs.
    # Values: "safe" | "human_requested" | "blocked"
    input_class: str
