"""
Tests that the ReAct graph compiles and can answer a question using the retriever tool.
No documents need to be ingested — the agent handles an empty knowledge base gracefully.
Usage: uv run scripts/test_graph.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from openai import AsyncOpenAI
from supabase import create_client
from langchain_core.messages import HumanMessage

from app.agent.graph import build_graph
from app.core.settings import settings

TEST_EMAIL = "test-graph@example.com"
TEST_PASSWORD = "test-graph-pw-5555"
TEST_QUESTION = "How do I reset my password?"


async def main() -> None:
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)
    if not settings.openai_api_key:
        print("ERROR: OPENAI_API_KEY not set in .env")
        sys.exit(1)

    service = create_client(settings.supabase_url, settings.supabase_service_role_key)
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    user_resp = service.auth.admin.create_user(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    )
    user_id: str = user_resp.user.id
    print(f"Temp user: {user_id}")

    conv = (
        service.table("conversations")
        .insert({"user_id": user_id, "title": "Test graph conversation"})
        .execute()
    )
    conversation_id: str = conv.data[0]["id"]
    print(f"Conversation: {conversation_id}")

    try:
        print("\nCompiling graph...")
        graph = build_graph(
            supabase=service,
            openai_client=openai_client,
            anthropic_api_key=settings.anthropic_api_key,
            llm_model=settings.llm_model,
        )
        print("Graph compiled OK")

        print(f"\nInvoking agent: {TEST_QUESTION!r}")
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=TEST_QUESTION)],
                "conversation_id": conversation_id,
                "user_id": user_id,
            }
        )

        final_msg = result["messages"][-1]
        print(f"\nAgent response:\n{final_msg.content}")

        tool_names = [
            tc["name"]
            for msg in result["messages"]
            if getattr(msg, "tool_calls", None)
            for tc in msg.tool_calls
        ]
        print(f"\nTools called: {tool_names}")
        assert tool_names, "Agent made no tool calls — expected at least retriever"
        assert "retriever" in tool_names, f"Expected retriever in tool calls, got {tool_names}"

        print("\nReAct graph OK")

    finally:
        service.table("conversations").delete().eq("id", conversation_id).execute()
        service.auth.admin.delete_user(user_id)
        print("Cleanup done")


if __name__ == "__main__":
    asyncio.run(main())
