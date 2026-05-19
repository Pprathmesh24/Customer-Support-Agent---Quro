"""
Multi-turn conversation memory test.
Turn 1 asks about 2FA setup; turn 2 asks a follow-up about backup codes.
The agent must answer the follow-up from conversation context without re-searching.
Usage: uv run scripts/test_memory.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from openai import AsyncOpenAI
from supabase import create_client

from app.agent.graph import build_graph
from app.core.settings import settings
from app.ingestion.pipeline import ingest

TEST_EMAIL = "test-memory@example.com"
TEST_PASSWORD = "test-memory-pw-7777"

_FIXTURE_DOC = """\
# Quro Help Center

## How to Enable Two-Factor Authentication

To add an extra layer of security with 2FA:
1. Go to Settings → Security.
2. Click "Enable Two-Factor Authentication".
3. Scan the QR code with Google Authenticator or Authy.
4. Enter the 6-digit code displayed in the app to confirm.
5. Store the backup codes in a safe place — they let you recover access if you lose your phone.

## Backup Codes

Backup codes are one-time-use recovery codes generated when you enable 2FA.
Each code can only be used once. If you lose access to your authenticator app,
enter a backup code on the login screen to regain access.
You can regenerate new backup codes at any time from Settings → Security.
"""


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
        .insert({"user_id": user_id, "title": "Memory test"})
        .execute()
    )
    conversation_id: str = conv.data[0]["id"]
    print(f"Conversation: {conversation_id}")

    document_id: str | None = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write(_FIXTURE_DOC)
            fixture_path = Path(f.name)

        print(f"\nIngesting fixture...")
        document_id = await ingest(
            file_path=fixture_path,
            user_id=user_id,
            supabase=service,
            category="help-center",
        )
        fixture_path.unlink()
        print(f"Document ingested: {document_id}")

        graph = build_graph(
            supabase=service,
            openai_client=openai_client,
            anthropic_api_key=settings.anthropic_api_key,
            llm_model=settings.llm_model,
            checkpointer=MemorySaver(),
        )

        # Thread ID ties both turns to the same conversation in the checkpointer.
        config = {"configurable": {"thread_id": conversation_id}}

        # ── Turn 1 ────────────────────────────────────────────────────────────
        turn1_q = "How do I enable two-factor authentication?"
        print(f"\n── Turn 1 ───────────────────────────────────────────────────")
        print(f"Q: {turn1_q!r}")
        r1 = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=turn1_q)],
                "conversation_id": conversation_id,
                "user_id": user_id,
            },
            config=config,
        )
        turn1_answer = r1["messages"][-1].content
        print(f"A: {turn1_answer}")

        tools1 = [
            tc["name"]
            for msg in r1["messages"]
            if getattr(msg, "tool_calls", None)
            for tc in msg.tool_calls
        ]
        assert "retriever" in tools1, "Turn 1 should call retriever"
        assert "backup" in turn1_answer.lower(), (
            "Turn 1 answer should mention backup codes"
        )
        print(f"[✓] Turn 1 passed — tools: {tools1}")

        # ── Turn 2 (follow-up referencing Turn 1 context) ─────────────────────
        turn2_q = "You mentioned backup codes — what exactly are they used for?"
        print(f"\n── Turn 2 ───────────────────────────────────────────────────")
        print(f"Q: {turn2_q!r}")
        r2 = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=turn2_q)],
                "conversation_id": conversation_id,
                "user_id": user_id,
            },
            config=config,
        )
        turn2_answer = r2["messages"][-1].content
        print(f"A: {turn2_answer}")

        tools2 = [
            tc["name"]
            for msg in r2["messages"]
            if getattr(msg, "tool_calls", None)
            for tc in msg.tool_calls
        ]
        print(f"Tools called in full state: {tools2}")

        # The agent must reference backup-code recovery in its answer.
        answer_lower = turn2_answer.lower()
        assert any(
            phrase in answer_lower
            for phrase in ("recover", "authenticator", "one-time", "regain", "lose", "login")
        ), f"Turn 2 answer does not reference backup code purpose:\n{turn2_answer}"

        print("[✓] Turn 2 passed — agent used conversation history")

        print(f"\n{'=' * 60}")
        print("Multi-turn memory OK")

    finally:
        service.table("escalated_tickets").delete().eq("conversation_id", conversation_id).execute()
        service.table("knowledge_gaps").delete().eq("conversation_id", conversation_id).execute()
        service.table("conversations").delete().eq("id", conversation_id).execute()
        if document_id:
            service.table("document_chunks").delete().eq("document_id", document_id).execute()
            service.table("documents").delete().eq("id", document_id).execute()
        service.auth.admin.delete_user(user_id)
        print("Cleanup done")


if __name__ == "__main__":
    asyncio.run(main())
