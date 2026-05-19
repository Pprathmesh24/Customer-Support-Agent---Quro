from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from openai import AsyncOpenAI
from supabase import Client

from ..tools.document_scope import DocumentScopeTool
from ..tools.escalation import EscalationTool
from ..tools.retriever import RetrieverTool
from ..tools.ticket_status import TicketStatusTool
from .nodes import make_agent_node, make_force_escalate_node, make_input_guard_node
from .state import AgentState


def _route_after_guard(state: AgentState) -> str:
    """
    Route based on the input classification set by the guard node.
      blocked          → END (canned response already in messages)
      human_requested  → force_escalate (direct tool call, no ReAct loop)
      safe / default   → agent (normal ReAct loop)
    """
    cls = state.get("input_class", "safe")
    if cls == "blocked":
        return END
    if cls == "human_requested":
        return "force_escalate"
    return "agent"


def _should_continue(state: AgentState) -> str:
    """After the agent node, continue the ReAct loop if tool calls were made."""
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return END


def build_graph(
    supabase: Client,
    openai_client: AsyncOpenAI,
    anthropic_api_key: str,
    llm_model: str = "claude-haiku-4-5-20251001",
    linear_api_key: str = "",
    linear_team_id: str = "",
    slack_webhook_url: str = "",
    resend_api_key: str = "",
    resend_from_email: str = "",
    support_team_email: str = "",
    crisp_website_id: str = "",
    crisp_identifier: str = "",
    crisp_key: str = "",
    checkpointer: BaseCheckpointSaver | None = None,
):
    """
    Compiles and returns the ReAct support agent graph.

    Graph topology:
      START → input_guard → (blocked)          → END
                          → (human_requested)  → force_escalate → END
                          → (safe)             → agent
                                                   → (tool_calls) → tools → agent (loop)
                                                   → END

    checkpointer: when provided (e.g. MemorySaver), the graph maintains its own
    state between calls via a thread_id in the run config. When None (the
    production default), the caller passes full message history on each request.
    """
    llm = ChatAnthropic(model=llm_model, api_key=anthropic_api_key)

    escalation_tool = EscalationTool(
        supabase=supabase,
        linear_api_key=linear_api_key,
        linear_team_id=linear_team_id,
        slack_webhook_url=slack_webhook_url,
        resend_api_key=resend_api_key,
        resend_from_email=resend_from_email,
        support_team_email=support_team_email,
        crisp_website_id=crisp_website_id,
        crisp_identifier=crisp_identifier,
        crisp_key=crisp_key,
    )

    tools = [
        DocumentScopeTool(supabase=supabase),
        RetrieverTool(supabase=supabase, llm=llm, openai_client=openai_client),
        escalation_tool,
        TicketStatusTool(supabase=supabase),
    ]

    llm_with_tools = llm.bind_tools(tools)

    builder = StateGraph(AgentState)
    builder.add_node("input_guard", make_input_guard_node(llm))
    builder.add_node("force_escalate", make_force_escalate_node(escalation_tool))
    builder.add_node("agent", make_agent_node(llm_with_tools))
    builder.add_node("tools", ToolNode(tools))

    builder.set_entry_point("input_guard")
    builder.add_conditional_edges(
        "input_guard",
        _route_after_guard,
        {"agent": "agent", "force_escalate": "force_escalate", END: END},
    )
    builder.add_edge("force_escalate", END)
    builder.add_conditional_edges(
        "agent",
        _should_continue,
        {"tools": "tools", END: END},
    )
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=checkpointer)
