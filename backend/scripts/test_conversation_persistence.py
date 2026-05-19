"""
Tests conversation persistence (Step 6.2):
  1. POST /chat with two different questions
  2. GET /conversations/{id} returns both turns in order with correct roles
  3. Second POST /chat uses history from DB (multi-turn context)
Usage: uv run scripts/test_conversation_persistence.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import httpx
from supabase import create_client

from app.core.settings import settings
from app.ingestion.pipeline import ingest
from app.main import app

TEST_EMAIL = "test-conv-persist@example.com"
TEST_PASSWORD = "test-conv-persist-pw-1010"

_FIXTURE_DOC = """\
# Quro Help Center

## Password Reset
To reset your password:
1. Go to the login page and click "Forgot password".
2. Enter your email and check your inbox for a reset link (valid 24 hours).
3. Click the link and choose a new password.

## Password Requirements
Passwords must be at least 8 characters and include one uppercase letter,
one digit, and one special character.
"""


async def main() -> None:
    service = create_client(settings.supabase_url, settings.supabase_service_role_key)
    anon = create_client(settings.supabase_url, settings.supabase_anon_key)

    user_resp = service.auth.admin.create_user(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    )
    user_id: str = user_resp.user.id
    print(f"Temp user: {user_id}")

    session = anon.auth.sign_in_with_password(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    token: str = session.session.access_token
    headers = {"Authorization": f"Bearer {token}"}

    conv = (
        service.table("conversations")
        .insert({"user_id": user_id, "title": "Persistence test"})
        .execute()
    )
    conversation_id: str = conv.data[0]["id"]
    print(f"Conversation: {conversation_id}")

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write(_FIXTURE_DOC)
        fixture_path = Path(f.name)

    document_id: str | None = None

    try:
        document_id = await ingest(
            file_path=fixture_path,
            user_id=user_id,
            supabase=service,
            category="help-center",
        )
        fixture_path.unlink()
        print(f"Document ingested: {document_id}")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

            # ── Turn 1: ask about password reset ─────────────────────────────
            print("\n── Turn 1 ────────────────────────────────────────────────")
            r1 = await client.post(
                "/chat",
                json={"message": "How do I reset my password?", "conversation_id": conversation_id},
                headers=headers,
                timeout=120.0,
            )
            assert r1.status_code == 200, f"{r1.status_code}: {r1.text}"
            print(f"Answer: {r1.json()['answer'][:150]}...")
            print(f"Sources: {r1.json()['sources']}")

            # ── Turn 2: follow-up referencing first answer ─────────────────────
            print("\n── Turn 2 (follow-up) ────────────────────────────────────")
            r2 = await client.post(
                "/chat",
                json={"message": "What are the password requirements you mentioned?", "conversation_id": conversation_id},
                headers=headers,
                timeout=120.0,
            )
            assert r2.status_code == 200, f"{r2.status_code}: {r2.text}"
            answer2 = r2.json()["answer"]
            print(f"Answer: {answer2[:200]}...")

            # Verify multi-turn context: the answer should mention password
            # requirements from the knowledge base (or from prior context)
            assert any(
                kw in answer2.lower()
                for kw in ("8 character", "uppercase", "digit", "special", "character")
            ), f"Turn 2 answer does not reference password requirements:\n{answer2}"

            # ── GET /conversations/{id}: verify both turns persisted ───────────
            print("\n── GET /conversations/{id} ───────────────────────────────")
            r3 = await client.get(
                f"/conversations/{conversation_id}",
                headers=headers,
            )
            assert r3.status_code == 200, f"{r3.status_code}: {r3.text}"
            history = r3.json()
            msgs = history["messages"]

            print(f"Messages returned: {len(msgs)}")
            for m in msgs:
                preview = m["content"][:80].replace("\n", " ")
                print(f"  [{m['role']}] {preview}...")

            # Expect 4 rows: user1, assistant1, user2, assistant2
            assert len(msgs) == 4, f"Expected 4 messages, got {len(msgs)}"
            assert msgs[0]["role"] == "user"
            assert msgs[1]["role"] == "assistant"
            assert msgs[2]["role"] == "user"
            assert msgs[3]["role"] == "assistant"
            assert "reset" in msgs[0]["content"].lower()
            assert msgs[1]["sources"], "Assistant message should have source citations"
            print("[✓] All 4 turns persisted in correct order with sources")

            # ── 404 for another user's conversation ───────────────────────────
            r4 = await client.get(
                "/conversations/00000000-0000-0000-0000-000000000000",
                headers=headers,
            )
            assert r4.status_code == 404
            print("[✓] 404 for unknown conversation")

        print(f"\n{'=' * 60}")
        print("Conversation persistence OK")

    finally:
        service.table("messages").delete().eq("conversation_id", conversation_id).execute()
        service.table("semantic_cache").delete().eq("user_id", user_id).execute()
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
