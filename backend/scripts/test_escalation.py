"""
End-to-end test of EscalationTool (Linear + Slack + Resend).
Creates a temp user and conversation, calls the tool, verifies DB rows, then cleans up.
Integrations that are not configured are skipped with a warning — test still passes.
Usage: uv run scripts/test_escalation.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from supabase import create_client

from app.agent.tools.escalation import EscalationTool
from app.core.settings import settings

TEST_EMAIL = "test-escalation@example.com"
TEST_PASSWORD = "test-escalation-pw-3333"
TEST_QUESTION = "How do I reset my 2FA device if I've lost access to my authenticator app?"


async def main() -> None:
    service = create_client(settings.supabase_url, settings.supabase_service_role_key)

    user_resp = service.auth.admin.create_user(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    )
    user_id: str = user_resp.user.id
    print(f"Temp user: {user_id}")

    ticket_ids: list[str] = []
    gap_ids: list[str] = []
    conversation_id: str | None = None

    try:
        conv = (
            service.table("conversations")
            .insert({"user_id": user_id, "title": "Test escalation conversation"})
            .execute()
        )
        conversation_id = conv.data[0]["id"]
        print(f"Conversation: {conversation_id}")

        tool = EscalationTool(
            supabase=service,
            linear_api_key=settings.linear_api_key,
            linear_team_id=settings.linear_team_id,
            slack_webhook_url=settings.slack_webhook_url,
            resend_api_key=settings.resend_api_key,
            resend_from_email=settings.resend_from_email,
            support_team_email=settings.support_team_email,
            crisp_website_id=settings.crisp_website_id,
            crisp_identifier=settings.crisp_identifier,
            crisp_key=settings.crisp_key,
        )

        print(f"\nQuestion: {TEST_QUESTION!r}")
        result = await tool._arun(
            question=TEST_QUESTION,
            conversation_id=conversation_id,
        )
        print(f"\nTool result:\n{result}")

        # Verify knowledge_gaps row
        gaps = (
            service.table("knowledge_gaps")
            .select("*")
            .eq("conversation_id", conversation_id)
            .execute()
        )
        assert len(gaps.data) == 1, f"Expected 1 knowledge_gaps row, got {len(gaps.data)}"
        gap = gaps.data[0]
        assert gap["question"] == TEST_QUESTION, "question mismatch"
        gap_ids.append(gap["id"])
        print(f"\n[✓] knowledge_gaps row: {gap['id']}")

        # Verify escalated_tickets row
        tickets = (
            service.table("escalated_tickets")
            .select("*")
            .eq("conversation_id", conversation_id)
            .execute()
        )
        assert len(tickets.data) == 1, f"Expected 1 escalated_tickets row, got {len(tickets.data)}"
        ticket = tickets.data[0]
        ticket_ids.append(ticket["id"])
        print(f"[✓] escalated_tickets row: {ticket['id']}")

        linear_status = (
            f"[✓] Linear: {ticket['linear_ticket_id']} ({ticket['linear_ticket_url']})"
            if ticket["linear_ticket_id"]
            else "[ ] Linear: skipped (set LINEAR_API_KEY + LINEAR_TEAM_ID)"
        )
        slack_status = (
            "[✓] Slack: sent" if settings.slack_webhook_url else "[ ] Slack: skipped (set SLACK_WEBHOOK_URL)"
        )
        resend_status = (
            "[✓] Resend: sent"
            if settings.resend_api_key and settings.support_team_email
            else "[ ] Resend: skipped (set RESEND_API_KEY + SUPPORT_TEAM_EMAIL)"
        )
        crisp_status = (
            "[✓] Crisp: conversation opened"
            if settings.crisp_website_id and settings.crisp_identifier and settings.crisp_key
            else "[ ] Crisp: skipped (set CRISP_WEBSITE_ID + CRISP_IDENTIFIER + CRISP_KEY)"
        )
        print(linear_status)
        print(slack_status)
        print(resend_status)
        print(crisp_status)

        print("\nEscalationTool OK")

    finally:
        for tid in ticket_ids:
            service.table("escalated_tickets").delete().eq("id", tid).execute()
        for gid in gap_ids:
            service.table("knowledge_gaps").delete().eq("id", gid).execute()
        if conversation_id:
            service.table("conversations").delete().eq("id", conversation_id).execute()
        service.auth.admin.delete_user(user_id)
        print("Cleanup done")


if __name__ == "__main__":
    asyncio.run(main())
