"""
Three-scenario test of the ReAct agent:
  1. Single retriever call   — question answerable from ingested docs.
  2. Multi-step retrieval    — compound question requiring two sub-lookups.
  3. Escalation trigger      — question not in the knowledge base.

A small TXT fixture is ingested before the tests and cleaned up afterward.
Usage: uv run scripts/test_agent.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from langchain_core.messages import HumanMessage
from openai import AsyncOpenAI
from supabase import create_client

from app.agent.graph import build_graph
from app.core.settings import settings
from app.ingestion.pipeline import ingest

TEST_EMAIL = "test-agent@example.com"
TEST_PASSWORD = "test-agent-pw-6666"

_FIXTURE_DOC = """\
# Quro Help Center

## Password Management

### How to Reset Your Password
To reset your password:
1. Go to the login page and click "Forgot password".
2. Enter your registered email address.
3. Check your inbox for a reset link (valid for 24 hours).
4. Click the link and choose a new password.

### Password Requirements
Your password must meet all of the following requirements:
- At least 8 characters long
- At least one uppercase letter (A–Z)
- At least one digit (0–9)
- At least one special character (!, @, #, $, %, ^, &, *)
- Must not match any of your last 5 passwords

## Account Settings

### How to Update Your Email Address
To change the email address on your account:
1. Navigate to Settings → Account.
2. Click "Change Email".
3. Enter your new email address and confirm your current password.
4. A verification link is sent to the new address.
5. Click the link within 48 hours to confirm the change.

### How to Enable Two-Factor Authentication
To add an extra layer of security with 2FA:
1. Go to Settings → Security.
2. Click "Enable Two-Factor Authentication".
3. Scan the QR code with Google Authenticator or Authy.
4. Enter the 6-digit code displayed in the app to confirm.
5. Store the backup codes in a safe place — they let you recover access if you lose your phone.
"""


def _tool_calls_in(result: dict) -> list[str]:
    return [
        tc["name"]
        for msg in result["messages"]
        if getattr(msg, "tool_calls", None)
        for tc in msg.tool_calls
    ]


async def run_scenario(
    label: str,
    question: str,
    graph,
    conversation_id: str,
    user_id: str,
) -> dict:
    print(f"\n{'─' * 60}")
    print(f"Scenario: {label}")
    print(f"Question: {question!r}")
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=question)],
            "conversation_id": conversation_id,
            "user_id": user_id,
        }
    )
    tools_called = _tool_calls_in(result)
    answer = result["messages"][-1].content
    print(f"Tools called: {tools_called}")
    print(f"Answer:\n{answer}")
    return result


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
        .insert({"user_id": user_id, "title": "Agent test"})
        .execute()
    )
    conversation_id: str = conv.data[0]["id"]
    print(f"Conversation: {conversation_id}")

    document_id: str | None = None

    try:
        # ── Ingest fixture doc ────────────────────────────────────────────────
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write(_FIXTURE_DOC)
            fixture_path = Path(f.name)

        print(f"\nIngesting fixture: {fixture_path.name}")
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
        )

        # ── Scenario 1 — single retriever call ───────────────────────────────
        r1 = await run_scenario(
            label="1 — Single retriever call",
            question="How do I reset my password?",
            graph=graph,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        tools1 = _tool_calls_in(r1)
        assert "retriever" in tools1, f"Expected retriever in {tools1}"
        assert "escalation" not in tools1, "Scenario 1 should NOT escalate"
        print("[✓] Scenario 1 passed")

        # ── Scenario 2 — multi-step retrieval ────────────────────────────────
        r2 = await run_scenario(
            label="2 — Multi-step retrieval",
            question=(
                "What are the password requirements? "
                "Also, what are the steps to enable two-factor authentication?"
            ),
            graph=graph,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        tools2 = _tool_calls_in(r2)
        retriever_calls = tools2.count("retriever")
        assert retriever_calls >= 1, f"Expected at least 1 retriever call, got {retriever_calls}"
        assert "escalation" not in tools2, "Scenario 2 should NOT escalate"
        print(f"[✓] Scenario 2 passed (retriever called {retriever_calls}x)")

        # ── Scenario 3 — escalation trigger ──────────────────────────────────
        r3 = await run_scenario(
            label="3 — Escalation trigger",
            question="What is included in the Enterprise pricing tier?",
            graph=graph,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        tools3 = _tool_calls_in(r3)
        assert "escalation" in tools3, f"Expected escalation in {tools3}"

        gaps = (
            service.table("knowledge_gaps")
            .select("id")
            .eq("conversation_id", conversation_id)
            .execute()
        )
        assert len(gaps.data) >= 1, "Expected at least 1 knowledge_gaps row"

        tickets = (
            service.table("escalated_tickets")
            .select("id")
            .eq("conversation_id", conversation_id)
            .execute()
        )
        assert len(tickets.data) >= 1, "Expected at least 1 escalated_tickets row"
        print(f"[✓] Scenario 3 passed — knowledge_gaps: {gaps.data[0]['id']}")

        print(f"\n{'=' * 60}")
        print("All three scenarios passed — ReAct agent OK")

    finally:
        # Clean up in dependency order
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
